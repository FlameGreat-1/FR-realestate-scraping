import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
from .base import Listing
from ..domain_seeds import get_additional_seed_urls
from ..utils.geocoder import get_coordinates
import re
import json
import asyncio


async def fetch_html(url: str, client: httpx.AsyncClient, timeout: float = 15.0) -> str:
    try:
        response = await client.get(url, follow_redirects=True, timeout=timeout)
        return response.text if response.status_code == 200 else ""
    except Exception:
        return ""


def _extract_from_json_ld(soup: BeautifulSoup) -> dict:
    data = {}

    def walk(node):
        if isinstance(node, dict):
            node_type = node.get("@type")
            if node_type in ('Product', 'RealEstateListing', 'SingleFamilyResidence', 'House', 'Apartment', 'Accommodation'):
                offers = node.get('offers')
                if isinstance(offers, dict):
                    for key in ('price', 'lowPrice', 'highPrice', 'priceValue'):
                        if offers.get(key) not in (None, ""):
                            data['price'] = str(offers.get(key))
                            break
                elif isinstance(offers, list):
                    for offer in offers:
                        if isinstance(offer, dict):
                            for key in ('price', 'lowPrice', 'highPrice', 'priceValue'):
                                if offer.get(key) not in (None, ""):
                                    data['price'] = str(offer.get(key))
                                    break
                            if data.get('price'):
                                break
                for key in ('price', 'lowPrice', 'highPrice', 'priceValue'):
                    if data.get('price'):
                        break
                    if node.get(key) not in (None, ""):
                        data['price'] = str(node.get(key))
                        break
            for key, value in node.items():
                if key in ('name', 'description') and isinstance(value, str):
                    data[key] = value
                elif key in ('url', '@id') and isinstance(value, str):
                    data['url'] = value
                elif key == 'address':
                    addr = value
                    if isinstance(addr, dict):
                        data['location'] = f"{addr.get('addressLocality', '')} {addr.get('postalCode', '')}".strip()
                    elif isinstance(addr, str):
                        data['location'] = addr
                elif key == 'mainEntityOfPage':
                    if isinstance(value, str):
                        data['url'] = value
                    elif isinstance(value, dict):
                        for nested_key in ('@id', 'url'):
                            nested_value = value.get(nested_key)
                            if isinstance(nested_value, str) and nested_value.strip():
                                data['url'] = nested_value.strip()
                                break
                elif key == 'geo' and isinstance(value, dict):
                    data['coordinates'] = f"{value.get('latitude', '')}, {value.get('longitude', '')}".strip(', ')
                elif isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            content = script.string
            if not content:
                continue
            parsed = json.loads(content)
            walk(parsed)
        except Exception:
            continue
    return data


def _resolve_detail_url(soup: BeautifulSoup, ld_data: dict, fallback_url: str) -> str:
    """Choose the most specific same-site detail URL we can infer from the page."""
    candidates: list[str] = []
    fallback = (fallback_url or "").split("#")[0].strip()
    fallback_netloc = urlparse(fallback).netloc.lower().replace("www.", "")

    def add_candidate(raw_url: str | None):
        if not raw_url:
            return
        raw_url = str(raw_url).strip()
        if not raw_url or raw_url.startswith(("mailto:", "tel:", "javascript:", "#")):
            return
        abs_url = urljoin(fallback_url, raw_url).split("#")[0]
        parsed = urlparse(abs_url)
        if parsed.scheme not in {"http", "https"}:
            return
        netloc = parsed.netloc.lower().replace("www.", "")
        if netloc != fallback_netloc:
            return
        candidates.append(abs_url)

    canonical_link = soup.find("link", rel=re.compile(r"canonical", re.I))
    if canonical_link:
        add_candidate(canonical_link.get("href") or canonical_link.get("content"))

    og_url = soup.find("meta", property=re.compile(r"^og:url$", re.I))
    if og_url:
        add_candidate(og_url.get("content"))

    twitter_url = soup.find("meta", attrs={"name": re.compile(r"^twitter:url$", re.I)})
    if twitter_url:
        add_candidate(twitter_url.get("content"))

    if isinstance(ld_data.get("url"), str):
        add_candidate(ld_data["url"])

    if isinstance(ld_data.get("url"), dict):
        add_candidate(ld_data["url"].get("@id") or ld_data["url"].get("url"))

    if not candidates:
        return fallback_url

    fallback_parsed = urlparse(fallback_url)
    fallback_path = fallback_parsed.path.rstrip("/")
    fallback_segments = [part for part in fallback_path.split("/") if part]

    def score(candidate: str) -> tuple[int, int, int]:
        parsed = urlparse(candidate)
        path = parsed.path.rstrip("/")
        segments = [part for part in path.split("/") if part]
        score_val = 0
        if _is_candidate_listing_url(candidate):
            score_val += 100
        if len(segments) > len(fallback_segments):
            score_val += 20
        if len(path) > len(fallback_path):
            score_val += 10
        if re.search(r"(vente|achat|buy|annonce|bien|listing|details?|property|immobilier)", path, re.I):
            score_val += 5
        if parsed.query:
            score_val += 1
        return (score_val, len(segments), len(candidate))

    best = max(dict.fromkeys(candidates), key=score)

    if best == fallback_url:
        return fallback_url
    if _is_candidate_listing_url(best):
        return best
    if not _is_candidate_listing_url(fallback_url):
        return best
    return fallback_url


def _extract_phone_from_json_ld(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string
            if not content:
                continue
            parsed = json.loads(content)
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else {}
            stack = [parsed] if isinstance(parsed, dict) else []
            while stack:
                item = stack.pop()
                if not isinstance(item, dict):
                    continue
                for key in ("telephone", "phone", "phoneNumber", "contactPoint"):
                    value = item.get(key)
                    if isinstance(value, str):
                        cleaned = _normalize_phone(value)
                        if cleaned:
                            return cleaned
                    elif isinstance(value, dict):
                        for nested_key in ("telephone", "phone", "phoneNumber"):
                            nested_value = value.get(nested_key)
                            if isinstance(nested_value, str):
                                cleaned = _normalize_phone(nested_value)
                                if cleaned:
                                    return cleaned
                    elif isinstance(value, list):
                        stack.extend(v for v in value if isinstance(v, dict))
                for nested_key in ("publisher", "author", "broker", "agent", "seller", "offers"):
                    nested = item.get(nested_key)
                    if isinstance(nested, dict):
                        stack.append(nested)
                    elif isinstance(nested, list):
                        stack.extend(v for v in nested if isinstance(v, dict))
        except Exception:
            continue
    return ""


def _harvest_email(soup: BeautifulSoup, html: str) -> str:
    # 1. Try mailto links
    mailto = soup.find('a', href=re.compile(r'^mailto:', re.I))
    if mailto:
        email = mailto['href'].replace('mailto:', '').split('?')[0].strip()
        if '@' in email and not any(ext in email.lower() for ext in ['.jpg', '.png', '.jpeg', '.gif', '.webp', '.svg']):
            return email

    # 2. RegEx hunt in text - strictly avoid image filenames
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    for email in emails:
        clean_email = email.lower()
        if not any(ext in clean_email for ext in ['.jpg', 'x320', 'x640', '.png', '.jpeg', '.gif', '.webp']):
            return email

    return ""


def _rip_coordinates(soup: BeautifulSoup, html: str) -> str:
    # 1. Look for inline script variables
    lat_match = re.search(r'(?:lat|latitude)\s*[:=]\s*([+-]?\d+\.\d+)', html, re.I)
    lng_match = re.search(r'(?:lng|longitude)\s*[:=]\s*([+-]?\d+\.\d+)', html, re.I)
    if lat_match and lng_match:
        return f"{lat_match.group(1)}, {lng_match.group(1)}"

    # 2. Look in iframes (Google Maps)
    iframe = soup.find('iframe', src=re.compile(r'maps\.google\.com|google\.com/maps'))
    if iframe:
        src = iframe.get('src', '')
        ll_match = re.search(r'[?&]ll=([\d.-]+),([\d.-]+)', src)
        if ll_match:
            return f"{ll_match.group(1)}, {ll_match.group(2)}"
        q_match = re.search(r'[?&]q=([\d.-]+),([\d.-]+)', src)
        if q_match:
            return f"{q_match.group(1)}, {q_match.group(2)}"

    return ""


def _clean_price(price_str: str) -> str:
    """Extract the first monetary amount from a price string."""
    if not price_str:
        return ""
    match = re.search(r"\d[\d\s\xa0.,]*", str(price_str))
    if not match:
        return ""
    digits = re.sub(r'[^\d]', '', match.group(0))
    if not digits:
        return ""
    # Guard against repeated captures like 620000620000.
    if len(digits) % 2 == 0:
        half = len(digits) // 2
        if digits[:half] == digits[half:]:
            digits = digits[:half]
    return digits


def _normalize_phone(phone_str: str) -> str:
    if not phone_str:
        return ""
    raw = phone_str.strip()
    digits = re.sub(r"[^\d]", "", raw)
    if raw.startswith("+33") or raw.startswith("0033") or digits.startswith("33"):
        local = digits[2:] if digits.startswith("33") else digits[4:] if digits.startswith("0033") else digits[2:]
        if len(local) == 9:
            return "0" + local
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) < 8:
        return ""
    return digits


def _extract_phone_from_dom(soup: BeautifulSoup, html: str) -> str:
    tel_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("tel:"):
            tel_links.append(href.split(":", 1)[1])

    # Prefer explicit tel: links.
    for candidate in tel_links:
        cleaned = _normalize_phone(candidate)
        if cleaned:
            return cleaned

    # Fall back to local text around phone labels.
    phone_label_patterns = [
        r"(?:t[eé]l(?:[ée]phone)?|phone)\s*[:\-]?\s*([+\d][\d\s().-]{7,})",
        r"([+\d][\d\s().-]{7,})\s*(?:t[eé]l(?:[ée]phone)?|phone)",
    ]
    for pattern in phone_label_patterns:
        match = re.search(pattern, html, re.I)
        if match:
            cleaned = _normalize_phone(match.group(1))
            if cleaned:
                return cleaned

    return ""


def _extract_price_from_dom(soup: BeautifulSoup, text: str, url: str = "") -> str:
    if url and re.search(r"(prix-m2|prix-rues|listing-categorie|achat-immobilier|vente-immobilier|/search(?:/|$)|/recherche(?:/|$)|/result(?:/|$)|/results(?:/|$)|/biens/result|/produits/all)", url, re.I):
        return ""

    candidates = []

    selectors = [
        "[itemprop='price']",
        "[data-price]",
        "[data-price-value]",
        "[data-price-amount]",
        "[class*='price' i]",
        "[id*='price' i]",
        "[class*='prix' i]",
        "[id*='prix' i]",
        "[class*='amount' i]",
        "[id*='amount' i]",
    ]
    for selector in selectors:
        for node in soup.select(selector):
            candidate_text = node.get("content") or node.get("data-price") or node.get("data-price-value") or node.get("data-price-amount") or node.get_text(" ", strip=True)
            if candidate_text:
                candidates.append(candidate_text)

    # Prioritize explicit price labels.
    label_patterns = [
        r"(?:prix(?:\s+de\s+vente)?|price)\s*[:\-]?\s*([^\n\r<]{2,50})",
        r"([0-9][0-9\s\xa0.,]*)\s*€",
    ]
    for pattern in label_patterns:
        for match in re.finditer(pattern, text, re.I):
            candidates.append(match.group(1))

    for candidate in candidates:
        if re.search(r"sur\s+demande", candidate, re.I):
            continue
        if re.search(r"(prix\s*-?\s*m2|prix-rues|par\s+m2|€/m2|€/m²|m\s*[²2])", candidate, re.I):
            continue
        if "€" not in candidate and not re.search(r"(prix|price)", candidate, re.I):
            continue
        cleaned = _clean_price(candidate)
        if cleaned and cleaned != "0":
            return cleaned

    return ""


def _extract_dpe_rating(soup: BeautifulSoup, html: str) -> str:
    # Prefer structured data if present.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string
            if not content:
                continue
            parsed = json.loads(content)
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else {}
            if isinstance(parsed, dict):
                for key in (
                    "energyEfficiencyCategory",
                    "energyClass",
                    "energyRating",
                    "dpeRating",
                    "epcRating",
                    "epcCategory",
                ):
                    value = parsed.get(key)
                    if isinstance(value, str):
                        m = re.search(r"\b([A-G])\b", value, re.I)
                        if m:
                            return m.group(1).upper()
        except Exception:
            continue

    text = " ".join(soup.stripped_strings)
    text = re.sub(r"\s+", " ", text)
    normalized = text.replace("é", "e").replace("É", "E")

    # Only accept explicitly labeled ratings.
    labeled_patterns = [
        r"\bdpe\b\s*[:\-]?\s*(?:classe\s*)?([A-G])\b",
        r"\bdiagnostic(?: de performance)?(?: energetique| énergétique)?\b\s*[:\-]?\s*(?:classe\s*)?([A-G])\b",
        r"\bclasse(?:ment)?(?: energie| énergétique)?\b\s*[:\-]?\s*([A-G])\b",
        r"\bconsommation(?: energetique| énergétique)?\b\s*[:\-]?\s*([A-G])\b",
    ]
    for pattern in labeled_patterns:
        m = re.search(pattern, normalized, re.I)
        if m:
            return m.group(1).upper()

    label_terms = re.compile(
        r"(dpe|diagnostic de performance energetique|diagnostic de performance énergétique|classe énergie|classe energie|consommation énergétique|consommation energetique)",
        re.I,
    )
    for node in soup.find_all(string=label_terms):
        parent = getattr(node, "parent", None)
        if not parent:
            continue
        parent_text = re.sub(r"\s+", " ", parent.get_text(" ", strip=True))
        for pattern in labeled_patterns:
            m = re.search(pattern, parent_text.replace("é", "e").replace("É", "E"), re.I)
            if m:
                return m.group(1).upper()

    return "No DPE rating"


def _is_candidate_listing_url(href: str) -> bool:
    if not href:
        return False

    parsed = urlparse(href)
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    full = f"{path}?{query}" if query else path

    if any(token in full for token in (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", "mailto:", "tel:", "facebook", "instagram", "linkedin")):
        return False

    exclude_terms = (
        "contact", "agence", "about", "apropos", "a-propos", "team", "equipe",
        "blog", "news", "actualites", "actualite", "article", "tag", "author",
        "mentions-legales", "privacy", "politique", "estimation", "vendre-nous",
    )
    if any(term in full for term in exclude_terms):
        return False

    hub_paths = {
        "/lots",
        "/lot",
        "/search",
        "/recherche",
        "/result",
        "/results",
        "/buy",
        "/listing-categorie",
        "/produits/all",
        "/biens/result",
        "/resultat.php",
    }
    normalized_path = path.rstrip("/")
    if normalized_path in hub_paths:
        return False
    if normalized_path.endswith("/search") and normalized_path.count("/") <= 2:
        return False
    if normalized_path.endswith("/buy") and normalized_path.count("/") <= 2:
        return False

    hubish_patterns = (
        r"achat-immobilier",
        r"vente-immobilier",
        r"listing-categorie",
        r"prix-m2",
        r"prix-rues",
        r"/search(?:/|$)",
        r"/recherche(?:/|$)",
        r"/result(?:/|$)",
        r"/results(?:/|$)",
        r"/biens/result",
        r"/produits/all",
        r"/annonce(?:s)?(?:/|$)",
    )
    if any(re.search(pattern, full, re.I) for pattern in hubish_patterns):
        return False

    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return False
    if len(segments) <= 3 and re.fullmatch(r"[a-z-]+-\d{4,5}", segments[-1]) and not re.search(r"(ref-|reference|id-|\d{6,})", path, re.I):
        return False
    if len(segments) <= 3 and not re.search(r"(ref-|reference|id-|\d{6,}|-[a-z0-9]{10,})", path, re.I):
        return False

    include_terms = (
        "listing", "lots", "lot", "biens", "bien",
        "vente", "buy", "produit", "produits", "property", "properties",
        "maison", "appartement", "villa", "terrain", "studio", "garage", "parking",
    )
    if any(term in full for term in include_terms):
        return True

    return bool(re.search(r"(\d{4,}|page=|rooms=|budget=|zipcode=|loc=vente|type=all)", full, re.I))


async def _crawl_listing_pages(base_url: str, client: httpx.AsyncClient, seed_urls: List[str], max_pages: int = 60) -> List[Listing]:
    queue = list(dict.fromkeys(seed_urls))
    seen = set()
    collected: List[Listing] = []
    fallback_domain_info = {"domain": urlparse(base_url).netloc.replace("www.", ""), "url": base_url}
    max_pages = max(10, max_pages)

    while queue and len(seen) < max_pages:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)

        page_html = await fetch_html(current, client, timeout=12.0)
        if not page_html:
            continue

        listing = await extract_listing_data(current, page_html, fallback_domain_info)
        if listing.price and any([listing.reference_id, listing.property_type, listing.location, listing.surface_area, listing.rooms, listing.bedrooms]):
            collected.append(listing)

        for a_href in re.findall(r'href=["\']([^"\']+)["\']', page_html, re.I):
            child = urljoin(current, a_href)
            if child.startswith(("http://", "https://")) and child not in seen and child not in queue:
                if _is_crawl_seed_url(child, base_url) or _is_candidate_listing_url(child):
                    queue.append(child)

    return collected


def _extract_reference_id(url: str, text: str, soup: BeautifulSoup) -> str:
    # JSON-LD / structured fields first.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string
            if not content:
                continue
            parsed = json.loads(content)
            if isinstance(parsed, list):
                parsed = parsed[0]
            if isinstance(parsed, dict):
                for key in ("sku", "productID", "identifier", "ref", "reference", "reference_id"):
                    value = parsed.get(key)
                    if isinstance(value, str) and len(value.strip()) >= 3:
                        return value.strip()
        except Exception:
            continue

    # Label-based extraction from visible text.
    patterns = [
        r"(?:r[ée]f(?:[ée]rence)?|réf\.?|ref\.?|n°\s*id)\s*[:#\.-]?\s*([A-Za-z0-9][A-Za-z0-9_\-\/]{2,})",
        r"(?:id)\s*[:#\.-]?\s*([A-Za-z0-9][A-Za-z0-9_\-\/]{2,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            candidate = match.group(1).strip().strip(".,;:")
            if len(candidate) >= 3 and candidate.lower() not in {"ref", "reference", "id"}:
                return candidate

    # Fallback to the last path segment, with comma-separated ref support.
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    if "," in slug:
        parts = [p for p in slug.split(",") if p]
        if parts:
            slug = parts[-1]
    slug = slug.strip().strip(".,;:")
    if len(slug) >= 3:
        return slug
    return ""


def _is_crawl_seed_url(href: str, base_url: str) -> bool:
    if not href:
        return False
    if not href.startswith(("http://", "https://")):
        return False

    href_netloc = urlparse(href).netloc.lower().replace("www.", "")
    base_netloc = urlparse(base_url).netloc.lower().replace("www.", "")
    if href_netloc != base_netloc:
        return False

    parsed = urlparse(href)
    path = (parsed.path or "").lower()
    full = f"{path}?{(parsed.query or '').lower()}" if parsed.query else path

    if any(token in full for token in (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", "mailto:", "tel:", "facebook", "instagram", "linkedin", "youtube")):
        return False

    if any(term in full for term in ("contact", "agence", "blog", "news", "article", "mentions-legales", "privacy", "politique")):
        return False

    return True


async def extract_listing_data(url: str, html: str, domain_info: dict) -> Listing:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    title = soup.title.string.lower() if soup.title and soup.title.string else ""
    h1 = soup.h1.get_text(separator=' ', strip=True).lower() if soup.h1 else ""

    # 1. Try JSON-LD first (high reliability)
    ld_data = _extract_from_json_ld(soup)
    resolved_url = _resolve_detail_url(soup, ld_data, url)

    # 2. Price — handles "Prix : 621 000 €", "170,000 €(Fixe)", "621 000 €", etc.
    price = _clean_price(str(ld_data.get('price', '')))
    if not price:
        price = _extract_price_from_dom(soup, text, url)
    if not price and re.search(r"sur\s+demande", text, re.I):
        price = ""
    if price in {"0", "00", "000"}:
        price = ""

    # 3. Reference ID - Stricter to avoid UI text spillover
    reference_id = _extract_reference_id(url, text, soup)
    if not reference_id or len(reference_id) < 3 or any(x in reference_id.lower() for x in ['partager', 'facebook', 'twitter', 'search', 'result', 'page']):
        reference_id = _extract_reference_id(url, "", soup) or url.rstrip('/').split('/')[-1]
        if "," in reference_id:
            reference_id = reference_id.split(",")[-1]

    # 4. Property Type — scan title + h1
    prop_types = ['maison', 'appartement', 'villa', 'terrain', 'garage', 'studio',
                  'chalet', 'moulin', 'duplex', 'loft', 'château', 'parking', 'immeuble']
    full_text = f"{title} {h1} {ld_data.get('title', '').lower()}"
    property_type = next((pt for pt in prop_types if pt in full_text), "")

    # 5. Surface Area — handles "90,76 m²", "90.76 m2", "90 m²"
    surface_match = re.search(r'([\d,. ]+)\s*m\s*[²2²]', text, re.I)
    surface_area = surface_match.group(1).strip().replace(',', '.') if surface_match else ""

    # 6. Rooms — bidirectional: "3 pièces" OR "Pièces : 3"
    rooms_match = re.search(
        r'(?:pi[èe]ces?|rooms?)\s*[:\-]?\s*(\d+)'
        r'|(\d+)\s*(?:pi[èe]ces?|rooms?)',
        text, re.I
    )
    rooms = (rooms_match.group(1) or rooms_match.group(2)) if rooms_match else ""

    # 7. Bedrooms — bidirectional: "2 chambres" OR "Chambres : 2" OR "Chambre 2"
    bedrooms = ""
    bedrooms_match = re.search(
        r'(?:chambres?|bedrooms?)\s*[:\-]?\s*(\d+)'
        r'|(\d+)\s*(?:chambres?|bedrooms?)',
        text, re.I
    )
    if bedrooms_match:
        bedrooms = bedrooms_match.group(1) or bedrooms_match.group(2)

    # 8. T-notation fallback: "T3" or "t3" in title/h1/url → 3 rooms, 2 bedrooms
    if not rooms or not bedrooms:
        t_match = re.search(r'\bT(\d+)\b', f"{full_text} {url}", re.I)
        if t_match:
            r_val = int(t_match.group(1))
            if not rooms:
                rooms = str(r_val)
            if not bedrooms:
                bedrooms = str(max(0, r_val - 1))

    # 9. DPE Rating - More robust regex
    dpe_rating = _extract_dpe_rating(soup, html)

    # --- PHASE 3 TARGETS ---

    # Location Detection
    location = ld_data.get('location', '')

    if not location:
        # Extract from French real estate URL pattern: ...-bordeaux-33000
        url_match = re.search(r'([a-z-]+)-(\d{5})(?:[,/]|$)', url, re.I)
        if url_match:
            city_slug = url_match.group(1).split('-')[-1]
            location = f"{city_slug.capitalize()} {url_match.group(2)}"

    if not location:
        # Try breadcrumbs
        bc = soup.find(['nav', 'div', 'ul'], class_=re.compile(r'breadcrumb|chemin', re.I))
        if bc:
            items = [li.get_text(strip=True) for li in bc.find_all(['li', 'a', 'span'])]
            for item in reversed(items):
                if re.search(r'\d{5}', item) or (len(item) > 3 and item.isalpha()):
                    location = item
                    break

    if not location:
        # Try meta tags
        meta_loc = soup.find('meta', property=re.compile(r'place:location:locality|og:locality', re.I))
        if meta_loc:
            location = meta_loc.get('content', '')

    if not location:
        # Fallback to agency city/postalcode from CSV
        location = f"{domain_info.get('city', '')} {domain_info.get('postalcode', '')}".strip()

    # Coordinate Detection
    coordinates = ld_data.get('coordinates', '')
    if not coordinates:
        coordinates = _rip_coordinates(soup, html)
    if not coordinates and location:
        coordinates = get_coordinates(location)

    # Email Detection
    email = _harvest_email(soup, html)

    clean_phone = _extract_phone_from_dom(soup, html)
    if not clean_phone:
        clean_phone = _extract_phone_from_json_ld(soup)
    if not clean_phone:
        clean_phone = _normalize_phone(str(domain_info.get('phone', '')).strip())

    return Listing(
        reference_id=reference_id,
        domain=domain_info['domain'],
        url=resolved_url,
        price=price.strip() if isinstance(price, str) else str(price),
        property_type=property_type,
        location=location,
        surface_area=surface_area,
        rooms=rooms,
        bedrooms=bedrooms,
        agency_name=domain_info.get('agency_name', ''),
        phone=clean_phone,
        email=email,
        coordinates=coordinates,
        dpe_rating=dpe_rating or "No DPE rating"
    )


async def extract_listings_from_domain(domain_info: Dict[str, Any], client: httpx.AsyncClient) -> List[Listing]:
    base_url = domain_info['url']
    extra_seed_urls = get_additional_seed_urls(base_url)
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    # Harvest domain-level email from homepage (short timeout so dead sites don't block)
    agency_email = ""
    try:
        home_html = await fetch_html(base_url, client, timeout=8.0)
        if home_html:
            agency_email = _harvest_email(BeautifulSoup(home_html, 'html.parser'), home_html)
            if agency_email:
                print(f"[{domain_info['domain']}] Found agency email: {agency_email}")
    except Exception as e:
        pass  # Silent fail — email from homepage is best-effort only

    # Try sitemap with and without www (many sites redirect)
    parsed_base = urlparse(base_url)
    hostname = parsed_base.hostname or ''
    www_base = f"{parsed_base.scheme}://www.{hostname.lstrip('www.')}" if not hostname.startswith('www.') else base_url
    nowww_base = f"{parsed_base.scheme}://{hostname.lstrip('www.')}" if hostname.startswith('www.') else base_url

    sitemap_url = urljoin(base_url, '/sitemap.xml')
    sitemap_url_alt = urljoin(www_base if base_url == nowww_base else nowww_base, '/sitemap.xml')
    print(f"[{domain_info['domain']}] Fetching sitemap: {sitemap_url}")
    html = await fetch_html(sitemap_url, client)
    if not html or ('<loc>' not in html and '<sitemap>' not in html):
        html = await fetch_html(sitemap_url_alt, client)
    listing_urls = []
    seed_urls = []

    if html and ('<loc>' in html or '<sitemap>' in html):
        print(f"[{domain_info['domain']}] Parsing sitemap...")
        try:
            soup = BeautifulSoup(html, 'xml' if '<?xml' in html else 'html.parser')
        except Exception:
            soup = BeautifulSoup(html, 'html.parser')

        urls = [loc.text for loc in soup.find_all('loc')]

        # Follow sitemap index if no direct URLs found
        sitemap_tags = soup.find_all('sitemap')
        if sitemap_tags and not urls:
            sitemap_urls = [loc.text for t in sitemap_tags for loc in t.find_all('loc')]
            target_sm = next(
                (u for u in sitemap_urls if re.search(r'(annonce|vente|location|bien|property|listing)', u, re.I)),
                sitemap_urls[0] if sitemap_urls else None
            )
            if target_sm:
                print(f"[{domain_info['domain']}] Navigating sitemap index to: {target_sm}")
                sub_html = await fetch_html(target_sm, client)
                if sub_html:
                    sub_soup = BeautifulSoup(sub_html, 'html.parser')
                    urls = [loc.text for loc in sub_soup.find_all('loc')]

        # Include listings, exclude blog/contact/agency/guides pages
        exclude_pattern = re.compile(r'(actualites|blog|news|article|categorie|tag|author|compte|contact|agence|prix-m2|estimation|guide|annuaire)', re.I)
        include_pattern = re.compile(r'(annonce|vente|location|bien|details|propriete|achat|-pieces|-chambres|/maison|/appartement)', re.I)

        listing_urls = []
        for u in urls:
            path = urlparse(u).path
            if _is_candidate_listing_url(u) or (include_pattern.search(path) and not exclude_pattern.search(path)):
                listing_urls.append(u)

        listing_urls = list(set(listing_urls))[:100]
        seed_urls = list(dict.fromkeys(seed_urls))[:100]
        print(f"[{domain_info['domain']}] Found {len(listing_urls)} potential listing URLs")

    if not listing_urls:
        home_html = await fetch_html(base_url, client, timeout=12.0)
        if home_html:
            print(f"[{domain_info['domain']}] Falling back to homepage link crawl...")
            home_soup = BeautifulSoup(home_html, 'html.parser')
            candidate_urls = []
            for a in home_soup.find_all('a', href=True):
                href = urljoin(base_url, a['href'])
                if _is_candidate_listing_url(href):
                    candidate_urls.append(href)
            listing_urls = list(dict.fromkeys(candidate_urls))[:75]
            print(f"[{domain_info['domain']}] Homepage crawl found {len(listing_urls)} potential listing URLs")

    for seed_url in extra_seed_urls:
        if seed_url not in seed_urls:
            seed_urls.append(seed_url)
        if _is_candidate_listing_url(seed_url) and seed_url not in listing_urls:
            listing_urls.append(seed_url)

    if not listing_urls and seed_urls:
        print(f"[{domain_info['domain']}] No direct listing URLs found; crawling internal seeds.")
        rescued = await _crawl_listing_pages(base_url, client, seed_urls, max_pages=60)
        print(f"[{domain_info['domain']}] Seed crawl rescued {len(rescued)} listings.")
        return rescued

    if not listing_urls:
        print(f"[{domain_info['domain']}] No listing URLs found.")
        return []

    # Junk reference IDs that indicate search/list pages, not actual listings
    junk_refs = {'trouv', 'aucun', 'recherche', 'liste', 'search', 'result', 'page', 'user', 'immobili', 'estimation', 'prix-m2'}

    all_listings = []
    listing_semaphore = asyncio.Semaphore(20)

    async def process_listing(idx: int, listing_url: str):
        async with listing_semaphore:
            if idx % 10 == 0:
                print(f"[{domain_info['domain']}] Extracting {idx}/{len(listing_urls)}...")
            page_html = await fetch_html(listing_url, client)
            if not page_html:
                return None

            listing = await extract_listing_data(listing_url, page_html, domain_info)

            # Apply agency email fallback
            if not listing.email:
                listing.email = agency_email

            # Reject junk/search/list pages by reference ID
            if any(jr in listing.reference_id.lower() for jr in junk_refs):
                return None

            # Keep only if a price was found and at least one core field was found.
            if listing.price and any([listing.reference_id, listing.property_type, listing.location, listing.surface_area, listing.rooms, listing.bedrooms]):
                return listing

            return None

    tasks = [process_listing(idx, listing_url) for idx, listing_url in enumerate(listing_urls)]
    for result in await asyncio.gather(*tasks):
        if result is not None:
            all_listings.append(result)

    print(f"[{domain_info['domain']}] Completed. Collected {len(all_listings)} listings.")
    return all_listings
