import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
from .base import Listing
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
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            content = script.string
            if not content:
                continue
            parsed = json.loads(content)
            if isinstance(parsed, list):
                parsed = parsed[0]
            if parsed.get('@type') in ('Product', 'RealEstateListing', 'SingleFamilyResidence', 'House', 'Apartment', 'Accommodation'):
                if 'offers' in parsed and isinstance(parsed['offers'], dict):
                    data['price'] = str(parsed['offers'].get('price', ''))
                if 'name' in parsed:
                    data['title'] = parsed['name']
                if 'description' in parsed:
                    data['description'] = parsed['description']
                if 'address' in parsed:
                    addr = parsed['address']
                    if isinstance(addr, dict):
                        data['location'] = f"{addr.get('addressLocality', '')} {addr.get('postalCode', '')}".strip()
                    elif isinstance(addr, str):
                        data['location'] = addr
                if 'geo' in parsed and isinstance(parsed['geo'], dict):
                    data['coordinates'] = f"{parsed['geo'].get('latitude', '')}, {parsed['geo'].get('longitude', '')}".strip(', ')
        except Exception:
            continue
    return data


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
    """Strip non-digit characters from a price string, keeping only numbers."""
    if not price_str:
        return ""
    return re.sub(r'[^\d]', '', price_str)


async def extract_listing_data(url: str, html: str, domain_info: dict) -> Listing:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    title = soup.title.string.lower() if soup.title and soup.title.string else ""
    h1 = soup.h1.get_text(separator=' ', strip=True).lower() if soup.h1 else ""

    # 1. Try JSON-LD first (high reliability)
    ld_data = _extract_from_json_ld(soup)

    # 2. Price — handles "Prix : 621 000 €", "170,000 €(Fixe)", "621 000 €", etc.
    price = ld_data.get('price', '')
    if not price:
        price_match = re.search(
            r'(?:prix\s*(?:de\s*vente)?|price)\s*[:.-]?\s*([\d\s\xa0,.]+)\s*€'
            r'|([\d\s\xa0,.]+)\s*€',
            text, re.I
        )
        if price_match:
            raw = price_match.group(1) or price_match.group(2)
            price = _clean_price(raw)
    else:
        price = _clean_price(price)

    # 3. Reference ID - Stricter to avoid UI text spillover
    ref_match = re.search(r'(?:r[ée]f(?:[ée]rence)?|ref|annonce)\s*[:.-]?\s*([a-zA-Z0-9_\-]+)', text, re.I)
    reference_id = ref_match.group(1).strip() if ref_match else url.strip('/').split('/')[-1]
    
    # Avoid junk like "Partager" in ref_id if it picked up nearby UI text
    if any(x in reference_id.lower() for x in ['partager', 'facebook', 'twitter']):
        reference_id = url.strip('/').split('/')[-1]

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
    dpe_match = re.search(r'(?:classe|dpe|conso)\s*[eé]nergie\s*[:.-]?\s*([A-G])|DPE\s*[:.-]?\s*([A-G])', text, re.I)
    dpe_rating = (dpe_match.group(1) or dpe_match.group(2)).upper() if dpe_match else ""

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

    clean_phone = str(domain_info.get('phone', '')).strip()
    if '.0' in clean_phone: clean_phone = clean_phone.split('.0')[0]

    return Listing(
        reference_id=reference_id,
        domain=domain_info['domain'],
        url=url,
        price=price.strip(),
        property_type=property_type,
        location=location,
        surface_area=surface_area,
        rooms=rooms,
        bedrooms=bedrooms,
        agency_name=domain_info.get('agency_name', ''),
        phone=clean_phone,
        email=email,
        coordinates=coordinates,
        dpe_rating=dpe_rating
    )


async def extract_listings_from_domain(domain_info: Dict[str, Any], client: httpx.AsyncClient) -> List[Listing]:
    base_url = domain_info['url']
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
            if include_pattern.search(path) and not exclude_pattern.search(path):
                listing_urls.append(u)

        listing_urls = list(set(listing_urls))[:100]
        print(f"[{domain_info['domain']}] Found {len(listing_urls)} potential listing URLs")

    if not listing_urls:
        print(f"[{domain_info['domain']}] No listing URLs found.")
        return []

    # Junk reference IDs that indicate search/list pages, not actual listings
    junk_refs = {'trouv', 'aucun', 'recherche', 'liste', 'search', 'result', 'page', 'user', 'immobili', 'estimation', 'prix-m2'}

    all_listings = []
    for idx, listing_url in enumerate(listing_urls):
        if idx % 10 == 0:
            print(f"[{domain_info['domain']}] Extracting {idx}/{len(listing_urls)}...")
        page_html = await fetch_html(listing_url, client)
        if not page_html:
            continue

        listing = await extract_listing_data(listing_url, page_html, domain_info)

        # Apply agency email fallback
        if not listing.email:
            listing.email = agency_email

        # Reject junk/search/list pages by reference ID
        if any(jr in listing.reference_id.lower() for jr in junk_refs):
            continue

        # Keep only if at least one core field was found
        if listing.price or listing.property_type or (listing.surface_area and listing.rooms):
            all_listings.append(listing)

        await asyncio.sleep(0.1)

    print(f"[{domain_info['domain']}] Completed. Collected {len(all_listings)} listings.")
    return all_listings
