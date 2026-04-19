import asyncio
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
import re
from .base import Listing
from .generic import extract_listing_data

async def extract_listings_playwright(domain_info: Dict[str, Any]) -> List[Listing]:
    base_url = domain_info['url']
    all_listings = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Randomize user agent to bypass basic blocks
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = await context.new_page()
        
        try:
            # --- PHASE 3: HARVEST DOMAIN EMAIL FALLBACK ---
            agency_email = ""
            try:
                await page.goto(base_url, timeout=12000, wait_until="domcontentloaded")
                home_html = await page.content()
                from .generic import _harvest_email
                import bs4
                agency_email = _harvest_email(bs4.BeautifulSoup(home_html, 'html.parser'), home_html)
            except Exception:
                pass

            # 1. Try sitemap bypassing CF
            sitemap_url = urljoin(base_url, '/sitemap.xml')
            response = await page.goto(sitemap_url, timeout=20000, wait_until="domcontentloaded")
            html = await page.content()
            
            listing_urls = []
            if html and ('<loc>' in html or '<sitemap>' in html):
                # Try to parse it just as we did before
                import bs4
                soup = bs4.BeautifulSoup(html, 'html.parser')
                urls = [loc.text for loc in soup.find_all('loc')]
                
                # Check for sitemap index
                sitemap_tags = soup.find_all('sitemap')
                if sitemap_tags and not urls:
                    sitemap_urls = [loc.text for t in sitemap_tags for loc in t.find_all('loc')]
                    target_sm = next((u for u in sitemap_urls if re.search(r'(annonce|vente|location|bien|property|listing)', u, re.I)), sitemap_urls[0] if sitemap_urls else None)
                    if target_sm:
                        await page.goto(target_sm, timeout=20000)
                        sub_html = await page.content()
                        sub_soup = bs4.BeautifulSoup(sub_html, 'html.parser')
                        urls = [loc.text for loc in sub_soup.find_all('loc')]
                
                exclude_pattern = re.compile(r'(actualites|blog|news|article|categorie|tag|author|compte|contact|agence)', re.I)
                include_pattern = re.compile(r'(annonce|vente|location|bien|details|propriete|achat|-m2|-pieces|-chambres|/maison|/appartement)', re.I)
                
                for u in set(urls):
                    path = urlparse(u).path
                    if include_pattern.search(path) and not exclude_pattern.search(path):
                        listing_urls.append(u)
            else:
                # 2. If no sitemap or blocked, go to homepage and brute force grab links
                await page.goto(base_url, timeout=12000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)  # Wait for JS to render
                
                # Find the search/vente link
                hrefs = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('a'))
                        .map(a => a.href)
                        .filter(href => href && href.startsWith('http'));
                }''')
                
                exclude_pattern = re.compile(r'(actualites|blog|news|article|categorie|tag|author|compte|contact|agence)', re.I)
                include_pattern = re.compile(r'(annonce|vente|location|bien|details|propriete|achat|-m2|-pieces|-chambres|/maison|/appartement)', re.I)
                for href in set(hrefs):
                    path = urlparse(href).path
                    if include_pattern.search(path) and not exclude_pattern.search(path):
                        listing_urls.append(href)
            
            listing_urls = list(set(listing_urls))[:20]  # Cap to 20 for Playwright speed
            
            for listing_url in listing_urls:
                try:
                    await page.goto(listing_url, timeout=12000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(800)  # Brief wait for price elements
                    page_html = await page.content()
                    
                    listing = await extract_listing_data(listing_url, page_html, domain_info)
                    
                    # Playwright Bonus: Try to grab phone numbers from JS revealed elements
                    if not listing.phone:
                        # Common phone reveal regex matching in rendered HTML
                        rendered_text = await page.evaluate("document.body.innerText")
                        phone_match = re.search(r'((?:0|\+33|0033)[\s.-]?[1-9](?:[\s.-]?\d{2}){4})', rendered_text)
                        if phone_match:
                            listing.phone = phone_match.group(1).strip()
                    
                    if listing.price or listing.property_type or listing.surface_area:
                        all_listings.append(listing)
                except Exception as e:
                    print(f"      [!] Failed fetching {listing_url} via Playwright: {e}")
                    
        except Exception as e:
            raise e
        finally:
            await browser.close()
            
    return all_listings
