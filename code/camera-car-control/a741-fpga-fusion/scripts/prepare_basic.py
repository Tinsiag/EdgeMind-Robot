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


def prepare(examples, screen_test=False, display_diagnostic=False, unlock_motor_pads=False,
            sequence_test=False, button_autonomous=False):
    if display_diagnostic and unlock_motor_pads:
        raise ValueError("Display diagnostic cannot be combined with unlocked motor pads")
    if sequence_test and button_autonomous:
        raise ValueError("Sequence test and button autonomous are separate variants")
    suffix = "-sequence-test" if sequence_test else "-button-autonomous" if button_autonomous else ""
    out=ROOT/(".local/platform-basic-tft800-screen-test" if screen_test else ".local/platform-basic-tft800"+suffix)
    if display_diagnostic:
        out=out.with_name(out.name+"-diagnostic")
    out.mkdir(parents=True,exist_ok=True)
    platform=CAMERA/".local/platform"
    if not (platform/"manifest.json").is_file():
        subprocess.run([sys.executable,str(CAMERA/"scripts/prepare_platform.py"),"--examples",str(examples)],check=True)
    archive=next(examples.glob("第38章*/*.zip"))
    chapter47=next(examples.glob("第47章*"))
    chapter47_cst=chapter47/"src/ov5640_ddr3_hdmi.cst"
    entries=["src/ddr3_memory_interface/ddr3_memory_interface.v","src/ddr_pll/ddr_pll.v",
             "src/ddr_pll/ddr_pll_mod.v","src/pll_mDRP_intf.v"]
    files=[]; record={}
    # Preferred board-specific chapter28 example; preserve all PLL parameters
    # and its startup sequence. Rename modules only to avoid ch59 collisions.
    chapter28=next(examples.glob("第28章*"))
    display_pll_record={}
    for name in ("gowin_pll/gowin_pll.v","gowin_pll/gowin_pll_mod.v","pll_init.v"):
        src=chapter28/"src"/name
        raw=src.read_bytes()
        pll=raw.decode("utf-8-sig")
        for old,new in (("Gowin_PLL_MOD","A741_TFT_PLL_MOD"),("Gowin_PLL","A741_TFT_PLL"),("PLL_INIT","A741_TFT_PLL_INIT")):
            pll=re.sub(r"\b"+old+r"\b",new,pll)
        dest=out/("tft_"+Path(name).name)
        write(dest,pll);files.append(dest)
        display_pll_record[str(src)]={"original_sha256":sha(src),"prepared_sha256":sha(dest)}
    with ZipFile(archive) as z:
        ddr_ipc=z.read("src/ddr3_memory_interface/ddr3_memory_interface.ipc")
        for name in entries:
            raw=z.read(name);dest=out/Path(name).name
            write(dest,raw);files.append(dest)
            record[name]={"original_sha256":hashlib.sha256(raw).hexdigest(),"sha256":sha(dest)}
    cst=(CAMERA/"constraints/acg720_camera_car.cst").read_text(encoding="utf-8")
    # During FPGA Reprogram the camera-reset PAD is briefly high impedance.
    # Hold it low with the I/O keeper so a powered OV5640 cannot continue its
    # old frame stream while the FPGA is being configured.
    cst=re.sub(r'IO_PORT "camera_reset_n" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=4;',
               'IO_PORT "camera_reset_n" IO_TYPE=LVCMOS33 PULL_MODE=DOWN DRIVE=4;', cst)
    if chapter47_cst.is_file():
        vendor=chapter47_cst.read_text(encoding="utf-8-sig")
        chapter47_source=chapter47_cst
    else:
        chapter47_source=next(chapter47.glob("*.zip"))
        with ZipFile(chapter47_source) as z:
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
        # All TFT pads are low-safe while the panel remains powered and the
        # FPGA is unconfigured.  This prevents floating PCLK/DE/HS/VS/RGB/BL
        # edges during a live Reprogram.  Other board I/O retains its prior
        # pull configuration.
        pull="DOWN" if signal in screen else "NONE"
        cst+=f'\nIO_LOC "{signal}" {ball};\nIO_PORT "{signal}" IO_TYPE=LVCMOS33 PULL_MODE={pull}{drive} BANK_VCCIO=3.3;\n'
    cst+="\n"+(ROOT/"constraints/board.cst").read_text(encoding="utf-8")
    cst+='\nIO_LOC "s1_n" A20;\nIO_PORT "s1_n" IO_TYPE=LVCMOS33 PULL_MODE=UP;\n'
    assigned={}
    for signal,balls in re.findall(r'IO_LOC "([^"]+)" ([A-Z0-9,]+);',cst):
        for ball in balls.split(","):
            if ball in assigned:
                raise ValueError(f"Pin conflict {ball}: {signal}/{assigned[ball]}")
            assigned[ball]=signal
    write(out/"a741.cst",cst)
    sdc=(CAMERA/"constraints/acg720_camera_car.sdc").read_text(encoding="utf-8")
    # The base camera project retains its historical provisional PHY budgets.
    # This profile explicitly programs and verifies the integrated delays.
    sdc="\n".join(line for line in sdc.splitlines() if not line.startswith("set_input_delay -clock rgmii_rx_clk"))+"\n"
    sdc+='create_generated_clock -name tx250m -source [get_ports {clk}] -multiply_by 5 [get_pins {clocks/u_pll/PLLA_inst/CLKOUT1}]\n'
    sdc+='create_generated_clock -name tx125m -source [get_pins {clocks/u_pll/PLLA_inst/CLKOUT1}] -master_clock tx250m -divide_by 2 [get_pins {tx_divider/CLKOUT}]\n'
    sdc+='create_generated_clock -name display33m -source [get_ports {clk}] -multiply_by 33 -divide_by 50 [get_pins {display_clocks/u_pll/PLLA_inst/CLKOUT0}]\n'
    sdc+='\ncreate_generated_clock -name memory400m -source [get_ports {clk}] -multiply_by 8 -phase 0 -duty_cycle 50 [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}]\n'
    sdc+='create_generated_clock -name ddr_ui100m -source [get_pins {memory_pll/u_pll/PLLA_inst/CLKOUT2}] -master_clock memory400m -divide_by 4 [get_pins {memory/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]\n'
    sdc+=(ROOT/"constraints/cdc.sdc").read_text(encoding="utf-8")
    sdc+='\n# Display mailboxes hold payload through synchronized req/ack; bound only crossing paths.\n'
    sdc+='set_max_delay 10 -to [get_pins {display_cdc/*/req_sync_0_s0/D display_cdc/*/ack_sync_0_s0/D}]\n'
    sdc+='set_false_path -hold -to [get_pins {display_cdc/*/req_sync_0_s0/D display_cdc/*/ack_sync_0_s0/D}]\n'
    sdc+='set_max_delay 20 -from [get_pins {display_cdc/*/held*/Q}] -to [get_pins {display_cdc/*/dst_data*/D}]\n'
    sdc+='set_false_path -hold -from [get_pins {display_cdc/*/held*/Q}] -to [get_pins {display_cdc/*/dst_data*/D}]\n'
    sdc+="\n"+(ROOT/"constraints/ddr_control.sdc").read_text(encoding="utf-8")
    sdc+="\n"+(ROOT/"constraints/ethernet.sdc").read_text(encoding="utf-8")
    sdc+='\nset_max_delay 10.000 -to [get_ports {tft_clk tft_de tft_hsync tft_vsync tft_bl tft_rgb[*]}]\n'
    sdc+='set_false_path -from [get_ports {imu_sda imu_scl}] -to [get_pins {core/sensors/imu_bus/sda_sync_0_s0/D core/sensors/imu_bus/scl_sync_0_s0/D}]\n'
    sdc+='set_false_path -from [get_ports {lidar_rx}] -to [get_pins {core/sensors/lu/sync_0_s0/D}]\n'
    write(out/"a741.sdc",sdc)
    extra=list(platform.glob("original/ch59/**/*.v"))
    # Keep the DDR PLL and every vendor source untouched. Only the Ethernet
    # PLL output divider changes from 6 to 3: 750 MHz VCO ->250 MHz ->CLKDIV/2.
    ethernet_pll=platform/"original/ch59/src/gowin_pll/gowin_pll_mod.v"
    pll_text=ethernet_pll.read_text(encoding="utf-8")
    if pll_text.count("ODIV1_SEL = 6;")!=1:
        raise RuntimeError("Unexpected Ethernet PLL parameters")
    prepared_pll=out/"ethernet_pll_mod.v"
    write(prepared_pll,pll_text.replace("ODIV1_SEL = 6;","ODIV1_SEL = 3;"))
    extra=[p for p in extra if p!=ethernet_pll]+[prepared_pll]
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
            if top.count(old)==1:
                top=top.replace(old,f"assign {signal}=1'b0;")
            elif f"assign {signal}=1'b0;" not in top:
                raise RuntimeError("Motor pad hard-disable injection failed: "+signal)
    sys.path.insert(0,str(ROOT/"host"))
    from board_config import compiled_parameters
    values,crc=compiled_parameters(json.loads((ROOT/"config/geometry.json").read_text(encoding="utf-8")),
                                   json.loads((ROOT/"config/calibration.json").read_text(encoding="utf-8")))
    parameters="defparam core.FUSION_ENABLED=1;\n"+"".join(f"defparam core.{k}={v};\n" for k,v in values.items())
    parameters+=f"defparam core.SEQUENCE_TEST={int(sequence_test)};\n"
    parameters+=f"defparam core.BUTTON_AUTONOMOUS={int(button_autonomous)};\n"
    parameters+=f"defparam core.FUSION_CONFIG_CRC=32'h{crc:08x};\n"
    defines="`define A741_MOTION_LIDAR\n"
    if unlock_motor_pads and not screen_test:
        defines += "`define A741_MOTOR_PADS_UNLOCKED\n"
    if display_diagnostic:
        defines += "`define A741_DISPLAY_DIAGNOSTIC\n"
    if button_autonomous:
        defines += "`define A741_BUTTON_AUTONOMOUS\n"
    write(out/"a741_top.v",defines+top.replace("endmodule",parameters+"endmodule"))
    write(out/"basic-parameters.json",json.dumps({"parameters":values,"crc32":crc},indent=2))
    write(out/"provenance.json",json.dumps({"chapter38":str(archive),"chapter38_sha256":sha(archive),
        "chapter47_source":str(chapter47_source),"chapter47_sha256":sha(chapter47_source),"files":record,"pin_assignments":assigned,
        "ddr_ipc_sha256":hashlib.sha256(ddr_ipc).hexdigest(),
        "ethernet_pll":{"original_sha256":sha(ethernet_pll),"prepared_sha256":sha(prepared_pll),"change":"ODIV1_SEL 6->3; 250MHz feeds CLKDIV/2 for 125MHz MAC"},
        "camera_size":[800,480],"display_pll":display_pll_record,
        "hdmi_enabled":False,"network_video_enabled":False,"navigation_enabled":False,
        "motor_locked":(screen_test or not unlock_motor_pads),"motor_pads_unlocked":(unlock_motor_pads and not screen_test),"display_diagnostic":display_diagnostic,
        "sequence_test":sequence_test,"button_autonomous":button_autonomous,
        "panel":"ACG720 ch28/TFT V3:33MHz,1056x525,800x480; rising-edge sample, half-cycle data setup; J1 unchanged"},indent=2))
    return list(dict.fromkeys([p for p in sources() if p.name!="a741_top.v"]+files+extra+[out/"a741_top.v"])),out
