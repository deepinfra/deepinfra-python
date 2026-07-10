"""Small internal helpers shared by the SDK."""

from __future__ import annotations

import random
import re
from collections.abc import Iterator, Mapping

_DURATION_RE = re.compile(r"(\d+)(h|m|s)")


def parse_duration(value: int | float | str) -> int:
    """Parse a duration into whole seconds.

    Accepts plain numbers (seconds) or strings like "90", "90s", "10m",
    "2h", and compounds like "1h30m". Raises ValueError on anything else.
    """
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError(f"Duration must be non-negative, got {value!r}")
        return int(value)
    text = value.strip().lower()
    if not text:
        raise ValueError("Duration string is empty")
    if text.isdigit():
        return int(text)
    matches = list(_DURATION_RE.finditer(text))
    if not matches or "".join(m.group(0) for m in matches) != text:
        raise ValueError(
            f"Invalid duration {value!r}; use seconds or e.g. '90s', '10m', '1h30m'"
        )
    factors = {"h": 3600, "m": 60, "s": 1}
    return sum(int(m.group(1)) * factors[m.group(2)] for m in matches)


def backoff_delays(
    initial: float = 0.5,
    maximum: float = 3.0,
    factor: float = 2.0,
    jitter: float = 0.2,
) -> Iterator[float]:
    """Yield an endless exponential backoff schedule with +/- jitter."""
    delay = initial
    while True:
        yield delay * random.uniform(1 - jitter, 1 + jitter)
        delay = min(delay * factor, maximum)


def tags_match(subset: Mapping[str, str], tags: Mapping[str, str]) -> bool:
    """True when every key/value in subset is present in tags."""
    return all(tags.get(k) == v for k, v in subset.items())
