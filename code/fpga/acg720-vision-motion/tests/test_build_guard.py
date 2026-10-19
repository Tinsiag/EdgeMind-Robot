import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('vision_build', ROOT / 'scripts' / 'build.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class BuildGuardTests(unittest.TestCase):
    def test_missing_manifest_is_explicit(self):
        with self.assertRaisesRegex(ValueError, 'Missing board support'):
            BUILD.verify_manifest(ROOT / '.local' / 'not-present.json')

    def test_example_cannot_build(self):
        with self.assertRaisesRegex(ValueError, 'review'):
            BUILD.verify_manifest(ROOT / 'platform.example.json')

    def test_rom_provenance_hash(self):
        import re
        values = re.findall(r"value=8'h([0-9a-f]{2})", (ROOT / 'rtl' / 'vl53l1x_config_rom.v').read_text())
        self.assertEqual(len(values), 91)
        record = json.loads((ROOT / 'vendor' / 'vl53l1x-source.json').read_text())
        self.assertEqual(hashlib.sha256(bytes(int(v, 16) for v in values)).hexdigest(), record['configuration_sha256'])

    def test_stale_dependency_hash_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            (temp / 'source.v').write_text('module x; endmodule')
            data = {'device': 'GW5AT-60B', 'part': BUILD.PART,
                    'top_module': 'acg720_vision_motion_board', 'io_reviewed': True,
                    'files': [{'path': 'source.v', 'sha256': '0' * 64}]}
            manifest = temp / 'manifest.json'
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'hash'):
                BUILD.verify_manifest(manifest)

    def test_source_list_contains_only_real_modules(self):
        self.assertTrue(all((BUILD.SHARED / (n + '.v')).is_file() for n in BUILD.SHARED_NAMES))
        self.assertFalse(list((ROOT / 'rtl').glob('*stub*')))

    def test_duplicate_and_unknown_tof_pins_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            files = []
            def add(name, text, role, kind='file.verilog'):
                path = temp / name
                path.write_text(text, encoding='utf-8')
                files.append({'path': name, 'sha256': BUILD.digest(path), 'role': role, 'type': kind})
            for role in BUILD.ROLES:
                add(role + '.v', 'vision_motion_top' if role == 'board_wrapper' else '// dependency', role)
            # A valid syntactic fixture is only used for checker unit tests; no
            # generated project or Gowin invocation can result from this test.
            cst = ''.join(f'IO_LOC "{port}" {ball};\n' for port, ball in BUILD.EXPECTED.items())
            add('board.cst', cst, 'constraints', 'file.cst')
            add('board.sdc', '# reviewed timing fixture', 'timing', 'file.sdc')
            evidence = temp / 'review.md'
            evidence.write_text('fixture')
            data = {'device': 'GW5AT-60B', 'part': BUILD.PART,
                    'top_module': 'acg720_vision_motion_board', 'io_reviewed': True,
                    'io_review_evidence': {'path': evidence.name, 'sha256': BUILD.digest(evidence)},
                    'files': files, 'tof_pins': {}}
            manifest = temp / 'manifest.json'
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'ToF pin'):
                BUILD.verify_manifest(manifest)
            cst_path = temp / 'board.cst'
            cst_path.write_text(cst + 'IO_LOC "tof_sda" Y18;\n')
            for item in files:
                if item['path'] == 'board.cst':
                    item['sha256'] = BUILD.digest(cst_path)
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                BUILD.verify_manifest(manifest)


if __name__ == '__main__':
    unittest.main()
