from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
import os

geolocator = Nominatim(user_agent="realestate_scraper_v1")

_geo_cache = {}

def get_coordinates(location_str: str) -> str:
    if not location_str or len(location_str) < 3:
        return ""

    if os.getenv("ENABLE_GEOCODING", "").lower() not in {"1", "true", "yes"}:
        return ""
    
    if location_str in _geo_cache:
        return _geo_cache[location_str]
        
    print(f"      [Geocoding] {location_str}...")
    try:
        location = geolocator.geocode(location_str, timeout=2)
        if location:
            coords = f"{location.latitude}, {location.longitude}"
            _geo_cache[location_str] = coords
            print(f"      [Geocoding] Success: {coords}")
            return coords
        else:
            print(f"      [Geocoding] No results found for: {location_str}")
            _geo_cache[location_str] = ""
    except (GeocoderTimedOut, Exception) as e:
        print(f"      [Geocoding] Error: {e}")
        pass
    return ""
