import pandas as pd
from urllib.parse import urlparse
from typing import Dict, List, Any
from pathlib import Path

def parse_domain(url: str) -> str:
    if not url or pd.isna(url) or url == 'nan':
        return ""
    url = str(url).strip().lower()
    if not url.startswith('http'):
        url = 'http://' + url
    domain = urlparse(url).netloc
    return domain.replace('www.', '')

def deduplicate_domains(csv_path: str) -> Dict[str, Dict[str, Any]]:
    df = pd.read_csv(csv_path)
    domains_map = {}
    
    no_website_entries = []
    
    for _, row in df.iterrows():
        website = row.get('website', '')
        agency_name = row.get('company_name', 'Unknown Agency')
        domain = parse_domain(website)
        
        if not domain:
            no_website_entries.append(agency_name)
            continue
            
        if domain not in domains_map:
            domains_map[domain] = {
                'domain': domain,
                'url': website if str(website).startswith('http') else 'https://' + str(website),
                'agency_name': row.get('company_name', ''),
                'phone': row.get('phone_1', ''),
                'city': row.get('city', ''),
                'postalcode': row.get('postalcode', ''),
                'rows_merged': 1
            }
        else:
            domains_map[domain]['rows_merged'] += 1
            # Pick best agency_name if missing
            if not domains_map[domain]['agency_name'] and row.get('company_name'):
                domains_map[domain]['agency_name'] = row.get('company_name')
                
    return domains_map, no_website_entries
