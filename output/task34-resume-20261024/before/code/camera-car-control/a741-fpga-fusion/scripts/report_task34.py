"""Record current task 3/4 evidence without publishing or programming firmware."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from check import ROOT, REPO, VISION, rtl_benches


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_inputs(values):
    return all(Path(p).is_file() and sha(Path(p))==h for p,h in values.items())


def main():
    build=ROOT/".local/gowin-fusion-tft480"
    result=json.loads((build/"result.json").read_text(encoding="utf-8"))
    if result.get("run_state")=="running":
        raise RuntimeError("Build has no final result yet; running/stale state cannot become acceptance evidence")
    tests=json.loads((ROOT/".local/tests/result.json").read_text(encoding="utf-8"))
    if not same_inputs(result["source_sha256"]) or not same_inputs(tests["input_sha256"]):
        raise RuntimeError("Current build/regression evidence must match all saved inputs")
    benches={p.stem for p in rtl_benches()}
    if benches!=set(tests["rtl_passed"]):
        raise RuntimeError("Regression does not cover all current RTL benches")
    geometry=json.loads((ROOT/"config/geometry.json").read_text(encoding="utf-8"))
    pins={};conflicts=[]
    for signal,balls in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);',(Path(result["platform_directory"])/"a741.cst").read_text(encoding="utf-8")):
        for ball in balls.split(","):
            if ball in pins:conflicts.append([ball,pins[ball],signal])
            pins[ball]=signal
    resources_path=build/"impl/gwsynthesis/a741_syn_rsc.xml"
    resources=ET.parse(resources_path).getroot().attrib if resources_path.is_file() else {}
    camera=[]
    for rel in ("rtl/a741_video.v","rtl/a741_hdmi.v","../constraints/acg720_camera_car.cst",
                "../rtl/ov5640_board_init.v","../rtl/video_udp_packetizer.v"):
        path=(ROOT/rel).resolve();repo_rel=path.relative_to(REPO).as_posix()
        original=subprocess.check_output(["git","show","HEAD:"+repo_rel],cwd=REPO)
        camera.append({"path":repo_rel,"sha256":sha(path),
                       "unchanged_text_from_HEAD":original.replace(b"\r\n",b"\n")==path.read_bytes().replace(b"\r\n",b"\n")})
    full_flow=result.get("mode") in ("build","pnr") and result["compile_passed"]
    record={"schema":1,"generated_local":datetime.now().astimezone().isoformat(),
        "variant":result["variant"],"compile_passed":bool(full_flow),
        "build_mode":result.get("mode"),"stage_compile_passed":result["compile_passed"],
        "synthesis_timing":result.get("synthesis_timing",{}),
        "build_timed_out":result.get("timed_out",False),"build_seconds":result["seconds"],
        "build_state":result.get("run_state"),"route_option":result.get("route_option"),"place_option":result.get("place_option"),
        "current_build_inputs_match":True,"current_test_inputs_match":True,
        "rtl_benches_passed":len(tests["rtl_passed"]),"rtl_benches":tests["rtl_passed"],
        "host_tests_passed":tests["host_tests"],"rtl_backend":tests.get("rtl_backend"),
        "rtl_backend_per_bench":tests.get("rtl_backend_per_bench",{}),
        "timing_signed_off":result.get("timing_signed_off",False),
        "timing_violations":result.get("timing_violations",{}),
        "worst_slack_ns":result.get("worst_reported_slack_ns",{}),
        "minimum_pulse_width_worst_slack_ns":result.get("minimum_pulse_width_worst_slack_ns"),
        "clock_frequencies":result.get("clock_frequencies",{}),
        "geometry_verified_from_cad":geometry.get("navigation_geometry_verified") is True,
        "physical_geometry_verified":geometry.get("physical_geometry_verified") is True,
        "geometry":geometry["cad_navigation_audit"],"resources":resources,
        "pin_conflicts":conflicts,"pin_assignments":pins,"preserved_camera_paths":camera,
        "camera_counter_timing_changes":[{"path":str(VISION/name),"sha256":sha(VISION/name)}
            for name in ("dvp_capture_continuous.v","ddr_framebuffer.v")],
        "firmware":json.loads((ROOT/"firmware/manifest.json").read_text(encoding="utf-8")),
        "hardware_programmed":False,"cold_boot_verified":False,"hardware_tested":False,
        "physical_tft_verified":False,"recorded_sensor_replay_completed":False,
        "motion_firmware_published":False,
        "stable_baseline":{"name":"A741-MOTION-LD06-H20-H14-20261022-130843",
            "expected_sha256":"e492146beb969e5ff97aaa2608b677f6ebab5b22354768cca6f55c5a8b15fe8e",
            "original_archive_available":False,"rebuilt_as_original":False},
        "evidence_sha256":{"build_result":sha(build/"result.json"),"test_result":sha(ROOT/".local/tests/result.json"),
            "build_log":sha(build/"build.log"),"test_log":sha(ROOT/".local/tests/wsl-regression.log")},
        "limitations":["Synthetic room and nearby waypoint fixture are not physical navigation validation",
            "Full board timing, I/O budgets, DDR dynamic phase and physical sensor latency require sign-off",
            "CAD geometry is audited; vehicle geometry and stopping distance have not been measured",
            "Runtime map/calibration/waypoints are not persisted by FPGA configuration Flash",
            "No vehicle motion or Flash operation was performed"]}
    for key in ("artifact","artifact_sha256","timing_report_sha256","synthesis_netlist_sha256"):
        if key in result:record[key]=result[key]
    (ROOT/"verification/TASK3-4-RESULTS.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# 任务3/4与RGB屏验证结果",f"记录时间：{record['generated_local']}",
        f"RTL {record['rtl_benches_passed']}组、Python {record['host_tests_passed']}项通过；后端 `{record['rtl_backend']}`；当前输入哈希一致。",
        f"本轮模式`{record['build_mode']}`；完整工具流程：{'通过' if record['compile_passed'] else '尚未完成'}，阶段耗时{record['build_seconds']:.1f}秒；时序尚未签核；未发布运动固件。",
        f"时序违例：`{record['timing_violations']}`；最差裕量ns：`{record['worst_slack_ns']}`；最小脉宽最差裕量ns：`{record['minimum_pulse_width_worst_slack_ns']}`。",
        "已实现LD06净空检测、减速/停车、停车重规划、栅格A*、位姿/局部匹配、起终点与最多16个航点。PicoRV32运行RV32I裸机程序，外部计算机仅设置和观察任务。",
        "联动仿真覆盖实际软核、核心仲裁、合成房间定位、A*及跟踪器的三个邻近航点，并验证过期外部TTL及任务执行时拒绝改图。单独避障仿真覆盖障碍暂停、重规划和恢复。它们均不代表实车已跑通。",
        "修复了压缩路径负方向的符号扩展，以及上一段到达状态取消下一段的问题；增加反向路径和实际软核导航联动回归。",
        "保留原OV5640、DDR3、HDMI、网口视频与原接线；新增J1/FPC 4.3寸RGB参数页。画面如下，使用仿真数值，非实物照片。",
        "视频内部计数器按跳帧数及图像像素/数据块范围缩窄，超长采集帧的计数饱和为无效值；视频功能和接口保留。回归同时覆盖原DDR背压、坏帧丢弃和双缓冲保护夹具。",
        "![RGB参数页仿真](tft480-simulation.png)",
        "CAD推导前/后/半宽为221/70/131mm，旋转半径257mm，雷达前偏164mm。运动学继续采用用户实测234mm轮距；实车外廓与精确扫描高度未验收。",
        f"管脚冲突{len(conflicts)}项；综合器资源原始字段：`{json.dumps(resources,ensure_ascii=False)}`。",
        "未烧录、未ARM、未驱动电机，未验证屏幕实物或真正断电重启。原130843归档在本机缺失，未覆盖或重新冒称原基线。",
        "固化入口为仓库scripts/fpga/program_flash.py。交付条件通过并关闭电机VM后，显式指定完整位流和SHA，执行外部Flash操作54、校验、Reprogram和状态读取，再实际断电验证。地图/标定/任务仍需按运行时机制恢复。",
        "详细源文件身份、测试清单、几何、管脚和工具证据见TASK3-4-RESULTS.json；实现和使用方式见../docs/TASK3-4.md。"]
    (ROOT/"verification/TASK3-4-REPORT.md").write_text("\n\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"rtl":record["rtl_benches_passed"],"python":record["host_tests_passed"],
                      "compile":record["compile_passed"],"hardware_programmed":False},ensure_ascii=False))


if __name__=="__main__":main()
