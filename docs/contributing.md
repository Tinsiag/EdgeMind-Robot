# 开发与签核

## 准备环境

使用Python 3.12；已有的 `code/camera-car-control/.venv/` 可继续使用。
重新建立开发环境时运行：

```powershell
python -m venv code/camera-car-control/.venv
& code/camera-car-control/.venv/Scripts/python.exe -m pip install -r code/camera-car-control/requirements-dev.txt
```

依赖版本记录来自本机已安装环境，不要求升级4A的系统库。
4A另用自己的 `venv-system`、SHL运行库和NPU驱动，见[视频部署](../code/camera-car-control/a745-autonomous/host/README-video.md)。

本机Gowin路径为 `C:/Gowin/Gowin_V1.9.12.04_x64`。
RTL测试使用WSL发行版 `Ubuntu-26.04` 中的Icarus与Verilator。

## 检查文档和本地版本

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/check_project.py
```

预期输出JSON报告 `passed: true`。
该检查不启动EDA、访问下载器或连接4A；不会把最新硬件验收改成通过。

## 运行回归

在仓库根目录运行：

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/scripts/check.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/tests/check_protocol.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/tests/check_detection.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/tests/check_turn_geometry.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/tests/check_path_geometry.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/tests/check_lidar_replay.py code/camera-car-control/a745-autonomous/tests/fixtures/ld06-capture.json
```

仅相关文档变更且构建输入哈希未变时，无须重复整板编译或烧录。

## 构建与原语门

```powershell
$env:GOWIN_PLACE_OPTION='2'
$env:GOWIN_ROUTE_OPTION='2'
$env:GOWIN_CLOCK_ROUTE_ORDER='1'
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/scripts/build.py build --timeout 1800
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/scripts/check_cpu_gate.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/scripts/check_navigation_gate.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/scripts/check_mission_gate.py
& code/camera-car-control/.venv/Scripts/python.exe -B code/camera-car-control/a745-autonomous/scripts/check_detection_gate.py
```

独立叶模块原语执行不代表整板优化网表仿真。
所有回执必须匹配当前源码和同一主综合网表。

## 审核实现

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/check_reverse_clearance.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/inspect_implementation.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/audit_tft_sdf.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/audit_tx_sdf.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/audit_rx_sdf.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/audit_camera_input.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/audit_constraint_targets.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/audit_display_isolation.py
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/validation/final_gate.py
```

所有同次时序与接口门通过才形成候选记录。
候选签核不会更新真实实板状态；Flash与用户验收另行记录。
烧录操作见[固化说明](../scripts/fpga/README.md)。
