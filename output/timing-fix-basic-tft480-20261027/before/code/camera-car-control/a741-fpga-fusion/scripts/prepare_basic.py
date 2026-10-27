"""Prepare the sole camera/DDR/TFT, IMU, LD06 and debug-Ethernet board profile."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile
from check import CAMERA, ROOT, VISION, sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    if isinstance(data, str):
        data=data.encode("utf-8")
    if not path.is_file() or path.read_bytes()!=data:
        path.write_bytes(data)


def prepare(examples, screen_test=False):
    out=ROOT/(".local/platform-basic-tft480-screen-test" if screen_test else ".local/platform-basic-tft480")
    out.mkdir(parents=True,exist_ok=True)
    platform=CAMERA/".local/platform"
    if not (platform/"manifest.json").is_file():
        subprocess.run([sys.executable,str(CAMERA/"scripts/prepare_platform.py"),"--examples",str(examples)],check=True)
    archive=next(examples.glob("第38章*/*.zip"))
    chapter47=next(examples.glob("第47章*/*.zip"))
    entries=["src/ddr3_memory_interface/ddr3_memory_interface.v","src/ddr_pll/ddr_pll.v",
             "src/ddr_pll/ddr_pll_mod.v","src/pll_mDRP_intf.v"]
    files=[]; record={}
    with ZipFile(archive) as z:
        ddr_ipc=z.read("src/ddr3_memory_interface/ddr3_memory_interface.ipc")
        for name in entries:
            raw=z.read(name);dest=out/Path(name).name
            write(dest,raw);files.append(dest)
            record[name]={"original_sha256":hashlib.sha256(raw).hexdigest(),"sha256":sha(dest)}
    cst=(CAMERA/"constraints/acg720_camera_car.cst").read_text(encoding="utf-8")
    with ZipFile(chapter47) as z:
        vendor=z.read("src/ov5640_ddr3_hdmi.cst").decode("utf-8-sig")
    cst+="\n"+"\n".join(line for line in vendor.splitlines() if re.match(r'IO_(LOC|PORT) "(O_ddr_|IO_ddr_)',line))
    pins=json.loads((ROOT/"config/sensor-pins.json").read_text(encoding="utf-8"))
    imu={"scl":"L18","sda":"M20","xda":"A1","xcl":"B2","ad0":"M17","int":"B1"}
    if any(pins["mpu6050"][name]["ball"]!=ball for name,ball in imu.items()):
        raise RuntimeError("IMU wiring differs from confirmed mapping")
    screen={"tft_clk":"AB20","tft_de":"AB22","tft_hsync":"V19","tft_vsync":"Y19","tft_bl":"AB21"}
    for bit,ball in enumerate(("R18","R14","P14","U18","U17","N13","R16","P15","P17","N17","T18","L6","N15","R17","P16","N14")):
        screen[f"tft_rgb[{bit}]"]=ball
    for signal,ball in {**{"imu_"+n:b for n,b in imu.items()},"lidar_control":"H20","lidar_rx":"H14",**screen}.items():
        drive=" DRIVE=8" if signal in screen else ""
        cst+=f'\nIO_LOC "{signal}" {ball};\nIO_PORT "{signal}" IO_TYPE=LVCMOS33 PULL_MODE=NONE{drive} BANK_VCCIO=3.3;\n'
    cst+="\n"+(ROOT/"constraints/board.cst").read_text(encoding="utf-8")
    assigned={}
    for signal,balls in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);',cst):
        for ball in balls.split(","):
            if ball in assigned:
                raise ValueError(f"Pin conflict {ball}: {signal}/{assigned[ball]}")
            assigned[ball]=signal
    write(out/"a741.cst",cst)
    sdc=(CAMERA/"constraints/acg720_camera_car.sdc").read_text(encoding="utf-8")
    sdc+='\ncreate_generated_clock -name memory400m -source [get_ports {clk}] -multiply_by 8 -phase 0 -duty_cycle 50 [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}]\n'
    sdc+='create_generated_clock -name ddr_ui100m -source [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}] -master_clock memory400m -divide_by 4 [get_pins {memory/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]\n'
    sdc+=(ROOT/"constraints/cdc.sdc").read_text(encoding="utf-8")
    sdc+='\nset_max_delay 10.000 -to [get_ports {tft_clk tft_de tft_hsync tft_vsync tft_bl tft_rgb[*]}]\n'
    sdc+='set_false_path -from [get_ports {imu_sda imu_scl}] -to [get_pins {core/sensors/imu_bus/sda_sync_0_s0/D core/sensors/imu_bus/scl_sync_0_s0/D}]\n'
    sdc+='set_false_path -from [get_ports {lidar_rx}] -to [get_pins {core/sensors/lu/sync_0_s0/D}]\n'
    write(out/"a741.sdc",sdc)
    extra=list(platform.glob("original/ch59/**/*.v"))
    extra += [platform/"ov5640_init_table_rgb.v",CAMERA/"rtl/ov5640_board_init.v",CAMERA/"rtl/acg720_rgmii_rx.v",
              CAMERA.parent/"fpga/acg720-ddr3/rtl/camera_init/ov5640_ctrl.v",
              CAMERA.parent/"fpga/acg720-ddr3/rtl/camera_init/sccb_master.v"]
    extra += [VISION/n for n in ("reset_sync.v","dvp_capture_continuous.v","capture_tokens.v","async_fifo.v",
                                 "cdc_mailbox.v","ddr_framebuffer.v","video_pixels.v")]
    top=(ROOT/"rtl/a741_top.v").read_text(encoding="utf-8")
    if screen_test:
        # Literal pad assignments, independent of every controller register.
        for signal,raw in (("left_in1","raw_l1"),("left_in2","raw_l2"),("right_in1","raw_r1"),("right_in2","raw_r2")):
            old=f"assign {signal}=IMU_TEST ? 1'b0:global_n && {raw};"
            if top.count(old)!=1:
                raise RuntimeError("Motor pad hard-disable injection failed: "+signal)
            top=top.replace(old,f"assign {signal}=1'b0;")
    sys.path.insert(0,str(ROOT/"host"))
    from board_config import compiled_parameters
    values,crc=compiled_parameters(json.loads((ROOT/"config/geometry.json").read_text(encoding="utf-8")),
                                   json.loads((ROOT/"config/calibration.json").read_text(encoding="utf-8")))
    parameters="defparam core.FUSION_ENABLED=1;\n"+"".join(f"defparam core.{k}={v};\n" for k,v in values.items())
    parameters+=f"defparam core.FUSION_CONFIG_CRC=32'h{crc:08x};\n"
    write(out/"a741_top.v","`define A741_MOTION_LIDAR\n"+top.replace("endmodule",parameters+"endmodule"))
    write(out/"basic-parameters.json",json.dumps({"parameters":values,"crc32":crc},indent=2))
    write(out/"provenance.json",json.dumps({"chapter38":str(archive),"chapter38_sha256":sha(archive),
        "chapter47_sha256":sha(chapter47),"files":record,"pin_assignments":assigned,
        "ddr_ipc_sha256":hashlib.sha256(ddr_ipc).hexdigest(),"camera_size":[480,272],
        "hdmi_enabled":False,"network_video_enabled":False,"navigation_enabled":False,
        "motor_locked":screen_test,"panel":"AC620 5MHz,525x286,DE42/11; J1 unchanged"},indent=2))
    return list(dict.fromkeys([p for p in sources() if p.name!="a741_top.v"]+files+extra+[out/"a741_top.v"])),out
