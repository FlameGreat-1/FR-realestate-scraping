from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CompanyInfo:
    company_name: str
    website: str
    contact_url: Optional[str] = None
    listings_url: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    social_links: List[str] = field(default_factory=list)
