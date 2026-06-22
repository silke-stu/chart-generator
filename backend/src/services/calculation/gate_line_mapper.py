"""
Gate and Line mapping from ecliptic longitude.

Converts astronomical ecliptic positions to Human Design gate/line activations.
"""


def ecliptic_to_gate_line(longitude: float) -> tuple[int, int]:
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

    # Ensure line is in valid range
    if line_number > 6:
        line_number = 6

    # Map to actual HD gate sequence (wheel order)
    gate = _map_to_hd_gate(gate_number)

    return gate, line_number


def _map_to_hd_gate(position: int) -> int:
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
