"""Freeze one diagnostic delivery; never overwrite an earlier release."""
from datetime import datetime
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from check import ROOT, REPO


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imu-test", action="store_true")
    parser.add_argument("--motion-lidar", action="store_true")
    args = parser.parse_args()
    if args.imu_test and args.motion_lidar:parser.error("choose one variant")
    build = ROOT / (".local/gowin-motion-lidar" if args.motion_lidar else ".local/gowin-imu-test" if args.imu_test else ".local/gowin-board")
    result = json.loads((build / "result.json").read_text(encoding="utf-8"))
    tests = json.loads((ROOT / ".local/tests/result.json").read_text(encoding="utf-8"))
    if not result["compile_passed"] or result["sources_changed"]:
        raise RuntimeError("No successful, unchanged A741 diagnostic build to archive")
    for listing in (result["source_sha256"], tests["input_sha256"]):
        for name, expected in listing.items():
            if digest(Path(name)) != expected:
                raise RuntimeError("Archive rejected; rerun build/tests after change: "+name)
    artifact = Path(result["artifact"])
    if digest(artifact) != result["artifact_sha256"]:
        raise RuntimeError("Bitstream hash changed")
    if args.imu_test and (not result.get("imu_enabled") or not result.get("motor_locked")):
        raise RuntimeError("Not an IMU-only, motor-locked build")
    if args.motion_lidar:
        audit=json.loads((ROOT / "verification/motion-lidar-output-audit.json").read_text(encoding="utf-8"))
        if not result.get("motion_lidar") or result.get("motor_locked") or audit["bitstream_sha256"]!=result["artifact_sha256"]:
            raise RuntimeError("Motion+LD06 build or audit mismatch")
    if args.imu_test:
        audit = json.loads((ROOT / "verification/imu-test-output-audit.json").read_text(encoding="utf-8"))
        if audit["bitstream_sha256"] != result["artifact_sha256"] or audit["netlist_sha256"] != result["synthesis_netlist_sha256"]:
            raise RuntimeError("Rerun audit_imu.py for this bitstream before archiving")
    prefix = "A741-MOTION-LD06-H20-H14" if args.motion_lidar else "A741-MPU6050-6500-IMU-TEST-MOTOR-LOCKED" if args.imu_test else "A741-MPU6050-DIAGNOSTIC"
    dest = ROOT / "release" / datetime.now().strftime(prefix+"-%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=False)
    source_list = {}
    for name, expected in result["source_sha256"].items():
        path = Path(name)
        relative = path.relative_to(REPO)
        # Proprietary board IP stays in the user's imported ZIP/local platform.
        # Keep its hash in the manifest, without adding that source to a Git release.
        if ".local/platform" in relative.as_posix():
            continue
        target = dest / "sources" / path.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        source_list[path.relative_to(REPO).as_posix()] = expected
    for folder in ("rtl", "host", "config", "scripts", "docs", "tests", "constraints", "verification"):
        shutil.copytree(ROOT / folder, dest / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if args.motion_lidar:
        shutil.copytree(ROOT / "third_party/coreslam", dest / "third_party/coreslam")
        shutil.copytree(ROOT / "native", dest / "native")
        (dest / ".local/mapping").mkdir(parents=True)
        shutil.copyfile(ROOT / ".local/mapping/edgemind_slam.dll", dest / ".local/mapping/edgemind_slam.dll")
        shutil.copyfile(ROOT / "requirements-mapping-build.txt", dest / "requirements-mapping-build.txt")
    shutil.copyfile(ROOT / "verification/ACCEPTANCE.md", dest / "ACCEPTANCE-PENDING.md")
    shutil.copyfile(ROOT / "verification/mpu6050-reference.json", dest / "mpu6050-reference.json")
    shutil.copyfile(ROOT / "README.md", dest / "SOURCE-README.md")
    shutil.copyfile(ROOT.parent / "third_party/verilog-ethernet/COPYING", dest / "ETHERNET-MIT-LICENSE")
    firmware_name = "A741-MOTION-LD06-H20-H14.fs" if args.motion_lidar else "A741-MPU6050-6500-IMU-TEST-MOTOR-LOCKED.fs" if args.imu_test else "A741-P4-DISABLED-DIAGNOSTIC.fs"
    shutil.copyfile(artifact, dest / firmware_name)
    for name in ("build.log", "result.json"):
        shutil.copyfile(build / name, dest / name)
    for name in ("a741.tr", "a741.tr.html", "a741_tr_cata.html", "a741_tr_content.html", "a741.pin.html", "a741.rpt.txt"):
        source = build / "impl/pnr" / name
        if source.is_file():
            shutil.copyfile(source, dest / name)
    shutil.copytree(ROOT / ".local/tests", dest / "test-results",
                    ignore=shutil.ignore_patterns("*.vvp", "*.hex"))
    platform = Path(result.get("platform_directory", ROOT / ".local/platform"))
    shutil.copyfile(platform / "provenance.json", dest / "platform-provenance.json")
    shutil.copyfile(platform / "a741.cst", dest / "a741.cst")
    shutil.copyfile(platform / "a741.sdc", dest / "a741.sdc")
    shutil.copyfile(platform / "a741_top.v", dest / "compiled-top.v")
    shutil.copyfile(ROOT / ".local/vendor/udp_checksum_gen.json", dest / "vendor-adaptation.json")
    (dest / "source-manifest.json").write_text(json.dumps(
        {"copied_sources": source_list, "all_compiler_inputs": result["source_sha256"],
         "manufacturer_ip": "Not redistributed; restore from the exact ZIP hashes in platform-provenance.json."},
        indent=2), encoding="utf-8")
    (dest / "README.md").write_text(
        ("# A741 运动+LD06+二维建图实验构建，不能用于运动验收\n\n" if args.motion_lidar else "# A741 MPU6050 诊断构建，不能用于运动验收\n\n")+
        ("运动+LD06：雷达CTL H20/DATA H14，电机硬锁解除；无ToF保护。建图在电脑运行，无自主导航。详见docs/MOTION-LIDAR-MAPPING.md。没有烧录/实车验收。\n" if args.motion_lidar else
         "仅 IMU 主 I2C 启用，支持 MPU6050/MPU6500 身份分支；电机硬件锁定，ToF/雷达禁用。测试步骤见 docs/IMU-TEST.md。没有烧录或实板测试。\n" if args.imu_test else
         "P4 物理端口禁用；尚未核实传感器硬件条件。没有烧录或实车测试。\n")+
        "timing_signed_off=false，即使位流生成也不表示时序/实板通过。\n"
        "此目录为审计快照；上位机请从仓库 code/camera-car-control/a741/launch.cmd 启动。"
        "重建时按 sources/ 内的仓库相对路径恢复，原厂 IP 按 provenance 指定 ZIP 导入。\n"
        "报告以 result.json 和 a741.tr 为准；ACCEPTANCE-PENDING.md 均待实测。\n\n"
        "详细接线、下载、上位机、标定和注意事项见 [固件使用说明](docs/FIRMWARE-GUIDE.md)。\n\n"
        "位流 SHA256: "+result["artifact_sha256"]+"\n"
        "RTL 组数: "+str(len(tests["rtl_passed"]))+"；Python 测试: "+str(tests["host_tests"])+"。\n",
        encoding="utf-8")
    checksums = {p.relative_to(dest).as_posix(): digest(p) for p in sorted(dest.rglob("*")) if p.is_file()}
    (dest / "SHA256SUMS.json").write_text(json.dumps(checksums, ensure_ascii=False, indent=2), encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
