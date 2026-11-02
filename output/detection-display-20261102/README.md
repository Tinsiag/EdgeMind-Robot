# FW74512 detection return / TFT integration

Goal: preserve local camera video and original HUD while overlaying 4A YOLO boxes.

- Input: 640x480 cropped camera frame; NPU 640x384 at target 5Hz; browser target15fps.
- ED10 display metadata: unicast UDP6105, up to8 boxes, IP/UDP checksums and MAC FCS validated.
- FPGA display: x+80 crop mapping, green2px outline below HUD, atomic frame update, ~1s expiry.
- No motion commands or automatic ARM. User reports motors disconnected and VM off.
- Actual bitstream/Flash/health state is recorded in RESULT.json after verification.
- Physical TFT observation and a new-image power-cycle require separate acceptance.

preflash-wire.json records real 4A sends before programming; old FW74511 has no RX.
first-routed-failed.json is a rejected, never-programmed candidate, retained as failure evidence.

The raw-socket wire probe temporarily disabled end1 TX checksum offload to inspect complete
UDP checksums. With offload enabled, local outgoing packet capture contains checksum seeds
before the NIC completes them; such captures do not show transmitted checksum errors.

Software setup and protocol: ../../code/camera-car-control/a745-autonomous/host/README-video.md
Timing and physical evidence: ../refactor-autonomous-20261030/

Additional rejected candidates:
- second-routed-failed.json: parser125 internal setup failures; fixed by parser50 with frame FIFO.
- third-routed-failed-pad-pulse.json: primary STA setup/hold passed, independent RX slow-corner
  hold and RAM minimum pulse checks failed. Never programmed. RX now has matched IODELAY96,
  and dedicated clock routing / route2-place2 are under final review.

- fourth-routed-failed-pulse.json: matched RX delays in place; TX RAM pulse still negative.
- fifth-routed-failed-pulse.json: frequency-first clock routing retained identical synthesis;
  RAM pulse worst -0.068ns. Never programmed.
- The next build uses PLL250 -> dedicated CLKDIV/2, following the recorded historical fix.
  Original vendor PLL source is preserved; prepare.py changes only generated ODIV1.
- See current project's docs/TIMING-CLOSURE.md for the historical Git paths and workflow.
- end1 TX checksum offload has now been restored to its original value1.
  preflash-offload-restored.json confirms25 local sends /5s with Linux AUXDATA marking
  checksum completion pending; these are not wire-checksum failures. Old74511 accepts0 as expected.
- HARDWARE-BASELINE.json records actual74511 until a new successful Flash audit exists.

Final: FW74512 programmed and verified by Flash54@0, reload, ready0x70022020 and UserCode0xA745.
SHA256888761b35c206f21d920bb192c920d785f3606ed9b2b73b64ff488a354bf4256.
37RTL benches,9navigation/attitude primitive checks,2display primitive checks and all final gates passed.
60s:600statuses/600attitudes healthy/IDLE/unarmed;299inferences and299outgoing results,
accepted delta298 across sampled status endpoints. Camera29.77fps/inference4.98Hz/web14.92fps.
User confirmed visible green boxes and original HUD normal; see DISPLAY-ACCEPTANCE.json.
New-image full power-cycle and movement were not tested. RESULT.json is the final summary.
