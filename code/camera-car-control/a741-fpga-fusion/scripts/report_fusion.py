"""Archive fusion source/test/tool evidence; never publish an unsigned motion image."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from check import ROOT,REPO


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unchanged(listing):
    return all(Path(p).is_file() and sha(Path(p))==h for p,h in listing.items())


def main():
    build=ROOT/".local/gowin-fusion"
    result=json.loads((build/"result.json").read_text(encoding="utf-8"))
    tests=json.loads((ROOT/".local/tests/result.json").read_text(encoding="utf-8"))
    geometry=json.loads((ROOT/"config/geometry.json").read_text(encoding="utf-8"))
    current=unchanged(result["source_sha256"])
    test_current=unchanged(tests["input_sha256"])
    if not current or not test_current:
        raise RuntimeError("Evidence does not match current inputs; rerun build/regression")
    xml=build/"impl/gwsynthesis/a741_syn_rsc.xml"
    resources={}
    ram={}
    if xml.is_file():
        root=ET.parse(xml).getroot();resources=dict(root.attrib)
        ram={e.attrib["name"]:e.attrib["T_Bsram"] for e in root.iter() if "T_Bsram" in e.attrib}
    cst=Path(result["platform_directory"])/"a741.cst"
    pins={};conflicts=[]
    for signal,balls in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);',cst.read_text(encoding="utf-8")):
        for ball in balls.split(","):
            if ball in pins:conflicts.append([ball,pins[ball],signal])
            pins[ball]=signal
    baseline=ROOT.parent/"a741/release/A741-MOTION-LD06-H20-H14-20261022-101036/A741-MOTION-LD06-H20-H14.fs"
    baseline_expected="fa9e1cd508b1f2b9e47884200fece220d6c7ea040f27a99cbaca8e13bb3491f9"
    baseline_ok=baseline.is_file() and sha(baseline)==baseline_expected
    signed=result.get("timing_signed_off") is True
    clear=all(result.get("timing_violations",{}).get(k)==0 for k in ("setup","hold","recovery","removal"))
    allowed=bool(result.get("compile_passed") and signed and clear and result.get("motion_release_allowed") is True
                 and geometry.get("navigation_geometry_verified") is True and not conflicts and baseline_ok)
    record={"schema":1,"generated_local":datetime.now().isoformat(),"compile_passed":result["compile_passed"],
            "current_build_inputs_match":current,"current_test_inputs_match":test_current,
            "rtl_benches_passed":len(tests["rtl_passed"]),"host_tests_passed":tests["host_tests"],
            "timing_signed_off":signed,"timing_violations":result.get("timing_violations",{}),
            "worst_slack_ns":result.get("worst_reported_slack_ns",{}),
            "minimum_pulse_width_worst_slack_ns":result.get("minimum_pulse_width_worst_slack_ns"),
            "geometry_verified":geometry.get("navigation_geometry_verified") is True,
            "motion_firmware_published":allowed,"hardware_programmed":False,"hardware_tested":False,
            "recorded_full_sensor_replay_completed":False,"pin_conflicts":conflicts,"pin_assignments":pins,
            "resources":resources,"ram_by_hierarchy":ram,"stable_baseline_unchanged":baseline_ok,
            "baseline_sha256":sha(baseline) if baseline.is_file() else None,
            "build_result_sha256":sha(build/"result.json"),"test_result_sha256":sha(ROOT/".local/tests/result.json"),
            "limitations":["Unverified full vehicle/axle/lidar geometry; navigation locked",
                "Unverified I/O budgets, board electrical conditions and full timing sign-off",
                "Locked build can prune tracking datapath; unlocked resource/timing require a fresh build",
                "No complete recorded sensor replay or board/vehicle acceptance"]}
    if result.get("artifact"):
        record["internal_tool_artifact_sha256"]=result["artifact_sha256"]
    verification=ROOT/"verification"
    (verification/"FUSION-RESULTS.json").write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# A741 FPGA 融合构建与验证报告","",f"生成时间：{record['generated_local']}","",
        f"完整工具流程：{'通过' if record['compile_passed'] else '未通过'}；时序签核：{'通过' if signed else '未通过'}；运动位流发布：{'允许' if allowed else '禁止'}。",
        f"RTL 测试台 {record['rtl_benches_passed']} 组，主机测试 {record['host_tests_passed']} 项；输入哈希一致。",
        f"时序违例端点：`{record['timing_violations']}`；最差裕量 ns：`{record['worst_slack_ns']}`。",
        f"最小脉宽最差裕量 ns：`{record['minimum_pulse_width_worst_slack_ns']}`。",
        f"资源（综合器原始字段）：`{json.dumps(resources,ensure_ascii=False)}`。",
        f"管脚重复分配：{len(conflicts)}；稳定基线 SHA-256 一致：{baseline_ok}。","",
        "几何未核实，导航硬锁；本次未烧录、未驱动电机、未做实板/实车验收。",
        "仿真包含合成输入与完整以太网栈，但没有完整同源录制传感器回放，不作为实车导航证据。",
        "锁定构建可能裁剪跟踪数据路径，资源余量不能用于宣称解锁后的导航已经适配。",
        "所有时序/I/O/CDC 和硬件条件通过前，不提供本版可刷写运动文件。","",
        "详细 RAM、引脚、哈希与限制见 FUSION-RESULTS.json；验收次序见 FUSION-ACCEPTANCE.md。"]
    (verification/"FUSION-REPORT.md").write_text("\n\n".join(lines)+"\n",encoding="utf-8")
    dest=ROOT/"release"/datetime.now().strftime("A741-FPGA-FUSION-EVIDENCE-%Y%m%d-%H%M%S")
    dest.mkdir(parents=True,exist_ok=False)
    for folder in ("rtl","host","config","scripts","constraints","docs","tests","verification"):
        shutil.copytree(ROOT/folder,dest/folder,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copyfile(ROOT/"README.md",dest/"README.md")
    reports=dest/"reports";reports.mkdir()
    for name in ("result.json","build.log","a741.gprj","build.tcl"):
        if (build/name).is_file():shutil.copyfile(build/name,reports/name)
    for p in (build/"impl/pnr").glob("*"):
        if p.is_file() and p.suffix in (".tr",".html",".txt",".log"):
            shutil.copyfile(p,reports/p.name)
    if xml.is_file():shutil.copyfile(xml,reports/xml.name)
    for name in ("a741.cst","a741.sdc","provenance.json","fusion-parameters.json"):
        p=Path(result["platform_directory"])/name
        if p.is_file():shutil.copyfile(p,reports/name)
    shutil.copytree(ROOT/".local/tests",dest/"test-results",ignore=shutil.ignore_patterns("*.vvp","*.hex"))
    if allowed:
        artifact=Path(result["artifact"])
        if sha(artifact)!=result["artifact_sha256"]:raise RuntimeError("Bitstream hash mismatch")
        shutil.copyfile(artifact,dest/"A741-FPGA-FUSION.fs")
    else:
        (dest/"NO-MOTION-FIRMWARE.txt").write_text("No motion firmware published: geometry/timing/board acceptance is incomplete.\n",encoding="ascii")
    manifest={p.relative_to(dest).as_posix():sha(p) for p in sorted(dest.rglob("*")) if p.is_file()}
    (dest/"SHA256SUMS.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"report":str(verification/"FUSION-REPORT.md"),"evidence":str(dest),"motion_firmware_published":allowed},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
