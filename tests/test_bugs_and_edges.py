import unittest

from slmp.constants import FrameType, PLCSeries, SlmpProfileClass
from slmp.core import (
    SlmpError,
    SlmpProfileRecommendation,
    SlmpTarget,
    TypeNameInfo,
    recommend_profile,
    unpack_bit_values,
)


class TestBugsAndEdges(unittest.TestCase):
    """Test suite for bugs and edge cases."""

    def test_unpack_bit_values_short(self) -> None:
        """Test unpacking bit values with short data."""
        # Need 3 bits (2 bytes), but got 1 byte
        data = b"\x11"
        with self.assertRaises(SlmpError) as cm:
            unpack_bit_values(data, 3)
        self.assertIn("bit data too short", str(cm.exception))

    def test_slmp_target_module_io_keywords(self) -> None:
        """Test SlmpTarget module_io keywords."""
        t = SlmpTarget(module_io="CONTROL_CPU")
        self.assertEqual(t.module_io, 0x03FF)
        t = SlmpTarget(module_io="own_station")
        self.assertEqual(t.module_io, 0x03FF)
        with self.assertRaises(ValueError):
            SlmpTarget(module_io="INVALID_KEYWORD")

    def test_recommend_profile_model_code_iqr(self) -> None:
        """Model code in 0x4800–0x4FFF range → iQ-R."""
        info = TypeNameInfo(raw=b"", model="R04CPU", model_code=0x4801)
        rec = recommend_profile(info)
        self.assertEqual(rec.frame_type, FrameType.FRAME_4E)
        self.assertEqual(rec.plc_series, PLCSeries.IQR)
        self.assertEqual(rec.profile_class, SlmpProfileClass.MODERN_IQR)
        self.assertTrue(rec.is_confident)

    def test_recommend_profile_model_code_legacy(self) -> None:
        """Model code in legacy range → Q/L."""
        info = TypeNameInfo(raw=b"", model="Q06UDVCPU", model_code=0x0050)
        rec = recommend_profile(info)
        self.assertEqual(rec.frame_type, FrameType.FRAME_3E)
        self.assertEqual(rec.plc_series, PLCSeries.QL)
        self.assertEqual(rec.profile_class, SlmpProfileClass.LEGACY_QL)
        self.assertTrue(rec.is_confident)

    def test_recommend_profile_model_name_r_prefix(self) -> None:
        """R-prefix model name (no code) → iQ-R."""
        info = TypeNameInfo(raw=b"", model="R08CPU", model_code=None)
        rec = recommend_profile(info)
        self.assertEqual(rec.profile_class, SlmpProfileClass.MODERN_IQR)

    def test_recommend_profile_model_name_rd_prefix_not_iqr(self) -> None:
        """RD prefix is excluded from the R-prefix iQ-R rule."""
        info = TypeNameInfo(raw=b"", model="RD75P4", model_code=None)
        rec = recommend_profile(info)
        # RD does not match iQ-R prefix rule → falls through to unknown
        self.assertEqual(rec.profile_class, SlmpProfileClass.UNKNOWN)

    def test_recommend_profile_model_name_q_prefix(self) -> None:
        """Q-prefix model name → Q/L legacy."""
        info = TypeNameInfo(raw=b"", model="Q06UDVCPU", model_code=None)
        rec = recommend_profile(info)
        self.assertEqual(rec.profile_class, SlmpProfileClass.LEGACY_QL)

    def test_recommend_profile_model_name_fx(self) -> None:
        """FX-prefix model name → Q/L legacy."""
        info = TypeNameInfo(raw=b"", model="FX5UCPU", model_code=None)
        rec = recommend_profile(info)
        self.assertEqual(rec.profile_class, SlmpProfileClass.LEGACY_QL)

    def test_recommend_profile_unknown(self) -> None:
        """Unrecognised model → Unknown / not confident."""
        info = TypeNameInfo(raw=b"", model="UNKNOWNCPU", model_code=None)
        rec = recommend_profile(info)
        self.assertEqual(rec.profile_class, SlmpProfileClass.UNKNOWN)
        self.assertFalse(rec.is_confident)

    def test_slmp_profile_recommendation_is_frozen(self) -> None:
        """SlmpProfileRecommendation is immutable."""
        rec = SlmpProfileRecommendation(FrameType.FRAME_4E, PLCSeries.IQR, SlmpProfileClass.MODERN_IQR, True)
        with self.assertRaises(Exception):  # noqa: B017
            rec.is_confident = False  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
