import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Listing:
    reference_id: str
    domain: str
    url: str
    price: str = ""
    property_type: str = ""
    location: str = ""
    surface_area: str = ""
    rooms: str = ""
    bedrooms: str = ""
    agency_name: str = ""
    agent_name: str = ""
    phone: str = ""
    email: str = ""
    coordinates: str = ""
    dpe_rating: str = ""
