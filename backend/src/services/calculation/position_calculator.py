"""Position calculator for planetary positions"""

from datetime import datetime
from typing import List
from src.models.celestial import CelestialBody
from src.models.chart import PlanetaryPosition


class PositionCalculator:
    """Calculate planetary positions using ephemeris data"""

    def __init__(self, ephemeris_source):
        """
        Initialize position calculator.

        Args:
            ephemeris_source: Ephemeris data source (e.g., SwissEphemeris)
        """
        self.ephemeris_source = ephemeris_source

    def calculate_positions(
        self, dt_utc: datetime
    ) -> List[PlanetaryPosition]:
        """
        Calculate planetary positions for a given datetime.

        Args:
            dt_utc: UTC datetime to calculate positions for

        Returns:
            List of PlanetaryPosition objects for all celestial bodies
        """
        positions = []

        # Get Julian Day
        jd = self.ephemeris_source.datetime_to_julian_day(dt_utc)

        # Calculate position for each celestial body
        for body in CelestialBody:
            try:
                # Get ecliptic longitude from ephemeris
                longitude = self.ephemeris_source.get_ecliptic_longitude(body, jd)

                # Convert to HD gate/line
                gate, line = self._longitude_to_gate_line(longitude)

                position = PlanetaryPosition(
                    body=body,
                    ecliptic_longitude=longitude,
                    gate=gate,
                    line=line,
                    gate_line=f"{gate}.{line}",
                    calculation_timestamp=datetime.utcnow(),
                    julian_day=jd,
                    source=self.ephemeris_source.get_source_name(),
                )
                positions.append(position)
            except Exception as e:
                print(f"Error calculating position for {body}: {e}")
                # Continue with other bodies

        return positions

    def _longitude_to_gate_line(self, longitude: float) -> tuple[int, int]:
        """
        Convert ecliptic longitude to HD gate and line.

        The 64 hexagrams are mapped to the 360° zodiac wheel.
        Each gate covers 5.625° (360/64).
        Each line covers 0.9375° (5.625/6).

        Args:
            longitude: Ecliptic longitude in degrees (0-360)

        Returns:
            Tuple of (gate, line) where gate is 1-64 and line is 1-6
        """
        # HD wheel starts at 58° in tropical zodiac
        # Adjust longitude to HD wheel starting point
        adjusted = (longitude + 58.0) % 360.0

        # Each gate is 5.625 degrees
        gate_number = int(adjusted / 5.625) + 1

        # Position within the gate
        position_in_gate = adjusted % 5.625

        # Each line is 0.9375 degrees
        line_number = int(position_in_gate / 0.9375) + 1
        if line_number > 6:
            line_number = 6

        # Map to actual HD gate sequence (wheel order)
        gate = self._map_to_hd_gate(gate_number)

        return gate, line_number

    def _map_to_hd_gate(self, position: int) -> int:
        """
        Map wheel position to actual HD gate number.

        Args:
            position: Position on wheel (1-64)

        Returns:
            HD gate number (1-64)
        """
        # HD gate wheel order starting from 58° tropical
        gate_wheel = [
            41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3,
            27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56,
            31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
            28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60
        ]

        if 1 <= position <= 64:
            return gate_wheel[position - 1]
        return 1  # Fallback
