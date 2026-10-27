import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("firmware_cache_under_test",PROJECT/"scripts/build_mission.py")
BUILD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class FirmwareCacheTests(unittest.TestCase):
    def fixture(self,root):
        shutil.copytree(PROJECT/"firmware",root/"firmware")

    def test_valid_pinned_image_needs_no_compiler_or_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            target=root/"firmware/mission.hex";before=target.stat().st_mtime_ns
            with patch.object(BUILD,"ROOT",root),patch.object(BUILD.subprocess,"run") as compiler:
                self.assertEqual(BUILD.build(),target)
                compiler.assert_not_called()
            self.assertEqual(target.stat().st_mtime_ns,before)

    def test_source_or_rom_change_invalidates_pinned_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            with patch.object(BUILD,"ROOT",root):
                source=root/"firmware/mission.c";original=source.read_bytes()
                source.write_bytes(original+b"\n/* changed */\n")
                self.assertIsNone(BUILD.cached_image())
                source.write_bytes(original)
                image=root/"firmware/mission.hex"
                image.write_bytes(b"00000000\n"+image.read_bytes()[9:])
                self.assertIsNone(BUILD.cached_image())


if __name__=="__main__":
    unittest.main()
