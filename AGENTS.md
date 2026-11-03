# EdgeMind-Robot 维护约定

## FW74513 模式/任务联调（2026-11-03，已Flash，实物待验收）

本次用户明确授权继续实现、编译布线、Flash及debug，不再仅规划；允许访问4A/NPU。用户报告电机VM电源关闭。禁止电脑ARM/模拟本地按键，实物运动仍由本地S1启动。本轮实现、Flash审计及待验收记录纳入FW74513提交；未关机。当前不是74512。

当前Flash FW74513，SHA `9abe7916e6a23454f8108eca4b157802ec9297a54e7859484bc189f87467614c`；审计 `output/refactor-autonomous-20261030/flash/20261102T175648.955546Z/audit.json`，54@0写入/校验、Reprogram、74就绪及73 UserCode通过，最终0x70022020。44项RTL/Verilator、CPU、9导航/姿态+4任务+2显示独立Gowin原语、协议/272340点路径几何/旧转向几何/回放/后退模型通过。同次PNR-STA-SDF/PAD：setup/hold/recovery/removal/脉宽最差+1.020/+0.038/+3.945/+0.213/+1.122ns，违例0；RX裕量0.376ns、TX偏斜0.022ns/余量0.243ns、TFT余量2.815ns。独立叶模块原语不是整板网表执行。

已实现S2/B20下一模式、S3/A21上一模式，仅IDLE可选，S1/A20启停、S0复位。原厂例程核对595为MSB先发`{dp,低有效7段,高有效8位选}`，M18/C2/F4驱动数码管1/2/3。1几何绕障、四转局部回线；2有符号yaw累计约360°，全周包络；3本地ARM后接受ET10 UDP6106有限动作。每次转向前后150ms等待；任务单段0.5秒/200mm/约10°需STOP分隔，120秒或任一轮累计绝对约3m总限，往返不抵消；换目标STOP取消旧绕行。保留前300mm、后严格>350mm/100mm/2秒一次短退和全部真实故障联锁。左右扇区600mm门槛改为原CAD转向包络+新出口扫掠，不把侧500mm一概判堵。四转回线基于轮计数/航向，无全局定位或障碍地图，尚无实物精度。

保持摄像头→4A NPU→ED10框回传和HUD。新EMT1状态经6103发送。整个RX如今确实可达电机，不再沿用74512的全RX结构隔离；routed图证明仅ED10框/类别/分数数据不可达电机，更新/ready共享流控、诊断计数经TX RAM有保守可达路径，未声称这些隔离。校验正确的ED10端口/魔数任务拒绝及实际core模式1/2/未ARM联锁由回归覆盖。

4A最新20项主机测试通过，部署哈希逐文件一致，服务active。网页选类别、不做颜色辨别，多帧/高阈值/单实例确认。标定默认verified=false、target_lidar_observable=false，**自动接近禁用**；不能用估计fx/外参冒充标定，不能宣称寻物到达完成。换目标会清除旧实物雷达可观测性。距离关联至少3点、深度集中、框两侧断差；身体方位计算含相机偏移/yaw。当前台面透明瓶被设备遮挡，低分约0.3～0.4，不能降阈值强行确认。已请求用户将不透明较高实物放在地面开阔处，并提供高度/距离/雷达窗口高度，尚未回复。

45.020秒被动健康451状态/451姿态/451任务状态全74513/IDLE/ERR0000/未ARM/目标零；CPU/IMU/摄像头/DDR正常，224回传被接收，视频29.76fps、推理4.98Hz、网页14.90fps，无新增坏包/partial/缺行。早期并行测试曾有缺行，未掩盖，稳定窗口单独记录。后续主机对实际74513网页切目标也通过，未ARM。当前实体模式按键/数码管/新SHA实屏、冷启动、运动和寻物到达全部待验收，ERR0001根因仍未知。async已请用户只按S2/S3检查显示，不按S1，等回复；不可自动补运动验收。

入口 `output/motion-task-20261103/RESULT.json`、`FINAL-CONSISTENCY.json`、`HEALTH-74513-REVIEW.json`、`HOST-LIVE-74513.json`，操作 `code/camera-car-control/a745-autonomous/docs/README-MODES-AND-TARGET-74513.md`。STATUS保留真实实板；inspect写CANDIDATE-IMPLEMENTATION、final_gate写独立CANDIDATE，避免未Flash候选覆盖实板状态。主编译输入已冻结且哈希复核，无需因待实体反馈重复编译/烧录。开发中主动中止的前几轮产物不可烧录；最终同源完整门已通过并已烧录上述唯一SHA。

## 本次接手追加要求（2026-10-31）

用户明确要求前方停车线从50cm改30cm、解除编码器无脉冲超时停车，并选择“三方都堵先后退一小段，停稳后重新择路”。源码FW74507候选已实现：前方300mm；无脉冲1秒仅TX提示，非法四相跳变仍锁存；后方>350mm才以60mm/s后退，任一轮约100mm或约2秒止，停稳150ms，同一堵塞阶段仅尝试一次。其余联锁、侧方600mm与CAD转向包络保持。详见output/refactor-autonomous-20261030/CHANGE-74507.md。本节取代下文旧版50cm/禁止自动后退/无脉冲停车约定，不能把候选当作已烧录。当前实板和SHA仍以STATUS.json及真实审计为准。ERR0001未复现定位、未修复。

74507最终门已通过：28项RTL、协议、91080点回放、122536点旋转几何、后退安装模型、CPU门及4导航叶模块6项原语、同次PNR/STA/SDF/PAD。当前实板74507，SHA cde3af917fd0c4e711633a7b4d6fa020129aeec50fd3b0832ec5974bd066063f，setup/hold/recovery/removal最差+1.273/+0.043/+2.693/+0.353ns、违例0。真实Flash审计output/refactor-autonomous-20261030/flash/20261031T084753.897504Z/audit.json，54@0写入/校验、Reprogram、74只读就绪、73版本比对通过，最终0x70022020。30秒300状态/300姿态均74507/IDLE/ERR0000/未ARM/目标0，CPU/IMU/摄像头/DDR健康，发送包0；记录imu-fault-20261031/74507-health-20261031.json。新SHA实屏、运动、真实冷启动仍未验收。

用户本次已再次确认VM关闭、轮子架空，并明确“以后不要我提醒直接烧录”。后续同类任务在持续授权、验证和已知VM关闭条件均满足时直接Flash，不重复问权限或等待用户再次提醒；只有物理状态已变化或未知时才核实条件。上电不ARM，禁止电脑启动运动。旧导航门临时目录删除被自动审批拒绝，已保留，使用新生成目录完成检查；不绕过重试删除。

## FW74506 阶段交接记录（当前实板已更新为上节74507）

活动工程code/camera-car-control/a745-autonomous，main分支，HEAD ac56a9e。上次交接与远端清理已推送该提交，本次74505/74506代码、证据及文档尚未提交推送。用户最新要求先写交接文档和提示词；交接任务不再启动运动测试，不关机。完整入口.agent/main/handoff.md、HANDOFF-20261031.md、NEXT-AI-PROMPT-20261031.md和output/refactor-autonomous-20261030/STATUS.json。

用户已确认74505能跑能转；后续平地直行偶发FAULT/ERR0001，S1可再启动。最新澄清为架空正常、落地触发，替代先前组合选项可能导致的架空必现推断。车太重是猜测，未确认原因。74505故障后900个状态全FAULT0001、总线错误0、样本年龄0～10ms，但未捕到触发边沿，不能拿恢复后的正常角度排除瞬时异常。

当前已固化FW74506诊断版，UserCode0xA745，位流code/camera-car-control/a745-autonomous/.local/gowin-a745-autonomous/impl/pnr/a745.fs，SHA-256 b5cb8e927ebd07fccbaa1dde327acde91f565e7d8b698bc2862bd7a9c93d3a1a。真实Flash审计output/refactor-autonomous-20261030/flash/20261031T075334.673715Z/audit.json，54@0写入/校验、Reprogram、74只读就绪、73版本比对通过，最终0x70022020。

74506仅锁存ERR0001原因、有效标志和触发roll/pitch，并输出IMU驱动诊断，未削弱停车保护或22.5度阈值。尚未用74506复现落地故障，ERR0001未解决，不把诊断版写成修复版。原因bit0..3为IMU航向无效、原始gyro采样无效、倾角无效、超倾角；EMS26/27和EMF42/43为原因/标志，EMF44..47为触发角度，EMF32..35为当前驱动诊断。详见output/refactor-autonomous-20261030/imu-fault-20261031/DIAGNOSTICS.md。

被动健康74506-health.json确认实际74506，120状态/120姿态均IDLE/ERR0000、未ARM、目标0；CPU递增、摄像头首试初始化、DDR/完整帧正常、IMU错误0，发送包0。WHO0x70、地址0x68（MPU6500兼容路径）。新SHA屏幕实物、运动和真实冷启动尚未验收。74504冷启动、74505运动确认均不可直接套给74506。

用户在74506烧录前最新确认VM关闭、轮子架空，之后没有启动运动。后续如再测试，在下一次重载前更新VM关闭确认。先用capture_imu_fault.py只接收故障，受控落地复现后关VM、保留FAULT、不按S1，再读取锁存原因修对应路径。不能盲增PWM、放宽倾角或屏蔽valid。

26项RTL/Verilator、独立协议、91,080点真实雷达回放、122536个旋转边界点几何检查通过；同源CPU证据哈希复核，4个导航叶模块5项Gowin原语执行通过（含imu_fault_latch_tb）。叶模块独立综合不是整板跨层优化网表执行。一次120秒子模块综合超时后改300秒，主编译结束后单独重跑通过；报告文件偶发Errno22，TX/约束报告采用临时文件原子替换后审查通过，没有降低检查。

## 当前运动逻辑

74505在导航前做两点前视的LD06近距点资格检查。弱反射且不足3个邻接点的细物体可能被过滤，必须单独低速验收；不可宣称可检测所有物体。capture_turn_blocks.py已按实际revision分别报告原始与资格检查后的阻挡点。

FW74507：F≤300mm立即禁止前进，F>800mm为120mm/s，其余可前进区为60mm/s。先停100ms，再按左右≥600mm通路和各自CAD转弯包络选路，两侧都通选更远一侧。前方≤300mm且两侧都堵、后方>350mm才以60mm/s后退，任一轮约100mm或约2秒止，停稳150ms重新择路；同一堵塞阶段只尝试一次，后方未知/近障保持等待。车身按0～90度左右扫掠凸包分别检查，含40mm基础余量和角度离散/查表预留，不再采用全周521mm锁转条件。模型验证不能替代实际安装/制动验收。

转弯陀螺仪目标90度，比例减速80→40mm/s，约87度撤销转动并停稳150ms，前方≥600mm才恢复直行并锁定实际新航向。直行航向差正确处理±180度环绕，并配合左右轮速同步和每轮速度PI。未实现卡尔曼滤波，不宣称消除长期航向漂移。转弯无航向进度4.5秒或明显反向时ERR0080锁存停车；架空时车身不转，测试必须约2秒按S1停，不把超时误判为烧录丢失。

S1先释放后新按启动LD06和静止校准，再按S1停止；S0复位急停。保留几何、倾斜、CPU、IMU、编码器和雷达失效联锁。普通障碍等待可以重新择路，真实传感器故障仍锁存。旧GND锁是FPGA内部锁低，不拆公共GND；A18/A19→左LAIN1/2，F13/F14→右RAIN1/2，FPGA与驱动板共地。

## 烧录和验证

持续Flash授权有效；核对明确路径/SHA及同源回归/同次PNR-STA-SDF/PAD，直接使用scripts/fpga/program_flash.py完成54@0/校验/Reprogram/只读就绪/版本比对并保留真实日志，不重复问权限。VM在烧录和重载时关闭，不自动ARM。写入/校验失败停查，不盲重试，不降级SRAM。

当前28项RTL/Verilator、独立协议、122536个旋转边界点几何检查、后退模型、同源CPU网表检查和导航四模块6项Gowin原语网表执行通过。导航网表为同源独立综合并保留全部可观测端口；主工程跨层优化，不能把独立模块执行写成整板网表执行。主工程SHA绑定，并检查转向表未误映射同步RAM。

当前PNR setup/hold/recovery/removal违例0，最差+1.273/+0.043/+2.693/+0.353ns；TFT按10ns输入预算及板线1ns、时钟0.3ns预留审查，TX偏斜和DVP延迟通过。属于器件模型，不是实测。不全局切时钟组或用false path掩盖问题。CPU显式FF寄存器和原监督固件/看门狗必须保留。

## 显示和网口

保留800×480/33MHz扫描、AB22 DE/AB21背光、P7 TY-OV5640自带晶振。文字32列在实拍480×272安全区，用户已验收比例；新SHA实物观察另记。D0时钟、D1摄像头、D2PHY、D3DDR、D4完整帧、D5摄像头/DDR错、D6溢出、D7运动故障。

网口只有UDP状态/姿态/雷达TX，无RX控制、ARM、配置或网络续约。新状态104..105是后方距离、106 bit0/bit1左/右转向几何许可、107扫描序号；实际选向还需侧方600mm通路，MODE9为SETTLE。

## 清理

清理351目标、18685文件、15918936378字节已实际完成，保留当前A745、PCB/CAD、V5所需5个基础几何/核验输入和.git。见PROJECT-CLEANUP.md、CLEANUP-RESULT/VERIFY.json。不要恢复旧备份、重跑已完成清单或新建备份包。本次交接提交包含当前源码、必要证据和清理删除记录，按用户要求同步推送远端main。

单独例外：后续删除旧74502暂存flash/20261030T161323.218749Z/image.fs被自动审批以blocked by policy拒绝，仍保留，未绕过重试。不要把该例外写成主体清理未执行，也不要写成所有后来生成暂存镜像均已删除。

## 最新状态：FW74508（2026-10-31）

FW74508 已完成外部 Flash 写入/校验、重载、就绪和 UserCode 比对。实板 SHA-256 `899034472dc21c4f39669929d592031e9521faabf2b6718ffb9ee83ab8813690`；审计 `output/refactor-autonomous-20261030/flash/20261031T092737.270324Z/audit.json`；最终状态 `0x70022020`。被动健康 `output/refactor-autonomous-20261030/imu-fault-20261031/74508-health-20261031.json` 有 300 状态/300 姿态，均 FW74508、IDLE/ERR0000、未 ARM、目标为零，CPU/IMU/摄像头/DDR 正常。

姿态层新增最近三个完整 roll/pitch 对按最大绝对倾角取中值，抑制单次加速度/振动尖峰；22.5° 阈值、valid 和真实倾斜停车保留。29 项 RTL/协议、回放、几何、CPU、8 项导航/姿态原语模型和同次 PNR/STA/SDF/PAD 已通过。运动、显示和真实冷启动未验收，`application_verified`、`err0001_fixed`、`root_cause_confirmed` 仍为 false。用户已确认 VM 关闭，烧录后未 ARM。

## 当前接手：FW74510（2026-11-02，Flash完成，运动待验收）

用户最新限定只处理FPGA运动，不访问荔枝派、不处理NPU。当前源码基线main/a48af99含FW74509的EV10按行视频；不能回退整个工程到74506或用旧74508状态冒充当前板卡。20个视频/摄像头/时钟/引脚文件与HEAD一致，见output/motion-20261102/VIDEO-INPUTS.json。

74510恢复被74509改为UTURN的100mm/2秒短退，保持前300mm、左右600mm/CAD转向检查、后方严格>350mm才60mm/s后退、停稳150ms、同一堵塞阶段仅一次。任一轮正反方向计数达到约100mm均停。屏幕BACK/REPLAN状态及ERR0001的SRC和故障时刻R/P快照已加入。保留三样本完整倾角对中值、22.5度和全部真实故障保护；ERR0001未确认根治，当前用户还不知道运动具体症状。

最终候选SHA-256为300b43a93a5e0cb259b0e139b9b50e9460643b53ae3ec1533d7310ced2996513；30项RTL、8项原语、协议/回放/几何/CPU及同次PNR-STA-SDF/PAD终检通过。setup/hold/recovery/removal最差+0.720/+0.045/+1.984/+0.322ns，违例0；TX偏斜0.023ns、裕量0.242ns。最后PNR仅改SDC，综合网表b1dc147a96b30f7766214039c828e29c72a90e69d824e43b5519ad517295a815前后不变并与原语回执绑定。时序脚本已修复漏解析文本路径表的问题，前两份失败候选未烧录；FIFO保持指针约束引用改为wr_ptr_sync_commit_reg，网口采用粗略绝对到达限制并强制完整SDF相对偏斜及Q至引脚独立预算，不能只看粗略限制。

20261102T062454.950796Z真实Flash尝试返回50，未完成写入/校验或重载；审计在output/refactor-autonomous-20261030/flash/20261102T062454.950796Z/audit.json。随后只读扫描无有效JTAG目标，Windows未枚举到FTDI；未重试写入、未降级SRAM。用户VM关闭、轮子架空，已请求重新连接下载器。恢复连接后先只读扫描，再按持续授权烧录同一已通过候选；无须再问权限。新SHA的显示、冷启动、运动均未验收，不自动ARM。当前入口output/motion-20261102/CHANGE-74510.md、IMPLEMENTATION.json、JTAG-CONNECTION.json及output/refactor-autonomous-20261030/STATUS.json。没有本机FPGA直连网口遥测，不得为取遥测而违反用户限定访问4A；后续可用本机TFT的SRC与锁存R/P定位。

上述连接故障已于2026-11-02恢复：用户重新确认FPGA通电、VM关闭、轮子架空；只读扫描识别FT2CH/0/548和唯一ID0x0001481B，预烧录终检再次通过。真实Flash审计output/refactor-autonomous-20261030/flash/20261102T090916.626313Z/audit.json已确认54@0写入/校验、Reprogram、74只读就绪及73 UserCode比对全部通过，最终状态0x70022020、UserCode0xA745，实板加载镜像SHA为上段300b43a9…96513。当前不再等待下载器连接，正在等待用户本地冷启动与架空S1启停验收，再做受控落地测试；显示、运动、冷启动、ERR0001根治均不可提前记为通过。未访问4A、未发送运动命令、未自动ARM。

## FW74511接续（2026-11-02，冷启动及本次运动验收通过）

用户已确认74510真实冷启动和画面文字正常，随后落地运行ERR0004；已重新确认VM关闭、轮子架空、FAULT保留，编码器VCC为3.3V（用户报告，未实测）。74510运动验收未通过，不能写成ERR0001/0004已根治。见output/motion-20261102/ACCEPTANCE-74510.json。

ERR0004是左右非法AB跳变累计>64，不是无脉冲停车。旧三拍同步后直接译码的短毛刺误累计已执行失败用例确认。74511候选加入50MHz下100次稳定AB采样、约2us的完整二位向量过滤，保持真实四倍频/正反转及稳定非法跳变>64停车，未增阈值、未清零累计。故障时锁存左右15位饱和错误计数，在本机TFT显示ENC:L/R/LR及十六进制L/R，0041即65。使用EMF原保留位，旧tilt valid bit0和所有原字段不变，旧接收器兼容测试通过。物理毛刺、接触、供电/共地等根因还未测定。

31项完整RTL/Verilator和9项同源Gowin原语通过，新增quadrature_filter_tb；视频3帧/1440包零错误，20个视频/时钟/摄像头/引脚文件保持。同次PNR-STA-SDF/PAD及最终门通过，setup/hold/recovery/removal最差+0.554/+0.043/+1.734/+0.356ns，违例0；TX偏斜0.023ns、剩余裕量0.242ns。更新证据副本时曾遇Windows临时文件锁，核对可写权限后重新归档成功，未跳过哈希或时序检查。

当前已固化并从Flash重载FW74511，SHA为9b9bfb97b32df6e70a4a186caa35ede5332ee0aec3a17cd145df13a6b7d167a9；审计output/refactor-autonomous-20261030/flash/20261102T094504.939045Z/audit.json，54@0写入/校验、Reprogram、74就绪、73 UserCode比对通过，最终0x70022020。当前尚待新SHA的本机显示、架空/落地运动及真实冷启动验收；ERR0004和ERR0001均不可提前宣称根治。用户确认VM关闭后直接烧录，未自动ARM。已请求先看IDLE/ERR0000、架空2秒启停，再空旷平地最多5秒本地S1测试；若0004，关VM保留FAULT并读ENC标记和L/R十六进制计数；若0001，读SRC和触发R/P。用户要求持续只处理FPGA，不访问4A。详见output/motion-20261102/CHANGE-74511.md、IMPLEMENTATION-74511.json和output/refactor-autonomous-20261030/STATUS.json。

最新用户验收回复为“架空和落地均正常，S1能停止”。74511短时架空/落地直行与S1停已通过，画面正常作为成功组合测试的前置条件记录，未拍照或独立采集应用遥测。见output/motion-20261102/ACCEPTANCE-74511.json。仅此范围通过，不把约5秒地面测试扩写为长时间稳定、转弯/后退或新SHA真实冷启动通过；err0004_fixed、err0001_fixed和硬件根因确认仍为false。接下来核实新SHA完整断电冷启动，以及累计20～30秒可分段的地面直行。无需重编译或重新烧录，禁止电脑ARM，仍不访问4A。

最终用户进一步确认“冷启动正常，IDLE/ERR0000”和“累计运行正常，S1能停止，未报错”。新SHA的完整断电冷启动、画面、架空/落地直行、累计约20～30秒可分段地面运行及S1停止已验收通过，记录已更新至ACCEPTANCE-74511.json、IMPLEMENTATION-74511.json和STATUS.json。本次报告的ERR0004回归验收通过，err0004_fixed=true仅指这个已验证范围；没有实测电气毛刺波形或根因，不宣称长时间绝不复发。旧ERR0001在该段未出现，但err0001_fixed和电气根因确认仍false。本SHA的自动转弯/短退没有重新做物理验收。当前没有待完成的本次直行回归操作，不再编译、烧录或自动运动；未获新指令前不转做4A/NPU或推送远端，不关机。

## 4A 视频识别恢复（2026-11-02，本次用户已明确重新授权访问4A/NPU）

本次任务由用户明确要求连接192.168.40.101（debian）修复 /home/debian/fpga 的推理，用户授权自行决定分辨率/帧率，取代前一轮仅运动/不访问4A的任务范围。未编译或烧录FPGA、未电脑ARM、未运动、未提交推送、未重启/关机；原74511运动验收状态保持。

已部署量化YOLOv5n的TH1520 NPU检测，浏览器 http://192.168.40.101:8090/ ，640×480预览目标15fps、640×384 NPU输入目标5次/秒。等比512×384后左右各64灰边，框完整逆映射。修复Python往文件路径协议的daemon写tensor导致双向pipe_write死锁；新增真实启动/读写超时和失败恢复；新C源码纠正YOLOv3 exp宽高解码为YOLOv5 sigmoid平方、分类NMS；用现有合法npu/shl.hhb.bm序列化模型（SHA c343b37b699fd4b5d87373c2931612d3c4a57edc484739224b978021a42fafad）。新daemon SHA 2924174b20817bca424d426c53e979fe2f7e1c990d3f0f4c4c4d8002054e91a3。

发现默认rmem_max=212992导致UDP socket丢包，已持久化16777216，实际SO_RCVBUF内核双倍计账33554432。最终60.078秒299次推理，摄像头29.761fps、网页14.947fps、识别4.977次/秒，bad/partial/missing均0、推理错误0；另连续解码60张真实MJPEG、56个不同JPEG确认实时。7项协议/超时/颜色/几何测试通过，NPU真实原始头独立NumPy解码对照3person+1kite吻合；SIGSTOP模拟NPU卡住后5秒超时且自行恢复，网页不中断。

服务采用已有用户systemd fpga-video.service并启用linger。驱动OCM1MiB/792MHz、modules-load和接收缓冲已设持久化；未重启4A，真实冷启动仍未验收。COCO外类别和模型精度未做标注集验收；不是通用多模态大模型，不宣称任意物体准确识别或修复CPU ONNX SIGILL。入口host/README-video.md及output/vision-inference-20261102/RESULT.json；源码/配置已逐文件比对本机与4A哈希一致。


## 检测框回传 FPGA TFT（2026-11-02，FW74512 已烧录、实屏通过）

本次用户明确授权4A推理结果回传FPGA显示、编译布线及直接Flash；用户确认VM关闭、电机驱动断开。未自动ARM、未发送运动指令、未运动、未关机。原运动逻辑、22.5度与编码器过滤保持，74511运动验收不能套给新SHA。

FW74512增加RGMII RX、MAC FCS/RX_ER整帧检查及UDP6105 ED10显示元数据解析（固定MAC/IP、IP/UDP校验和、非分片、长度、字段、坐标、序号检查），最多8框。parser50MHz，经整帧FIFO和握手邮箱跨域，33MHz场消隐原子更新，约1秒过期清框。640×480推理源裁自本机800×480的x80..719，显示框x+80；绿色2px框位于原HUD下面，类别/分数在网页。叠最新本地视频、有推理延迟、非逐帧锁定；没有回传整帧JPEG或运动命令。EMS1 byte23为模256接受计数，只用于遥测；真实routed原语可达分析确认RX数据不能到四电机输出。

已部署4A静态邻居systemd+NetworkManager dispatcher，主机每成功推理回传，空结果清框，发送错误隔离。保持NPU640×384/5Hz、摄像头640×480、网页15fps目标。调试曾暂关end1 TX checksum offload，现已恢复原值1，AUXDATA识别本机抓包的checksum completion pending，不能把NIC完成前seed当坏包。源码哈希HOST-HASHES.json一致。

用户提醒布线优化文档；从ac56a9e^的TIMING-FIX-20261027.md、旧TIMING-CLOSURE.md及USER-OPTIMIZATION-IDEAS-1.md找到历史依据，已整理到当前docs/TIMING-CLOSURE.md并加README链接，未恢复旧工程。PLL直出125MHz时setup/hold虽通过，RAM最小脉宽-0.068ns不放行；现prepare仅将生成PLL副本ODIV1从6改3，以250MHz经专用CLKDIV/2生成125MHz，去掉强制BUFG。最终place2/route2/clock_route_order1，37项RTL、9项导航/姿态及2项显示独立原语、CPU/协议/回放/几何、同次PNR/STA/SDF/PAD全部通过。最差setup/hold/recovery/removal/脉宽+0.247/+0.038/+3.208/+0.348/+1.122ns，违例0；RX两沿三PVT最差裕量+0.376ns，TFT+2.815ns。独立叶模块执行不是整板网表执行。显示综合脚本曾在生成结果后等待退出超时，显式Tcl exit后完整重跑通过，未跳过执行。

真实Flash审计output/refactor-autonomous-20261030/flash/20261102T142044.944132Z/audit.json：54@0写入/校验、Reprogram、74只读就绪、73 UserCode通过；最终0x70022020，UserCode0xA745。实板SHA888761b35c206f21d920bb192c920d785f3606ed9b2b73b64ff488a354bf4256。60.000秒600状态/600姿态全74512/IDLE/ERR0000/未ARM/目标零，CPU/IMU/摄像头/DDR健康；299次推理/299回传，状态采样首尾接受计数增298，摄像头29.77fps、识别4.98Hz、网页14.92fps，无新增坏包/不完整帧/缺行或推理错误。

用户本地回复“有绿色框，参数文字正常”，新SHA显示验收通过。application_verified=true仅限本次检测回传/显示及被动健康；新SHA完整断电启动、运动仍未验收，ERR0001根因未确认。入口output/detection-display-20261102/RESULT.json、DISPLAY-ACCEPTANCE.json及最新STATUS.json。持续Flash授权保留；本任务已完成，不为补做运动而自动ARM，不擅自推送远端。
