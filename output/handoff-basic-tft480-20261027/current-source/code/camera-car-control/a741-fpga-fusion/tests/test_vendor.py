"""Repeated preparation must preserve Gowin's cached compiler-input identity."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vendor_adapter", ROOT / "scripts/vendor.py")
vendor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vendor)


class VendorPreparationTests(unittest.TestCase):
    def test_repeated_prepare_preserves_timestamps_and_repairs_changed_output(self):
        pinned = ROOT.parent / "third_party/verilog-ethernet/rtl/udp_checksum_gen.v"
        raw = pinned.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "project"
            project.mkdir()
            source = base / "third_party/verilog-ethernet/rtl/udp_checksum_gen.v"
            source.parent.mkdir(parents=True)
            source.write_bytes(raw)
            output = vendor.checksum_source(project)
            metadata = output.with_suffix(".json")
            expected = {p: p.read_bytes() for p in (output, metadata)}
            for p in expected:
                os.utime(p, ns=(1_700_000_000_000_000_000,) * 2)
            timestamps = {p: p.stat().st_mtime_ns for p in expected}
            self.assertEqual(vendor.checksum_source(project), output)
            for p in expected:
                self.assertEqual(p.read_bytes(), expected[p])
                self.assertEqual(p.stat().st_mtime_ns, timestamps[p])
            output.write_bytes(b"corrupted cache")
            vendor.checksum_source(project)
            self.assertEqual(output.read_bytes(), expected[output])
            self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(hashlib.sha256(pinned.read_bytes()).digest(), hashlib.sha256(raw).digest())


if __name__ == "__main__":
    unittest.main()
