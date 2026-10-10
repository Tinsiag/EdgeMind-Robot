# ACG720 / AT8236 电机测试与持续启停

2026-10-10 为用户已经接好的现有电源板建立独立测试工程。器件为 GW5AT-LV60PG484AC1/I0、GW5AT-60B，使用板载 50 MHz，不依赖 DDR、PLL 或摄像头 IP。

当前板上为 **A716：50 kHz、最高 80%、S1/S2 独立切换左右持续运行，再按一次停止**。已完成仿真、编译、实际引脚审查及 SRAM 下载，独立回读 `0x0000A716`。A713 的 65% 左右持续启停已获用户确认；A714 的 1 kHz/80% 用户感觉未明显变快。A715 已编译但在下载前被用户的“直接上50kHz”要求替代，未上板。A716 实际运行及速度变化待反馈。

此前 A712 的 1 kHz/50% 短时测试中，用户反馈“转了，亮了”，电机启动及编码器活动通过。A710、A711 的 25% 测试均未转动，对照支持此前启动激励不足；电流、最低启动占空比、转向和速度闭环尚未验证。各版本使用相同引脚，均默认停止、手动启动、S0 停止，只下载 SRAM。

| 版本 | 编译脚本 | PWM | 最高占空比 | 单次时限 | 实物结果 |
| --- | --- | --- | --- | --- | --- |
| A710 | `build.tcl` | 20 kHz | 25% | 2 秒 | 两轮均未转 |
| A711 | `build_1khz.tcl` | 1 kHz | 25% | 2 秒 | 两轮均未转，S1 时用户听到电机声音 |
| A712 | `build_start50.tcl` | 1 kHz | 50% | 1 秒 | 用户反馈电机转动、编码器活动灯亮 |
| A713 | `build_toggle.tcl` | 1 kHz | 65% | 按键启停，持续运行 | 用户确认左右启停正常 |
| A714 | `build_toggle80.tcl` | 1 kHz | 80% | 按键启停，持续运行 | 已下载；用户感觉未明显变快 |
| A715 | `build_toggle20k80.tcl` | 20 kHz | 80% | 按键启停，持续运行 | 已仿真及编译；用户改为 50 kHz，未下载 |
| A716 | `build_toggle50k80.tcl` | 50 kHz | 80% | 按键启停，持续运行 | 已下载，实际运行及速度待反馈 |

排查过程、结论及复现方法见 [排查与实现文档](MOTOR-IMPLEMENTATION-2026-10-10.md)。下载过的 A712、A713、A714、A716 位流及构建证据分别归档到 `release/` 同名目录；原厂资料和工具仍留在 `.local/`。

## 如何测试

1. 车轮架空，两只电机连接原有六针插座。12 V 电源接电源板，FPGA 由自己的电源供电，两板共地。编码器和驱动参考端使用 FPGA 开发板的 3.3 V。用户照片确认 USB J2 下的黄色排针是 P4；照片中 USB 在上、HDMI2 在下，最上端一对 P4-1 为经磁珠引出的 3.3 V，P4-2 为 GND，可分别连接电源板 L-6、L-5。
2. 下载本工程的 SRAM 位流后，先松开 S1、S2。约 100 ms 初始化及 20 ms 松键确认后可以开始。默认四个电机 IN 都为 0。
3. A713～A716 下，按 **S1** 启动左电机，松开后再按一次停止；**S2** 同样控制右电机。两轮独立，允许同时运行。**这些持续版不会在一秒或两秒后自动停止。** 若使用历史 A712，则每次约 1 秒自动停止；A710/A711 为 2 秒。
4. **S0** 随时停止并复位。停止状态为 IN1=IN2=0，电机滑行，机械惯性不会由本程序立即消除。
5. 看电机是否旋转、对应的运行 LED 是否亮，以及编码器活动 LED 是否亮。转向暂不定义为车身“前进”，需要结合实际安装方向确认。

S1/S2 使用 20 ms 防抖；A713～A716 每键必须先稳定松开才允许下一次有效按下，长按不会反复启停，按住上电或释放 S0 不会自动启动。A710～A712 同时按下会拒绝启动，持续版则允许同时切换两轮。各版均不自动换向。

## LED 定义

这套灯态与原摄像头/DDR 自检不同。

| 灯 | 含义 |
| --- | --- |
| D0 | 启动延时结束，系统运行；是否允许启动还取决于按键是否已松开 |
| D1 | 左电机正在测试，期间常亮 |
| D2 | 右电机正在测试，期间常亮 |
| D3 | 左编码器 A/B 至少出现一次跳变，保持到下一次测试或 S0 |
| D4 | 右编码器 A/B 至少出现一次跳变，保持到下一次测试或 S0 |
| D5 | A713～A716 为两轮均停止；历史 A710～A712 为测试定时结束，不表示验证通过 |
| D6 | A713～A716 保留且灭；历史 A710～A712 为同时按键拒绝标志 |
| D7 | 1 Hz 心跳，每 0.5 秒翻转 |

编码器活动灯不代表转速、方向、四倍频计数或完整线序已经验证。复位后先建立采样基线，静态高电平不会被当成活动。持续版启动某轮只清除该轮活动记录，历史 A710～A712 开始一次测试时两侧都清零。停止后也可以手转电机检查活动。

## 与实际接线对应

| 顶层端口 | P7 | FPGA 球号 | 电源板 |
| --- | --- | --- | --- |
| left_in1 | 1 | A13 | L-1 / LAIN1 |
| left_in2 | 2 | A14 | L-2 / LAIN2 |
| left_enc_a | 3 | A15 | L-7 / LF_ENA |
| left_enc_b | 4 | A16 | L-8 / LF_ENB |
| right_in1 | 31 | F16 | R-5 / RAIN1 |
| right_in2 | 32 | E17 | R-6 / RAIN2 |
| right_enc_a | 33 | D20 | R-2 / RF_ENA |
| right_enc_b | 34 | C20 | R-1 / RF_ENB |

S0=F15、S1=A20、S2=B20，低有效；时钟 Y18=50 MHz。全部信号 IO 使用 LVCMOS33，实际 VCCIO 需为 3.3 V。AIN2 保持低，AIN1 送 PWM，适配 AT8236 的双 IN 接口；不要套用 TB6612 的独立 PWM/STBY 接法。未使用的 B 通道输入按接线图接电源板公共地。

完整板端针序与电源见 [接线文档](../../../doc/电机/ACG720与现有电源板接线_2026-10-10.md)。

## A710 默认实现及公共控制逻辑

- 50 MHz 计数生成 20 kHz PWM，每周期 2500 个时钟。前 50 ms 为 10%，50～100 ms 为 15%，100～200 ms 为 20%，之后为 25%，最高高电平时间 625 个时钟。
- 另生成 1 ms 时基，按键防抖、松键确认和单次 2 秒计时均用该时基。定时误差小于 1 ms。
- 上电计数器和状态寄存器初始化为停止；S0 异步清除状态并门控 PWM，复位释放经两拍同步。启动前必须检测到两个启动键已经稳定松开。
- 编码器与启动键各经过两级寄存器同步。编码器只做活动检查，不参与闭环，不根据无反馈自动加大 PWM。
- 本版将 P7-17/C14 摄像头复位保持低。独立测试 SRAM 位流暂时替代摄像头程序；原摄像头工程与通过位流保留不变，恢复原摄像头 SRAM 位流即可继续使用。

## 编译及仿真

在本目录执行：

```powershell
& 'C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe' './build.tcl'

$motorIcarus = '../acg720-ddr3/.local/tools/iverilog/bin'
New-Item -ItemType Directory -Force '.local' | Out-Null
& "$motorIcarus/iverilog.exe" -g2012 -Wall -s acg720_motor_test_tb -o '.local/motor_test.vvp' 'rtl/acg720_motor_test.v' 'tests/acg720_motor_test_tb.v'
& "$motorIcarus/vvp.exe" '.local/motor_test.vvp'

& 'C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'tests/audit_build.py'
```

`tests/audit_build.py` 核对实际 PNR 报告中的 21 个顶层端口、方向、全部 3.3 V IO、四路驱动输出的下拉，以及 setup/hold 违反数和位流 User Code，结果保存在 `.local/build-audit-20261010.json`。

## A710 验证及排查记录

- Icarus 仿真通过：配置时按住启动键、防抖、左右选择、25% PWM 周期、编码器基线与映射、单次超时、按住不重复、S0 在 PWM 高期间异步停止、复位释放不重启、同时按键拒绝及重新启动。
- Gowin V1.9.12 完成综合、布局布线和位流生成；21 个实际端口与接线一致。
- 50 MHz 时序：setup/hold 违反端点均为 0；报告 Fmax 为 166.268 MHz，最差 setup slack 13.986 ns、hold slack 0.275 ns。异步外部输入路径已明确约束；这不替代实物信号质量验证。
- User Code：`0x0000A710`。
- 位流：`impl/pnr/acg720_motor_test.fs`。
- SHA256：`82247E0D4383C2208AFEDE85997A5DAAAC3058376CB8DF465B90D2E36B1B7ADA`。
- SRAM 下载已完成：Gowin USB Cable(FT2CH)，USB location=548，FPGA ID=`0x0001481B`；operation_index=2 下载 100%，User Code=`0x0000A710`，Status=`0x70022020`。随后再次独立读取 User Code 和 Status，结果一致，外部 Flash 未写。
- 下载前实际读取的 User Code 为 `0x0000BC6C`，不再沿用历史记录中的 `0xAF89` 作为当时板上状态。已验证摄像头实景 `0xAF89` 源码及位流仍保留在 `../acg720-ddr3/.local/framebuffer-first/ch38-camera-live/`。
- 首次实物反馈：两只电机均未转动；S1/S2 分别使 FPGA D1/D2 亮，随后运行灯灭、D5 亮，D3/D4 均未亮。运行灯和完成灯只能证明控制状态及定时已执行，不能证明驱动端已收到信号或电机已供电；本版会在约 2 秒后自动停止，无需再按一次启动键。
- 用户随后反馈电源板电源指示灯未亮。当前优先检查电机 VM 电源通路：原理图为 CN1 的 VCCIN → SW2 → VM → 两个 AT8236 模块；LED1 由 VM 供电，位号 D1 则为 TVS，不是指示灯。尚无 VM 或 3.3 V 实测读数，因此暂不能确定为开关、供电、焊接、线束或 PWM 启动力矩问题。
- 用户进一步确认 SW2 已连通、12 V 可以提供；后续不再要求安装或重复操作 SW2。仍需区分供电源有 12 V 与驱动模块 VM/GND 端实际测到 12 V，并测 L-6/L-5 的 3.3 V。停止后手转车轮、观察 D3/D4，可独立核查编码器供电及反馈通路，不以未转电机的编码器灯灭判定输入故障。
- 3.3 V 测量点为 L-6 对 L-5：按用户 PCB 截图方向，右侧上排标 L 的八针接口从左到右为 1～8，黑表笔接第 5 针 GND，红表笔接第 6 针 3.3 V。另需测驱动模块标注 VM 对 GND，正常应接近外部 12 V 电源电压；不要把 VM 接到 FPGA IO 或 3.3 V。
- 用户实测反馈：L-6 对 L-5 为 3.3 V，驱动 VM 为 12 V；停止后手转左右轮，D3/D4 仍均未亮。现阶段不能认定电机或编码器损坏，也不能把故障仅归因于 25% PWM。复核官方 P7 管脚和实际约束一致；待测左轮 L-1 对 L-5 在 S1 测试期间的 PWM 直流平均值（平台预计约 0.825 V）、L-7/L-8 对 L-5 在手转停位时的高低电平，以及下方左电机六针插座 2 对 5 的编码器电源。板端针序不代表电机线束顺序已确认，MG513 霍尔/GMR 版本的编码器供电极性需结合实物核对。
- 同日补核 [WHEELTEC MG513X 官方产品页](https://www.wheeltec.net/product/html/?223.html)：[编码器参数图](https://www.wheeltec.net/kindeditor/attached/image/20251121/20251121160212_30101.jpg) 明确输出带上拉到编码器 VCC，供电范围 3.3～5 V。因此不能在尚未测量 A/B 电平时将无反馈归因于“必须补外部上拉”；[实物类型图](https://www.wheeltec.net/kindeditor/attached/image/20251121/20251121160211_88837.jpg) 可辅助辨认裸露霍尔板与带后盖 GMR 版本，最终仍以用户实物/线序为准。
- 后续实测：S1 运行时 L-1 对 L-5 约 0.8 V，证明控制线在电源板 L 排针端存在与当前 PWM 相符的直流平均电压；左电机六针插座 2 对 5 为 3.3 V。手转左轮 L-7 可到约 2.3 V、L-8 持续约 2.3 V，尚待确认停止后的高低电平和 FPGA 端电平，不能用平均读数代替波形。
- 用户新增裸露霍尔编码器照片，插座旁丝印从上到下为电机+、编码器 GND、B 相、A 相、编码器 5V、电机-。用户说明对应右下方左电机插座从右到左，故实际信号对应为 6/5/4/3/2/1，与板端定义一致；供电正极位置正确，本批次 3.3 V 的实际工作状态仍待验证。未以此推断焊接导通、驱动输出或编码器功能已通过。
- S1 测试期间，用户测左电机六针插座 6 对 1 的最高直流电压约 0.05 V，电机未转。该读数是 20 kHz 快衰减 PWM 下万用表的平均测量，不能直接替代输出波形，也不能证明模块完全不工作。电机功率来自 VM=12 V，编码器供电 3.3 V 与模块参考输入不等同于电机供电；不能把共用 3.3 V 网改接 5 V。模块本体的 VCC、AIN1/AIN2 实测值仍待确认。

## 1 kHz 频率对照工程（A711）

为排查低占空比快衰减模式下的启动电流不足，新增 `acg720_motor_test_1khz.gprj` 和 `rtl/acg720_motor_test_1khz.v`。包装顶层只将原控制器的 `PWM_HZ` 设为 1000，沿用全部原管脚、IO 电压、编码器输入偏置、10%→25% 爬升、单轮选择、2 秒超时和 S0 停止逻辑。原 A710 工程仍为 20 kHz，可随时重新编译；已验证 A710 位流及报告另外保留在忽略目录 `.local/history/A710/`。

1 kHz 时，每周期为 50000 个 50 MHz 时钟，25% 的高电平为 12500 个时钟，即 250 µs；A710 同占空比的高电平为 12.5 µs。更长的脉冲用来检验电机电流建立和芯片唤醒条件，测试结果尚未证明这是不转的根因。快衰减的关断阶段包含电感续流，电机两端直流平均值不能简单认定为 `VM × 占空比`。

编译和检查：

```powershell
& 'C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe' './build_1khz.tcl'
& 'C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'tests/audit_build.py' --variant 1khz
```

专用仿真 `tests/acg720_motor_test_1khz_tb.v` 已验证包装顶层的 1 kHz 周期、准确 25% 占空比、单轮输出、定时结束、按住不重复及 S0 异步停止。User Code 为 `0x0000A711`；位流路径为 `impl/pnr/acg720_motor_test_1khz.fs`。编译、实际 PNR 审查及 SRAM 下载的完成情况需按后续记录确认。

A711 完成记录：

- Gowin V1.9.12 编译完成，21 个实际 PNR 管脚通过审查；50 MHz setup/hold 违反端点均为 0，Fmax=188.612 MHz。
- 位流 SHA256：`81C8BF4A7A41FAAC8D94A18ECF846A082514C6449708F9C8F36D9EFFEE989CF3`。
- 下载前独立读取 User Code 为 `0x0000A710`。使用 operation_index=2 下载 A711 至 SRAM，进度 100%；下载后独立读取 User Code=`0x0000A711`、Status=`0x70022020`，外部 Flash 未写。
- 用户反馈 A711 两轮仍均不转；S1 时明显听到电机声音。用户确认此前测量的是 PCB 图右侧、L 上方的左轮 AT8236 模块，本体 VCC 对 GND 为 3.3 V，AIN1/AIN2 未测出电压。该输入读数与此前 L-1 的约 0.8 V 不一致；两秒窗口、表笔接触、通道/安装方向或导通问题仍需区分。声音不能证明输出正常，频率降低也未解决故障。
- A711 位流、报告、审查 JSON 和当时 RTL 已另存 `.local/history/A711/`。后续公共控制器添加占空比参数后，A710/A711 默认仍为 25%，仿真回归均通过；旧位流的构建证据以对应历史源文件和审查哈希为准。
- 编译、审查、下载及回读证据保存在 `.local/build-1khz-20261010.log`、`.local/build-audit-1khz-20261010.json`、`.local/sram-1khz-program-20261010.log`、`.local/after-1khz-usercode-20261010.log`、`.local/after-1khz-status-20261010.log`。

## 50% 短时启动对照工程（A712）

新增 `acg720_motor_test_start50.gprj`、`rtl/acg720_motor_test_start50.v` 和 `build_start50.tcl`。公共控制器新增默认值为 25 的 `DUTY_PERCENT` 参数；A712 包装顶层显式设置为 50，PWM 仍为 1 kHz，单次时限缩短至 1000 ms。爬升阶段依次为 10%（前 50 ms）、25%（50～100 ms）、40%（100～200 ms）、50%（之后至超时）。选择、松键确认、S0 停止、编码器采样和全部管脚保持原逻辑。

这次对照用于检验启动电流/扭矩不足的可能性。用户随后反馈“转了，亮了”，因此 A712 已解决本次短时测试不转的问题。此前仅将频率从 20 kHz 降到 1 kHz 并未解决；在同为 1 kHz 的对照中，提高最高占空比及爬升阶段后启动成功。未测量实际电流及桥输出波形，不将电感、摩擦、限流或具体启动阈值记为已经确认。若后续复测仍只有声音、不转，应核对模块安装和导通，不直接继续提高占空比。

编译及审查：

```powershell
& 'C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe' './build_start50.tcl'
& 'C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'tests/audit_build.py' --variant start50

$motorIcarus = '../acg720-ddr3/.local/tools/iverilog/bin'
& "$motorIcarus/iverilog.exe" -g2012 -Wall -DSTART50_TEST -s acg720_motor_test_1khz_tb -o '.local/motor_test_start50.vvp' 'rtl/acg720_motor_test.v' 'rtl/acg720_motor_test_start50.v' 'tests/acg720_motor_test_1khz_tb.v'
& "$motorIcarus/vvp.exe" '.local/motor_test_start50.vvp'
```

A712 完成记录：

- A710 安全测试、A711 的 1 kHz/25% 测试回归通过；A712 专用包装顶层测试验证准确 1 kHz/50%、单轮选择、超时、按住不重复及 S0 异步停止。仿真缩短运行参数以加快测试；实际编译顶层使用 `RUN_MS=1000`。
- 首次高云编译在布线阶段异常退出（退出码 `-1073741819`）；保留 `.local/build-start50-20261010-attempt1-crash.log`，重新编译成功生成位流。未下载失败构建的产物。
- Gowin V1.9.12 完成综合、布局布线和位流生成，21 个实际 PNR 管脚核对通过；50 MHz setup/hold 违反端点均为 0，Fmax=183.823 MHz。
- 位流 `impl/pnr/acg720_motor_test_start50.fs`，User Code=`0x0000A712`；SHA256=`84B3E192B543C1EF72AAC51B141E789BF2733C6563BE163DEAA7D5FE1A0DA7FF`。
- 下载前独立读取 User Code=`0x0000A711`；operation_index=2 SRAM 下载完成后，独立读取 User Code=`0x0000A712`、Status=`0x70022020`。外部 Flash 未写。
- 用户在 S1/S2 逐轮测试及 D3/D4 活动灯观察提示后，于 2026-10-10 回复“转了，亮了”。按该反馈记录电机转动及编码器活动通过；用户未提供逐轮速度、方向、A/B 波形或脉冲数。D1/D2 只表示测试状态，D5 只表示时限结束；新测试会清除两侧上次活动记录。
- 证据保存在 `.local/sim-start50-20261010.log`、`.local/build-start50-20261010.log`、`.local/build-audit-start50-20261010.json`、`.local/sram-start50-program-20261010.log`、`.local/after-start50-usercode-20261010.log`、`.local/after-start50-status-20261010.log`。

本工程没有电流测量、堵转判定、方向核对或速度闭环，首次验证应架空、逐轮进行。只下载 SRAM，不写外部 Flash，断电后本次配置丢失；外部 Flash 原有程序的行为不受本程序约束。

## 持续运行与再次按键停止（A713）

用户在 A712 启动通过后要求 S1/S2 分别持续驱动左/右电机，再按一次停止，并提高速度。新增独立控制器 `rtl/acg720_motor_toggle.v`、`acg720_motor_toggle.gprj` 和 `build_toggle.tcl`，保留 A712 的源码及位流字节。

- **S1** 每次有效按下切换左轮运行/停止；**S2** 独立切换右轮。两轮可以同时运行；不会自动换向。
- 上电和 S0 后默认停止，各键必须先稳定松开再允许下一次按下。长按只切换一次，20 ms 防抖；**S0** 不等待防抖或时钟，立即停止两侧 PWM。停止仍为滑行。
- 使用已通过的 1 kHz，将最高占空比从 50% 提高到 **65%**。前 50 ms 为 10%，50～100 ms 为 25%，100～200 ms 为 40%，200～300 ms 为 50%，300～400 ms 为 60%，之后保持 65%，直到再次按对应键或 S0。
- 两侧独立记录爬升进度。编码器灯仍为活动锁存；启动某轮时只清除该轮活动历史，不影响另一轮。没有一秒或两秒超时，也没有速度 PID。
- LED：D0=系统就绪，D1=左轮运行，D2=右轮运行，D3/D4=各轮编码器活动，**D5=两轮均停止**，D6=保留且灭，D7=心跳。D5 不再表示测试超时。

编译 `build_toggle.tcl`，实际顶层为 `acg720_motor_toggle`，User Code=`0x0000A713`；审查使用 `tests/audit_build.py --variant toggle`。专用仿真 `tests/acg720_motor_toggle_tb.v` 验证准确 1 kHz/65%、持续超过旧两秒时限、长按无重复、再次按下停止、两侧独立及同时运行、编码器历史独立清除、S0 在时钟之间停止，以及复位时按住不启动。

65% 是 PWM 输出设定，实际转速仍由供电、负载和电机决定，需用户观察；没有把实际速度增幅当作已测得数据。

A713 完成记录：

- Icarus 专用仿真通过，已覆盖上述持续运行和启停行为；不重复编译或改写 A712 的已通过源码。
- Gowin V1.9.12 编译成功，21 个实际端口与接线一致，50 MHz setup/hold 违反端点均为 0，Fmax=184.374 MHz。
- 位流 `impl/pnr/acg720_motor_toggle.fs`；SHA256=`A144E8D407B4D39044E1852272FFC0E007B97EFCCD6E736DA8F3A85F61831307`。
- 下载前独立读取 `0x0000A712`；operation_index=2 SRAM 下载完成，随后独立读取 User Code=`0x0000A713`、Status=`0x70022020`。未写外部 Flash。
- 用户在持续启停提示后回复“都可以了，再调快点，调到80%”，确认 A713 左右启停正常。没有提供转速、电流或长时间负载数据。
- 本次源码、位流及证据归档至 `release/A713/`。源码构建入口为 `build_toggle.tcl`，审查为 `tests/audit_build.py --variant toggle`。

## 用户指定 80% 的持续运行版（A714）

新增包装顶层 `rtl/acg720_motor_toggle_80.v`，复用 A713 控制器，仅将 `DUTY_PERCENT` 显式设为 **80**。顶层 `acg720_motor_toggle_80` 使用 `build_toggle80.tcl` 编译，User Code=`0x0000A714`；审查为 `tests/audit_build.py --variant toggle80`。S1/S2 独立持续启停、S0 停止、1 kHz 周期、400 ms 爬升和编码器记录规则均沿用 A713；平台高电平为每周期 40000/50000 个时钟，即 800 µs。

仿真以 `-DTOGGLE80_TEST` 编译同一持续启停测试，实际检查 80/100 的平台 PWM，并覆盖长按、持续运行、第二次停止、独立两轮和 S0 停止。A713 的已通过源码及记录没有修改，便于对照及恢复。构建/下载和实物结果按后续完成记录确认。

A714 完成记录：

- 仿真通过，21 个实际 PNR 管脚与接线一致；50 MHz setup/hold 违反端点均为 0，Fmax=170.122 MHz。
- 位流 `impl/pnr/acg720_motor_toggle_80.fs`；SHA256=`4E65CDF93D7B43819BFF3ACB35E94D34A5DE69E4DF51D26C7BFD1F11E373EC23`。
- 下载前独立读取 `0x0000A713`，SRAM 下载后独立读取 User Code=`0x0000A714`、Status=`0x70022020`。外部 Flash 未写；证据归档 `release/A714/`。
- 用户反馈“感觉并没有变快，除了调整占空比，是不是频率也要设置一下？”。未获得实测转速，因此只记录没有主观明显加速，不能确认 65% 和 80% 实际转速完全相同。

## 20 kHz、80% 频率对照（A715）

A715 包装顶层 `rtl/acg720_motor_toggle_20khz_80.v` 复用同一持续控制器，将频率从 1 kHz 改为 20 kHz，保持 80%、400 ms 爬升、按键和 IN1=PWM/IN2=0 快衰减接法。一个周期 2500 个 50 MHz 时钟；平台高电平 2000 个时钟（40 µs），低电平 500 个时钟（10 µs）。编译 `build_toggle20k80.tcl`；审查 `tests/audit_build.py --variant toggle20k80`，User Code=`0x0000A715`。

本次对照不承诺加速。AT8236 原厂手册第 3 页允许控制 PWM 至 100 kHz，第 5 页说明快/慢衰减接法，第 6 页说明 VREF/ISEN 决定电流阈值；目前使用快衰减。频率会影响电流建立、纹波和噪声，而稳态转速还受负载、供电及电流限制影响；没有电流、波形或转速数据时，不将其中某项认定为根因。TI 的 [PWM 与衰减接口说明](https://e2e.ti.com/support/motor-drivers-group/motor-drivers/f/motor-drivers-forum/963987/faq-what-interface-ph-en-or-pwm-to-use-for-controlling-brushed-dc-motors) 和 [电流续流及衰减应用报告](https://www.ti.com/lit/an/slva321/slva321.pdf) 用于核对一般原理，不替代 AT8236 本体规格。

仿真使用 `-DTOGGLE20K80_TEST`，每 1 ms 同时核对 PWM 上升沿数和高电平占比，避免只验证平均占空比而遗漏频率；还覆盖持续启停和 S0 停止。实物转速变化需要后续观察或编码器计数比较。

A715 仿真及编译完成，但下载前用户要求“直接上50kHz”，因此 **A715 未下载**，不记任何实板结果。源码和构建入口保留供后续对照。

## 用户指定 50 kHz、80%（A716）

包装顶层 `rtl/acg720_motor_toggle_50khz_80.v` 显式设 `PWM_HZ=50000`、`DUTY_PERCENT=80`，复用已验证的持续启停控制器。板载 50 MHz 下每周期 1000 个时钟，高电平 800 个时钟（16 µs），低电平 200 个时钟（4 µs）。400 ms 爬升、S1/S2 启停、S0、编码器及接线保持原实现。

使用 `build_toggle50k80.tcl` 和 `tests/audit_build.py --variant toggle50k80`，User Code=`0x0000A716`。仿真 `-DTOGGLE50K80_TEST` 使用可精确表示 80% 的测试时钟，每毫秒检查 50 个上升沿及 80% 高电平，并验证持续运行和按键停止。提高频率不是转速提高的证明，实际结果另记。

A716 完成记录：

- 专用仿真通过，21 个实际 PNR 端口与接线一致；50 MHz setup/hold 违反端点均为 0，Fmax=188.257 MHz。
- 位流 `impl/pnr/acg720_motor_toggle_50khz_80.fs`；SHA256=`9C85F5250EF1EF790036797F47320E03269E792131773B30437A78106287890B`。
- 下载前独立读取 `0x0000A714`；SRAM 下载后独立读取 User Code=`0x0000A716`、Status=`0x70022020`，未写 Flash。
- 已请用户观察实际启停、声音及转速变化，目前待反馈。50 kHz 对照的输出设置已确认，尚未确认提速。
- 位流、源码哈希、实际 PNR/时序、仿真、构建及下载/回读记录保存在 `release/A716/`。

当前版复现：

```powershell
& 'C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe' './build_toggle50k80.tcl'
& 'C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'tests/audit_build.py' --variant toggle50k80

$motorIcarus = '../acg720-ddr3/.local/tools/iverilog/bin'
& "$motorIcarus/iverilog.exe" -g2012 -Wall -DTOGGLE50K80_TEST -s acg720_motor_toggle_tb -o '.local/motor_toggle50k80.vvp' 'rtl/acg720_motor_toggle.v' 'rtl/acg720_motor_toggle_50khz_80.v' 'tests/acg720_motor_toggle_tb.v'
& "$motorIcarus/vvp.exe" '.local/motor_toggle50k80.vvp'
```
