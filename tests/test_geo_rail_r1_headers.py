"""Isolated TIFF header parser tests — synthetic bytes only."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("geo_rail_r1_probe", TOOLS / "geo_rail_r1_probe.py")
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)


def minimal_tiff(width=3600, height=3600):
    header = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    entries = (struct.pack("<HHII", 256, 4, 1, width) +
               struct.pack("<HHII", 257, 4, 1, height))
    return header + struct.pack("<H", 2) + entries + struct.pack("<I", 0)


class TiffHeaderTests(unittest.TestCase):
    def test_dimensions_and_signature(self):
        info = geo.parse_tiff_prefix(minimal_tiff())
        self.assertTrue(info["tiff_signature_valid"])
        self.assertEqual(info["width_px"], 3600)
        self.assertEqual(info["height_px"], 3600)

    def test_reject_wrong_signature(self):
        info = geo.parse_tiff_prefix(b"NOT_A_TIFF_FILE_012345")
        self.assertFalse(info["tiff_signature_valid"])

    def test_does_not_crash_on_broken_ifd(self):
        data = b"II" + struct.pack("<H", 42) + struct.pack("<I", 999_999)
        info = geo.parse_tiff_prefix(data)
        self.assertTrue(info["tiff_signature_valid"])
        self.assertIsNone(info["width_px"])

    def test_prefix_budget(self):
        self.assertEqual(geo.MAX_PREFIX_BYTES, 16384)


if __name__ == "__main__":
    unittest.main()
