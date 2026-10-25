"""Offline tests for hardware-write selection and failure handling; never use JTAG."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import program_flash as flash


class FlashTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.image = root / "完整 image.fs"
        self.image.write_bytes(b"test bitstream; not for hardware")
        self.tool = root / "programmer_cli.exe"
        self.tool.write_bytes(b"mock tool; not executable")
        self.logs = root / "logs"
        self.argv = ["--bitstream", str(self.image), "--sha256", flash.sha256(self.image),
                     "--programmer", str(self.tool), "--log-dir", str(self.logs)]

    def invoke(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return flash.main(self.argv + list(extra))

    def audit(self):
        return json.loads(next(self.logs.glob("*/audit.json")).read_text(encoding="utf-8"))

    def test_preview_never_invokes_programmer(self):
        with patch.object(flash.subprocess, "run") as run:
            self.assertEqual(self.invoke(), 0)
        run.assert_not_called()
        self.assertFalse(self.logs.exists())

    def test_wrong_hash_rejected_before_hardware(self):
        self.image.write_bytes(b"different image")
        with patch.object(flash.subprocess, "run") as run:
            self.assertEqual(self.invoke("--program"), 1)
        run.assert_not_called()

    def test_success_stages_exact_image_and_keeps_cold_boot_pending(self):
        results = [subprocess.CompletedProcess([], 0, b"Program and Verify Flash Successfully."),
                   subprocess.CompletedProcess([], 0, b"Reprogram completed"),
                   subprocess.CompletedProcess([], 0, b"Status Code: 0x1234")]
        with patch.object(flash.subprocess, "run", side_effect=results) as run:
            self.assertEqual(self.invoke("--program"), 0)
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual([c[c.index("--run") + 1] for c in calls], ["54", "1", "74"])
        self.assertEqual(calls[0][calls[0].index("--spiaddr") + 1], "0x000000")
        self.assertEqual(calls[0][calls[0].index("--device") + 1], "GW5AT-60B")
        audit = self.audit()
        self.assertTrue(audit["flash_program_verify_completed"])
        self.assertTrue(audit["reload_command_completed"])
        self.assertFalse(audit["cold_boot_verified"])
        self.assertFalse(audit["application_verified"])
        self.assertEqual(Path(audit["staged_bitstream"]).read_bytes(), self.image.read_bytes())

    def test_verify_failure_even_with_exit_zero_stops_before_reload(self):
        with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"Verify Failed at address 0x100")) as run:
            self.assertEqual(self.invoke("--program"), 1)
        self.assertEqual(run.call_count, 1)
        self.assertFalse(self.audit()["flash_program_verify_completed"])
        self.assertEqual(self.audit()["steps"][-1]["state"], "failed")

    def test_verify_evidence_can_come_from_vendor_output_file(self):
        def output_file_result(command, **kwargs):
            if command[command.index("--run") + 1] == "54":
                Path(command[command.index("--output") + 1]).write_bytes(b"Program and Verify flash successfully.")
            return subprocess.CompletedProcess(command, 0, b"")
        with patch.object(flash.subprocess, "run", side_effect=output_file_result):
            self.assertEqual(self.invoke("--program"), 0)
        self.assertTrue(self.audit()["flash_program_verify_completed"])

    def test_missing_verify_evidence_is_not_success(self):
        with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"Done")) as run:
            self.assertEqual(self.invoke("--program"), 1)
        self.assertEqual(run.call_count, 1)

    def test_nonzero_exit_overrides_success_text(self):
        with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"Verify Success")) as run:
            self.assertEqual(self.invoke("--program"), 1)
        self.assertEqual(run.call_count, 1)

    def test_timeout_preserves_incomplete_result_without_retry(self):
        with patch.object(flash.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 900, output=b"partial")) as run:
            self.assertEqual(self.invoke("--program"), 1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.audit()["state"], "failed")
        self.assertFalse(self.audit()["reload_command_completed"])

    def test_reload_failure_preserves_flash_success_without_claiming_boot(self):
        results = [subprocess.CompletedProcess([], 0, b"Verify flash successfully."),
                   subprocess.CompletedProcess([], 1, b"Error: cable disconnected")]
        with patch.object(flash.subprocess, "run", side_effect=results) as run:
            self.assertEqual(self.invoke("--program"), 1)
        self.assertEqual(run.call_count, 2)
        audit = self.audit()
        self.assertTrue(audit["flash_program_verify_completed"])
        self.assertFalse(audit["reload_command_completed"])
        self.assertFalse(audit["cold_boot_verified"])


if __name__ == "__main__":
    unittest.main()
