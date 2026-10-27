"""Compare active LCD pixels with the pre-change 480-screen implementation."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PROJECT = REPO / "code/camera-car-control/a741-fpga-fusion"


def linux(path):
    value = Path(path).resolve().as_posix()
    return "/mnt/" + value[0].lower() + value[2:]


def wsl(args, **kwargs):
    return subprocess.run(["wsl.exe", "-d", "Ubuntu-26.04", "--cd", linux(PROJECT),
                           "--exec", *args], check=True, **kwargs)


def render(variant):
    folder = OUT / variant
    folder.mkdir(exist_ok=True)
    if variant == "before":
        for name, relative in (("panel.v", "display/rtl/a741_tft480_panel.v"),
                               ("bench.v", "display/tests/tft480_panel_tb.v")):
            result = subprocess.run(["wsl.exe", "-d", "Ubuntu-26.04", "--cd", linux(REPO),
                "--exec", "git", "show",
                "HEAD:code/camera-car-control/a741-fpga-fusion/" + relative],
                check=True, capture_output=True)
            (folder / name).write_bytes(result.stdout)
        panel, bench = folder / "panel.v", folder / "bench.v"
    else:
        panel = PROJECT / "display/rtl/a741_tft480_panel.v"
        bench = PROJECT / "display/tests/tft480_panel_tb.v"
    with (folder / "compile.log").open("wb") as log:
        wsl(["iverilog", "-g2012", "-s", "tft480_panel_tb", "-o", linux(folder / "panel.vvp"),
             linux(PROJECT / "rtl/a741_osd.v"), linux(panel), linux(bench)],
            stdout=log, stderr=subprocess.STDOUT)
    with (folder / "run.log").open("wb") as log:
        wsl(["vvp", linux(folder / "panel.vvp"), "+FRAME=" + linux(folder / "frame.ppm")],
            stdout=log, stderr=subprocess.STDOUT)
    return folder / "frame.ppm"


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        before, after = list(pool.map(render, ("before", "after")))
    from PIL import Image, ImageChops
    with Image.open(before) as old, Image.open(after) as new:
        if old.size != (480, 272) or new.size != (480, 272):
            raise RuntimeError("Unexpected LCD dimensions")
        if ImageChops.difference(old, new).getbbox():
            raise RuntimeError("Active LCD pixels changed")
        new.save(OUT / "screen480-simulation.png")
    record = {"active_size": [480, 272], "pixels_identical": True,
              "ppm_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                             for name, path in (("before", before), ("after", after))},
              "hardware_tested": False}
    (OUT / "FRAME-COMPARISON.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
