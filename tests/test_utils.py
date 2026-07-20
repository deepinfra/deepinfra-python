import pytest

from deepinfra._utils import backoff_delays, parse_duration, tags_match


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, 0),
        (90, 90),
        # fractional seconds round up: 0 means "server default", so a small
        # positive timeout must never truncate to 0
        (0.5, 1),
        (90.9, 91),
        ("90", 90),
        ("90s", 90),
        ("10m", 600),
        ("2h", 7200),
        ("1h30m", 5400),
        ("1h30m15s", 5415),
        (" 10M ", 600),
    ],
)
def test_parse_duration_valid(value, expected):
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "10x", "m10", "1.5m", "10m5", -5])
def test_parse_duration_invalid(value):
    with pytest.raises(ValueError):
        parse_duration(value)


def test_backoff_delays_grow_and_cap():
    delays = backoff_delays(initial=0.5, maximum=3.0, factor=2.0, jitter=0.0)
    values = [next(delays) for _ in range(5)]
    assert values == [0.5, 1.0, 2.0, 3.0, 3.0]


def test_backoff_jitter_bounds():
    delays = backoff_delays(initial=1.0, maximum=1.0, jitter=0.2)
    for _ in range(50):
        assert 0.8 <= next(delays) <= 1.2


def test_tags_match():
    assert tags_match({}, {"a": "1"})
    assert tags_match({"a": "1"}, {"a": "1", "b": "2"})
    assert not tags_match({"a": "2"}, {"a": "1"})
    assert not tags_match({"c": "3"}, {"a": "1"})
