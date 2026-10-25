# 2026-10-15 诊断构建审查证据

最新新增 A71B（hold50）实际 PNR/STA 报告、两项专用仿真、A71A 回归、构建审查与 SRAM 下载/独立回读日志。21 端口匹配，50 MHz setup/hold 违例 0/0，Fmax 151.558 MHz，User Code A71B。用户随后报告 S1/S2 两轮均不转，D1/D2 各约 1 秒，D3/D4 未亮；电机问题尚未解决。最新构建记录为 `hold50-build-program-evidence-20261015.json`，后续用户观察另存，不覆盖原始记录。

A718与A719的实际管脚、IO配置、时序违例计数、Fmax、User Code、位流及源码哈希。文件名中的20261014指接线修订日期，不是构建日期。SHA256SUMS.json校验归档文件。

审查只能验证工具报告，不能证明实板VCCIO、引脚波形、桥输出或电气安全。A718后续由用户报告已下载并测试但未转动；A719后续用户提供IN静态电压3.2V。初始“未下载”的构建记录是当时状态，不是当前状态。无现场下载器回读User Code证据。

位流保留在本地impl/pnr，不提交二进制；使用各build脚本复现，重新构建哈希可能因工具和环境改变。VM物理断开才可使用A719。

本机后续新增 A71A 的两项仿真日志及 `bridge-probe-prebuild-evidence-20261015.json`，记录源码哈希、Windows 签名拦截、当前隔离状态和未构建/未下载的边界。**A71A 没有完成 PNR/STA，不是构建通过证据。** 原有 A718/A719 审查文件不变。

上述 prebuild 是首次阻断时的历史快照。后续 16:55 已恢复构建，并新增 `bridge-probe-build-evidence-20261015.json`、实际 PNR/STA 报告、build-audit-bridge_probe、SRAM 下载和独立回读日志：21 端口符合当前接线，setup/hold 违例 0/0，Fmax 182.731 MHz，User Code A71A。用户在其后确认 VM 断开时 S1/D1 约 2 秒到时、D5 亮；该用户观察不等于桥电压或电机起动验证。位流本体不提交。

Windows 检出曾将原 A718/A719 的两个审查 JSON 从 LF 转成 CRLF，导致原始 SHA256 的字节校验失败；确认转回 LF 恰好匹配原清单后，已恢复为原哈希对应的字节，原清单条目不改写。verification/.gitattributes 禁止证据目录自动转换换行，本轮新增证据按实际字节归档。


最新A71D左路固定电平版：用户报告右驱动损坏后要求LAIN1=1/LAIN2=0，右路两输入0，无PWM及按键/超时门控，VM继续断开。专用仿真、10项管脚静态回归、21个PNR端口、OBUF常量及50MHz时序审查通过；仅SRAM下载并独立回读A71D / 0x70022020。详见left-static-build-program-evidence-20261015.json；本轮未验证物理输出或电机起动。


### 后续实物反馈：两路分别使能、VM均约11V，AOUT仍无输出

**后续用户明确补充：分别在A71C右路、A71D左路测试时，两模块本体VM端均约11V，但两路AOUT均无输出。** 不能再以VM断开或只测了未使能通道解释该结果。两路输出链路异常，重点怀疑驱动模块或底板输出通路；尚无这两次带VM恒定输出测试中模块AIN1/GND、AIN2/GND的实测记录，也未新确认电机插头状态或排除底板短路/钳位，故不把两颗AT8236芯片烧毁作为已证实根因。测试后VM当前通断状态未提供，不再假定仍断开。本次仅记录判断，未改代码、未烧录或操作VM。

证据：both-static-aout-zero-vm-present-user-observation-20261015.json。
