"""
Bodygraph calculation service.

Determines chart properties (Type, Authority, Centers, etc.) from planetary positions.
"""

from typing import List, Dict, Set, Tuple
from src.models.chart import (
    ChartResponse,
    TypeInfo,
    AuthorityInfo,
    ProfileInfo,
    Center,
    Channel,
    IncarnationCross,
    PlanetaryPosition,
)
from src.models.celestial import CelestialBody
from src.services.calculation.gate_line_mapper import ecliptic_to_gate_line


class BodygraphCalculator:
    """Calculates Human Design bodygraph from planetary positions."""

    # Center Definitions
    CENTERS = {
        "head": {"gates": [64, 61, 63]},
        "ajna": {"gates": [47, 24, 4, 17, 43, 11]},
        "throat": {"gates": [62, 23, 56, 16, 20, 31, 8, 33, 35, 12, 45]},
        "g": {"gates": [1, 7, 10, 15, 2, 46, 25, 13]},
        "heart": {"gates": [21, 51, 26, 40]},
        "sacral": {"gates": [34, 5, 14, 29, 59, 9, 3, 42, 27]},
        "spleen": {"gates": [48, 57, 44, 50, 32, 28, 18]},
        "solar": {"gates": [36, 22, 37, 6, 49, 55, 30]},
        "root": {"gates": [41, 19, 53, 60, 52, 54, 38, 39, 58]},
    }

    # Channel Definitions (Gate A, Gate B, Center A, Center B)
    CHANNELS_MAP = [
        (64, 47, "head", "ajna"),
        (61, 24, "head", "ajna"),
        (63, 4, "head", "ajna"),
        (17, 62, "ajna", "throat"),
        (43, 23, "ajna", "throat"),
        (11, 56, "ajna", "throat"),
        (16, 48, "throat", "spleen"),
        (20, 57, "throat", "spleen"),
        (31, 7, "throat", "g"),
        (8, 1, "throat", "g"),
        (33, 13, "throat", "g"),
        (35, 36, "throat", "solar"),
        (12, 22, "throat", "solar"),
        (45, 21, "throat", "heart"),
        (25, 51, "g", "heart"),
        (10, 20, "g", "throat"),
        (10, 34, "g", "sacral"),
        (10, 57, "g", "spleen"),
        (15, 5, "g", "sacral"),
        (2, 14, "g", "sacral"),
        (46, 29, "g", "sacral"),
        (26, 44, "heart", "spleen"),
        (40, 37, "heart", "solar"),
        (34, 57, "sacral", "spleen"),
        (34, 20, "sacral", "throat"),
        (59, 6, "sacral", "solar"),
        (9, 52, "sacral", "root"),
        (3, 60, "sacral", "root"),
        (42, 53, "sacral", "root"),
        (27, 50, "sacral", "spleen"),
        (57, 10, "spleen", "g"),
        (57, 34, "spleen", "sacral"),
        (32, 54, "spleen", "root"),
        (28, 38, "spleen", "root"),
        (18, 58, "spleen", "root"),
        (36, 35, "solar", "throat"),
        (22, 12, "solar", "throat"),
        (37, 40, "solar", "heart"),
        (6, 59, "solar", "sacral"),
        (49, 19, "solar", "root"),
        (55, 39, "solar", "root"),
        (30, 41, "solar", "root"),
        (41, 30, "root", "solar"),
        (19, 49, "root", "solar"),
        (13, 33, "g", "throat"),
        (53, 42, "root", "sacral"),
        (60, 3, "root", "sacral"),
        (52, 9, "root", "sacral"),
        (54, 32, "root", "spleen"),
        (38, 28, "root", "spleen"),
        (58, 18, "root", "spleen"),
    ]

    def calculate_chart(
        self,
        personality_positions: List[PlanetaryPosition],
        design_positions: List[PlanetaryPosition],
        first_name: str,
        calculation_source: str = "SwissEphemeris",
    ) -> ChartResponse:
        """
        Calculate complete chart data.

        Raises:
            ValueError: If required planetary positions are missing
        """
        # Validate that we have all required planetary positions
        self._validate_planetary_positions(personality_positions, design_positions)

        # 1. Extract Active Gates
        conscious_gates = {p.gate for p in personality_positions}
        unconscious_gates = {p.gate for p in design_positions}

        # Add Earth gates (Sun + 180)
        p_sun = next((p for p in personality_positions if p.body == CelestialBody.SUN), None)
        d_sun = next((p for p in design_positions if p.body == CelestialBody.SUN), None)

        if p_sun is None or d_sun is None:
            raise ValueError("Sun position required for bodygraph calculation")

        # Earth gate comes from the positions list (already computed as Sun+180° by the ephemeris source)
        p_earth_pos = next((p for p in personality_positions if p.body == CelestialBody.EARTH), None)
        d_earth_pos = next((p for p in design_positions if p.body == CelestialBody.EARTH), None)

        if p_earth_pos is None or d_earth_pos is None:
            raise ValueError("Earth position required for incarnation cross calculation")

        p_earth_gate, p_earth_line = p_earth_pos.gate, p_earth_pos.line
        d_earth_gate, d_earth_line = d_earth_pos.gate, d_earth_pos.line

        all_active_gates = conscious_gates.union(unconscious_gates)

        # 2. Determine Defined Channels
        defined_channels = []
        defined_centers_set = set()
        # Centers that have at least one defining channel involving a
        # Personality (conscious) gate - i.e. "normally" defined, vs.
        # centers whose definition comes exclusively from Design
        # (unconscious) gates ("unbewusst definiert").
        consciously_defined_centers_set = set()

        # Helper to check if channel is defined
        active_channels_map = {}  # Store defined channels for type calc

        # Deduplicate channels map for processing
        unique_channels = set()
        for g1, g2, c1, c2 in self.CHANNELS_MAP:
            # Sort gates to ensure uniqueness
            gate_pair = tuple(sorted((g1, g2)))
            if gate_pair not in unique_channels:
                unique_channels.add(gate_pair)

                if g1 in all_active_gates and g2 in all_active_gates:
                    lo, hi = sorted((g1, g2))
                    code = f"{lo}-{hi}"
                    defined_channels.append(Channel(code=code))
                    defined_centers_set.add(c1)
                    defined_centers_set.add(c2)

                    # A channel counts as "consciously" involved if either
                    # of its two gates is activated via the Personality
                    # (birth/conscious) side. If both gates are active only
                    # via the Design (unconscious) side, the channel - and
                    # the centers it connects - is purely unconscious.
                    channel_is_conscious = (
                        g1 in conscious_gates or g2 in conscious_gates
                    )
                    if channel_is_conscious:
                        consciously_defined_centers_set.add(c1)
                        consciously_defined_centers_set.add(c2)

                    # Store for type calculation
                    active_channels_map[gate_pair] = (c1, c2)

        # 3. Determine Defined Centers
        centers = []
        center_names = {
            "head": "Kopf",
            "ajna": "Ajna",
            "throat": "Kehlzentrum",
            "g": "G-Zentrum",
            "heart": "Herz/Ego",
            "sacral": "Sakral",
            "spleen": "Milz",
            "solar": "Solarplexus",
            "root": "Wurzel",
        }

        for code, name in center_names.items():
            is_defined = code in defined_centers_set
            if not is_defined:
                definition_type = "open"
            elif code in consciously_defined_centers_set:
                definition_type = "defined"
            else:
                definition_type = "unconscious"

            centers.append(
                Center(
                    name=name,
                    code=code,
                    defined=is_defined,
                    definitionType=definition_type,
                )
            )

        # 4. Determine Type & Authority
        type_info = self._determine_type(defined_centers_set, active_channels_map)  # type: ignore
        authority_info = self._determine_authority(defined_centers_set, type_info.code)

        # 5. Determine Profile
        # Profile is based on Personality Sun Line / Design Sun Line
        # (Standard HD Profile is P-Sun / D-Sun)
        profile_info = self._determine_profile(p_sun.line, d_sun.line)

        # 6. Incarnation Cross
        cross_name = self._determine_incarnation_cross(p_sun.gate, profile_info.code)
        incarnation_cross = IncarnationCross(
            code=f"{p_sun.gate}-{p_earth_gate}-{d_sun.gate}-{d_earth_gate}",
            name=cross_name,
            gates=[
                str(p_sun.gate),
                str(p_earth_gate),
                str(d_sun.gate),
                str(d_earth_gate),
            ],
        )

        # 7. Format Gates
        # Add Earth to gates list for display?
        # Usually gates list is just a list of active gates, or grouped by planet.
        # The ChartResponse expects dict with "conscious" and "unconscious" lists of strings "gate.line"

        # All 13 bodies (incl. Earth + South Node) are already in the positions lists
        c_gates_list = [f"{p.gate}.{p.line}" for p in personality_positions]
        u_gates_list = [f"{p.gate}.{p.line}" for p in design_positions]

        gates = {"conscious": c_gates_list, "unconscious": u_gates_list}

        # 8. Impulse
        short_impulse = self._generate_impulse(type_info.code, authority_info.code)

        return ChartResponse(
            firstName=first_name,
            type=type_info,
            authority=authority_info,
            profile=profile_info,
            centers=centers,
            channels=defined_channels,
            gates=gates,
            incarnationCross=incarnation_cross,
            shortImpulse=short_impulse,
            calculationSource=calculation_source,
        )

    def _validate_planetary_positions(
        self,
        personality_positions: List[PlanetaryPosition],
        design_positions: List[PlanetaryPosition],
    ) -> None:
        """
        Validate that all required planetary positions are present.

        Required bodies for Human Design calculation:
        - SUN (for Earth + 180° calculation)
        - MOON
        - MERCURY, VENUS, MARS, JUPITER, SATURN, URANUS, NEPTUNE, PLUTO
        - NORTH_NODE (for South Node + 180° calculation)

        Raises:
            ValueError: If any required celestial body is missing from either position set
        """
        required_bodies = {
            CelestialBody.SUN,
            CelestialBody.MOON,
            CelestialBody.MERCURY,
            CelestialBody.VENUS,
            CelestialBody.MARS,
            CelestialBody.JUPITER,
            CelestialBody.SATURN,
            CelestialBody.URANUS,
            CelestialBody.NEPTUNE,
            CelestialBody.PLUTO,
            CelestialBody.NORTH_NODE,
        }

        personality_bodies = {p.body for p in personality_positions}
        design_bodies = {p.body for p in design_positions}

        missing_personality = required_bodies - personality_bodies
        missing_design = required_bodies - design_bodies

        if missing_personality or missing_design:
            error_parts = []
            if missing_personality:
                bodies_str = ", ".join(b.value for b in sorted(missing_personality, key=lambda x: x.value))
                error_parts.append(f"Personality: {bodies_str}")
            if missing_design:
                bodies_str = ", ".join(b.value for b in sorted(missing_design, key=lambda x: x.value))
                error_parts.append(f"Design: {bodies_str}")
            raise ValueError(
                f"Missing required celestial bodies for bodygraph calculation: {'; '.join(error_parts)}"
            )

    def _determine_type(
        self,
        defined_centers: Set[str],
        active_channels: Dict[Tuple[int, int], Tuple[str, str]],
    ) -> TypeInfo:
        """Determine Human Design Type."""

        # Check for Motor-Throat connection
        has_motor_to_throat = self._check_motor_to_throat(
            defined_centers, active_channels
        )

        if "sacral" in defined_centers:
            # Generator or Manifesting Generator
            if has_motor_to_throat:
                return TypeInfo(
                    code="2",
                    label="Manifestierender Generator",
                    shortDescription="Als Manifestierender Generator hast du eine konstante Lebensenergie und kannst schnell initiieren.",
                )
            else:
                return TypeInfo(
                    code="1",
                    label="Generator",
                    shortDescription="Als Generator hast du eine konstante Lebensenergie und ziehst das Leben an.",
                )

        if has_motor_to_throat:
            return TypeInfo(
                code="4",
                label="Manifestor",
                shortDescription="Als Manifestor hast du die Gabe, Dinge zu initiieren und in Bewegung zu bringen.",
            )

        if len(defined_centers) > 0:
            return TypeInfo(
                code="3",
                label="Projektor",
                shortDescription="Als Projektor bist du hier, um andere zu leiten und Systeme zu verstehen.",
            )

        return TypeInfo(
            code="5",
            label="Reflektor",
            shortDescription="Als Reflektor bist du ein Spiegel für deine Umgebung und nimmst tief wahr.",
        )

    def _check_motor_to_throat(
        self,
        defined_centers: Set[str],
        active_channels: Dict[Tuple[int, int], Tuple[str, str]],
    ) -> bool:
        """Check if any motor center is connected to the Throat."""
        if "throat" not in defined_centers:
            return False

        # BFS to find path from any motor to throat
        motors = {"heart", "solar", "root", "sacral"}
        queue = ["throat"]
        visited = {"throat"}

        while queue:
            current = queue.pop(0)
            if current in motors and current in defined_centers:
                return True

            # Find neighbors via defined channels
            for centers in active_channels.values():
                c1, c2 = centers
                if c1 == current and c2 not in visited and c2 in defined_centers:
                    visited.add(c2)
                    queue.append(c2)
                elif c2 == current and c1 not in visited and c1 in defined_centers:
                    visited.add(c1)
                    queue.append(c1)

        return False

    def _determine_authority(
        self, defined_centers: Set[str], type_code: str
    ) -> AuthorityInfo:
        """Determine Inner Authority."""
        if type_code == "5":  # Reflector
            return AuthorityInfo(
                code="lunar",
                label="Lunar",
                decisionHint="Warte einen Mondzyklus (28 Tage) für wichtige Entscheidungen.",
            )

        if "solar" in defined_centers:
            return AuthorityInfo(
                code="emotional",
                label="Emotional",
                decisionHint="Warte auf emotionale Klarheit über die Zeit.",
            )

        if "sacral" in defined_centers:
            return AuthorityInfo(
                code="sacral",
                label="Sakral",
                decisionHint="Höre auf deine Bauchstimme (Mmh-hmm oder Uh-uh) im Moment.",
            )

        if "spleen" in defined_centers:
            return AuthorityInfo(
                code="spleen",
                label="Milz",
                decisionHint="Vertraue deiner spontanen Intuition im Jetzt.",
            )

        if "heart" in defined_centers:
            # Ego Manifested or Projected
            if type_code == "4":  # Manifestor
                return AuthorityInfo(
                    code="ego_manifested",
                    label="Ego-Manifestiert",
                    decisionHint="Informiere und folge deinem Willen.",
                )
            else:  # Projector
                return AuthorityInfo(
                    code="ego_projected",
                    label="Ego-Projektiert",
                    decisionHint="Warte auf Einladung und folge deinem Willen.",
                )

        if "g" in defined_centers:
            return AuthorityInfo(
                code="self_projected",
                label="Selbst-Projektiert",
                decisionHint="Sprich mit anderen und höre dir selbst zu.",
            )

        # Mental Projector (Head/Ajna defined, no centers below throat)
        return AuthorityInfo(
            code="mental",
            label="Mental / Keine",
            decisionHint="Besprich Entscheidungen mit anderen, um Klarheit zu gewinnen.",
        )

    def _determine_profile(self, p_line: int, d_line: int) -> ProfileInfo:
        """Determine Profile from Sun lines."""
        code = f"{p_line}/{d_line}"

        descriptions = {
            "1/3": "Investigator / Märtyrer - Forschen und Ausprobieren.",
            "1/4": "Investigator / Opportunist - Forschen und Netzwerken.",
            "2/4": "Einsiedler / Opportunist - Naturtalent und Netzwerken.",
            "2/5": "Einsiedler / Ketzer - Naturtalent und Problemlöser.",
            "3/5": "Märtyrer / Ketzer - Ausprobieren und Problemlöser.",
            "3/6": "Märtyrer / Rollenvorbild - Ausprobieren und Vorbild sein.",
            "4/6": "Opportunist / Rollenvorbild - Netzwerken und Vorbild sein.",
            "4/1": "Opportunist / Investigator - Netzwerken und Forschen.",
            "5/1": "Ketzer / Investigator - Problemlöser und Forschen.",
            "5/2": "Ketzer / Einsiedler - Problemlöser und Naturtalent.",
            "6/2": "Rollenvorbild / Einsiedler - Vorbild sein und Naturtalent.",
            "6/3": "Rollenvorbild / Märtyrer - Vorbild sein und Ausprobieren.",
        }

        return ProfileInfo(
            code=code,
            shortDescription=descriptions.get(code, "Dein einzigartiges Profil."),
        )

    def _determine_incarnation_cross(self, sun_gate: int, profile_code: str) -> str:
        """Determine the name of the Incarnation Cross."""
        import json
        import os

        # Load cross data (in production, cache this)
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_path = os.path.join(
                base_path, "config", "data", "incarnation_crosses.json"
            )

            with open(data_path, "r", encoding="utf-8") as f:
                cross_data = json.load(f)

            gate_str = str(sun_gate)
            if gate_str in cross_data:
                angle = self._get_profile_angle(profile_code)
                return cross_data[gate_str].get(angle, f"Kreuz von Tor {sun_gate}")

        except Exception as e:
            print(f"Error loading incarnation crosses: {e}")

        return f"Kreuz von Tor {sun_gate}"

    def _get_profile_angle(self, profile_code: str) -> str:
        """Determine angle (right, juxtaposition, left) from profile."""
        right_angle = ["1/3", "1/4", "2/4", "2/5", "3/5", "3/6", "4/6"]
        juxtaposition = ["4/1"]
        # left_angle = ["5/1", "5/2", "6/2", "6/3"]

        if profile_code in right_angle:
            return "right_angle"
        elif profile_code in juxtaposition:
            return "juxtaposition"
        else:
            return "left_angle"

    def _generate_impulse(self, type_code: str, authority_code: str) -> str:
        """Generate personalized impulse."""
        import json
        import os

        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_path = os.path.join(base_path, "config", "data", "impulses.json")

            with open(data_path, "r", encoding="utf-8") as f:
                impulses_data = json.load(f)

            if (
                type_code in impulses_data
                and authority_code in impulses_data[type_code]
            ):
                return impulses_data[type_code][authority_code]

        except Exception as e:
            print(f"Error loading impulses: {e}")

        return "Vertraue deiner inneren Autorität - sie kennt deinen Weg."
