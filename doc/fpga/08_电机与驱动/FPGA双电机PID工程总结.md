# FPGA 双电机 PID 控制工程——开发工作总结与交接说明

> 项目目录：`D:/AAAAEDA/PID`  
> 汇总日期：2026-09-13  
> 

## 1. 当前结论

**核心数字逻辑设计及当前默认配置的 50 MHz 内部时序验证已经完成；板级接口设计和实物验证尚未完成。**

已完成：

- 双电机 RTL 分层设计与顶层整合。
- 两片 TB6612 独立方向、PWM、STBY 控制。
- 保留原四通道 PID IP，以 ch0/ch1 控制左右轮，闲置 ch2/ch3。
- 双路 PID 输出适配、精确缩放、限幅及流水化。
- RPM 周期锁存与多周期整数除法，默认 100 Hz 发布转速。
- 遥测共享多周期除法、100 Hz 计算更新及完整 UART 帧保持。
- 按原理图确认 50 MHz 时钟、Y18 引脚、LVCMOS33 电气约束。
- 八项功能自检通过，使用真实 Gowin PID 仿真模型。
- 最新记录的 P&R：Fmax **77.836 MHz**，setup slack **+7.152 ns**，hold slack **+0.237 ns**，setup/hold 违例端点均为 **0**。

尚未完成：

- 其余 15 个外部信号的实际引脚分配及接口电平核对。
- 完整引脚约束下重新 P&R 和板级接口时序检查。
- 编码器参数、正反方向、机械安装及实际电机闭环调试。
- PID 参数整定、堵转/断线/失联等故障处理方案及实物安全验证。

**当前自动生成的 fs/bin 不是可安全烧录的交付物。P&R 报告中的 Fmax 是工具分析结果，不是板上实测频率或电机实测性能。**

## 2. 硬件目标与系统参数

| 项目 | 当前配置 |
|---|---|
| FPGA | Gowin GW5AT-LV138PG484AC1/I0（GW5AT-138B） |
| 板卡资料 | ACG720-138&60K 通用原理图及用户提供截图 |
| 系统时钟 | 50 MHz，20 ns |
| 时钟源 | U2，`50M_Active` 有源晶振 |
| 时钟网络/引脚 | `FPGA_GCLK1` → Y18，Bank 4 |
| 时钟 I/O 电压 | Bank 4 VCCO=3.3 V，LVCMOS33 |
| 电机 | 两台 MG513X 系列电机，具体型号与参数待实物核对 |
| 驱动 | 两片 TB6612，各控制一台电机，两个 STBY 独立 |
| 编码器参数 | `PULSE_PER_REV=364`，含义及减速比需实物确认 |
| PWM | 20 kHz；50 MHz 下每周期 2500 拍 |
| PID | 保留原四通道 3P3Z IP；`PID_FREQ=1500` |
| RPM 发布 | 默认 100 Hz，每 500000 拍发起一次计算 |
| 遥测计算 | 默认 100 Hz，与 UART 帧发送速率分离 |
| UART | 115200 baud、8N1 |

注意：`PID_FREQ=1500` 是保留的配置值。原输入调度中 `ready_slow_down` 的保持行为仍是已知边界，不能只依据参数名称认定实际每通道严格按 1500 Hz 提交。

原理图中磁珠的 `120OHM_100Mhz` 是阻抗规格，不是系统时钟频率。

## 3. 最终模块层级

```text
src/top.v                         FPGA 工程入口，薄封装
└── robot_top.v                   系统整合层
    ├── UART_controller           接收双轮目标和停止状态
    ├── UART_driver               遥测快照、计算及发送
    │   └── signed_divider_seq    两轮共享的遥测除法器
    └── motor_control.v           双电机闭环子系统
        ├── RPM_reader × 2
        │   └── rpm_divider_seq × 2
        ├── PID_Input_Processor   保留原参数初始化与调度
        ├── PID_Controller_3p3z_Top
        │   ├── ch0：左轮
        │   ├── ch1：右轮
        │   └── ch2/ch3：零目标、零反馈，输出忽略
        ├── dual_pid_adapter      两路映射、缩放与流水线
        └── dual_motor_driver
            ├── tb6612_motor_driver：左轮
            └── tb6612_motor_driver：右轮
```

`robot_top` 为后续视觉、IMU、TOF、LicheePi 通信及 debug 留出系统级扩展位置。本阶段没有添加功能重复的空 `system_top`。

## 4. 开发过程与完成内容

### 4.1 双电机驱动与顶层迁移

新增 `dual_motor_driver.v`，复用两份已验证的单路 TB6612 驱动：

- 左右独立命令、方向、PWM、enable 和 STBY。
- 不把两个 STBY 做 AND，不让单轮禁用自动传播至另一轮。
- 保留底层 signed16 `motor_cmd` 接口；幅值和方向仍在原单路驱动中转换。
- 新增 `motor_control.v`、`robot_top.v`，最后将活动 `src/top.v` 改为薄封装。
- Gowin 与 ModelSim 统一引用 `src/top.v`，避免根目录旧顶层与活动顶层混用。

旧四电机输出链保留参考，不进入新的 TB6612 执行链。

### 4.2 双路 PID 适配

新增 `dual_pid_adapter.v`，不重新生成或手改原四通道 PID IP：

- ch0 更新左轮，ch1 更新右轮，其他通道不驱动电机。
- 原 PID 输出限幅仍为 ±1023。
- 默认精确整数映射：

```text
cmd = clamp(u, -1023, 1023) × 26214 / 1023
```

整数运算向零截断。零对应零命令，±1 对应 ±25，端点对应 ±26214，约为驱动命令满量程的 80%。没有旧输出处理器的 20% 起步底座。

- `-32768` 的幅值在适配层先限制至不超过 32767，再缩放并恢复符号，不修改底层 PWM 核心。
- 左右 stop/disable 优先，清对应命令和有效标志。
- 停止后恢复需等待该侧新的有效 PID 输出，不立即复用旧执行缓存。

### 4.3 50 MHz 时钟约束与参数贯通

新增并登记到 `PID.gprj`：

`constraint/top.cst`：

```tcl
IO_LOC "clk" Y18;
IO_PORT "clk" IO_TYPE=LVCMOS33;
```

`constraint/top.sdc`：

```tcl
create_clock -name clk -period 20.000 \
    -waveform {0.000 10.000} [get_ports {clk}]
```

时钟参数从 top、robot_top 传到 motor_control、UART_controller/driver，再传到测速、PID 输入调度、PWM、UART_recv/send，避免约束按 50 MHz、内部计时仍按 27 MHz。

50 MHz 下 `60*CLK_FREQ` 会超过 signed32。最初以包装层 64 位参数覆盖修复；后续 reader 改造中在其内部直接使用 64 位常量运算，使独立实例也正确。

### 4.4 遥测低资源化

原遥测使用变量组合除法。仅降低寄存器更新频率不能消除该组合硬件，因此改为一个共享的 26 步恢复除法器：

```text
最新左右 u/RPM/stop 保持值
          ↓ 每 10 ms 捕获一组快照
共享 signed_divider_seq，依次计算左右
          ↓ 两路同时提交
结果缓存 → 整帧快照 → UART
```

- busy 期间输入变化不污染已接受的计算。
- 两路结果同时更新，避免左新右旧。
- UART 整帧和单字节保持稳定，避免跨数字甚至跨 bit 的数据撕裂。
- 不使用新派生时钟，使用主时钟域内的单拍使能。
- 保留原数值含义：回传原始 PID `u/rpm`，不是 PWM 百分比，也不是直接转速。

### 4.5 RPM 多周期测速

保持 `RPM_reader` 原有端口及前三个参数兼容，仅重写内部并新增 `rpm_divider_seq.v`：

```text
编码器同步及逐拍计数
        ↓
完整 periodA、periodB 与方向资格
        ↓ 每 10 ms 锁存快照
32 步无符号整数除法
        ↓
rpm_data_o + 单拍 rpm_valid_o
```

- 保留三级同步，A 领先 B 为正。
- 使用 A/B 上升沿到上升沿的完整周期；修复原分支互斥造成的另一通道少计拍。
- 常量及公式：

```text
NUMERATOR = floor(60 × CLK_FREQ / PPR)
rpm_magnitude = floor(2 × NUMERATOR / (periodA + periodB))

50 MHz、PPR=364：
NUMERATOR = 8241758
被除数 = 16483516
```

- 分子 32 位，周期和先扩展至 33 位，试减余数 34 位。
- 除零固定延迟返回零；busy 不接受新 start；done 单拍。
- 默认第一次 valid 在复位释放后的第 500033 拍，此后间隔 500000 拍。
- 没有可信周期时，也按相同发布节拍输出零。
- 首次测量、反转及异常 A/B 同拍变化后重新建立完整测量资格。
- 方向、周期和有效性作为同一事务锁存；在途反转、异常或超时撤销旧结果资格。
- 超时独立于 100 Hz 发布周期，默认 `10*NUMERATOR=82417580` 拍，约 1.648 秒；计数饱和、不回绕。超时后零输出还可能等待下次发布点，约再增加 10 ms 和计算延迟。

**100 Hz 是转速结果发布频率，不是编码器采样频率；约 1.648 秒超时不是 10 ms 停机保护，也不是硬件堵转保护。**

### 4.6 后续 agent 完成 PID 适配层时序收敛

RPM 优化后，关键路径从测速除法转移到 PID 输出至 adapter 命令寄存器。后续 agent 将精确缩放改成五级流水：

- 接受沿到发布沿相隔 4 拍，50 MHz 下为 80 ns。
- 吞吐率仍为每拍一个输入，支持左右通道连续交替。
- 默认除以 1023 使用三段 10 位数字折叠及比较修正，与原整数公式精确等价。
- stop/disable 清对应通道的流水线在途命令，保持左右隔离。
- 额外遍历全部 65536 个 signed16 输入，覆盖默认及 32767 全幅参数、停止撤销、禁用及复位。
- 非默认参数仍提供通用常数除法路径，但当前物理时序通过结论仅针对工程默认配置。

## 5. 资源与时序演进

各阶段均以对应保存的工作区快照、相同目标器件和 50 MHz 设置进行验证。资源来自综合报告；Fmax/slack 来自对应 P&R 报告，不混用两种指标。

| 阶段 | 整体 LUT | Register | ALU | P&R Fmax | 最差 setup slack |
|---|---:|---:|---:|---:|---:|
| 遥测优化前 | 12672 | 2230 | 2155 | 本表不列 | 本表不列 |
| 遥测共享除法后 | 5623 | 2501 | 252 | 11.110 MHz | −70.007 ns |
| RPM 多周期化后 | 3162 | 2851 | 258 | 25.339 MHz | −19.464 ns |
| PID adapter 流水化后 | **2666** | **2905** | **309** | **77.836 MHz** | **+7.152 ns** |

局部优化：

- 遥测 LUT：8968 → 606。
- adapter LUT：656 → 85；寄存器 34 → 88。
- 最终 setup TNS=0、违例端点=0。
- 最终最差 hold slack=+0.237 ns，hold TNS=0、违例端点=0。
- 最终最差 setup 路径位于遥测文本编码至 `tx_byte`，当前满足 20 ns。

这些结果没有通过新增 false path 或 multicycle path 来掩盖真实同步路径。综合仍存在原 IP/遥测及部分受参数范围约束的截位告警，不能表述为整个工具链零告警。

## 6. UART 接口约定

### 接收

- 115200 baud，8N1。
- `0x91` 进入设置模式。
- 连续发送高、低两个 byte：
  - 高 byte：`{channel[2:0], rpm[12:8]}`。
  - 低 byte：`rpm[7:0]`。
- RPM 为 signed13，范围 −4096～4095。
- ch0 左轮，ch1 右轮；ch2～7 消费完整字节对，但不更新目标/stop。
- **仅等待高 byte 时 `0xff` 表示退出**；低 byte 的 `0xff` 是合法数值。
- −3～3 停止，±4 及之外运行；停止目标保留原数值，不自动改写成零。

### 回传

帧格式为 20 字节，通道符号随数据变化：

```text
0+ddd.ddd 1+ddd.ddd\n
```

- 单个 LF，无 CRLF。
- 原始 `u/rpm` 采用符号＋幅值定点表示，不是二补码定点输出。
- 幅值为 `floor((abs(u)<<10)/abs(rpm))` 的低19位，整数9位回绕、不饱和。
- 除零幅值为零但保留符号，因此允许负零；stop 强制正零。
- 十进制转换保留原截断方式，例如 `1/10` 显示 `0.099`。
- 100 Hz 是计算频率。发送保留 `CLK_FREQ/(11*OUTPUT_RATE)` 的字节调度，默认 `OUTPUT_RATE=8`，不是100帧/秒。

## 7. 测试与证据

| 自检 | 主要覆盖 |
|---|---|
| `dual_motor_driver_tb` | 独立 STBY、正反方向、完整 PWM 周期、占空比、零、禁用、复位 |
| `dual_pid_adapter_tb` | 限幅、signed16 全域、精确缩放、交替通道、流水延迟与停止撤销 |
| `motor_control_tb` | 真实四通道 PID IP、双路编码器、完整周期测量、独立停机 |
| `robot_top_tb` | 引脚级 UART 目标输入至真实 PID 和驱动、通道过滤、死区及协议边界 |
| `uart_driver_tb` | 500000拍计算间隔、原子提交、在途输入变化、两帧40字节完整解码及稳定性 |
| `signed_divider_seq_tb` | 1101次原组合参考比较、极值、零除、负零、回绕、busy/done/reset |
| `rpm_divider_seq_tb` | 32步固定时延、33位分母、零除、随机比较、busy隔离和复位 |
| `rpm_reader_tb` | 完整测量资格、正反数值、默认100Hz、超时、恢复、反转及异常边沿 |

八项自检均有通过记录。集成使用真实 PID `.vo` 和 GW5A `prim_sim.v`，未以 mock 或 force PID 输出替代真实链路。

主要证据位置：

- `sim/out_rpm/tests/results.txt`：八项回归结果。
- `sim/out_50mhz/`：遥测优化历史综合/P&R。
- `sim/out_rpm/before/`、`sim/out_rpm/after/`：测速优化前后报告。
- `sim/out_closure/latest.json`：最新时序收敛运行索引。
- `sim/out_closure/2026-09-13T12-05-22-874Z/`：已记录的最终通过运行，含源码快照、`source-sha256.json`、`summary.json`、`shell.log`、`impl/pnr/PID_tr_content.html`。

本次文档整理只读核实了 `latest.json`/`summary.json` 中的 Fmax=77.836 MHz、`internalTimingPass=true`、`boardReleaseReady=false`、setup/hold零违例，以及八项落盘PASS。slack和资源明细依据用户提供的最新README汇总，本次未重新解析所有详细物理报告，也未将历史快照哈希与当前全部源码逐一比对。

报告对应当次快照；日后更改 RTL、参数、器件或约束后，必须重新验证，不能沿用本表结论。

## 8. 如何复现

当前 README 推荐 Node.js 24，无需强制使用 Bun。需安装可用 ModelSim、Gowin 工具和有效许可证。

项目根目录执行：

```powershell
# 仅在当前终端尚未继承本机已配置许可证变量时使用
$env:MGLS_LICENSE_FILE = [Environment]::GetEnvironmentVariable('MGLS_LICENSE_FILE','Machine')

node sim/run_tests.ts
node sim/run_closure.ts
```

本机默认工具位置：

- ModelSim：`F:/modeltech64_10.6d/win64/`。
- Gowin：`F:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe`。
- GW5A 仿真库：`F:/Gowin/Gowin_V1.9.12_x64/IDE/simlib/gw5a/prim_sim.v`。

不同安装路径请检查脚本支持的环境变量（如 `MODELSIM_BIN`、`GOWIN_PRIM`、`GOWIN_SH`），不要把本机绝对路径当作通用安装要求。

`run_closure.ts` 每次新建独立输出目录，保存源码 SHA256，检查 50 MHz 设置、实际 SDC、P&R 完成状态及 setup/hold 违例，内部时序失败返回非零。

历史阶段比较脚本保留用于溯源：

```sh
bun sim/run_synthesis.ts    # 遥测历史基线对比
bun sim/run_rpm_timing.ts   # RPM历史基线对比
```

这些历史脚本依赖保存的 before 快照；快照缺失时不能用当前代码伪造旧基线，也无需每次日常回归都重跑历史阶段。

## 9. 主要源码及交付文件

| 文件 | 职责 |
|---|---|
| `src/top.v` | 活动 FPGA 顶层薄封装 |
| `src/robot_top.v` | 系统集成、UART与电机子系统连接 |
| `src/motor_control.v` | 两路测速、原PID链和执行端整合 |
| `src/dual_motor_driver.v` | 两份原TB6612驱动封装 |
| `src/dual_pid_adapter.v` | 两路输出适配、精确缩放及流水线 |
| `src/rpm_reader.v` | 周期计数、有效性、100Hz调度及结果发布 |
| `src/rpm_divider_seq.v` | RPM整数多周期除法 |
| `src/signed_divider_seq.v` | 共享遥测定点多周期除法 |
| `src/uart_controller.v` | 双通道目标、协议和停止死区 |
| `src/uart_driver.v` | 遥测快照、共享计算、格式化及发送 |
| `constraint/top.cst`、`top.sdc` | 已确认时钟物理/时序约束 |
| `constraint/PINOUT_PENDING.md` | 待分配信号和板级资料清单 |
| `PID.gprj`、`PID.mpf` | 综合与仿真工程配置 |
| `sim/*_tb.sv` | 八项自动判定测试 |
| `sim/run_tests.ts`、`run_closure.ts` | 当前功能/时序验证入口 |
| `README.md` | 原有技术说明、历史记录及最新状态 |
| `README_WORK_SUMMARY.md` | 本开发总结及交接说明 |

保留参考：

- `reference/top_author.v`：作者顶层归档。
- `reference/pid_output_processor_old.v`：旧四电机输出处理器归档。
- 根目录 `top.v`、`src/pid_output_processor.v` 原内容保留，不参与新活动链编译。
- `src/signed_divider.v` 保留作为旧遥测算法参考。

原 `pid_input_processor.v`、PID IP 目录及 `tb6612_motor_driver.v` 保持原实现。reader 是后续经授权内部重构；adapter 流水化属于后续时序收敛修改。不要把“早期核心保护范围”误解为 reader 永远未改。

**不要递归通配编译整个仓库所有 `.v`**，否则会引入旧顶层、同名归档和不匹配的历史测试。

## 10. 拿到板子后的工作清单

### 10.1 接口与引脚设计

目前只有 clk 实际约束。待分配15个信号：

| 类别 | 信号 |
|---|---|
| 复位 | `rstn` |
| 编码器 | `enc0_a`、`enc0_b`、`enc1_a`、`enc1_b` |
| UART | `uart_rx`、`uart_tx` |
| 左驱动 | `left_in1`、`left_in2`、`left_pwm`、`left_stby` |
| 右驱动 | `right_in1`、`right_in2`、`right_pwm`、`right_stby` |

- 根据准确板型、排针编号及原理图核对 FPGA 球脚和 Bank 电压。
- 确认 UART 使用板载USB串口还是外部设备，再选择实际映射。
- 核对编码器输出是否为3.3V/5V或开漏，必要时设计电平转换；不能默认FPGA引脚耐5V。
- 区分 TB6612 的逻辑 VCC 与电机 VM，确认电平兼容、共地、供电与去耦。
- 两个 STBY 必须独立，明确复位期间与FPGA未配置期间的硬件安全电平。
- 确认复位按键极性、去抖与复位释放策略，以及未用TB6612通道的处理。

### 10.2 重新验证

- 补全 `top.cst`，按实际外部接口需求补充合理时序约束。
- 用完整物理约束重新运行功能回归和P&R，复核setup/hold及未约束路径。
- 只有这些检查通过后，才生成并使用对应的板级配置文件。

### 10.3 实物调试

1. 先断开电机动力或保持驱动禁用，验证时钟、复位及UART。
2. 验证左右独立STBY、方向和20kHz PWM。
3. 核对编码器每转脉冲定义、减速比、左右镜像安装与符号；正目标应得到同符号反馈。
4. 在受控、限流条件下逐台验证，再测试双轮闭环。
5. 实物整定PID，确认低速起转、稳态误差、响应、反转和停止行为。
6. 明确堵转、编码器断线、UART失联、急停和恢复策略，再进行比赛场景测试。

## 11. 已知限制与交接注意

- 100Hz反馈对目标应用是否足够，需要结合实际机械动态和PID整定验证，不能仅凭仿真判定。
- stop/disable 撤销执行端及adapter流水线，但**不清 PID IP 内部历史或内部在途事务**；恢复后首输出未必对应恢复后的新目标。
- 原PID调度行为保留，未实现IP历史重置、anti-windup或通用通信看门狗。
- RPM计数超时不是安全认证的堵转保护；转速极值仍按DATA_WIDTH截断，没有新增饱和。
- 遥测保留旧回绕、负零和截断语义，不应把显示值当作高精度物理测量。
- 仿真证明数字链路在测试范围内的行为，P&R证明当前约束下的内部时序；两者都不能单独证明实际电机闭环稳定或整机安全。
- 开发验证采用独立输出目录，原作者参考源码、原工作库和波形应继续保留；Git提交状态以实际仓库为准。

---

**最终交接结论：双电机 FPGA 核心逻辑和默认 50 MHz 内部时序已经完成。下一阶段是板级接口与电气设计、完整约束复验，再进入实际电机闭环调试。**
