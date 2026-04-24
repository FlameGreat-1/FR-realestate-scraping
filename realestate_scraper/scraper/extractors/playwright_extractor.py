import asyncio
import httpx
import re
from typing import Any, Dict, List
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from .base import Listing
from .generic import (
    _extract_phone_from_dom,
    _extract_phone_from_json_ld,
    _is_candidate_listing_url,
    _normalize_phone,
    extract_listing_data,
)


async def extract_listings_playwright(domain_info: Dict[str, Any]) -> List[Listing]:
    base_url = domain_info["url"]
    all_listings: List[Listing] = []

    async def safe_fetch_html(page, target_url: str, timeout: int, wait_until: str = "domcontentloaded"):
        try:
            response = await page.goto(target_url, timeout=timeout, wait_until=wait_until)
            if response is None:
                return ""
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/html" not in content_type and "xml" not in content_type and "xhtml" not in content_type:
                return ""
            return await page.content()
        except Exception:
            return ""

    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, verify=False) as client:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )
            page = await context.new_page()

            try:
                agency_email = ""
                try:
                    home_html = await safe_fetch_html(page, base_url, timeout=15000)
                    from .generic import _harvest_email
                    import bs4

                    agency_email = _harvest_email(bs4.BeautifulSoup(home_html, "html.parser"), home_html)
                except Exception:
                    pass

                sitemap_url = urljoin(base_url, "/sitemap.xml")
                html = await safe_fetch_html(page, sitemap_url, timeout=20000)

                listing_urls = []
                if html and ("<loc>" in html or "<sitemap>" in html):
                    import bs4

                    soup = bs4.BeautifulSoup(html, "html.parser")
                    urls = [loc.text for loc in soup.find_all("loc")]

                    sitemap_tags = soup.find_all("sitemap")
                    if sitemap_tags and not urls:
                        sitemap_urls = [loc.text for t in sitemap_tags for loc in t.find_all("loc")]
                        target_sm = next(
                            (u for u in sitemap_urls if re.search(r"(annonce|vente|location|bien|property|listing)", u, re.I)),
                            sitemap_urls[0] if sitemap_urls else None,
                        )
                        if target_sm:
                            sub_html = await safe_fetch_html(page, target_sm, timeout=20000)
                            sub_soup = bs4.BeautifulSoup(sub_html, "html.parser")
                            urls = [loc.text for loc in sub_soup.find_all("loc")]

                    for u in set(urls):
                        if _is_candidate_listing_url(u):
                            listing_urls.append(u)
                else:
                    await safe_fetch_html(page, base_url, timeout=15000)
                    await page.wait_for_timeout(2000)

                    hrefs = await page.evaluate(
                        """() => {
                            return Array.from(document.querySelectorAll('a'))
                                .map(a => a.href)
                                .filter(href => href && href.startsWith('http'));
                        }"""
                    )

                    for href in set(hrefs):
                        if _is_candidate_listing_url(href):
                            listing_urls.append(href)

                listing_urls = list(set(listing_urls))[:20]

                for listing_url in listing_urls:
                    try:
                        page_html = await safe_fetch_html(page, listing_url, timeout=15000)
                        if not page_html:
                            continue

                        await page.wait_for_timeout(800)
                        listing = await extract_listing_data(listing_url, page_html, domain_info, client=client)

                        if not listing.phone:
                            from bs4 import BeautifulSoup

                            soup = BeautifulSoup(page_html, "html.parser")
                            listing.phone = _extract_phone_from_dom(soup, page_html) or _extract_phone_from_json_ld(soup)
                        if not listing.phone:
                            rendered_text = await page.evaluate("document.body.innerText")
                            phone_match = re.search(r"((?:0|\+33|0033)[\s.-]?[1-9](?:[\s.-]?\d{2}){4})", rendered_text)
                            if phone_match:
                                listing.phone = _normalize_phone(phone_match.group(1).strip())

                        if listing.price and any(
                            [listing.reference_id, listing.property_type, listing.location, listing.surface_area, listing.rooms, listing.bedrooms]
                        ):
                            all_listings.append(listing)
                    except Exception as e:
                        print(f"      [!] Failed fetching {listing_url} via Playwright: {e}")
            finally:
                await browser.close()

    return all_listings
