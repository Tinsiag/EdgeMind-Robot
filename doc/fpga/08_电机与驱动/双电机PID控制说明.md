# 双电机 PID 控制

## 当前交付状态（2026-09-13，时序收敛续作）

已核实 RPM 多周期优化此前就已完成。此前 RPM 优化后的真实报告为 Fmax=25.339MHz、setup slack=-19.464ns，瓶颈是 PID IP 输出 → adapter 命令寄存器的组合缩放，并非 RPM 周期相加。此次将 `dual_pid_adapter` 的精确缩放改为流水线，保护的 PID IP、`pid_input_processor`、`tb6612_motor_driver` 和 RPM/遥测 RTL 均未改动。

实际 ModelSim 八项自检全部 PASS；adapter 额外遍历全部65536个 signed16 输入，连续每拍左右交替，覆盖默认及32767全幅参数、流水线各阶段停止撤销、禁用与复位。默认数值与原公式完全一致；延迟增加4拍（80ns），吞吐率仍为每拍一个输入。

Gowin V1.9.12、GW5AT-LV138PG484AC1/I0、50MHz/20ns 当前源码综合及P&R结果：

| 项目 | RPM优化后、adapter修改前 | 本次adapter流水化后 |
|---|---:|---:|
| Actual Fmax | 25.339MHz | **77.836MHz** |
| 最差 setup slack | -19.464ns | **+7.152ns** |
| setup 违例端点 | 32 | **0** |
| setup TNS | -614.725ns | **0.000ns** |
| 最差 hold slack | — | **+0.237ns** |
| hold 违例端点 / TNS | 0 / 0.000ns | **0 / 0.000ns** |
| 整体 LUT / Register / ALU | 3162 / 2851 / 258 | **2666 / 2905 / 309** |
| adapter LUT / Register / ALU | 656 / 34 / 0 | **85 / 88 / 51** |

报告目录：`sim/out_closure/2026-09-13T12-05-22-874Z/`，含源码快照、`source-sha256.json`、`shell.log`、`summary.json` 和 `impl/pnr/PID_tr_content.html`。本轮最差setup路径转移到遥测文本编码 → `tx_byte`，已满足20ns。没有加入false/multicycle约束。综合仍有原IP/遥测截位告警；adapter两处15bit赋值截位受LIMIT/CEILING≤32767约束，默认及全幅参数的完整signed16回归已验证，不宣称零告警。

可复现命令（Node 24，无需Bun）：

```powershell
# 如果当前终端未继承本机已配置的ModelSim许可证：
$env:MGLS_LICENSE_FILE = [Environment]::GetEnvironmentVariable('MGLS_LICENSE_FILE','Machine')
node sim/run_tests.ts
node sim/run_closure.ts
```

`run_closure.ts` 每次创建独立目录，记录源码SHA256，检查50MHz综合参数、实际SDC、P&R完成和报告setup/hold违例；内部时序失败返回非零。`sim/out_closure/latest.json` 指向最新结果，同时列出未分配IO。历史比较脚本仍保留，不必为每次验证重跑旧基线。

**内部寄存器时序已通过，板级交付尚未完成。** 仍只有clk有实际引脚约束，另外15个信号及电气资料见 `constraint/PINOUT_PENDING.md`。当前自动生成的fs/bin不能作为上板文件；拿到板型、排针原理图、实际接线和接口电平后，补全IO并重新P&R，再进行上板验证。下方“上一轮”段落保留历史记录，不代表当前时序仍失败。

## 层级与接口

```text
src/top.v（薄包装）
└─ robot_top（系统整合；后续 vision/sensor 仲裁在此扩展）
   ├─ UART_controller / UART_driver
   └─ motor_control
      ├─ 2 × RPM_reader
      ├─ PID_Input_Processor → 原四通道 PID_Controller_3p3z_Top
      └─ dual_pid_adapter → dual_motor_driver → 2 × tb6612_motor_driver
```

- 顶层输入：`clk`（50 MHz，20 ns）、低有效 `rstn`、`enc0_a/b`（左）、`enc1_a/b`（右）、`uart_rx`。
- 顶层输出：`uart_tx`；左右各自的 `*_in1`、`*_in2`、`*_pwm`、`*_stby`。两片 TB6612 的 STBY 必须独立接线，未合并为总使能；未使用的芯片通道须由硬件安全处理。
- `motor_control` 接收 `target_valid/target_channel[2:0]/target_rpm signed16`，以及左右独立 `enable/stop`；暴露两路 RPM 数据/valid 与原始 PID 数据/channel/valid 供遥测使用。
- `robot_top` 当前将左右 enable 置 1，但上电/复位仍由 stop 和 adapter 的有效数据标志保持安全。外部 enable/stop 应同步于 clk。
- 仍初始化、调度 PID 的全部四个通道。ch0 左、ch1 右；ch2/3 目标和反馈保持 0，输出忽略。输入目标先过滤无效通道。外围 3-bit 与真实 IP 2-bit channel 仅在 `motor_control` 显式截取/补零转换。

## 标度及停止语义

原 PID 上下限仍为 ±1023。adapter 保持下式的整数结果：

`cmd = clamp(u, -1023, 1023) × 26214 / 1023`

整数除法向零截断；默认端点 ±26214，约为 signed16 满命令的 80%；0→0，±1→±25，没有 20% 起转底座。`PID_LIMIT` 限定到 1..32767，`MAX_CMD` 限定到 0..32767。adapter 使用无符号幅值限幅、30bit 乘积和最后符号恢复，-32768 的幅值先限到不超过32767；底层没有新增修正。五级流水每拍可接受一个输入，从接受沿到发布沿相隔4拍（50MHz下80ns），原接口不变。默认除以1023使用三段10bit数字折叠及比较修正，与原公式精确等价；其他参数使用常数无符号除法，但本轮50MHz物理时序结论只针对工程默认参数。

驱动接口**保持 signed16 motor_cmd，而非幅值＋方向端口**。幅值与方向在原 `tb6612_motor_driver` 内部转换。单独使用 dual_driver 时调用方必须排除 -32768。默认 PWM 20 kHz；实际占空受原核心 `(abs(cmd)*(PWM_PERIOD-1))>>15` 量化影响，不等于精确 80%。支持的 PWM 周期应为 2..65536，时钟/PWM 参数须为正。

左右 stop 或 enable=0 优先于同拍有效 PID 输出，各自清缓存、撤销有效标志、禁用驱动，并清除adapter流水线中该侧的在途命令；不会影响另一侧。恢复后需要该侧有效 PID 输出才能重新使能。原底层输出是时钟寄存器，STBY 在下一时钟沿响应，PWM 使用上一拍 duty；测试留出合理时钟延迟，不宣称组合式立即关断。

**停止不清 PID IP 历史，不撤销 PID IP 内部在途运算，也不能保证恢复后的第一个输出来自停止后提交的目标。** 暂停仅约束执行端；本阶段不实现 PID IP 事务代际标记、PID anti-windup 或 IP 历史重置。

## UART 保持原协议

115200 baud、8N1：`0x91` 进入设置模式，反复发送高 byte `{channel[2:0], rpm[12:8]}` 与低 byte `rpm[7:0]`；RPM 为 signed13（-4096..4095）。只接收 ch0/1；其他 channel 的完整高低 byte 被消费但不更新目标/stop。**仅等待高 byte 时的 `0xff` 表示退出**；低 byte 的 `0xff` 仍是数据。

RPM -3..3 停止，±4 及之外运行；ch2/3 stop 始终为 1。停止目标保留原数值，不另改写为零。遥测格式不变，标签 0/1 已改为实际 ch0/1 的原始 `u/rpm`（不是归一化驱动命令）。遥测现在使用一个共享的 26 步恢复除法器 `signed_divider_seq`，原 `signed_divider.v` 不改并作为等价参考。每 500000 个时钟（100 Hz）捕获最新保持的左右 u/RPM/stop，左右依次计算、双路原子提交；同拍 valid 使用拍前保持值。在途输入改变不影响该批结果，stop 的执行端控制不依赖遥测。UART 每帧开始锁存左右结果，每个 byte 保持整个发送过程。格式严格为 `0+ddd.ddd 1+ddd.ddd\n`，20 bytes，无 CRLF。100 Hz 只控制计算频率；保留 `CLK_FREQ/(11*OUTPUT_RATE)` 的 byte 调度约定，默认 OUTPUT_RATE=8，非强制 100 帧/秒。

除法符号为 A[15] xor B[15]；幅值等于 `floor((abs(A)<<10)/abs(B))` 低 19 位，整数低 9 位回绕，不饱和。显式 17 位绝对值支持 -32768，除零幅值为 0 但保留符号（负零），stop 强制正零。小数转换仍为 `floor(frac*1000/1024)`，因此 1/10 显示 0.099。恢复除法是 26-bit 分子、16-bit 除数、17-bit 试减余数，没有变量 `/` 或 `%`；文本编码只有常数除法。`UART_send.tx_done` 在停止位开始出现，发送端另用完整 10-bit 时间保护，不能据 done 提前覆盖数据或截断停止位。

## 原代码保护与工程

- `src/tb6612_motor_driver.v`、`src/pid_input_processor.v`、整个 `src/pid_controller_3p3z/` 保持原样；本轮经授权只重写 `RPM_reader` 内部，全部原输入输出和前三个参数保持兼容。遥测除法核心、协议、左右独立 STBY 不改。
- `reference/top_author.v` 是修改前作者 `src/top.v` 的逐字节备份；根目录 `top.v` 原副本保留不动。
- `src/pid_output_processor.v` 原内容保留；`reference/pid_output_processor_old.v` 是原内容归档副本。两者及作者 top 都不在新编译清单中，避免同名模块冲突。不要对仓库所有 `.v` 做递归通配编译。
- `PID.gprj` 仅包含新链 RTL 和原综合 IP `.v`，不含 TB/旧输出链；`PID.mpf` 使用 `src/top.v`、真实仿真 IP `.vo`、GW5A primitives 和八个自检 TB，依赖完整。
- 用户截图确认 U2=50M_Active，FPGA_GCLK1 为 Y18 / Bank4，VCCO_4=3.3V；`constraint/top.cst` 仅约束 clk 为 Y18/LVCMOS33，`constraint/top.sdc` 为 `create_clock -name clk -period 20.000 -waveform {0 10} [get_ports {clk}]`。gprj 分别使用 `file.cst`/`file.sdc`。没有猜测其他 IO，没有 false/multicycle 掩盖时序。
- 50MHz 参数从 top→robot_top→motor_control、UART_controller/driver→UART_recv/send 传递；PWM=20kHz、PID_FREQ=1500 保持。上一轮由 motor_control 的 64-bit 参数覆盖绕过原 reader 常量溢出；本轮 reader 自身使用 `64'd60*CLK_FREQ/PULSE_PER_REV`，独立实例传入普通 50MHz 整数也正确。
- **仅 clk 有引脚约束，其他外部 IO 未约束，不能安全下载；综合成功不等于布局布线/时序或板级电气验证通过。**

## 可复现自检

安装有效 ModelSim 许可后，在项目根执行（Bun 为执行脚本的运行时）：

```sh
bun sim/run_tests.ts
```

默认工具路径 `F:/modeltech64_10.6d/win64/{vlog,vsim,vlib,vmap}.exe`，库路径 `F:/Gowin/Gowin_V1.9.12_x64/IDE/simlib/gw5a/prim_sim.v`。可用环境变量 `MODELSIM_BIN`、`GOWIN_PRIM` 覆盖。脚本自动创建独立 `sim/out_rpm/tests/` 工作库、映射、宏和日志，不触碰原根目录 work/WLF。每个工具进程最多 180 秒；各 TB 另有仿真时间 watchdog；退出码和 PASS 标记/错误文本共同判定，任一失败返回非零。

本次实际运行结果（ModelSim SE-64 10.6d，2026-09-13）：

| 自检 | 结果与覆盖 |
|---|---|
| dual_motor_driver_tb | PASS：独立 STBY、两种方向、零、±32767、整周期占空计数、单侧禁用、复位 |
| dual_pid_adapter_tb | PASS：完整 -1023..1023 共 2047 个值、饱和、-32768→-32767、零/无底座、ch2..7 忽略、stop/enable 优先与恢复等待 |
| motor_control_tb | PASS：真实 IP 四通道初始化/输入/输出、正负响应、独立停止/禁用、两个真实 encoder reader 数据与 valid 捕获 |
| robot_top_tb | PASS：通过 src/top 的引脚级 UART 收发输入、真实 IP 到驱动、signed13 两端、低 0xff、高 0xff 退出、ch2..7 过滤、-3..3 与 ±4 |
| uart_driver_tb | PASS：真实 500000-cycle/100Hz 间隔、双路原子提交、同拍 valid、在途 stop/输入变化、两帧共 40 个 UART 引脚解码 byte、整 byte 数据稳定 |
| signed_divider_seq_tb | PASS：与原组合除法 1101 次比较（100 个边界组合＋1000 随机＋复位后 1/10），含 -32768、除0、负零、511/512/513 回绕，26 步、busy 输入隔离、done 单拍、异步复位 |

| rpm_divider_seq_tb | PASS：32步固定时延、33bit最大分母/零除/最大分子、200组随机参考、busy期间start及操作数变更、done单拍、复位取消 |
| rpm_reader_tb | PASS：首次完整资格、正反转精确周期与数值、超时饱和/恢复、反转/异常同拍边沿/在途超时失效、tick同拍旧快照、实际默认500000拍间隔 |

RTL、IP、GW5A 库均编译成功；最终八项仿真全部 PASS。结果在 `sim/out_rpm/tests/results.txt`，详细 `compile-*.log` 和各 TB `.log` 可复核。使用真实 `.vo` 与 GW5A primitive，没有 mock PID、没有 force IP 输出。所有 TB 时钟为 20ns；motor_control 使用实际 50MHz/20kHz/1500Hz 参数，dual_motor_driver 测量完整 2500-cycle PWM 周期（满幅 2498 高拍，半幅 1249 高拍）。UART TB 为缩短仿真仅将 OUTPUT_RATE 改成 80，计算间隔仍为真实 500000 拍。

## 上一轮遥测优化历史记录（不是本轮 RPM 基线）

```sh
bun sim/run_synthesis.ts
```

脚本使用本机官方 SUG1220 Tcl 接口（gw_sh 的 stdin console，`open_project`、`set_option -global_freq 50`、`run syn`），在 ignored `sim/out_50mhz/before/`、`after/` 中运行，绝不覆盖原 `impl/`。before 是中止前保存的真实工作树快照，不是历史 100MHz 报告或 git HEAD；两侧统一当前 top/robot_top/motor_control/UART_controller、UART_send 时钟参数覆盖、器件和约束。快照不在 git 中，若缺失脚本明确失败，不伪造 baseline。官方手册确认参数名是 `-global_freq`，脚本强制检查生成 PID.prj 的 `global_freq=50.000`，避免误用无效的 `-frequency` 后静默保持 100MHz。

2026-09-13 本机 Gowin V1.9.12 两侧综合实际成功（均有既有/截位告警，不是零告警），同一 GW5AT-LV138PG484AC1/I0、50MHz：

| 层级/资源 | before | after |
|---|---:|---:|
| top LUT | 12672 | 5623 |
| top Register | 2230 | 2501 |
| top ALU | 2155 | 252 |
| telemetry LUT | 8968 | 606 |
| telemetry Register | 153 | 424 |
| telemetry ALU | 1935 | 32 |
| top MULTALU27X18 | 5 | 5 |
| top MULT12X12 | 3 | 2 |

来源：两侧 `impl/gwsynthesis/PID_syn_rsc.xml`，运行输出 `shell.log`。资源类别按 Gowin 原报告保留，不能把 LUT/ALU 简单相加。after 的共享 divider 为 86 registers / 166 LUT / 32 ALU。综合 prj 不包含 SDC/CST；不能据 `run syn` 宣称物理约束已验证或 20ns 时序收敛。

另在 after 独立目录实际执行 `gw_sh.exe check_constraints.tcl`（内容为 open_project / `set_option -global_freq 50` / `run pnr`）。布局布线工具完成，但 **50MHz 时序失败**，不把工具退出码当作时序通过。`pnr-shell.log` 确认 top.cst 解析完成；`impl/pnr/PID.pin.html` 确认 clk=Y18/Bank4、LVCMOS33；`PID_tr_content.html` 明确使用 top.sdc、20.000ns/50.000MHz。实际 Fmax=11.110MHz，最差 setup slack=-70.007ns，TNS=-4026.133ns / 64 endpoints，hold TNS=0。最差路径为 `robot/motors/rpm_right/counter_b_0_s0/Q` → `rpm_data_o_10_s0/D`，证实原 RPM 组合除法是当前瓶颈。工具自动生成的 fs/bin 只位于 ignored 输出，**不得烧录**：IO 不完整且时序未收敛。没有改动保护源码或加 false/multicycle 规避。

上一轮保护检查：18 个受保护文件（3 个指定核心、PID IP 目录全部 tracked 文件、原 signed_divider）与真实 before 工作树快照逐字节相等，git diff 亦为空；git blob 与本地 CRLF 可能不同，未据此错误宣称原始字节相同。未修改原 wave/WLF，未提交 git。

## 本轮 RPM 多周期测速

- 每拍采样，保留三级同步；A 领先 B 为正。使用 A、B **上升沿到上升沿**的完整周期（旧源码注释写下降沿，但实现为上升沿）。两路计数独立递增，修正旧 `else if` 导致另一通道边沿拍漏计的问题。
- `NUMERATOR=floor(60*CLK_FREQ/PPR)`，结果幅值为 `floor((2*NUMERATOR)/(periodA+periodB))`；50MHz/PPR364 时 NUMERATOR=8241758，32bit分子=16483516。周期相加先扩展至33bit。正负输出仍按 DATA_WIDTH 截断，不新增幅值饱和。
- 新增 `rpm_divider_seq`：32bit无符号分子、33bit分母、34bit试减；接受start后固定32个计算拍，busy拒绝新start，done单拍，除零同延迟返回0。与遥测Q格式除法器独立。
- 新增 `UPDATE_HZ=100`；50MHz默认每500000拍锁存拍前周期/方向/资格，32步完成后下一拍发布，首次valid为复位释放后的第500033拍，此后间隔500000拍。valid仅持续一拍；没有可信周期也按相同节拍发布0。要求 `CLK_FREQ/UPDATE_HZ>=34`，非整除频率按整数周期取整。PID仍为1500Hz并保持最新反馈，不将编码器采样降为100Hz。
- 至少各取得两个同方向上升沿才有完整A/B周期。检测任意反向正交步或A/B同拍变化时丢弃资格（该异常/反向首步也不作为周期起点）；恢复后重新采集完整周期。方向、分母和有效性随事务锁存，tick同拍正常新边沿不改变该批快照；反转/异常/超时在途发生则粘性撤销旧结果资格，不能把旧非零再次发布。
- `TIMEOUT_CYCLES` 独立于发布节拍，默认为 `10*NUMERATOR=82417580` 拍（1.6483516秒，沿用约0.1RPM阈值）。任一路已启动周期计数达到阈值，即使没有任何新边沿也清资格；计数在阈值饱和，不回绕。输出按下次100Hz发布清零，故外部观察到零还可能多等待约10ms及33拍。该机制不是10ms停转判据，也不是硬件堵转保护。
- 保留 DATA_WIDTH=16、CLK_FREQ=27MHz、PULSE_PER_REV=364 的独立模块旧默认；系统顶层明确覆盖50MHz。参数检查限制DATA_WIDTH 2..32、超时2..2^32-1及32bit分子，仿真时不允许静默截断配置。

本轮可复现流程：`bun sim/run_tests.ts`，然后 `bun sim/run_rpm_timing.ts`。before为修改任何RPM源码前冻结的当前工作树，不是git HEAD。每侧综合从自己的完整源码/工程/约束读取，同一器件、top及50MHz，无替换telemetry模块混用基线。所有输出仅在 ignored `sim/out_rpm/`；旧 `sim/out_50mhz/`、根impl和波形均保留。基线缺失时明确报错，不自动用新源码重建旧基线。

## 已知阶段边界

原输入调度的 `ready_slow_down` 可能保持为 1，本次不修改调度算法。没有板子和接线资料，本轮仅保留 clk=Y18/LVCMOS33 和20ns约束，另外15个外部信号不猜引脚。P&R自动IO分配只用于内部时序评估，不代表板级电气/外部时序通过；自动生成配置文件不得用于烧录，不作为交付物。接口自检不是PID闭环稳定性、堵转保护或物理电机安全认证。
