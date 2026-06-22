"""
Geocoding service.

Resolves place names to coordinates and timezones.
"""

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from typing import Tuple, Optional
import os


class GeocodingService:
    """Service for geocoding and timezone lookup."""

    def __init__(self):
        # User agent is required by Nominatim usage policy (moved to environment variable)
        user_agent = os.getenv("NOMINATIM_USER_AGENT", "hd-chart-generator")
        self.geolocator = Nominatim(user_agent=user_agent)
        self.tf = TimezoneFinder()

        # Fallback/Cache for common test locations to avoid rate limits
        self.known_locations = {
            "Berlin, Germany": (52.5200, 13.4050, "Europe/Berlin"),
            "London, UK": (51.5074, -0.1278, "Europe/London"),
            "New York, USA": (40.7128, -74.0060, "America/New_York"),
            "München, Deutschland": (48.1351, 11.5820, "Europe/Berlin"),
            "Hamburg, Deutschland": (53.5511, 9.9937, "Europe/Berlin"),
        }

    def get_location_data(
        self, place_name: str
    ) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Resolve place name to lat, long, timezone.

        Args:
            place_name: Name of the place (e.g., "Berlin, Germany")

        Returns:
            Tuple of (latitude, longitude, timezone_str)
            Returns (None, None, None) if location not found
        """
        # Check known locations first
        if place_name in self.known_locations:
            return self.known_locations[place_name]

        try:
            location = self.geolocator.geocode(place_name)
            if not location:
                return None, None, None

            lat, lng = location.latitude, location.longitude
            timezone_str = self.tf.timezone_at(lng=lng, lat=lat)

            return lat, lng, timezone_str
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None, None, None

    def get_timezone_from_coords(
        self, lat: float, lng: float
    ) -> Optional[str]:
        """Look up timezone string from coordinates."""
        return self.tf.timezone_at(lng=lng, lat=lat)
