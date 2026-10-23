# A741 Fusion 验证记录

本文件其余内容为创建工程时继承的历史记录，不能代表最终融合版本。当前结论以 [融合构建报告](FUSION-REPORT.md)、[机器记录](FUSION-RESULTS.json) 与 [实板验收表](FUSION-ACCEPTANCE.md) 为准。几何未核实时导航保持硬锁，时序未签核不发布运动位流。

## FPGA 融合增量（2026-10-22）

独立新增 `a741_pose_fusion`、`a741_grid_map`、`a741_ray_mapper`、`a741_nav_guard` 及封装 `a741_fusion_core`。模块级 Icarus 仿真覆盖 0°/90°位姿投影、无效样本、地图完整清零/读写、Bresenham 空闲/障碍写入、几何未确认拒绝启动、障碍减速/停车和链路丢失锁定。

此验证仅覆盖模块级 RTL。尚无融合工程板级顶层连接、LD06 点投影、路径规划/跟踪、地图协议/GUI 或新的 Gowin 综合/布局布线报告；未生成融合版位流，未进行硬件验收。原 `a741` 发布固件未被覆盖。

## 当前运动与雷达实验包

2026-10-20当前选定包为[A741-MOTION-LD06-H20-H14](../release/README.md)：21组RTL、26项Python通过，源码/位流/网表及H20/H14静态审计通过。固件未烧录，时序未签核（setup/hold端点70/25，sys_clk Fmax48.959MHz低于50MHz）。完整结果见[运动与建图记录](MOTION-LIDAR-MAPPING-20261020.md)。

用户MPU日志已出现ready/sample_valid=true、fault=0，但flat_install=false仍不满足静止校准。LD06独立串口GUI已获纸板移动与方向确认，不代表本工程FPGA/PWM/局部地图通过。VL53L1X未接入，无前向测距保护。机械轮距由用户报告234mm，轮径/CPR和实车精度仍待验证。

以下为旧P4禁用与IMU硬锁变体的历史记录，只适用于当时位流，不能把旧数字当成最新实验包状态。

现场WHO_AM_I=0x70后新增MPU6500测试分支，19组RTL/15项Python通过；最新构建仍未通过50MHz主时钟和整板时序，见 [MPU6500现场适配报告](BUILD-MPU6500-TEST-20261020.md)。旧测试包及其结果保留为历史，不能混用哈希。

新增仅MPU6050接口启用、电机锁定版本的构建/验证见 [IMU测试版报告](BUILD-IMU-TEST-20261020.md)；18组RTL和14项Python通过，实板未测。以下早期P4禁用位流结果保留为历史记录。

日期：2026-10-20。没有烧录、没有发送实物电机命令，也没有把历史 A740 运行反馈算作 A741 验收。

本轮结果见 [构建交付记录](BUILD-20261020-FINAL.md)：位流已生成，主时钟报告Fmax 50.016 MHz、显示43.381 MHz；仍有72个setup、30个hold违例端点及复位恢复/脉宽问题，传感器端口禁用，不能用于小车运动。

MPU6050 首轮诊断构建有 **1164 个 setup、38 个 hold 违例端点**，详见 [历史失败记录](MPU6050-BUILD-20261020.md)。本轮将运动除法、航向积分、OSD 转换和雷达校验分周期执行；最终结果以同一交付目录的 result.json 和 a741.tr 为准，不能将历史数字作为最新构建结果。

## 回归范围

| 层级 | 组数 | 范围 |
| --- | --- | --- |
| A741 RTL | 16 | MPU6050 I2C/配置/积分、运动/PI、多周期目标与提交边界、雷达校验/断流恢复、遥测/网络、OSD/DDR/HDMI；最终以 result.json 为准 |
| A741 Python | 12 | 几何/标定、拒绝旧 JY901 固件、雷达重组/断流、遥测偏移、UDP 不重发、取消/释放时序、界面卡顿续约、桌面布局与截图 |
| 复用视觉工程 RTL | 16 | 含两张 800×480 完整帧跨 FIFO/DDR/显示域无撕裂、I2C/ToF、CDC、PWM 与协议 |
| 父工程 Python | 19 | 12 项 EMV1/视频，7 项传输/取消/兼容性 |

运行：

~~~powershell
$py = 'code/camera-car-control/.venv/Scripts/python.exe'
& $py code/camera-car-control/a741/scripts/build.py prepare
& $py code/camera-car-control/a741/scripts/check.py
& $py code/camera-car-control/a741/scripts/regress_related.py
~~~

机器记录在 a741/.local/tests/result.json、host.log、各组 RTL 日志和 related-results.json。正式归档须核对源码 SHA256；运行中修改过源码的结果不作为最终构建使用。

多周期目标测试覆盖 203 组参考算术，包括半圈误差和安装方向；另有最终除法、提交边沿的取消/失能/替换命令/STOP/ToF/TTL 用例。MPU 积分覆盖正负极值、时间戳回绕、采样异常及取消在途结果。新增运算延迟为微秒量级，不改变 100 Hz 斜坡周期；STOP 和故障仍从使能路径立即撤销输出。

PI 在每次 tick 锁存输入，最多 15 拍计算后原子提交；完整 32 位反馈使用 33 位误差和 34 位未限幅输出，避免极端反馈溢出。测试含 64 位参考逐 tick 对照、250 组随机参数/目标/测量、正负积分限幅、抗饱和、换向、负数向零截断和每个在途阶段失能取消。

共享视觉工程的 16 组 RTL 结果沿用该工程已有记录，脚本逐项比对输入哈希；本轮重新运行父工程 19 项 Python 测试。未修改共享视觉 RTL，不将复核历史结果写成重新执行全部共享仿真。

## 编译与时序

只构建 P4-disabled 诊断顶层，User Code A741。P4 没有物理端口，不是传感器可接线/可上车版本。完整板级脚本和原厂依赖哈希见 scripts/build.py 及生成的 platform-provenance.json。

首轮探索构建有 319 个 setup、99 个 hold 违例。缩短轮速算术、加入有界 CDC 约束、使用专用 HDMI 串行器和补充 DDR 时钟后，中间构建下降到 78/37；该中间构建期间源码仍在修改，没有作为最终位流归档。

**最终数字、位流哈希和是否完成工具流程只以最终归档 result.json 为准。** 即使生成位流，timing_signed_off 仍单独为 false。DDR IP 跨时钟、RGMII 输入预算、recovery/removal、I/O 输出约束与实板条件需要继续核实，不能通过扩大 false path 或放宽频率来宣称通过。

CDC 约束只作用于已实现的同步器输入、Gray 指针和握手保持的数据，不切断整组时钟。FIFO/握手两端共用视频全局复位；DDR 控制器软复位不单独清除一侧指针。显示在第一张完整摄像头帧之前不会误报普通画面欠载。

时钟静态模型依据本机原厂 IPC、模块网表及 Gowin 官方 SUG940-2.0.5、UG306-1.0.9（PLLA 章节）。显式建立 165 MHz/400 MHz 父时钟后再 `/5`、`/4`，解决当前工具在解析 SDC 时默认 PLL 时钟尚未建立的问题；频率目标未放宽，未添加内部 DDR 或整组时钟 false path。DDR 动态 MDRP、PHY 输入预算、MAC 握手约束与最小脉宽仍须独立审查。

## 依赖适配

- 原厂第 38/47/59 章源文件按 ZIP 哈希导入，不修改原包；TMDS 编码保留原厂算法，串行输出使用 OSER10 与 3.3 V 模拟差分输出，物理接线仍须实板核实。
- 父目录 MIT 网络依赖保持原 SHA256。A741 本地生成 udp_checksum_gen 副本，为 FIFO 指针 next-state 增加显式复位默认值，使本机 Icarus 在初始零指针条件下正确启动组合逻辑；正常传输算法未改变。原始/适配哈希及许可保留。

## 实板条件

用户提供51/Arduino测试源码、商品截图和ACG720 CSV，并明确否定此前模块原理图。旧图的VCC_5V、上拉/下拉及J1/J2针序不再使用。CSV六球号标LVCMOS33且无当前约束冲突；实物上拉、AD0电平、FPGA连接器针序/实际Bank及机械轮距仍待核实。实板验收、外部精度和30分钟并发未完成，见 [待填验收表](ACCEPTANCE.md)。

A740 交付位流仍为 SHA256：

98b41b4cbddf258d2759e12f10f8afd7f86c63e73e4160e6f3c778826d79eda5
