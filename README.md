# EdgeMind-Robot

## 现阶段可用版本：A741 130843（优先使用）

**用户于 2026-10-23 明确确认：下面的 `130843` 固件及其归档代码是现阶段能用的版本。日常联调、恢复小车运动及后续修改优先以此版本为基准，必须保留，不要被更新日期更晚的实验固件替代。**

| 内容 | 位置 |
| --- | --- |
| **当前可用固件** | `C:\Users\Administrator\Documents\EdgeMind-Robot\code\camera-car-control\a741-imu-motion\release\A741-MOTION-LD06-H20-H14-20261022-130843\A741-MOTION-LD06-H20-H14.fs` |
| **该固件对应的归档源码** | 同一 `130843` 目录中的 `rtl/`、`host/`、`config/`、`scripts/` 和 `sources/`；精确编译输入见 `source-manifest.json`、`result.json` |
| 当前维护代码 | [a741-imu-motion](code/camera-car-control/a741-imu-motion/README.md)；此工作目录包含归档后的上位机及控制更新，不等同于原始发布快照 |
| **日常上位机入口** | `C:\Users\Administrator\Documents\EdgeMind-Robot\code\camera-car-control\a741-imu-motion\launch.cmd` |
| 固件 SHA-256 | `e492146beb969e5ff97aaa2608b677f6ebab5b22354768cca6f55c5a8b15fe8e` |

本次已实读固件并核对哈希一致。“现阶段可用”为用户实车反馈，不代表所有精度、低速故障或时序问题均已解决；该归档仍记录 `timing_signed_off=false`。固件、原厂 IP 和完整 release 为本机归档，按仓库忽略规则不随本次源码提交上传。

**`a741-fpga-fusion` 仅为感知融合/导航开发验证版，不是当前可用版本，不用于替换 `130843`。** 几何未核实、时序未签核，未发布可用于运动的融合位流。旧 `101036` 是通信历史基线；A740 及下方各日期“最新”记录属于历史，不改变此处推荐。

## 2026-10-23 FPGA 感知融合实验

新增独立目录 [A741 FPGA 感知融合](code/camera-car-control/a741-fpga-fusion/README.md)：纯 RTL 的编码器/IMU 位姿融合、LD06 投影与保护、128×128 栅格、局部匹配、A* 与路径跟踪，以及地图 UDP/上位机界面。**不是已验收自动驾驶固件。** 完整车体/轮轴/雷达外参尚待核对，导航硬锁；本次综合/布线和时序状态以该目录 `verification/FUSION-RESULTS.json` 为准。保留此前确认的稳定固件 [A741-LD06 基线](code/camera-car-control/a741/release/A741-MOTION-LD06-H20-H14-20261022-101036/A741-MOTION-LD06-H20-H14.fs)，新工程不会覆盖它。

## 2026-10-22 项目交接摘要

当前摄像头/小车/LD06/MPU6500工程入口为 `code/camera-car-control/a741-imu-motion`。GUI提供分级日志、长按前进/后退/原地左右转、定距任务、摄像头、雷达和局部2D建图；地图可导出反向轨迹供后续导航模块使用。低速编码器无反馈故障 `0x0004` 仍属于待硬件确认问题，不能通过放宽保护掩盖。

## 2026-10-21 网口诊断交接

本次依据用户提供的 RTL8211F-CG Rev.1.4 手册核对 A741 网口初始化。PHY 复位保持低电平至少 10 ms，释放后等待 50 ms；初始化只读取 PHYID、BMCR、BMSR，不写未在公开手册中定义的保留位。新增 `EMP1` 独立 PHY 诊断包，记录真实 PHY ID、状态寄存器、ready/error/fault 和复位等待参数；EMS1/EML1 协议保持兼容。详细说明见 [A741 网口诊断](code/camera-car-control/a741/docs/NETWORK-DIAGNOSIS.md)。

最新运动+LD06构建位流 SHA-256 为 `03fa2b87728b7d632b58cb8aa1f45867118954d3ee3a0ccb4c22fed2c8282fc8`，本机归档目录为 `code/camera-car-control/a741/release/A741-MOTION-LD06-H20-H14-20261021-223907`。该构建已通过 25 个 RTL bench、34 项 Python 测试和动态输出审计，但 `timing_signed_off=false`，存在 setup/hold 违例，未完成实板验收。

2026-10-21 22:50 现场诊断未收到控制回复、遥测或雷达帧；Windows 以太网适配器显示 `Disconnected`、链路速率 `0 bps`。这优先指向网线/USB网卡物理链路尚未建立，而不是可以仅凭 UDP 超时判定 FPGA 控制桥故障。测试前应关闭 Wi-Fi/VPN，确认以太网链路为 Up，再 ping `192.168.0.2`，然后运行 `code/camera-car-control/a741/diagnose-control.cmd`。电机 VM 关闭期间不得 ARM 或运行运动命令。

基于 ACG720 FPGA 的自主移动机器人项目。当前底盘概念采用两台 MG513X 驱动后轮、两只前万向轮支撑的四轮结构，左右后轮差速转向。目标是先完成轮速闭环、传感器感知、视频链路与安全保护，再按需要扩展 Lichee Pi 4A 视觉计算。

## 历史入口与状态（截至2026-10-21）

以下保留当时记录；现阶段固件和代码以本文顶部明确确认的 **A741 130843** 为准。

新增 [A741 多传感器与运动控制](code/camera-car-control/a741/README.md)：独立实现IMU转角闭环、LD06扫描、DDR/HDMI与网络OSD、新上位机和回归。当前运动+LD06实验变体使用CTL H20 / DATA H14，电脑端新增局部扫描匹配的 [二维地图与导出](code/camera-car-control/a741/docs/MOTION-LIDAR-MAPPING.md)。MPU6050/MPU6500兼容采样已有用户有效数据反馈；机械轮距由用户实测234 mm。**VL53L1X未接入，无前向测距保护；板级电气及整板时序仍未签核，尚未实车建图验收。** 保留先前电机硬锁的IMU诊断包；A740交付包未覆盖。

当前入口包括A740网口摄像头/运动实验、A741多传感器/建图实验和LD06串口GUI。用户已确认LD06串口GUI在旋转90°后能正确显示移动纸板回波。A741最新运动+LD06实验包未烧录，整板时序及实物建图未验收；不能用串口雷达测试替代FPGA链路验收。A740已有运行反馈，但距离、转角、起停和通信稳定性仍待改进。

| 工程 | 用途与状态 | 入口 |
| --- | --- | --- |
| A740 摄像头与小车融合 | 800×480 RGB565、RJ45 UDP 控制；已有用户运行反馈，仍为实验版 | [使用说明](code/camera-car-control/README.md) / [固件与报告](code/camera-car-control/release/A740-20261019/README.md) |
| A723 双轮运动控制 | 串口运动、FPGA 右桥极性修正、上位机双轮同步减速；架空与落地结果分开记录 | [工程](code/fpga/acg720-motion-control/README.md) / [串口上位机](code/fpga/acg720-motion-control/host/README.md) |
| OV5640 + DDR3 + HDMI | 既有实景显示验证；不等同于 A740 网口链路 | [验证包](code/fpga/acg720-ddr3/verification/verified-20261008/README.md) |
| 视觉循线 + ToF | 逻辑与仿真工程，完整板级验收尚未完成；A740 只复用部分公共 RTL | [工程说明](code/fpga/acg720-vision-motion/README.md) |
| LD06 串口雷达 GUI | PWLINK2/USB串口230400，用户实测纸板移动回波及显示方向正常 | [操作与实测记录](code/ld06-radar-gui/README.md) |
| A741 运动 + LD06 + 2D地图 | CTL H20 / DATA H14；电脑端CoreSLAM局部建图，时序及实板未验收 | [工程与交付](code/camera-car-control/a741/README.md) / [建图指南](code/camera-car-control/a741/docs/MOTION-LIDAR-MAPPING.md) |

### LD06 串口界面

在 `code/ld06-radar-gui` 双击 `launch.cmd` 实物接收，或用 `demo.cmd` 看模拟。串口为230400 baud、8N1；程序只接收，不控制CTL/PWM。2026-10-20已确认的观察设置为旋转90°、半径0.5 m、保留0.2秒；重启需重选，COM9仅为当次设备端口。用户以20～40 cm竖直纸板确认回波随移动变化且方向正确；较矮小摆件是否穿过雷达扫描平面仍需检查。23项自动测试通过与纸板实测分开记录。

### A741 地图与交付

最新归档 `A741-MOTION-LD06-H20-H14-20261020-234354` 包含CTL H20、DATA H14及电脑端2D地图；见 [位流、哈希和构建报告](code/camera-car-control/a741/release/README.md)。21组RTL及26项Python通过；位流未烧录，整板时序有违例，尚未实车验证。H14复用USB_PA3，板载冲突待核实。VL53L1X未接入，无前向测距停车保护，LD06不自动避障。地图支持轨迹、缩放/拖动及PNG/PGM/YAML/JSON导出，不含全局回环闭合、重定位或导航。数据中断时冻结，暂停期间移动后需新建地图。

### 启动 A740 上位机

电脑有线网卡设置 `192.168.0.3/24`，网线直连 FPGA；本版要求1Gbps链路。FPGA为 `192.168.0.2`，控制UDP端口5000，电脑控制端口5001，视频端口6102。

```powershell
cd code/camera-car-control
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe host/app.py
```

后续可双击 `launch.cmd`；无硬件演示用 `demo.cmd`。选择UDP连接，使用源码上位机，旧EXE不保证支持新能力查询和标定参数。摄像头保留P7 TY-OV5640接线，完整引脚和LED定义见 [板级说明](code/camera-car-control/rtl/README.md)。

### A740 标定与已知问题

统一交接见 [当前运行状态与标定](code/camera-car-control/CURRENT-STATUS.md)。A740转向补偿经历130 → 260 → 234 mm：用户先报告90°约45°，260参数下约100°，234待复测；此处是有效补偿值，不是机械轮距。A741后来单独获得用户实测机械轮距234mm，已写入其独立配置；两字段恰好相同不代表可以混用。A740修改Python参数后重启上位机，不需要重刷固件。

直行长度和起停平顺性尚未解决。当前轮径/CPR在代码中仍有重复常量，不能单改一处视为完成标定；PI目标归零递减仍按FPGA时钟执行，没有形成预期的平滑停车。A740当前归档时序报告有3项setup、27项hold端点违例，不能称为时序闭合版。控制日志中的“串口没有匹配回复”是共享协议层文案，使用UDP时也可能出现，并不证明实际使用串口。

固件必须按SHA256区分：A740同一User Code曾重新构建，当前归档为 `98b41b4cbddf258d2759e12f10f8afd7f86c63e73e4160e6f3c778826d79eda5`。构建时未操作硬件；后续用户运行反馈另存，不能由User Code反推具体实测位流哈希。

仓库保留源码、测试、MIT网络依赖和选定交付证据；`.venv`、`.local`、工具缓存及原厂ZIP不入库。构建需要本机Gowin和原厂第47/59章依赖，详见 [构建记录](code/camera-car-control/BUILD-2026-10-19.md)。

## 历史交接（以下为各时点记录）

以下“当前”“最新”“尚未下载”等表述仅指对应历史日期，以以上当前入口及各工程最新交接为准。

后续已按用户要求实现 [A723右桥修正与同步减速](code/fpga/acg720-motion-control/release/A723-20261019/README.md)：FPGA轮速PI之后修正右桥极性，新GUI自动识别并关闭旧主机反相，增加双轮行程同步、共同减速及遥测低速稳定检查。编译/数字回归通过，尚未烧录或实车验证，物理90°精度仍待标定。

用户报告已查出此前问题、现在可以正常行驶，并确认前轮为两只万向轮、后轮双电机差速驱动。具体排除的方法尚未提供。当前仍有直行末段走弯、90°转弯不到位的问题，不能将“能够行驶”视为距离/角度精度验收通过。本轮日志兼有到目标结束、无反馈故障停车及串口拒绝访问，须分别保留。原始日志、分析及改进顺序见 [行驶验证与精度排查](code/fpga/acg720-motion-control/verification/2026-10-19/README.md)。本轮仅更新文档和保存用户日志，没有修改控制逻辑或烧录。

## 2026-10-18 视觉循线与单 ToF 集成工程

新增 [acg720-vision-motion](code/fpga/acg720-vision-motion/README.md)：纯 RTL 连续摄像头采集、双区域循线、VL53L1X 测距、减速停车、双轮控制、DDR3 双帧显示与 OSD。新固件在 PI 输出后修正右桥方向，上位机通过能力查询自动关闭旧补偿。当前交付为逻辑与仿真，完整位流受原厂视频 IP 和 ToF 引脚资料缺失限制；未下载或进行实车验收，不改变下方已确认板上状态。验证及限制见新工程说明。

## 2026-10-18 小车图形上位机已验证可用（最新状态）

用户更换驱动并恢复原接线后，已确认带右轮驱动反向补偿的图形上位机可用。支持前进/后退指定距离、原地左转/右转指定角度、预设与自定义值，以及停止/空格取消。串口为COM4（以实际设备为准），使用入口：

```bat
cd code\fpga\acg720-motion-control
python -m pip install pyserial
python host/car_control_gui.py
```

连接前默认勾选“右轮驱动反向补偿”。本次方向适配仅修改上位机，没有烧录方向修订固件；此前A720/A721/A722构建与证据见[运动工程README](code/fpga/acg720-motion-control/README.md)。主机补偿不能修正FPGA内部右轮PI反馈符号，右轮可能达到50%限幅；用户确认功能可用不等于轮速、距离/角度精度或安全保护已完成量化验收。完整步骤、参数、限制见[上位机说明](code/fpga/acg720-motion-control/host/README.md)。本轮27项Python回归和10项接线静态检查通过，无自动硬件运动测试。

以下为各日期历史交接，不能将旧A719或旧VM状态当成当前板上状态。

## 2026-10-15 电机联调交接（历史）

**当前按用户测量推定板上为 A719 静态 GPIO 诊断版，VM 已物理断开且必须保持断开。A719 无运行超时，禁止接 VM 用来试电机；没有串口控制。** 未独立回读板上配置，复电后需重新确认。

- 新接线闭环 UART、ARM/STOP 和手转编码器验证通过；数次20kHz短脉冲没有起动反馈，不构成闭环运动通过。
- 新接线A718：1kHz、最高50%、最长约1秒手动单轮。用户已测试左轮：D1按时亮/灭、D5亮，但无声音/抖动/转动，编码器活动D3不亮。
- 用户确认A18→模块LAIN1、A19→LAIN2和公共地导通；A719实测松键模块IN1/2为0/0V，S1下A18/模块IN1均3.2V，S2下A19/模块IN2均3.2V。**左静态控制链路有电平证据，但未验证PWM波形、桥OUT或电机动力通路。**
- VM在模块端实测11.2V；只有万用表。下一步核对电机动力线A/B通道、模块安装/针脚、OUT到绕组通路，先断电查线和照片，不再盲目提高输出。
- 机械参数：CPR左1469/右1471，轮径66.3mm，中心轮距121.4mm；整数协议66/66/121，复位丢参数且PI上限回1000。历史3.3V对地短路烧毁根因仍未定位。

**完整交接入口：[开环工程README最新交接段](code/fpga/acg720-motor-test/README.md#当前交接状态2026-10-15优先阅读覆盖下方历史当前板上说法)**。另见[闭环README](code/fpga/acg720-motion-control/README.md)、[原始串口证据](code/fpga/acg720-motion-control/verification/2026-10-15/README.md)、[诊断构建证据](code/fpga/acg720-motor-test/verification/2026-10-15/README.md)。以下2026-10-14进展为历史时点，固件后续已由用户刷入并参与上述测试。

## 2026-10-14 电机联调进展

- **接线修订**：维修后八根控制/反馈线的当前球号已统一到源码、接线文档及图纸；旧接线图和旧固件明确标记为历史版本。3.3 V 对地短路的烧毁根因仍未确认，不能将编译通过视为电气安全证明。
- **实板已确认**：修复 STATUS 丢字节和 Python 分包解析后，收到三次完整 35 字节 CRC 正确回复；用户手转验证两侧车身前进反馈均为正，并完成 CPR 初步测量。这不等于闭环运动通过。
- **采用机械参数**：左 CPR **1469**、右 CPR **1471** counts/输出轴圈；左右轮径 **66.3 mm**；左右轮中心距 **121.4 mm**。当前整数毫米协议使用 **66 / 66 / 121**，参数复位后丢失。
- **源码已修复并回归**：编码器启动初始化、右侧反馈方向、PI 有符号运算和条件积分、首次运动无反馈窗口、STOP/DISARM/故障取消旋转、旋转参数锁存、独立心跳，以及 CLI 异常退出尝试停车。
- **最新验证**：14 个 RTL 仿真、12 个 Python 测试、10 个接线静态测试通过；Gowin V1.9.12.04 最终 P&R Fmax **50.374 MHz**，setup/hold 违例 **0/0**，最差已报告 slack **+0.149/+0.247 ns**，裕量较小。
- **尚待验收**：截至10月14日当时最新控制修复版未下载；10月15日后续实板记录见上方最新状态；电机驱动极性、架空限幅闭环、失联/堵转/换向、旋转精度和落地运动仍需分阶段验证。STOP 为滑行，串口断开时不能保证软件 STOP 送达。

详见 [运动工程 README](code/fpga/acg720-motion-control/README.md)、[最新修复与构建记录](code/fpga/acg720-motion-control/BUILD-MOTION-SAFETY-2026-10-14.md)和[上位机协议](code/fpga/acg720-motion-control/host/README.md)。生成位流、仿真日志、虚拟环境和厂家原始资料留本地，不纳入本次提交。

## 文档与设计

- [项目功能需求书](doc/项目功能需求书.md)
- [系统设计文档](doc/文档.md)
- [电源预算与电源板架构初稿](doc/电源板/电源预算与架构初稿.md)
- [拟用电机资料核对](doc/电机/拟用电机资料核对.md)
- [FPGA 资料索引](doc/fpga/README.md)
- [代码目录](code/README.md)（含 ACG720 摄像头、DDR3 和电机工程入口与联调记录）
- [ACG720 双轮运动控制工程](code/fpga/acg720-motion-control/README.md)（编码器闭环、差速运动、定点旋转、CH340E Type-C 串口和 Python CLI；2026-10-14 已完成新接线构建、串口/手转反馈验证及控制逻辑回归；已有实板短脉冲记录，尚未起动通过）
- [OV5640 与 DDR3 帧缓存排查及实现](code/fpga/acg720-ddr3/DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md)（800×480 静态、彩条、实景单帧链路通过）
- [DDR3 实景 HDMI 固件与验证资料](code/fpga/acg720-ddr3/verification/verified-20261008/README.md)（导入位流、实景显示反馈、照片与构建报告；完整时序尚未闭合）
- [硬件机械模型与参考图](model/README.md)（电源驱动板、荔枝派、MG513X、ACX720 V2/V3；含 STEP、DWG 和离线查看器）
- [四轮底盘概念与尺寸说明](output/chassis-concept-2026-10-12/四轮版本说明.md)
- [嘉立创 EDA 电源板工程](pcb/power/power——1.eprj3)（当前现板对应资料）
- [ACG720 与现有电源板接线](doc/电机/ACG720与现有电源板接线_2026-10-14.md)

当前电源驱动板以用户正在使用的嘉立创 EDA 现板资料及 2026-10-12 导出的 STEP 为机械参考。`pcb/power/kicad/` 为历史对照设计，不用于当前现板的接口和结构布局。板卡、电机、驱动、电池以及模块的供电范围和实际电流仍须按实物复核。

仓库收录项目文档、可编辑设计文件、底盘概念图，以及用户于 2026-10-12 提供并要求收纳的硬件机械模型。模型索引与文件校验清单位于 `model/`，荔枝派的大型 STEP 使用 Git LFS 保存。其他 WHEELTEC、ACG720 等厂家随附的原始 PDF、安装包、视频与示例工程仍保留在本地；这些模型的加入不改变其余原厂资料的收录范围，原始设计文件的权利归相应提供方所有。
