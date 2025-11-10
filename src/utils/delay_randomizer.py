from __future__ import annotations

import random

def random_delay_ms(min_ms: int, max_ms: int) -> int:
    """
    Random integer in [min_ms, max_ms], swapping if provided in reverse.
    """
    a, b = (min_ms, max_ms) if min_ms <= max_ms else (max_ms, min_ms)
    return random.randint(a, b)