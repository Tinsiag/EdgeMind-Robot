# A71A 空载桥输出测量构建与实板记录，2026-10-15

**最新：A71B 两路试转均未起动，R 模块 AOUT 测为 0 V；用户在驱动期间未观察到 VM 下降，但没有给出最低数值。为隔离电机负载及 PWM 平均读数，用户已确认两电机插头都拔下、VM 断开、FPGA 逻辑供电。核对原已审查 A71A 位流与全部源码哈希不变后，从 A71B 切回 A71A，仅 SRAM 下载，独立回读 A71A / 0x70022020。两个电机必须继续拔下；当前请求单次 S2、D2 亮的最长 2 秒内测 R 模块本体 AOUT1 对 AOUT2，测后松键断 VM。用户明确确认 D2亮约2秒、万用表一直0 V；随后只读回读仍为 A71A。已确认空载也无可测输出，不能单靠电机负载或PWM占空比解释全部现象；尚未验证带VM时模块IN1/2恒定电平及底板是否钳位输出，不能认定模块本体损坏。当前不再追加同类重复测量。** 新证据为 `verification/2026-10-15/r-unloaded-reprogram-evidence-20261015.json` 及带 r-unloaded 的日志；本次未改源码、未重新编译、未写 Flash。下文 17:25 等为此前阶段历史记录。

**用户纠正此前 3.3 V“测的不是 AOUT”，该值不得作为输出证据。17:25 后重新下载 A71A 到 SRAM，独立回读 A71A / 0x70022020 成功；用户按正确 AOUT 测点复测要求反馈 0 V。两电机继续拔下，下一步实测 AIN1/2 对 GND 的控制电平，无电机起动通过证据。** 本次仍未写 Flash，不能假定断电重启后仍为 A71A。

## 最新构建、下载与实板观察

- 用户处理系统设置后，只读检查智能应用控制状态为 0；实时防护仍关闭，已提醒可以恢复开启。系统设置由用户操作，代理未修改。此前签名拦截记录保留在下方。
- Gowin V1.9.12 Windows x64 于 2026-10-15 16:55:25（Asia/Shanghai）完成综合、P&R 和位流生成。实际 21 个端口、方向、LVCMOS33、驱动下拉、User Code 审查 PASS；50 MHz setup/hold 违例 0/0，Fmax 182.731 MHz，最差报告 setup/hold slack +14.528/+0.275 ns。工具配置不代表实测 VCCIO。
- 位流 `impl/pnr/acg720_bridge_probe.fs`；SHA256 `B8D3DE04C7500B1B90E066FCEBB27C489F2C10F88401ACA3A18284EBD088DD32`；User Code `0x0000A71A`。
- 下载前独立回读 A719。核对上述位流哈希后，经 Gowin USB Cable(FT2CH)、USB location=8740、器件 ID=`0x0001481B` 执行 operation_index=2（SRAM Program），100% 完成，未写 Flash。
- 下载后另行执行 operation_index=73/74，独立回读 User Code=`0x0000A71A`、Status=`0x70022020`。
- 用户随后按 VM 断开、两电机拔下、松开两键后单独持 S1 超过 2 秒的要求，确认 D1 亮约 2 秒后自动灭、D5 亮。只证明用户观察到左路控制灯/定时行为；尚未实测 IN 电压、桥输出或右路实板计时。
- 随后用户按板上左电机六针插座红 6、黑 1 的直流测量要求反馈 `0 V`，追问后明确是 D1 亮期间的读数。此后再次独立回读 A71A 成功（`.local/after-zero-voltage-usercode-20261015.log`），未重新下载。板端无压的现象已得到用户读数，但本次模块端 VM、IN 和 OUT 实测仍待补，不能据此定模块损坏。
- 后续用户测左模块本体 VM 对 GND 为 11 V，再反馈 3.3 V。**随后用户纠正该 3.3 V 测点不是 AOUT，输出推论撤销。** 原始反馈 JSON 保留为历史，另存更正记录，不覆盖原数据；没有可用于对比板端 0 V 的有效模块 AOUT 电压。
- 17:25 后按用户“再烧一次程序”要求，位流哈希核对与已审查版本一致，下载前实际回读 A719。针对同一器件/下载器执行 SRAM Program 100% 完成，随后独立回读 A71A、Status=0x70022020。日志使用 reprogram-20261015-1725 后缀，未写 Flash，未改源码或提高输出时限。
- 构建日志、实际 PNR/STA 报告、审查 JSON、下载前/下载/下载后日志已归档 `verification/2026-10-15/`，包含位流和源码哈希；不归档位流本体。`bridge-probe-prebuild-evidence-20261015.json` 保留最初被阻断的历史状态，最新成功构建见 `bridge-probe-build-evidence-20261015.json`。

## 目的与固定行为

用户确认两电机六针插头都已从电源板拔下。现有静态控制输入测量左 IN1/2 高电平约 3.2 V，模块 VCC 约 3.3 V，但新接线下尚无电机起动证据；需下一阶段检查空载桥输出是否到达电机板端插座。

本固件在两电机都拔下时使用静态输入，以便万用表测稳定直流输出。**静态高电平相当于该方向全幅使能，不是 50% PWM；严禁用本固件接电机试起动。** 没有电机插头检测、VM 检测或电流检测，软件不能验证隔离条件。

- 顶层 `rtl/acg720_bridge_probe.v`；工程 `acg720_bridge_probe.gprj`；入口 `build_bridge_probe.tcl`；User Code `0x0000A71A`。
- 配置默认禁止，初始化 100 ms；两键先稳定松开 20 ms，才接受后续单键按住。
- S1：左 IN1=A18 高、左 IN2=A19 低。S2：右 IN1=F13 高、右 IN2=F14 低。一次仅一路；无 UART。
- 松键、S0 或同时按键直接门控输出为低，不等待去抖或时钟；按住最长 2 秒。长按到时不会重复，必须两键重新稳定松开；切换剩余键不能自动启动。
- 计时按系统时钟周期独立计数；PROBE_MS 测试参数上限硬裁剪到 2000 ms。时限依赖 FPGA 时钟和配置，不能代替物理断电。
- 停止为 IN1/IN2=00，桥为高阻/滑行；停止后的万用表电压不必立即为 0，不据此判故障。
- D0=初始化释放，D1=左实际 IN1 逻辑高，D2=右实际 IN1 逻辑高，D3/D4=左右同步 AB 任一高，D5=2 秒到时锁存，D6=双键拒绝锁存，D7=心跳。LED 不代表桥输出实测；与 A719 灯义不同。
- 沿用维修后当前 CST/SDC 与 camera_reset_n=C14 保持低，不修改历史位流、闭环参数或电机方向配置。

## 已完成验证

本地 Icarus：

1. `acg720_bridge_probe_tb` PASS：配置/复位持键锁止、去抖、左右选择、准确计时、长按到时不重复、松键/S0/双键异步禁止、释放抖动不重新允许、双键后剩余键不启动、重新稳定松键、LED 对应。
2. `acg720_bridge_probe_duration_tb` PASS：降低仿真时钟但保留默认 2000 ms 参数，计时准确；将 PROBE_MS 设为 4000 仍于 2000 ms 到时，不因持键重复。
3. 当前接线静态回归 10 项 PASS。初次 Windows 默认 GBK 解码文档失败，改用 Python `-X utf8` 后全通过；不是引脚或 RTL 故障。

仿真输出见 `.local/sim/acg720_bridge_probe*_tb.log`，交接证据另存于 `verification/2026-10-15/`。这些验证不证明实际桥电压、实际 VCCIO 或电机好坏。

复现示例（本工程目录，按实际本机工具路径调整）：

```powershell
$probeIvlRoot = Resolve-Path '../acg720-ddr3/.local/tools/iverilog'
New-Item -ItemType Directory -Force '.local/sim' | Out-Null
foreach ($probeTb in @('acg720_bridge_probe_tb','acg720_bridge_probe_duration_tb')) {
    & "$probeIvlRoot/bin/iverilog.exe" -B "$probeIvlRoot/lib/ivl" -g2012 -Wall -s $probeTb -o ".local/sim/$probeTb.vvp" 'rtl/acg720_bridge_probe.v' "tests/$probeTb.v"
    if ($LASTEXITCODE -ne 0) { throw "Compile failed: $probeTb" }
    & "$probeIvlRoot/bin/vvp.exe" ".local/sim/$probeTb.vvp"
    if ($LASTEXITCODE -ne 0) { throw "Simulation failed: $probeTb" }
}
```

仓库根目录接线回归：`python -X utf8 -B -m unittest discover -s code/fpga/tests -v`。

## 此前构建阻断与后续恢复

启动 `C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe` 后，用户反映 Windows 安全中心连续通知，指明 DDR.dll 被阻止。系统 CodeIntegrity/Operational 的 3077/3033 事件确认 gw_sh 加载多个 IP 库不满足签名策略。DDR.dll 路径为 `IDE/ipcore/DDR/DDR.dll`；文件签名状态 NotSigned，gw_sh.exe 自身状态 Valid。其他已记录拦截涉及 CAN、EASYCDR、EDID_PROM。

脚本包装入口的首条输出也未执行，因此不能报告已综合或已做布局布线。所有本轮构建进程已停止，不修改 Windows 安全策略，不移走被拦截库或套用历史 `.fs`。

用户确认此前 Linux 构建环境目前不能使用。后续只读检查发现本机 `HKLM/SYSTEM/CurrentControlSet/Control/CI/Policy/VerifiedAndReputablePolicyState=1`（智能应用控制开启）；CiTool 列举策略返回访问被拒绝，没有提权或更改策略。微软当前 FAQ 说明智能应用控制没有单个应用例外，可在安全中心关闭，近期 Windows 更新支持重新启用；这些是供用户选择的系统设置说明，当前尚未实际关闭。资料：https://support.microsoft.com/zh-cn/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions 。

后续用户要求继续时，检查发现智能应用控制已关闭（状态 0）。重新运行 `build_bridge_probe.tcl` 后构建成功，`python -X utf8 -B tests/audit_build.py --variant bridge_probe` 已对新生成的实际 PNR/STA 报告通过审查，详见本文件顶部最新记录。此前被阻断的证据不覆盖。

## 后续测量条件

正确 AOUT 测点复测优先于此前因错误 3.3 V 而提出的导通测试。FPGA 保持供电、不重启，左右电机插头均保持拔下。VM 关闭时用直流电压档，红笔接左模块实际 AOUT1、黑笔接实际 AOUT2。用户第一张 PCB 截图的上方黄色框内，从左起 1=AOUT2、2=AOUT1；需按实际模块丝印确认，不能将 VCC/3.3V 或 AIN 当作 AOUT。

固定好测点后接 VM，单独持 S1，在 D1 亮的最长 2 秒内读数，松键、断 VM 后反馈。用户随后按此复测要求反馈 0 V。下一步检查 AIN1/2 的本轮实际电平，不能直接判模块坏。

用户进一步确认此前 3.3 V 的表笔接法为红 AIN1、黑 AIN2，即输入之间的差分电压；不能作为两个输入各自对地为高的证据。下一步只补 AIN2 对 GND：VM 关闭时黑笔接模块 GND、红笔接 AIN2，直流电压档，接 VM 后在 S1/D1 亮期间读取，松键断 VM；保持 FPGA 供电、两电机拔下，2 秒时限不变。按第一张图下排从画面左向右，GND 第 1 个（编号 7）、AIN2 第 4 个（编号 4），预期 AIN2 约 0 V。若不能确认实物测点，先取得模块实物照片再带电；停止高阻后的读数不用于判定驱动时电压。
