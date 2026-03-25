"""Cross-language spec compliance: SLMP device spec encoding vectors.

Each vector in slmp_device_vectors.json defines an expected byte sequence for a
given device string and series. The same JSON is consumed by the .NET test suite,
ensuring Python and .NET produce identical wire bytes.
"""

import json
from pathlib import Path

import pytest

from slmp.constants import PLCSeries
from slmp.core import encode_device_spec

_VECTORS_PATH = Path(__file__).parent / "vectors" / "slmp_device_vectors.json"
_VECTORS = json.loads(_VECTORS_PATH.read_text())["vectors"]


@pytest.mark.parametrize("vec", _VECTORS, ids=lambda v: v["id"])
def test_device_spec_encoding(vec: dict) -> None:
    series = PLCSeries.IQR if vec["series"] == "iqr" else PLCSeries.QL
    result = encode_device_spec(vec["device"], series=series)
    expected = bytes.fromhex(vec["hex"])
    assert result == expected, (
        f"[{vec['id']}] device={vec['device']} series={vec['series']}: "
        f"got {result.hex().upper()!r}, expected {vec['hex']!r}"
    )
