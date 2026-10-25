# A741 多传感器与运动控制

## 当前合并固件（2026-10-22，优先阅读）

“网口控制链路已经恢复”对话的回退方案已与上一版 IMU 运动源码处于同一固件：使用本机归档 `release/A741-MOTION-LD06-H20-H14-20261022-101036/A741-MOTION-LD06-H20-H14.fs`，SHA-256 `fa9e1cd508b1f2b9e47884200fece220d6c7ea040f27a99cbaca8e13bb3491f9`。已恢复原厂 `phy_reg_config`，不再用实验身份检查门控 MAC，EMP1 禁用。电机硬锁仍解除，配置/校准/ARM 和故障保护保留；LD06 H20/H14、摄像头等接线不变。

核对全部 93 项编译输入及归档 240 个文件校验通过；上一版的运动、目标计算、PI、IMU 采样和航向积分五个模块与回退版逐字节一致，因此本次复用该已有合并位流，没有重新生成不同哈希的位流。详细证据与功能限制见 [合并核对记录](verification/NETWORK-MOTION-INTEGRATION-20261022.md)。

直线具备 IMU 航向纠偏，原地旋转具备 IMU 相对角度闭环；弧线目前是几何轮速换算加编码器 PI，并非 IMU 角速度闭环。距离任务重复下发目标会刷新航向原点，长距离航向保持尚有改进空间。回退版现场只读请求合计 575/602 成功，仍有超时；setup/hold 违例为 70/30，时序未签核、运动精度未验收。先保持 VM 关闭验证通信。

上位机使用本目录 `launch.cmd`。下方 2026-10-21 的“最新”位流及 EMP1 描述均为历史记录，以本节和合并核对记录为准。

## 2026-10-22 PHY 初始化回退

用户反馈 20261021-223907/234236 诊断初始化版本冷启动后 D2 不亮、控制和遥测均不可用；旧固件能连接。当前源码恢复旧版 `phy_reg_config` 的复位/自协商流程，停用实验性 PHY 身份门控和 EMP1 发送，保留 EMS1 MAC/FCS 诊断、运动、IMU 和 LD06。此回退用于恢复连接基线，不代表之前间歇性超时已经解决。实验性初始化失败的具体寄存器/原因尚未通过实板读回证实。保持 VM 关闭验收网络，禁止以 ping 回复替代 A741 协议身份和控制回复验证。

## 下一版运动固件（2026-10-21）

本版基于 `MOTION_LIDAR` 变体解除电机硬锁，并启用 MPU6050 闭环运动：

- **闭环直线**：上位机发送等速左右轮目标，FPGA 使用编码器速度 PI；直行模式以启动瞬间 IMU 航向为基准，按航向误差限幅修正左右轮速。
- **设定角度原地转弯**：命令使用相对 IMU 航向，支持正负角度、±180° 回绕、减速和低速稳定判定；IMU 无效立即停车，不回退到编码器角度。
- **大幅度转弯**：上位机按线速度和角速度计算左右轮目标，FPGA 统一限幅并保留 IMU/编码器闭环；GUI 的“左弧线/右弧线”按钮用于连续大半径或小半径转弯。

本版修正了连续直行/弧线动作的航向原点锁存问题：每次新命令都使用当前 IMU 航向，不沿用上一动作的航向原点。电机解锁不等于可以直接上地面运行，首次必须架空、低速、短时验证方向和 STOP。

最新实验固件归档：`release/A741-MOTION-LD06-H20-H14-20261021-234236`。位流 SHA-256 和时序状态以该目录 `README.md`、`result.json` 为准；当前仍为 `timing_signed_off=false`，未完成实板运动验收。

## 2026-10-21 最新网口诊断

RTL8211F-CG 初始化现按用户提供的 Rev.1.4 手册执行：PHYRSTB 低电平至少 10 ms，释放后等待 50 ms；仅读取 PHYID/BMCR/BMSR，不写未公开定义的保留位。新增 32 字节 `EMP1` 诊断包，每秒发送一次，包含 PHY ID、BMCR、启动/当前 BMSR、PHY 地址和 fault；EMS1/EML1 保持兼容。相关实现和判断规则见 [NETWORK-DIAGNOSIS.md](docs/NETWORK-DIAGNOSIS.md) 与 [协议说明](docs/PROTOCOL.md)。

最新运动+LD06位流本机归档为 `release/A741-MOTION-LD06-H20-H14-20261021-223907`，SHA-256：`03fa2b87728b7d632b58cb8aa1f45867118954d3ee3a0ccb4c22fed2c8282fc8`。25 个 RTL bench、34 项 Python 测试和动态引脚审计通过，但 `timing_signed_off=false`，存在 setup/hold 违例，未完成实板验收。

22:50 现场诊断没有收到控制回复、EMS1 或 EML1，Windows 以太网适配器显示 `Disconnected`、`0 bps`。这次应先检查网线、USB 网卡和 RJ45 Link 灯，关闭 Wi-Fi/VPN，确认 `192.168.0.3/24` 可 ping `192.168.0.2`，再运行 `diagnose-control.cmd`。保持电机 VM 关闭；UDP 超时本身不能证明 FPGA 控制桥已损坏。

2026-10-21控制超时仍在排查。新增[网口诊断步骤](docs/NETWORK-DIAGNOSIS.md)和 `diagnose-control.cmd`，诊断构建会在EMS1中上报MAC坏FCS、有效收帧和控制桥状态。主机对明确可重复的STOP/配置/状态查询最多重试一次，运动命令不重试；不代表控制通信已修复。旧固件归档保持不变。

当前增加独立 `--motion-lidar` 实验变体：MPU6050/MPU6500兼容采样、LD06 CTL=H20 / DATA=H14、解除电机硬锁、电脑二维建图。VL53L1X未接入，无前向测距停车保护，LD06不自动避障。实测机械轮距234 mm由用户提供；轮径/CPR仍需外部校验。**当前整板时序未签核，不可作运动验收版。** 见 [接线与建图](docs/MOTION-LIDAR-MAPPING.md)。

保留 `--imu-test` 电机硬锁测试变体及默认P4禁用诊断变体，不能混用位流。2026-10-20现场身份0x70已有MPU6500兼容分支，用户随后报告 `fault=0, ready=True, sample_valid=True`；`flat_install=False`仍不能静止校准。未知身份继续拒绝。旧包名称含 `IMU-TEST-MOTOR-LOCKED`，不具备LD06功能。见 [IMU测试步骤](docs/IMU-TEST.md)。

2026-10-20 IMU诊断位流见 [历史诊断构建记录](verification/BUILD-20261020-FINAL.md)。最新运动+LD06实验位流见 [独立构建与建图记录](verification/MOTION-LIDAR-MAPPING-20261020.md)：生成且静态审计通过，但整板时序有违例、未烧录、未实板验收。

A741 在独立目录实现运动、IMU/ToF/雷达采集、上位机与双端视频。运动+LD06变体由主机运行局部扫描匹配及二维占据地图，导出PNG/PGM/YAML/JSON。建图操作、数据门控和精度限制见 [LD06二维建图说明](docs/MOTION-LIDAR-MAPPING.md)。A740 的源码入口和 release/A740-20261019 保持原样。

各变体的位流生成状态、时序违例和哈希以独立交付目录的 `result.json`、`a741.tr` 为准；`compile_passed` 不代表时序或实板通过。RTL/Python回归不能代替时序签核、传感器实测或地图精度验收。

**当前不是可上车验收完成版。** 先前MPU6050原理图已被用户撤回，不能据此假定上拉或AD0下拉。用户实测VCC/SCL/SDA=3.3 V，AD0=3.2 V；实际I2C日志为0x68，与AD0静态测量差异未解决。模块上拉、Bank电压、H14板载复用隔离和完整物理针序仍未签核。见 [MPU6050替换记录](docs/MPU6050.md) 和 [验证记录](verification/README.md)。

详细的固件辨识、下载前条件、接线限制、上位机设置、标定、LED、故障排查及复现步骤见 [固件使用与注意事项](docs/FIRMWARE-GUIDE.md)。

## 实现

- 前进/后退距离任务、按住驾驶、左右弧线、相对 IMU 原地旋转；取消、失联、IMU 失效、ToF 联锁、无反馈故障停车。
- 100 Hz 目标速度和 PWM 变化限制。换向先经过零输出；普通起停在控制周期更新，STOP/故障立即封锁桥输出。STOP 为撤销驱动，物理停车距离仍须测量。
- 旋转累加相邻 IMU 航向差，处理 ±180° 回绕，依据剩余角度降速，按角速度/轮速预测制动。制动后等待至少 200 ms 低速稳定并检查 ±5° 容差；不自动补转、不退回编码器转角。
- 直行由编码器行程规划，IMU作限幅航向修正。弧线采用用户实测机械轮距234 mm换算左右轮速并同比限幅。历史编码器转向补偿字段与机械轮距字段独立。
- MPU6050 主 I2C 地址探测、身份/配置回读校验、14 字节连续读取与故障重试；64 个静止样本零偏校准，平放 Z 轴相对航向积分。失效作废校准，恢复后需人工重启；不支持绝对方位或任意空间安装。
- VL53L1X 复用已有 ST 初始化表/I2C 驱动，开漏总线、XSHUT、状态/采样时间、150 ms 有效期与故障重初始化。
- LD06 包长/CRC8/角度插值/置信度/分区最近距离；独立 EML1 通道送上位机组装完整扫描，坏包、角度断点、丢包和断流使扫描失效。
- DDR3 完整帧发布后读出 HDMI；同一 OSD 图像经独立、允许丢帧的网络 FIFO 发送。HDMI 为 800×480，网络为 400×240 抽样，避免 50 MHz 字节打包器持续溢出。拥塞不反压 HDMI 或运动环。
- 十进制 FPGA OSD：模式、停止原因、目标/实测轮速、航向、ToF、雷达分区、DDR/摄像头状态。无效值显示 STALE/INVAL；中文上位机显示“无效 / 过期”。
- PC 摄像头、二维雷达、局部建图及 PNG/PGM/YAML/JSON 导出、遥测、配置编辑保存、静止校准、截图与 JSONL 日志。连续驾驶需界面每 200 ms 内续约，释放、失焦或界面停顿结束驾驶。

不含循线、全局闭环SLAM、自主导航。LD06仅参与本地匹配建图和显示，不参与电机避障；后退没有前方 ToF 保护承诺。

A741 LED（高电平亮）：D0 网络 PLL 锁定，D1 摄像头初始化就绪，D2 PHY 初始化就绪，D3 DDR 校准完成，D4 完整显示帧可用，D5 DDR/显示错误，D6 视频 FIFO 溢出，D7 运动故障。该定义与 A740 不同；D7 熄灭不表示已允许 ARM。

## 启动

[当前实验固件与报告](release/README.md)和[独立串口雷达GUI](../../ld06-radar-gui/README.md)是两个入口。串口GUI已获用户纸板移动/方向实测反馈；它不经FPGA，不能证明本工程雷达/PWM/地图已经实板通过。

在仓库根目录运行，也可双击 a741/launch.cmd：

~~~powershell
& code/camera-car-control/.venv/Scripts/python.exe -X utf8 code/camera-car-control/a741/host/app.py
~~~

依赖复用父目录 requirements.txt 和 .venv。界面不会自动连接/使能电机。电脑网卡沿用 192.168.0.3/24，FPGA 为 192.168.0.2，要求 1 Gbps RJ45。FPGA 控制端口 5000、PC 控制端口 5001、视频 6102、传感器/雷达 6103。旧上位机需释放同一 UDP 端口。

连接先发 STOP 建立 EMC1 会话，再查 A741 能力并逐项写入/回读配置。EVM1 能力 bit4 表示 A741 接口，bit5 表示 P4 物理端口已启用；诊断构建只有 bit4。保留 EMV1/EMC1 封装，但新传感器命令与旧视觉工程 0x41～0x45 意义不同，必须判断能力，不能混用。

## 标定

唯一主机标定入口：[config/calibration.json](config/calibration.json)。界面“标定参数”可载入、编辑、保存并采用配置；连接期间禁止修改。修改后递增 revision，重新连接并静止校准。

| 字段 | 单位/含义 |
| --- | --- |
| wheel_cpr | 左右每圈计数；1469/1471 为待复核历史初值 |
| wheel_diameter_um | 左右轮径 µm；66300 为待复核历史初值 |
| mechanical_track_um | 实测机械轮距 µm；用户本轮实测234000，不再使用未经确认的补偿值代用 |
| historical_encoder_turn_track_um | 仅记录，不下发、不参与弧线几何 |
| max_speed_mm_s | 最大轮速，初始 200 mm/s |
| speed_step_mm_s_per_10ms | 每 10 ms 起停速度变化；5 对应 500 mm/s² |
| pwm_step_per_10ms / pwm_limit | PWM 变化量/上限；512 对应沿用的 50% 上限 |
| imu_yaw_sign / imu_axis | ±1 / 当前仅 z |
| imu_model / imu_i2c_hz | MPU6050 / 100000；主机核对 FPGA 模型 ID 6050，不再使用 UART 波特率 |
| imu_supply_v / hardware_verified | 用户确认 3.3 V / 完成硬件核实记录，不能代替上拉与 Bank 电压测量 |
| tof_offset_mm | 从测距值减去的安装偏移，mm |
| lidar_clockwise / lidar_zero_offset_deg | 雷达原始角度顺时针标记/前向安装偏置，显示与地图共用，需实物核实 |
| lidar_duty_permille | 雷达PWM占空比‰；0停止，200～600运行，初值400 |

ToF 当前固定策略：净空 ≤250 mm 停车，250～500 mm 线性降速，超过 150 ms 无效；均为待实测初值，尚未作为在线可调参数发布。只约束前进/前弧线，故障锁存后须清故障并人工重启。

轮速 PI 初始比例项为误差本身，积分每周期增加 error/16，带限幅/积分饱和处理。初始增益尚未完成实车整定。

## 构建

### 新克隆环境

父目录 `.venv` 尚不存在时，先从仓库根目录创建运行环境：

```powershell
python -m venv code/camera-car-control/.venv
& code/camera-car-control/.venv/Scripts/python.exe -m pip install -r code/camera-car-control/requirements.txt
& code/camera-car-control/.venv/Scripts/python.exe -m pip install -r code/camera-car-control/a741/requirements-mapping-build.txt
& code/camera-car-control/.venv/Scripts/python.exe -X utf8 code/camera-car-control/a741/scripts/setup_mapping.py
```

最后一步由随仓库提供且固定版本的CoreSLAM源码构建本机可替换DLL；不是把其他平台的DLL直接改名使用。完整RTL仿真还需要本机Icarus工具，板级编译需Gowin和原厂ZIP，见下文。

依赖用户本机原厂第 38/47/59 章 ZIP。脚本记录 ZIP、导入文件和适配文件哈希；不修改 ZIP 或父目录固定版本 MIT 源码。

~~~powershell
$py = 'code/camera-car-control/.venv/Scripts/python.exe'
& $py code/camera-car-control/a741/scripts/build.py prepare
& $py code/camera-car-control/a741/scripts/check.py
& $py code/camera-car-control/a741/scripts/build.py build
~~~

运动+LD06独立变体：从a741目录运行 `scripts/build.py build --motion-lidar`，输出在 `.local/gowin-motion-lidar`。建图DLL缺失时，使用同一个Python运行 `-m pip install -r requirements-mapping-build.txt` 后运行 `scripts/setup_mapping.py`；再执行完整 `scripts/check.py`。运行 `scripts/audit_motion_lidar.py` 验证当前位流/源码哈希、动态输出及引脚报告，`scripts/archive.py --motion-lidar` 保存独立实验包。所有相对脚本路径基于a741目录。完整状态见 [运动与建图构建记录](verification/MOTION-LIDAR-MAPPING-20261020.md)。

默认诊断输出为 a741/.local/gowin-board，IMU测试输出为 `.local/gowin-imu-test`，User Code均为0000A741；仅凭User Code不能区分变体，须同时核对能力和位流SHA-256。compile_passed仅表示对应源码快照完成工具流程；timing_signed_off单列。失败构建不采用遗留报告。

[硬件核对表](docs/HARDWARE.md) / [协议](docs/PROTOCOL.md) / [实板验收表](verification/ACCEPTANCE.md)。

日志在 a741/.local/logs/会话时间/session.jsonl。截图同名 JSON 记录视频帧号、主机收图时间、最新有效 FPGA 遥测、雷达点和配置哈希；这是接收时关联，不代表曝光与 IMU 的硬件同步。
