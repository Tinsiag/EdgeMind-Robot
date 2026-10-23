# A741 感知输入与 FPGA 核心融合

**现阶段可用固件和代码是用户确认的 `a741-imu-motion/release/A741-MOTION-LD06-H20-H14-20261022-130843`，固件 SHA-256 为 `e492146beb969e5ff97aaa2608b677f6ebab5b22354768cca6f55c5a8b15fe8e`。日常上位机从 `a741-imu-motion/launch.cmd` 启动，详见 [可用版本说明](../a741-imu-motion/README.md)。本融合目录仅为未验收开发版，不替代该固件和代码。**

独立工程 `a741-fpga-fusion`。保留原 `a741`、`a741-imu-motion` 与历史发布包。采集、位姿、栅格、定位、规划、跟踪和停车由 Verilog 执行；摄像头仅用于 HDMI / UDP 画面与记录，无视觉识别或边缘 AI。

**当前为开发验证版本，不能替换已验证的运动固件。** 几何基准未核实，自动导航在 RTL 内锁定。仿真、综合、布局布线、时序签核和实车验收分别记录，最终证据见 `verification/FUSION-RESULTS.json` 和 `verification/FUSION-REPORT.md`。时序不通过时不发布可刷写运动位流。

以下仅为创建融合工程时保留的历史通信基线，当前可用版本以顶部 `130843` 为准：

```text
C:\Users\Administrator\Documents\EdgeMind-Robot\code\camera-car-control\a741\release\A741-MOTION-LD06-H20-H14-20261022-101036\A741-MOTION-LD06-H20-H14.fs
SHA-256: fa9e1cd508b1f2b9e47884200fece220d6c7ea040f27a99cbaca8e13bb3491f9
```

用户曾反馈基线通过 501/501 只读请求；不代表本版本的时序、运动精度或导航验收。A740 基础移动反馈、A741 低速 `0x0004` 问题保留在历史工程中，不将其写成本版已经实测解决。

## 实现范围

| 部分 | 实现与限制 |
| --- | --- |
| 采集 | MPU6050/6500、LD06 UART/CRC/点流、左右编码器；沿用时间戳、序号、失效与错误计数 |
| 位姿 | 编码器区间增量直接转换为 Q16 毫米，左右均值配合相对 IMU 航向与 CORDIC 积分；人工设置初始位姿 |
| 地图 | BSRAM，128×128，50 mm/格，2 bit/格，范围 [-3200,3200) mm；射线空闲/端点占据；人工探索后冻结 |
| 定位 | 最多 64 点，±50 mm / ±3° 的 27 候选局部匹配；连续两帧确认、400 ms 过期；拒绝同分模糊结果；无全局回环 |
| 规划 | 8 邻域 10/14 代价 A* 波前搜索，最多 16,384 格；仅已知空闲格，禁止切过对角障碍；同步 RAM |
| 外廓 | 完整外廓的旋转半径加 100 mm 裕量，保守方形膨胀；当前待核实 |
| 跟踪 | 前视单元与差速轮速换算，自动轮速 ≤100 mm/s；末端 L1 位置误差 ≤100 mm、航向约 ≤15° |
| 恢复 | 先停车稳定，再以 40 mm/s 轮速扫描，每段 30°，最多 12 段，段间停车；单段超时锁定 |
| 电机 | 既有轮速 PI、100 Hz 斜坡，手动上限 400 mm/s；规划期间独占零目标，跟踪时禁止手动抢占 |
| 安全 | IMU/雷达失效、障碍、无反馈、无路径及命令租约过期停车；不自动清故障或重启；无 ToF 保护 |
| 视频 | DDR3 完整帧、HDMI 和可丢帧 UDP 通道；融合位姿与状态加入共享 FPGA OSD |
| 上位机 | 摄像头/雷达、FPGA 地图上传下载/清空/保存、初始位姿、目标点、启动/取消/停止、日志与截图；历史电脑建图页隐藏 |

控制、传感器与视频保留 EMC1/EMS1/EML1/EMV1，新增 EMM1 地图、EMF1 遥测。详见 `docs/FUSION-PROTOCOL.md` 与 `docs/FUSION-ARCHITECTURE.md`。

## 几何与接线

`config/geometry.json` 记录基准和锁定原因。已知下壳 STL 约 180×254×28 mm，STEP 使用毫米，用户确认 LD06 在前端中心并朝前，轮距实测 234 mm。待确认：整车含车轮/突出物外廓、轮轴中点、雷达扫描中心相对轮轴偏移、扫描平面高度。不用下壳尺寸或截图估算代替实测基准。

未核实时导航拒绝启动，旋转净空也不借用虚构半径放行。默认零雷达偏移只供未标定预览，不代表准确地图外参。补齐几何后须重新综合、时序检查和验收。构建与上位机共用 `host/fusion_config.py` 比较编译配置 CRC，防止参数与位流不一致。

| 信号 | FPGA 球号 | 说明 |
| --- | --- | --- |
| IMU SCL / SDA | L18 / M20 | 开漏 I2C；用户测得模块与总线空闲约 3.3 V |
| IMU XDA / XCL | A1 / B2 | 输入高阻，非主 I2C |
| IMU AD0 / INT | M17 / B1 | 输入不驱动；探测 0x68/0x69，曾读出 0x70 MPU6500 |
| LD06 CTL / DATA | H20 / H14 | 沿用调速/UART；H14 板载复用冲突按历史记录核查 |
| VL53L1X | 未绑定 | 未接入，状态无效，无 ToF 保护 |

表中为芯片球号，并非排针序号。电机、摄像头、DDR3、HDMI、RJ45 保留现有接线。`docs/HARDWARE.md` 是继承资料，其中早期候选引脚不得替代本表；没有新增 5 V 输入设计。

## 工作流

双击本目录 `launch.cmd`。只做传感器检查：

```bat
launch.cmd --sensors-only
```

有线电脑 192.168.0.3，FPGA 192.168.0.2；端口：控制 5000/5001、视频 6102、遥测 6103、地图 6104。启动不会自动连接或运行电机，连接后静止校准不会 ARM。

1. VM 关闭时核对传感器、网络、IMU 校准及版本。未签核构建只做离线验证，不安排实车运动。
2. 在“FPGA地图 / 导航”新建地图，硬件验收后人工驾驶探索。结束建图冻结并计算 CRC，下载后保存 JSON/PNG/PGM/YAML。
3. 上传只接受本版 128×128、50 mm/格 JSON，核对长度、CRC32、SHA-256；不能直接上传 CoreSLAM 地图。先 DISARM，取消/失败不提交半图。
4. 选择“初始位姿”，设置角度后点击地图；前方朝上，左侧朝左。等待可靠匹配，再选择目标。
5. 几何、时序和全部验收通过后启动导航。规划期间零目标、持续心跳；人工停止/取消始终优先。
6. “返回起点”向本会话人工确认的起点重新规划，不保证原路返回，同样受全部安全锁约束。

日志位于本目录 `.local/logs/YYYYMMDD-HHMMSS/session.jsonl`，有 INFO/DEBUG/WARNING/ERROR、FPGA 时间/序号、状态、故障和通信统计。截图含最新遥测与配置元数据，不是曝光时刻的硬同步测量。UI 卡住后停止续租，FPGA 最迟在有效 TTL（通常 250 ms）内停车；板级延迟必须实测。

## 构建与验收

在本目录执行，使用既有 Python、Icarus 与 Gowin V1.9.12.04：

```powershell
& ..\.venv\Scripts\python.exe scripts/build.py prepare --fusion
& ..\.venv\Scripts\python.exe -u scripts/check.py
& ..\.venv\Scripts\python.exe scripts/build.py build --fusion
& ..\.venv\Scripts\python.exe scripts/report_fusion.py
```

原厂 IP 从本机例程 ZIP 按哈希恢复，网络 MIT 许可保留。结果在本目录 `.local/gowin-fusion`。继承的 `scripts/archive.py` 不用于融合发布；`scripts/report_fusion.py` 归档本版证据，时序不通过时不归档运动位流。

次序见 `verification/FUSION-ACCEPTANCE.md`。软件仿真仅证明覆盖的模型行为；没有完整录制数据回放、几何核对、实板/实车验收的项目保持待验证。首版仅限室内平整静态环境，不覆盖动态人群、低矮或透明障碍及边缘 AI。
