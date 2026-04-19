from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="realestate_scraper_test")
loc_str = "Bordeaux 33000"
try:
    location = geolocator.geocode(loc_str, timeout=10)
    if location:
        print(f"Success: {location.latitude}, {location.longitude}")
    else:
        print("Failed to find location")
except Exception as e:
    print(f"Error: {e}")
