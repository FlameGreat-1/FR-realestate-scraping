import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

CONTACT_KEYWORDS = ["contact", "nous contacter", "contactez", "contact-us", "contact-us", "contacter"]
LISTINGS_KEYWORDS = ["immobilier", "vente", "location", "listings", "properties", "annonces"]
SOCIAL_DOMAINS = ["facebook.com", "twitter.com", "linkedin.com", "instagram.com", "youtube.com"]

def find_contact_page(soup: BeautifulSoup) -> Optional[str]:
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(separator=' ', strip=True).lower()
        if any(k in text for k in CONTACT_KEYWORDS):
            return href
    return None

def find_listings_page(soup: BeautifulSoup) -> Optional[str]:
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(separator=' ', strip=True).lower()
        if any(k in text for k in LISTINGS_KEYWORDS):
            return href
    return None

def extract_meta(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    description = None
    if meta_desc := soup.find('meta', attrs={'name': 'description'}):
        description = meta_desc.get('content', None)
    elif meta_desc := soup.find('meta', attrs={'property': 'og:description'}):
        description = meta_desc.get('content', None)
    return {"meta_title": title, "meta_description": description}

def find_social_links(soup: BeautifulSoup) -> List[str]:
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(domain in href for domain in SOCIAL_DOMAINS):
            links.append(href)
    return links

def normalize_url(base_url: str, link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    if link.startswith('http'):
        return link
    # handle relative URLs
    from urllib.parse import urljoin
    return urljoin(base_url, link)

def discover_patterns(base_url: str, html: str) -> Dict:
    soup = BeautifulSoup(html, 'html.parser')
    contact = normalize_url(base_url, find_contact_page(soup))
    listings = normalize_url(base_url, find_listings_page(soup))
    meta = extract_meta(soup)
    socials = find_social_links(soup)
    result = {
        "contact_url": contact,
        "listings_url": listings,
        "meta_title": meta.get('meta_title'),
        "meta_description": meta.get('meta_description'),
        "social_links": socials,
    }
    return result
