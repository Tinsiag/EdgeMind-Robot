"""Verify that the IMU motion fork retains the exact tested network/video RTL."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/"a741/release/A741-MOTION-LD06-H20-H14-20261022-101036"
ALLOWED={"a741_motion.v","a741_protocol.v","a741_udp_control.v"}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest=json.loads((BASE/"SHA256SUMS.json").read_text(encoding="utf-8"))
    firmware=BASE/"A741-MOTION-LD06-H20-H14.fs"
    if sha(firmware)!=manifest[firmware.name]:
        raise RuntimeError("Baseline firmware hash mismatch")
    matches={}
    for p in (BASE/"rtl").glob("*.v"):
        if p.name not in ALLOWED:
            if sha(p)!=sha(ROOT/"rtl"/p.name):
                raise RuntimeError("Non-motion RTL changed: "+p.name)
            matches[p.name]=sha(p)
    if {p.name for p in (ROOT/"rtl").glob("*.v")}!={p.name for p in (BASE/"rtl").glob("*.v")}:
        raise RuntimeError("RTL file list differs from baseline")
    record={"baseline":str(BASE),"baseline_sha256":sha(firmware),
            "non_motion_rtl_sha256":matches,"allowed_motion_files":sorted(ALLOWED),
            "field_result":"User-confirmed baseline; 501/501 read-only requests, 20261022-115436; not a motion acceptance"}
    (ROOT/"verification/baseline.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print("PASS baseline firmware hash and exact non-motion RTL equality")

if __name__=="__main__":main()
