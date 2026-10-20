# 代码目录

- [LD06 激光雷达 GUI](ld06-radar-gui/README.md)：白色中文桌面界面，PWLINK2/USB串口230400只读接收，支持轮廓、四向距离、自动量程、旋转、暂停及CSV。用户确认旋转90°、0.5 m、保留0.2 s时纸板回波及方向正确；23项自动测试通过。启动 `ld06-radar-gui/launch.cmd`，模拟预览 `demo.cmd`。

- [A741 FPGA + LD06 + 2D地图](camera-car-control/a741/README.md)：CTL H20 / DATA H14，经FPGA网口传送完整扫描和里程遥测，PC本地匹配建图及导出。21组RTL/26项Python通过，最新位流未烧录且时序未签核。串口GUI实测不能代替本分支验收；H14板载复用待核实，无ToF前向停车保护。[交付索引](camera-car-control/a741/release/README.md)。

## 当前主线

新增 [A741运动+LD06实验分支](camera-car-control/a741/README.md)：CTL H20 / DATA H14，通过FPGA网口传输雷达扫描和里程遥测，电脑提供局部二维建图、轨迹、缩放/拖动及地图导出。详见 [建图操作说明](camera-car-control/a741/docs/MOTION-LIDAR-MAPPING.md)。整板时序与实车地图尚未验收，无ToF前向保护，不包含导航或全局闭环。

优先使用 [A740 摄像头与小车网口融合](camera-car-control/README.md)：电脑RJ45直连，UDP控制与视频共线。用户已反馈运行成功；距离/转角精度、起停和通信稳定性仍待完善。当前有效轮距234 mm是待复测的转向补偿，见 [当前状态与标定](camera-car-control/CURRENT-STATUS.md)。A723保留为串口运动工程；其架空结果不能替代落地验收。

以下保留各子工程及历史交接，最新状态以上述入口为准。

- [摄像头循线与 ToF 停车集成](fpga/acg720-vision-motion/README.md)：2026-10-18 新增纯 RTL 工程、模块与端到端仿真、能力协商及感知调试界面。当前无完整板级位流，原厂视频 IP 与 ToF 引脚未补齐；构建检查会明确拦截，未进行硬件操作。
- [摄像头与小车融合控制](camera-car-control/README.md)：电脑网线直连FPGA RJ45，OV5640 EMV1视频和EMC1控制共用网口，复用A723。已结合原厂第47/59章生成A740板级实验位流，并有用户运行反馈；时序和精度尚未验收。包含中文上位机、模拟模式、历史测试证据及完整构建记录。

> **2026-10-18 最新交接**：更换驱动后，用户已验证带右轮驱动反向补偿的[图形上位机](fpga/acg720-motion-control/host/README.md)可用。运行 `python host/car_control_gui.py`（在motion-control目录），支持前后距离、左右转角、预设/自定义及停止。27项Python和10项接线静态检查通过。方向补偿仅主机侧，仍有固件右轮PI反馈符号限制，未量化距离/角度精度。以下A719等描述保留历史时点。

> **2026-10-15 电机交接**：按用户反馈当前板上为A719静态GPIO版，**VM必须物理断开**，无电机超时/串口控制；静态IN电平0/3.2V已由用户测得，A718新接线起动仍未通过。最新结果、参数、固件哈希和下一步以[电机工程交接README](fpga/acg720-motor-test/README.md)为准，不直接使用旧接线位流。


> 2026-10-14：两套电机工程已更新维修后信号球号，见 [当前接线](../doc/电机/ACG720与现有电源板接线_2026-10-14.md)。旧下载、时序与实物证据只适用于旧接线；新接线闭环已重新构建，实板电气检查仍须独立确认，3.3 V 短路根因未确认。

- [ACG720 / AT8236 电机控制](fpga/acg720-motor-test/README.md)：A712 启动和编码器活动、A713 左右持续启停已实测通过；历史 A717 为 50 kHz，占空比从 0% 到 100% 每 0.5 秒增加 5% 后循环，已下载，实物表现待反馈。S1/S2 独立启停，S0 停止，仅操作 SRAM。
- [电机启动排查与实现文档](fpga/acg720-motor-test/MOTOR-IMPLEMENTATION-2026-10-10.md)：接线、电源、三个 PWM 对照版本、通过证据及复现方法；尚未实现速度 PID 或与摄像头合并。
- [ACG720 双轮差速运动控制](fpga/acg720-motion-control/README.md)：GW5AT-60B RTL、AT8236 PWM、编码器反馈、CH340E UART、CLI与图形上位机。2026-10-18用户确认主机右轮反向补偿后可用；A721已有左轮起动遥测，A722构建资料及功能边界保留。支持自定义距离/转角，实车精度和完整闭环保护仍待验收。
- [ACG720 GW5AT-60 DDR3 验证工程](fpga/acg720-ddr3/README.md)：原有 800×480 静态、彩条、实景单帧验证均通过。另已合入 [实景 HDMI 交付包](fpga/acg720-ddr3/verification/verified-20261008/README.md)，包含位流、实物反馈与完整验证资料；有图像显示反馈，时序尚未闭合，包内未提供完整 RTL。许可证已解决。
- [DDR3 帧缓存排查与实现文档](fpga/acg720-ddr3/DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md)：旧诊断缺陷、时钟与缓存实现、摄像头配置、仿真/实板证据、复现步骤和断电保存边界。

原厂配套源码、加密 IP 和位流保留在工程的 `.local/` 中，不直接并入公开仓库。我们编写的说明和构建入口纳入版本管理。
