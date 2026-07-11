"""Cross-language spec compliance: shared SLMP device vectors."""

import json
import unittest
from pathlib import Path

from slmp.constants import PLCSeries
from slmp.core import encode_device_spec

_SHARED_SPEC_DIR = Path(__file__).resolve().parent / "shared-spec"
_VECTORS = json.loads((_SHARED_SPEC_DIR / "device_spec_vectors.json").read_text(encoding="utf-8"))["vectors"]


class TestDeviceVectors(unittest.TestCase):
    def test_device_spec_encoding(self) -> None:
        for vec in _VECTORS:
            if "python" not in vec.get("implementations", []):
                continue
            with self.subTest(case=vec["id"]):
                series = PLCSeries.IQR if vec["series"] == "iqr" else PLCSeries.QL
                result = encode_device_spec(vec["device"], series=series, plc_profile="melsec:iq-r")
                expected = bytes.fromhex(vec["hex"])
                self.assertEqual(
                    result,
                    expected,
                    msg=(
                        f"[{vec['id']}] device={vec['device']} series={vec['series']}: "
                        f"got {result.hex().upper()!r}, expected {vec['hex']!r}"
                    ),
                )
