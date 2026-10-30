# EdgeMind-Robot 完整交接：FW74504 与 BLOCK 转弯诊断

2026-10-31，由 Codex 在 main 分支整理。项目目录 C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot。本文假定接手者没有聊天历史。

## 目标

继续完成本地 S1 自主避障：前方触线停车，选择可走侧转弯，用陀螺仪完成转角并保持转后直行。用户最终明确“仅把前方停车线改为50cm，侧后方按车身转弯空间检查”；旧30cm、四周一律50cm均已撤回。

显示/摄像头要在烧录和真实断电启动后正常。网口仅传状态、姿态和雷达数据，不能控制运动。完成标准包括真实左右转向、S1停止、约90度落地转弯及转后直行，不能仅凭离线通过或烧录成功结案。

本次用户另外授权更新交接、提示词、上传GitHub，并将本地清理同步至远端main。本次只整理上传，不再操作硬件，不关机。

## 当前状态

- 已验证：活动工程为 code/camera-car-control/a745-autonomous。FW74504 / UserCode 0x0000A745 已写外部SPI Flash地址0，写入校验、Reprogram、只读就绪与版本比对通过，状态0x70022020。
- 已验证：当前唯一发布位流为 output/releases/fw74504/a745.fs，SHA-256 74cef81a075feb78f9c5bc70a91384a368dc81e080ad65a3eccbb867f01719df。manifest.json记录器件、源码/生成输入哈希和验收边界。Git LFS保存位流、当前SDF及物理网表，git lfs pull后核实实际字节哈希。
- 已验证：真实成功审计 output/refactor-autonomous-20261030/flash/20261030T172515.341214Z/audit.json。此前172050尝试因USB下载器不在返回50；停止后用户重接，扫描FT2CH通道0/位置548、器件ID0x0001481B成功才重试，没有盲重擦写或退回SRAM。
- 已验证：TURNING-74504-HEALTH.json捕获实际revision74504、CPU alive/progress递增、摄像头首次初始化成功、DDR/完整视频正常；IDLE/ERR0000、未ARM、目标与速度0，无坏包，没有发控制包。
- 用户已确认：74504“冷启动后都正常”；随后报告“能前进，但是没有转弯，显示BLOCK”。因此本SHA冷启动与前进已验收，转弯尚未验收。
- 未解决：缺少用户实际BLOCK场景的F/L/R、左右几何许可与雷达点。先前90秒采集只覆盖IDLE，重启后F曾52～103mm而双向许可阻；不能拿这段待机数据证明用户BLOCK时的根因。后续15秒及45秒监听均0包。
- 当前物理状态未知：用户曾为测试开启VM；之后已要求先S1停止、关VM、保持板卡/屏幕通电并连接网线、前挡板固定35～45cm、抄F/L/R与VM状态，尚未答复。后续烧录不能假定VM已关闭。
- 离线已验证：23项RTL/Verilator、独立协议、122536个旋转边界点几何检查、同源CPU网表及导航三模块Gowin原语模型执行通过。导航为同源叶模块独立综合、全部端口可观测；不能说执行了整板跨层优化网表。主工程SHA绑定，转向表未误推断同步RAM。
- 实现已验证：布局1/布线1，setup/hold/recovery/removal违例端点0，最差裕量+1.135/+0.051/+3.952/+0.325ns。TFT同次SDF以10ns预算另留板线1ns和时钟0.3ns，剩余2.8145ns；TX最大偏斜0.022ns、剩余0.243ns；DVP十路IODELAY96通过。均是模型/实现检查，不是实测。
- 清理已执行：351目标、18685文件、15918936378字节。保留当前源码、PCB/CAD、V5所需5个V4基础文件及.git。本次提交同步删除8297个已跟踪旧文件，GitHub当前主分支目录随提交清理；历史提交保留。
- 清理单独例外：旧74502暂存 flash/20261030T161323.218749Z/image.fs 后续删除被自动审批以blocked by policy拒绝，仍在本机且未绕过；该文件不在351项已完成计划中，也不在本次发布位流路径。

## 下一步

1. 先恢复只读诊断条件：获取用户VM关闭确认、固定挡板场景F/L/R；保持FPGA/屏幕通电和网线连接。电脑网卡192.168.0.3/24，板卡广播来自192.168.0.2:6103。不要发网络运动命令。
2. 运行 capture_turn_blocks.py，读取当前EMS1的F/L/R、rear、left_clear/right_clear、scan_sequence，以及实际阻止左右转弯的点角度/距离。核对实际revision74504和当前查表SHA，避免使用未烧录新源码解释旧位流。
3. 核对BLOCK分支：停轮100ms后，F≥600且非未知值应恢复前进；否则左侧需要left_clear且L≥600，右侧需要right_clear且R≥600，两侧都通选更远侧。若这些条件均满足却持续BLOCK，再查tick/状态机与整板综合连接；若不满足，查具体阻挡点和扫掠空间，不能直接降低保护门槛。
4. 轮子架空先测试选向、左右轮方向及约2秒后S1停止。左转左轮后退/右轮前进，右转相反。架空时车身不转，4.5秒无航向进度会ERR0080，不能把此超时当作IMU坏。
5. 架空验收通过后，在受控平整开阔场地低速验证约90度落地转弯、转后直行及障碍停车，记录起止YAW、轮速、MODE/ERR、距离和S1停止。不要远程自动ARM。
6. 如修改RTL，重新建立当前输入的完整回归、导航/CPU原语模型、PNR/STA/SDF和PAD证据后，VM关闭时按持续授权直接烧录。写入/校验失败先诊断，不盲重试，不降级SRAM。真实断电启动和运动仍按每个新SHA单独验收。

## 关键文件

| 文件 | 用途 |
| --- | --- |
| AGENTS.md | 当前维护约定、授权和安全边界；A741/A744历史记录不代表当前实板 |
| output/refactor-autonomous-20261030/STATUS.json | 当前结构化状态及成功/失败烧录记录 |
| output/releases/fw74504/manifest.json | 当前发布位流SHA、60个编译输入身份与验收范围 |
| output/refactor-autonomous-20261030/TURNING-74504-PHYSICAL-ACCEPTANCE.json | 用户确认冷启动正常、能前进但BLOCK不转 |
| output/refactor-autonomous-20261030/TURNING-RELEASE-74504.json | 完整离线/实现检查、烧录及健康证据 |
| code/camera-car-control/a745-autonomous/rtl/a745_autonomy.v | 500mm停车、左右择路、陀螺仪转弯、等待与故障状态机 |
| code/camera-car-control/a745-autonomous/rtl/a745_navigation_scan.v | 完整扫描/新鲜度、方向距离、左右转向几何许可；近点立即撤销许可 |
| code/camera-car-control/a745-autonomous/scripts/generate_turn_envelope.py | 根据CAD生成左右0～90度扫掠凸包查表；prepare检查表与配置匹配 |
| code/camera-car-control/a745-autonomous/rtl/a745_turn_envelope.v | 5度方位区间保守半径表；40mm基础余量、6mm采样预留及外扩 |
| code/camera-car-control/a745-autonomous/rtl/a745_core.v | 传感器/控制组装、74504身份、后距和左右许可遥测 |
| code/camera-car-control/a745-autonomous/lib/a741_motion_feedback.v | 转后重新锁航向、±180度环绕、左右轮速同步；每轮PI另保留 |
| code/camera-car-control/a745-autonomous/rtl/a745_camera_boot.v | 明确上电/复位等待、官方SCCB引擎、有界重试和关键回读 |
| code/camera-car-control/a745-autonomous/rtl/a745_cpu_regs.v | 显式FF双组合读，防止PicoRV32寄存器被误映射同步SDPB |
| output/refactor-autonomous-20261030/capture_turn_blocks.py | 只接收诊断，CRC校验并列出左右扫掠包络内实际雷达点 |
| output/refactor-autonomous-20261030/TURNING-TEST-PROCEDURE.md | 架空选向与低速落地验收步骤 |
| PROJECT-CLEANUP.md | 已执行清理、保留内容和单个审批拒绝例外 |

## 决策和注意事项

- 当前前方停车阈值是雷达原点读数500mm，不是车头外壳到障碍的距离；F>800mm巡航120mm/s，501～800mm为60mm/s，恢复前进/侧方通路门槛600mm。
- 转向空间分别按左右扫掠几何检查，不再用全周521mm把两个方向都锁死。两侧都堵时BLOCK等待，不自动倒车；普通障碍等待可重新择路，真正传感器/CPU/编码器故障仍锁存。
- 陀螺仪相对目标90度，比例减速80→40mm/s，约87度停轮制动、SETTLE150ms，前方≥600mm后直行并锁实际新航向。当前没有卡尔曼滤波；IMU已有DLPF=3，不能将零偏积分或加速度计倾角称为卡尔曼，也不宣称消除长期航向漂移。
- 保留几何锁、倾斜、CPU、IMU、编码器、雷达新鲜度及S0急停；不以false path/全局切时钟或屏蔽保护掩盖问题。
- 上电不ARM。S1先释放再新按，启动LD06/静止校准，再按S1停止；S0复位急停。烧录持续授权有效，不重复问烧录权限，但必须核实真实VM关闭状态。
- 旧GND锁是旧固件内部锁低，不拆公共地。A18/A19→左LAIN1/2，F13/F14→右RAIN1/2，FPGA和驱动板共地。
- 保留800×480/33MHz、AB22 DE/AB21背光、P7 TY-OV5640自带晶振和32列安全区文字。用户已验收文字比例及74504真实冷启动，不再盲改显示接口。
- 网口只有TX，EMS1长度112；104..105后方距离、106 bit0/bit1左右几何许可、107扫描序号；实际选向还要侧方600mm，MODE9为SETTLE。
- 证据目录20261030是任务起始日期，真实本地日期为2026-10-31；Flash目录时间戳为UTC。原始programmer审计保持当时状态，后续物理确认另存，不篡改历史日志。
- .venv/.local为本机环境和缓存，不作为Git源码依赖。当前工程自带必要vendor/board文件，不依赖已删除旧应用缓存；发布位流有独立Git LFS路径。

## 运行和验证

在仓库根目录、已安装Gowin V1.9.12.04、WSL Ubuntu-26.04的Icarus12/Verilator5.032环境执行。新机器先git lfs pull，并创建code/camera-car-control/.venv；现有机器保留已有环境。这些构建命令更新本地构建证据，不会烧录或ARM。

```powershell
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/check.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/tests/check_protocol.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/tests/check_turn_geometry.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/build.py build --timeout 1800
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/check_cpu_gate.py
code/camera-car-control/.venv/Scripts/python.exe code/camera-car-control/a745-autonomous/scripts/check_navigation_gate.py
```

当前实现审查依次运行output/refactor-autonomous-20261030下inspect_implementation.py、audit_tft_sdf.py、audit_tx_sdf.py、audit_camera_input.py、audit_constraint_targets.py，再运行final_gate.py。final_gate写“待烧录”本地候选状态，不代表实板已改变；实际硬件以Flash审计和遥测为准。

只读诊断命令：

```powershell
code/camera-car-control/.venv/Scripts/python.exe output/refactor-autonomous-20261030/capture_turn_blocks.py --seconds 45
```

确认VM关闭、路径/SHA及当前检查后，才可使用scripts/fpga/program_flash.py的--program。不要为本次交接上传再次烧录或ARM。完整源码/清理记录/必要证据随同一main提交上传GitHub，后续用git log -1确认所在提交。
