# 摄像头与小车融合控制工程

## 现阶段可用：A741 130843

**2026-10-23 用户明确确认：`a741-imu-motion/release/A741-MOTION-LD06-H20-H14-20261022-130843/A741-MOTION-LD06-H20-H14.fs` 及其归档源码是现阶段能用的版本，优先使用并保留。**

固件完整位置：

```text
C:\Users\Administrator\Documents\EdgeMind-Robot\code\camera-car-control\a741-imu-motion\release\A741-MOTION-LD06-H20-H14-20261022-130843\A741-MOTION-LD06-H20-H14.fs
SHA-256: e492146beb969e5ff97aaa2608b677f6ebab5b22354768cca6f55c5a8b15fe8e
```

日常上位机使用 `C:\Users\Administrator\Documents\EdgeMind-Robot\code\camera-car-control\a741-imu-motion\launch.cmd`。当前维护代码见 [a741-imu-motion](a741-imu-motion/README.md)；精确发布源码保存在上述 `130843` 归档的 `rtl/host/config/scripts/sources`，编译清单和哈希以归档报告为准。工作源码已有后续修改，不宣称与原发布逐文件一致。

`a741-fpga-fusion` 是独立未验收开发工程，导航几何锁定、时序未签核，不能替换此可用版本。`101036` 及下面各日期记录为历史依据。“能用”为用户反馈，不表示精度、低速 `0x0004` 或时序问题全部验收通过；不覆盖原发布包。

## 2026-10-22 当前状态

推荐入口为 `a741-imu-motion`。其上位机支持摄像头、LD06、IMU、2D地图、长按手动控制、定距前进/后退、原地左右转和分级日志。短时UDP超时会记录为WARNING并保持连接。

当前已知边界：低速运动偶发 `faults=0x0004` 编码器无反馈保护；A741反馈观察窗口已延长到1000 ms，但仍需实车确认编码器线束、桥输出和负载。地图可导出反向轨迹 JSON，暂不自动执行返程路线。A741位流仍以各自release报告的时序签核状态为准，不能把软件回归通过等同于实板验收。

## 2026-10-22 稳定基线与 IMU 运动增强

用户确认 `a741/release/A741-MOTION-LD06-H20-H14-20261022-101036` 为本轮基线，`20261022-115436` 现场只读诊断501/501成功、无重试。基于其发布源码独立新增 [a741-imu-motion](a741-imu-motion/README.md)：修正直行续发命令丢失航向原点，增加弧线期望航向闭环，保留原地相对IMU角度旋转。新旧上位机、源码、固件分目录，不覆盖稳定发布包，不沿用后续PHY/网络诊断修改。运动精度及新位流通信需重新验收；下方2026-10-21说明为历史记录，不能作为当前推荐固件入口。

## 2026-10-21 最新网口交接

A741 分支已依据 RTL8211F-CG Rev.1.4 手册完成只读 PHY 身份/状态初始化：硬复位 10 ms，释放后等待 50 ms，不写公开手册未定义的保留位；新增 `EMP1` PHY 诊断包，保留 EMS1/EML1 兼容。运动+LD06位流 SHA-256 为 `03fa2b87728b7d632b58cb8aa1f45867118954d3ee3a0ccb4c22fed2c8282fc8`，本机归档位于 `a741/release/A741-MOTION-LD06-H20-H14-20261021-223907`。

22:50 现场记录显示控制、遥测、雷达均无数据，且电脑 Realtek USB GbE 网卡为 `Disconnected / 0 bps`。排查顺序是先确认网线和 RJ45 Link 灯、关闭 Wi-Fi/VPN、确认电脑 `192.168.0.3/24` 与 FPGA `192.168.0.2` 互通，再运行 `a741/diagnose-control.cmd`。电机 VM 必须保持关闭。构建虽已通过回归和 Gowin P&R，仍标记 `timing_signed_off=false`，不可视为实车验收版。

最新实验交付入口：[A741 固件与哈希索引](a741/release/README.md)。LD06独立串口GUI的[实物回波与方向确认](../ld06-radar-gui/VALIDATION.md)不经本工程网口，不等于A741实板通过。A740以下使用方法、有效轮距和LED含义仍只适用于A740。

2026-10-20 新增独立 [A741 多传感器分支](a741/README.md)，含运动、MPU6050/6500、LD06、双端视频及电脑局部二维建图。最新运动+LD06实验变体使用CTL H20 / DATA H14，支持 [地图显示和PNG/PGM/YAML/JSON导出](a741/docs/MOTION-LIDAR-MAPPING.md)；VL53L1X未接入，无前向测距保护。电气/整板时序及实车建图尚未验收；旧电机锁定IMU测试包独立保留。下文为A740入口与历史结果。

2026-10-19，在 `code` 下新增独立目录。提供中文桌面上位机、OV5640视频分包/接收协议和FPGA并行集成核心，复用引用讨论中的A723运动控制、右桥识别与同步减速。原有工程及板上配置不由本目录修改。

已使用用户提供的 ACG720 原厂第47/59章工程，接入摄像头初始化表、PLL、MDIO、RGMII 与 MAC FIFO，建立完整板级顶层和 CST/SDC。摄像头沿用此前 DDR3 验证工程的 P7 TY-OV5640 接线。用户已反馈运行成功，日志证明运动控制链路有实际运行；视频性能、精度与长期可靠性尚未验收。最新交接见 [当前运行状态与标定](CURRENT-STATUS.md)。

已生成 [A740实验固件](release/A740-20261019/README.md)，User Code `0000A740`，当前哈希以release为准。47个管脚检查、历史22项融合上位机、50项原运动上位机和5项RTL测试记录保留；PI后续修改未重跑全部RTL。当前位流时序有3项setup、27项hold端点违例，尚未签核。仅支持1Gbps链路，构建工具未自动烧录。

当前上位机转向有效轮距 **234.0 mm**，待左右90度复测；它是补偿参数，不是机械轮距。距离不足和起停不顺畅尚未解决，修改参数的位置、130→260→234的标定过程和停车斜坡缺陷见 [标定说明](CURRENT-STATUS.md)。参数修改后重启源码GUI即可。

## 连接方式

主方案是“电脑网线直连 FPGA RJ45”，摄像头和控制共用 UDP/IP；UART/TCP 只保留作旧固件或外部调试后备。

| 链路 | 上位机入口 | 设备要求 |
| --- | --- | --- |
| FPGA OV5640 → RJ45 → PC | 视频 UDP，默认6102 | `EMV1` 视频载荷和 RTL8211F/MAC/UDP 平台 |
| PC → RJ45 → FPGA | 控制 UDP，PC 5001 / FPGA 5000 | `EMC1` 封装的原运动协议；会话号、递增序号、CRC |
| PC → USB串口 → FPGA | UART，选择实际COM | 旧 A723 运动固件，115200 8N1 |
| PC → 网线串口模块 → FPGA UART | TCP，填写模块IP/端口 | 调试后备，不能代替 FPGA RJ45 控制端点 |

UDP 连接选项是直连 FPGA RJ45 的主入口；FPGA 端 `camera_ethernet_core.v` 将 `EMC1` 控制端点和 `EMV1` 视频端点复用在同一 MAC。TCP 连接选项用于外部网线转串口模块，不能代替 FPGA RJ45 控制端点。网口、UART和RJ45接口不能混为同一种电气接口。

## 使用

推荐Python3.12或更新版本，在本目录安装依赖并启动：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe host/app.py
# 无硬件预览，不打开串口或网口：
.venv/Scripts/python.exe host/app.py --demo
```

Windows可双击 `launch.cmd` 启动，双击 `demo.cmd` 查看模拟画面。`run.ps1 -Demo` 也可启动模拟模式。本机已经创建可用的 `.venv`，虚拟环境不纳入Git。

上位机包括实时画面、FPS/丢帧统计、原始帧截图、轮速/PWM/编码器/故障状态、距离前进/后退、角度左转/右转、停止及人工清故障。默认100mm/s、20cm、90°。空格或Esc可取消任务，连接不会自动使能电机。截图保存在本目录 `captures/`。模拟画面明确标记SIMULATED CAMERA，模拟轮速模型仅供界面演示，不代表真实小车性能。

1. 电脑网卡设置为静态 `192.168.0.3/24`，FPGA 默认 `192.168.0.2/24`；上位机选择 UDP、FPGA IP `192.168.0.2`、端口 `5000`。视频接收端口是 `6102`。
2. 使用现有运动固件时，选择 UART 作为临时后备；A723自动识别右桥修正，旧A722按原硬件需要设置“旧固件右轮补偿”。关闭旧上位机以释放同一个COM。
3. 使用TCP串口模块时，将模块配置为TCP服务端和原始二进制透传，填写模块IPv4与监听端口。模块不会自动承载摄像头数据。
4. 视频源和控制固件必须实现 [EMV1/EMC1协议](PROTOCOL.md)。接收程序不会自动修改网卡或防火墙设置。
5. 首次验证先静止收图，再架空检查电机方向、停车、失联、编码器与限幅，最后标定实车距离/角度。当前STOP为滑行，遥测PWM归零不等于物理瞬停。摄像头断流会标记画面过期，当前不会联动停止独立的运动任务。

原厂第59章使用另一套行号协议和不同默认分辨率，不可直接给本接收器发原厂载荷。详情及逐字节格式见 [PROTOCOL.md](PROTOCOL.md)。本目录从相邻运动/视觉工程导入公共源码，分发时需保留仓库目录结构。

## 代码与验证

| 入口 | 用途 |
| --- | --- |
| `host/app.py` | 中文Tk上位机 |
| `host/control.py` / `transport.py` | 单线程串口/TCP控制、取消与停车 |
| `host/video.py` | 有界UDP组帧、RGB565转换 |
| `host/demo.py` | 不连接硬件的模拟控制与动态图像 |
| `rtl/camera_ethernet_core.v` | OV5640/FIFO/EMV1视频与EMC1控制共享RJ45集成核心 |
| `rtl/acg720_camera_car_top.v` | ACG720 管脚、摄像头初始化、PLL、MDIO、RGMII/MAC FIFO |
| `rtl/ethernet_udp_router.v` | ARP/IPv4/UDP栈的帧路由 |
| `rtl/udp_uart_control.v` | EMC1 控制端点与内部 A723 UART 桥接 |
| `rtl/video_udp_packetizer.v` | EMV1分块、帧提交和坏帧撤销 |
| `scripts/check_fpga.py` | 输出源码依赖/核心elaboration，不生成位流 |
| `scripts/run_rtl_tests.py` | RTL仿真及RTL输出到Python解码交叉验证 |
| `scripts/prepare_platform.py` / `build_fpga.py` | 导入原厂依赖、核对哈希、Gowin 综合及布局布线 |

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -p 'test_*.py' -v
.venv/Scripts/python.exe -X utf8 -B scripts/check_fpga.py
.venv/Scripts/python.exe -X utf8 -B scripts/run_rtl_tests.py
```

Icarus需在PATH，或传 `--iverilog <路径>` / `--vvp <路径>`；本仓库本机工具在 `tmp/vision-motion-tools/bin/` 时自动使用。生成物在 `.local/`，不代表板级时序闭合或实机验收。验证记录见 [VALIDATION.md](VALIDATION.md)。
