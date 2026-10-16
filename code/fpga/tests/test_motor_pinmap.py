"""Static regression for the user-reported 2026-10-14 motor rewiring.

No FPGA toolchain or hardware is used. This does not validate bank voltages,
connector positions, routed timing, bitstreams, or electrical safety.
"""
import ast
import hashlib
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = {
    "left_in1": ("A18", "LAIN1", "L-1", "out"),
    "left_in2": ("A19", "LAIN2", "L-2", "out"),
    "left_enc_a": ("A15", "LF_ENA", "L-7", "in"),
    "left_enc_b": ("A16", "LF_ENB", "L-8", "in"),
    "right_in1": ("F13", "RAIN1", "R-5", "out"),
    "right_in2": ("F14", "RAIN2", "R-6", "out"),
    "right_enc_a": ("E13", "RF_ENA", "R-2", "in"),
    "right_enc_b": ("E14", "RF_ENB", "R-1", "in"),
}
PROJECTS = {
    "acg720-motion-control": "acg720_motion_control.cst",
    "acg720-motor-test": "acg720_motor_test.cst",
}


class MotorPinmapTests(unittest.TestCase):
    def test_constraints_pinmap_and_io_settings(self):
        for project, cst in PROJECTS.items():
            with self.subTest(project=project):
                text = (ROOT / "code/fpga" / project / "constraints" / cst).read_text()
                locs = re.findall(r'IO_LOC\s+"([^"]+)"\s+(\w+);', text)
                self.assertEqual(len(locs), len(dict(locs)), "Duplicate port constraint")
                self.assertEqual(len(locs), len({ball for _, ball in locs}), "Ball conflict")
                actual = dict(locs)
                for port, (ball, _, _, _) in EXPECTED.items():
                    self.assertEqual(actual[port], ball)
                    self.assertRegex(text, rf'IO_PORT "{port}" IO_TYPE=LVCMOS33 PULL_MODE=DOWN(?: DRIVE=4)?;')

    def test_motor_audit_expected(self):
        path = ROOT / "code/fpga/acg720-motor-test/tests/audit_build.py"
        tree = ast.parse(path.read_text())
        expected = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "expected" for t in node.targets))
        for port, (ball, _, _, direction) in EXPECTED.items():
            self.assertEqual(expected[port], (ball, direction))

    def test_motion_audit_expected(self):
        path = ROOT / "code/fpga/acg720-motion-control/tests/audit_build.py"
        tree = ast.parse(path.read_text())
        expected = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "EXPECTED" for t in node.targets))
        for port, (ball, _, _, direction) in EXPECTED.items():
            self.assertEqual(expected[port], (ball, direction))

    def test_project_files_reference_current_constraints(self):
        for project, cst in PROJECTS.items():
            folder = ROOT / "code/fpga" / project
            projects = list(folder.glob("*.gprj"))
            self.assertTrue(projects)
            for path in projects:
                with self.subTest(path=path.name):
                    files = ET.parse(path).findall(".//File")
                    self.assertEqual([f.attrib["path"] for f in files
                                      if f.attrib.get("type") == "file.cst"], ["constraints/" + cst])
                    for f in files:
                        self.assertTrue((folder / f.attrib["path"]).is_file())

    def test_canonical_document_matches_ports_balls_and_board_pins(self):
        text = (ROOT / "doc/电机/ACG720与现有电源板接线_2026-10-14.md").read_text()
        for port, (ball, net, board, direction) in EXPECTED.items():
            label = "输出" if direction == "out" else "输入"
            self.assertIn(f"| {net} | {port} | {ball} | {board} | {label} |", text)

    def test_current_readme_tables(self):
        folder = ROOT / "code/fpga/acg720-motor-test"
        text = (folder / "README.md").read_text()
        for port, (ball, net, board, _) in EXPECTED.items():
            self.assertIn(f"| {port} | {ball} | {board} / {net} |", text)
        text = (ROOT / "code/fpga/acg720-motion-control/README.md").read_text()
        for balls in ["A18 / A19", "A15 / A16", "F13 / F14", "E13 / E14"]:
            self.assertIn(balls, text)

    def test_current_constraint_comments_reference_current_wiring(self):
        for project, cst in PROJECTS.items():
            text = (ROOT / "code/fpga" / project / "constraints" / cst).read_text()
            self.assertNotIn("接线_2026-10-10.md", text)
            self.assertIn("2026-10-14", text)

    def test_historical_releases_are_marked_incompatible(self):
        folder = ROOT / "code/fpga/acg720-motor-test/release"
        for readme in sorted(folder.glob("*/README.md")):
            with self.subTest(release=readme.parent.name):
                text = readme.read_text()
                self.assertIn("2026-10-14", text)
                self.assertIn("旧", text)
                self.assertIn("接线", text)

    def test_archived_diagrams_match_manifest(self):
        archive = ROOT / "output/pdf/archive/2026-10-10"
        entries = (archive / "SHA256SUMS").read_text().splitlines()
        self.assertTrue(entries)
        for entry in entries:
            digest, filename = entry.split("  ", 1)
            with self.subTest(file=filename):
                self.assertEqual(hashlib.sha256((archive / filename).read_bytes()).hexdigest(), digest)

    def test_top_level_port_directions(self):
        for source in ["acg720-motion-control/rtl/motion_top.v",
                       "acg720-motor-test/rtl/acg720_motor_test.v",
                       "acg720-motor-test/rtl/acg720_motor_toggle.v",
                       "acg720-motor-test/rtl/acg720_motor_sweep.v"]:
            text = (ROOT / "code/fpga" / source).read_text()
            # Check ANSI port declarations; motion_top groups several wire names.
            header = text[:text.index(");")]
            declarations = re.findall(r'\b(input|output)\s+([^;]*?)(?=\binput\b|\boutput\b|\);)', header + ");", re.S)
            for port, (_, _, _, direction) in EXPECTED.items():
                actual = [kind for kind, names in declarations if re.search(rf'\b{port}\b', names)]
                self.assertEqual(actual, ["input" if direction == "in" else "output"], (source, port))


if __name__ == "__main__":
    unittest.main()
