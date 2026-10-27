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
        self.image.write_bytes(b"//UserCode: 0x0000A72E\nmock bitstream; never for hardware")
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
                   subprocess.CompletedProcess([], 0, b"Status Code is: 0x70022020"),
                   subprocess.CompletedProcess([], 0, b"User Code is: 0x0000A72E")]
        with patch.object(flash.subprocess, "run", side_effect=results) as run:
            self.assertEqual(self.invoke("--program"), 0)
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual([c[c.index("--run") + 1] for c in calls], ["54", "1", "74", "73"])
        self.assertEqual(calls[0][calls[0].index("--spiaddr") + 1], "0x000000")
        self.assertEqual(calls[0][calls[0].index("--device") + 1], "GW5AT-60B")
        audit = self.audit()
        self.assertTrue(audit["flash_program_verify_completed"])
        self.assertTrue(audit["reload_command_completed"])
        self.assertTrue(audit["configuration_ready"])
        self.assertTrue(audit["user_code_verified"])
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
            messages={"54":b"Program and Verify flash successfully.","1":b"Reprogram completed",
                      "74":b"Status Code is: 0x70022020","73":b"User Code is: 0x0000A72E"}
            Path(command[command.index("--output") + 1]).write_bytes(messages[command[command.index("--run") + 1]])
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

    def test_pending_configuration_is_only_polled_not_reprogrammed(self):
        texts=[b"Program and Verify Flash successfully.",b"Reprogram completed",
               b"Status Code is: 0x30000460",b"Status Code is: 0x70022020",b"User Code is: 0x0000A72E"]
        with patch.object(flash.subprocess,"run",side_effect=[subprocess.CompletedProcess([],0,x) for x in texts]) as run, patch.object(flash.time,"sleep"):
            self.assertEqual(self.invoke("--program"),0)
        operations=[c.args[0][c.args[0].index("--run")+1] for c in run.call_args_list]
        self.assertEqual(operations,["54","1","74","74","73"])
        self.assertEqual(len(self.audit()["configuration_status_samples"]),2)
        self.assertTrue(self.audit()["user_code_verified"])

    def test_configuration_error_stops_without_rewrite(self):
        texts=[b"Program and Verify Flash successfully.",b"Reprogram completed",b"Status Code is: 0x70022021"]
        with patch.object(flash.subprocess,"run",side_effect=[subprocess.CompletedProcess([],0,x) for x in texts]) as run:
            self.assertEqual(self.invoke("--program"),1)
        self.assertEqual(run.call_count,3)
        self.assertTrue(self.audit()["flash_program_verify_completed"])
        self.assertFalse(self.audit()["configuration_ready"])

    def test_wakeup_timeout_never_rewrites_or_reads_user_code(self):
        texts=[b"Program and Verify Flash successfully.",b"Reprogram completed",b"Status Code is: 0x30000460"]
        with patch.object(flash.subprocess,"run",side_effect=[subprocess.CompletedProcess([],0,x) for x in texts]) as run, patch.object(flash,"CONFIG_TIMEOUT_SECONDS",0):
            self.assertEqual(self.invoke("--program"),1)
        self.assertEqual(run.call_count,3)
        self.assertFalse(self.audit()["configuration_ready"])

    def test_ready_status_with_wrong_user_code_is_not_accepted(self):
        texts=[b"Program and Verify Flash successfully.",b"Reprogram completed",b"Status Code is: 0x70022020",b"User Code is: 0xDEADBEEF"]
        with patch.object(flash.subprocess,"run",side_effect=[subprocess.CompletedProcess([],0,x) for x in texts]) as run:
            self.assertEqual(self.invoke("--program"),1)
        self.assertEqual(run.call_count,4)
        self.assertTrue(self.audit()["configuration_ready"])
        self.assertFalse(self.audit()["user_code_verified"])

    def test_missing_user_code_header_rejected_before_hardware(self):
        self.image.write_bytes(b"not a bitstream")
        self.argv[self.argv.index("--sha256")+1]=flash.sha256(self.image)
        with patch.object(flash.subprocess,"run") as run:
            self.assertEqual(self.invoke("--program"),1)
        run.assert_not_called()

    def test_missing_status_is_not_ready(self):
        texts=[b"Program and Verify Flash successfully.",b"Reprogram completed",b"Finished"]
        with patch.object(flash.subprocess,"run",side_effect=[subprocess.CompletedProcess([],0,x) for x in texts]) as run:
            self.assertEqual(self.invoke("--program"),1)
        self.assertEqual(run.call_count,3)
        self.assertFalse(self.audit()["configuration_ready"])

    def test_known_register_values_use_documented_bits(self):
        self.assertFalse(flash.configuration_status("Status Code is: 0x30000460")["ready"])
        self.assertTrue(flash.configuration_status("Status Code is: 0x70026020")["ready"])
        self.assertEqual(flash.configuration_status("Status Code is: 0x70026020")["error_bits"],"0x00000000")


if __name__ == "__main__":
    unittest.main()
