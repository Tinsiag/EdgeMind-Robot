# 摄像头与小车融合控制工程

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
