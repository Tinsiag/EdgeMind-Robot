# EdgeMind-Robot 完整交接：FW74508 已烧录，落地运动待验收

> 最新状态（2026-10-31）：FW74508 已完成外部 Flash 写入/校验、重载、就绪和 UserCode 比对。实板 SHA-256 为 `899034472dc21c4f39669929d592031e9521faabf2b6718ffb9ee83ab8813690`，审计 `output/refactor-autonomous-20261030/flash/20261031T092737.270324Z/audit.json`，最终状态 `0x70022020`。被动健康 `imu-fault-20261031/74508-health-20261031.json` 有 300 状态/300 姿态，全部 FW74508/IDLE/ERR0000/未 ARM/目标 0，CPU/IMU/摄像头/DDR 正常。
>
> FW74508 在姿态 CORDIC 发布层对最近三个完整 roll/pitch 对按最大绝对倾角取中值，过滤单次加速度/振动尖峰；22.5° 阈值、valid 和真实倾斜停车保留。29 项 RTL/协议、回放、几何、CPU、8 项导航/姿态原语模型及同次 PNR/STA/SDF/PAD 通过。运动、显示和真实冷启动未验收，`STATUS.json` 保持 `application_verified=false`、`err0001_fixed=false`、`root_cause_confirmed=false`。用户已确认 VM 关闭，烧录后未 ARM。

> 2026-10-31本次接手更新：用户已继续工作，并追加30cm前停、无脉冲只提示、三方都堵时先后退一小段再重新择路，旧版“50cm/不倒车”约定已由用户覆盖。源码候选为FW74507，具体行为和当前验证边界见`output/refactor-autonomous-20261030/CHANGE-74507.md`。当前实板仍以STATUS.json和真实审计为准，不能将下文旧74506签核用于新源码。被动180秒1800状态/1800姿态均IDLE/ERR0000，用户答复尚未测试，ERR0001未修复。

> 当前已固化FW74507，SHA为`cde3af917fd0c4e711633a7b4d6fa020129aeec50fd3b0832ec5974bd066063f`。审计`output/refactor-autonomous-20261030/flash/20261031T084753.897504Z/audit.json`：54@0写入/校验、Reprogram、只读就绪、UserCode通过，最终0x70022020。`imu-fault-20261031/74507-health-20261031.json`有300状态/300姿态，全74507/IDLE/ERR0000/未ARM/目标0，CPU/IMU/摄像头/DDR正常，发送包0。28项RTL、协议、回放、几何、CPU和6项导航原语以及同次整板PNR/STA/SDF/PAD最终门通过。新版本实屏、运动和真实冷启动均未验收，ERR0001未修复。
>
> 用户再次确认VM关闭、轮子架空并要求“以后不要我提醒直接烧录”。持续授权和已知VM关闭条件满足时，检查通过直接Flash，不重复问权限；已变化/未知的物理状态仍须核实。烧录后只有被动健康，没有ARM或运动。下文74506条目为历史交接事实，当前行为和SHA优先采用本段、CHANGE-74507.md和STATUS.json。

2026-10-31（Asia/Shanghai），分支 `main`，目录 `C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot`。接手者无需聊天历史。用户最新要求先写交接文档与提示词；本轮在已开始的Flash操作安全结束后，只核对了被动健康，没有继续启动运动测试。

## 目标

解决小车落地平地直行偶发FAULT/ERR0001、需要再按S1恢复的问题，保留已恢复的前进与转弯能力。完成标准是负载平地多次启动、直行和转弯无误报，真实IMU断流/坏数据/过倾斜仍能停车，S1/S0停止正常，并逐个新SHA验收真实冷启动。不能将诊断能力或烧录成功写成故障已修复。

用户最终避障要求仅前方50cm停车，侧后方按车身转弯空间检查，转后用陀螺仪锁定新航向直行。上电不ARM，网口仅传数据。

## 当前状态

- 已验证：当前实板FW74506、UserCode0x0000A745，位流`code/camera-car-control/a745-autonomous/.local/gowin-a745-autonomous/impl/pnr/a745.fs`，SHA-256 `b5cb8e927ebd07fccbaa1dde327acde91f565e7d8b698bc2862bd7a9c93d3a1a`。
- 已验证：审计`output/refactor-autonomous-20261030/flash/20261031T075334.673715Z/audit.json`，外部Flash54@0写入/校验、Reprogram、74只读就绪、73版本比对通过，最终状态0x70022020。没有失败后盲重写或退回SRAM。
- 已验证：`output/refactor-autonomous-20261030/imu-fault-20261031/74506-health.json`包含120个状态和120个姿态包，实际74506，CPU进度递增、摄像头首试初始化成功、DDR/完整帧正常，全部IDLE/ERR0000、未ARM、目标0，总线错误0，0个发送包。末次F/L/R=2034/540/1163mm。IMU诊断0x07007068，WHO=0x70、地址0x68，当前芯片按MPU6500兼容路径工作；不要把WHO非0x68直接判坏。
- 用户已确认：74505能跑、能转弯，随后平地直行会突然ERR0001，S1可再启动。最新澄清为“架空跑没事，一放到地上就出现ERR”。该澄清替代早先组合选项可能造成的“架空必现”推断；车太重是用户猜测，未证实根因。
- 尚未解决：74506只增加故障瞬间原因/角度锁存及遥测，原停车条件和22.5度阈值保持。尚未用74506复现落地错误，没有捕到新锁存原因，不能宣称修复ERR0001。
- 旧74505数据：`imu-fault-20261031/74505-straight-repro.json`末尾仅到CALIBRATE；`74505-straight-repro-02.json`的900个状态全为FAULT0001、IMU/gyro有效、总线错误0、样本年龄0～10ms，未捕到进入FAULT边沿。故障后倾角最大约7.21/8.78度，不能据此排除触发瞬间的倾斜或坏样本。
- 当前物理状态：用户在74506烧录前明确确认VM关闭、轮子架空，此后没有请求或执行新的运动。后续若用户再测试，重新加载前须更新VM关闭确认。不得自动ARM。
- 离线已验证：26项RTL/Verilator、独立协议、91,080点真实雷达回放、122,536几何边界点、同源CPU证据哈希复核；4个导航叶模块的5项Gowin原语执行，包括新增故障锁存用例。叶模块独立综合，不是整板跨层优化网表执行。
- 实现已验证：PNR446.687秒，setup/hold/recovery/removal违例0，最差+1.273/+0.040/+2.966/+0.225ns。TFT、TX、DVP和约束目标审查通过，属于实现模型，不是实测。主综合网表SHA为bbd15646af6ff17fd1b611acab18276beeb38a0d15d964fa8d1ed1920374a878。
- 74506尚未实物验收屏幕、新SHA真实冷启动和运动；旧74504冷启动、74505运动确认不能直接套用。
- Git：HEAD为ac56a9e，main。上次交接和清理已推送该提交；本次74505/74506源码、证据、交接仍有未提交修改和未跟踪文件，尚未推送。本次请求只先交接，没有执行新的Git上传。`output/releases/fw74504`是上次发布镜像，不是当前74506。

## 下一步

1. 先读`AGENTS.md`、本文件、`output/refactor-autonomous-20261030/STATUS.json`和`imu-fault-20261031/DIAGNOSTICS.md`，核实实际74506与上述SHA；不要直接再次烧录相同诊断版。
2. 恢复只读监听，运行`capture_imu_fault.py --seconds 180 --output 新文件路径`。准备受控开阔平地短程测试，前方超过1m、停止条件可用。由用户本地S1启动，出现ERR0001后先关闭VM、保留FAULT，不再按S1清除；电脑不发运动包。
3. 读取锁存`imu_fault_sources`、`imu_fault_valid_flags`、`fault_roll/fault_pitch`，结合IMU时间、错误计数、序号及当前驱动诊断定位。bit0航向/IMU无效、bit1原始采样无效、bit2倾角无效、bit3超倾角；不要把实时恢复后的正常角度当作触发值。
4. 按证据修对应路径。若是负载振动导致瞬时加速度倾角，设计有依据的姿态估计/样本资格处理并保留真实倾斜保护；若是总线或新鲜度问题，查实际断点和供电/接线条件。不要盲增PWM、抬高倾角阈值、屏蔽valid或移除故障锁存。
5. 修改后先证明对应失败场景，再完整回归、原语检查和同次PNR/STA/SDF/PAD；确认VM关闭后按持续授权写外部Flash。写入/校验失败停查，不盲重试、不降级SRAM。
6. 用户分别验收架空启停、负载直行/左右转弯、S1/S0停止和真正断电启动，记录新SHA的结果；根因和验收未完成前保持application_verified=false。用户要求上传时再提交推送当前修改；不关机。

## 关键文件

| 仓库相对路径 | 作用 |
| --- | --- |
| `code/camera-car-control/a745-autonomous/rtl/a745_autonomy.v` | 原运动状态机；新增ERR0001原因、有效标志和当时roll/pitch锁存，S1清除。未改安全判断。 |
| `code/camera-car-control/a745-autonomous/rtl/a745_core.v` | 74506身份、故障快照连接、EMS/EMF保留位扩展、IMU驱动诊断。 |
| `code/camera-car-control/a745-autonomous/host/receiver.py` | 被动解码新诊断字段和原有IMU时间/错误/序号。 |
| `code/camera-car-control/a745-autonomous/lib/a741_attitude.v` | 由加速度计CORDIC求倾角；正常计算期间保持已发布valid，坏/旧样本失效。不是卡尔曼。 |
| `code/camera-car-control/a745-autonomous/lib/mpu6050_heading.v` | gyroZ相对航向、零偏、样本间隔/过载检查；间隔0或>30ms无效。 |
| `code/camera-car-control/a745-autonomous/lib/mpu6050_driver.v` | MPU6050/6500、100Hz、DLPF3、配置回读、I2C错误/150ms新鲜度。 |
| `code/camera-car-control/a745-autonomous/lib/a741_imu_i2c.v` | 开漏I2C、ACK/重复启动/拉伸/超时。 |
| `code/camera-car-control/a745-autonomous/tests/imu_fault_latch_tb.v` | 故障原因区分、触发角度原子锁存、恢复后证据保持、S1清除、立即停止。 |
| `code/camera-car-control/a745-autonomous/tests/check_protocol.py` | 诊断保留位和有符号角度布局、原UDP校验。 |
| `code/camera-car-control/a745-autonomous/scripts/check_navigation_gate.py` | 4个叶模块、5个原语模型用例；含锁存测试。 |
| `output/refactor-autonomous-20261030/imu-fault-20261031/capture_imu_fault.py` | 只接收故障证据，不发送控制包。 |
| `output/refactor-autonomous-20261030/imu-fault-20261031/DIAGNOSTICS.md` | 字段含义、已知证据和诊断边界。 |
| `output/refactor-autonomous-20261030/imu-fault-20261031/PHYSICAL-REPORT.json` | 用户最新澄清、旧版复现边界。 |
| `output/refactor-autonomous-20261030/STATUS.json` | 当前实板、SHA、审计及待验收状态。 |
| `output/refactor-autonomous-20261030/turn-diagnostics-20261031/DIAGNOSIS.md` | 74505近距离散点修复及回放证据。 |

## 决策和注意事项

- **故障快照格式**：EMS1长度112，26/27字节为原因/当时标志；EMF1长度48，42/43为原因/标志，44..45为roll、46..47为pitch（有符号Q15半周，乘180/32768度），32..35为当前驱动诊断。只在实际revision≥74506时解释新保留位。原因的校准bit4/bit5为未静止/未校准；标志bit0..7为IMU、gyro、tilt有效、超倾角、静止、CPU正常、雷达流、完整扫描。
- **74505修复保留**：LD06近距弱单点/双点噪声先做两点前视邻接资格检查，强度≥220单点及连续≥3且邻距差≤3%的弱点保留。原始EML1完整发送，导航F/L/R用合格点。弱反射细小物体需单独实测；不是近距几何豁免。
- **避障参数保留**：F≤500mm禁止前进，F>800mm120mm/s，其余可走区60mm/s。先停100ms，侧距≥600mm且对应CAD包络许可才能转；两侧都堵BLOCK，不自动倒车。仅前方停车线50cm，非四周统一50cm。
- **转弯与安全保留**：gyro相对目标90度，约87度制动、SETTLE150ms，前方≥600mm才恢复并锁新航向。保留±180度环绕、轮速同步和每轮PI。未实现卡尔曼，也不宣称消除航向长期漂移。架空机身不转，转向持续4.5秒会ERR0080，应约2秒S1停止。
- **显示接线保留**：800×480/33MHz，AB22 DE、AB21背光，P7 TY-OV5640自带晶振，32列实拍可见安全区。CPU显式FF寄存器、原监督固件及看门狗不删除，不用false path掩盖时序问题。
- **硬件控制**：上电不ARM，S1先释放再按用于校准/启动，再按停止；S0急停。A18/A19左LAIN1/2，F13/F14右RAIN1/2，共地保持。旧GND锁是固件内部锁低，不拆公共GND。持续Flash授权有效，核实VM关闭是实际硬件条件，不是重复索取烧录权限。
- **环境小故障**：本轮一次子模块综合在120秒超时，主工程未受影响；执行上限改300秒，主编译结束后单独重跑5项均通过。Windows报告文件偶发Errno22，TX和约束报告改临时文件原子替换后审查通过；没有放宽检查。
- **清理/历史**：18,685文件、约15.92GB已清理，保留当前源码、PCB/CAD和所需几何输入，Git历史保留。旧74502暂存镜像删除曾被自动审批以blocked by policy拒绝，未绕过；不重新执行旧清理或恢复备份。不关机。

## 运行与验证

在仓库根目录使用现有Python、GowinV1.9.12.04和WSL Ubuntu-26.04（Icarus12、Verilator5.032）。以下前缀均为`code/camera-car-control/.venv/Scripts/python.exe`。

```powershell
code/camera-car-control/.venv/Scripts/python.exe output/refactor-autonomous-20261030/imu-fault-20261031/capture_imu_fault.py --seconds 180 --output output/refactor-autonomous-20261030/imu-fault-20261031/74506-loaded-repro.json
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/check.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/tests/check_protocol.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/tests/check_turn_geometry.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/tests/check_lidar_replay.py output/refactor-autonomous-20261030/turn-diagnostics-20261031/static-clear-raw.json
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/build.py build --timeout 1800
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/check_cpu_gate.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/check_navigation_gate.py
```

实现审查执行`output/refactor-autonomous-20261030/`下的inspect_implementation.py、audit_tft_sdf.py、audit_tx_sdf.py、audit_camera_input.py、audit_constraint_targets.py，再final_gate.py。后者会把STATUS改为候选待烧录，已有实板结论后不要无故重跑。烧录统一用`scripts/fpga/program_flash.py --bitstream 明确fs路径 --sha256 明确SHA --log-dir output/refactor-autonomous-20261030/flash --program`；确认VM关闭，不能自动ARM或用SRAM代替Flash。日志目录名是UTC，用户日期按上海时区。
