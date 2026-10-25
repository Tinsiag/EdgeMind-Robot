"""Prepare an isolated source snapshot while the preceding PNR owns its inputs."""
from pathlib import Path
import hashlib
import json
import re
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / "code/camera-car-control/a741-fpga-fusion"
OUT = HERE / "phase-safe-hdmi"
SNAP = OUT / "workspace"
if SNAP.exists():
    raise RuntimeError("Refusing to overwrite an existing experiment")
manifest = {}
def copy(source):
    relative = source.relative_to(REPO)
    target = SNAP / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    manifest[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()

for record, key in ((BASE / ".local/gowin-fusion-tft480/result.json", "source_sha256"),
                    (HERE / "interface-and-telemetry-fix/tests/result.json", "input_sha256")):
    values = json.loads(record.read_text(encoding="utf-8"))[key]
    for name, expected in values.items():
        source = Path(name)
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Input changed: " + name)
        copy(source)
for folder in (BASE / "scripts", BASE / "config", BASE / "firmware",
               BASE.parent / ".local/platform", BASE.parent / "third_party/verilog-ethernet/rtl"):
    for source in folder.rglob("*"):
        if source.is_file() and "__pycache__" not in source.parts:
            copy(source)
(OUT / "before-sha256.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
root = SNAP / BASE.relative_to(REPO)
hdmi = root / "rtl/a741_hdmi.v"
text = hdmi.read_text(encoding="utf-8")
text = text.replace('    (* ASYNC_REG="TRUE" *) reg [2:0] serial_reset_pipe;\n', '')
text, n = re.subn(r'    // A separate 33 MHz PLL output.*?else serial_reset_pipe<=\{serial_reset_pipe\[1:0\],1\'b0\};\n', '', text, flags=re.S)
assert n == 1
text = text.replace('        wire serial_data;', '''        wire serial_data;
        // Divide-by-3 reset clock and divide-by-5 pixel clock cover every
        // integer serial-clock phase at startup. Keep reset FFs local to each
        // serializer so recovery/removal timing includes short physical paths.
        (* ASYNC_REG="TRUE", syn_preserve=1, syn_keep=1 *) reg [2:0] serial_reset_pipe;
        always @(posedge reset_clk or negedge rst_n)
            if(!rst_n) serial_reset_pipe<=3'b111;
            else serial_reset_pipe<={serial_reset_pipe[1:0],1'b0};''')
hdmi.write_text(text, encoding="utf-8")
build = root / "scripts/build.py"
text = build.read_text(encoding="utf-8")
for old, new in (("supplies a 33 MHz reset clock", "supplies a 55 MHz reset clock"),
                 ('b"ODIV0_SEL = 25"', 'b"ODIV0_SEL = 15"'),
                 ('-name hdmi_reset33m -source [get_ports {clk}] -multiply_by 33 -divide_by 50',
                  '-name hdmi_reset55m -source [get_ports {clk}] -multiply_by 11 -divide_by 10'),
                 ('hdmi/serial_reset_pipe*/PRESET', 'hdmi/lanes*.serial_reset_pipe*/PRESET')):
    assert text.count(old) == 1, old
    text = text.replace(old, new)
build.write_text(text, encoding="utf-8")
fixture = HERE / "timing-fix/hdmi-clock-audit/hdmi_phase_reset_tb.v"
(root / "tests/hdmi_tb.v").write_text(fixture.read_text().replace("module hdmi_phase_reset_tb;", "module hdmi_tb;"), encoding="utf-8")
(OUT / "README.md").write_text("# HDMI启动相位修正候选\n\n独立源码快照；未修改正在运行的整板PNR输入。55MHz复位时钟、四路局部同步复位、五种CLKDIV启动相位。保留网口、视频、全部RESET时序检查与几何锁。尚未整板或实板通过，不可烧录。\n", encoding="utf-8")
print(root)
print("copied inputs", len(manifest))
