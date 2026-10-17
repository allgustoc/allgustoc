import pytest

from radar.airports import expand_airports


def test_expand_groups_and_dedupe():
    assert expand_airports("GRU, pt") == ["GRU", "LIS", "OPO", "FAO"]
    assert expand_airports("LIS,PT") == ["LIS", "OPO", "FAO"]
    assert "MAD" in expand_airports("PTES") and "LIS" in expand_airports("PTES")


def test_expand_rejects_invalid():
    with pytest.raises(ValueError):
        expand_airports("LISBOA")
