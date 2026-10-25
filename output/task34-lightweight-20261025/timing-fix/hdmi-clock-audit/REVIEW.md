# HDMI 隔离时序实验审查

所有实验仅在本目录运行，没有修改主工程，也未操作硬件。

原 serial 域复位同步器的三个 FF 存在最小脉宽违例；移到 pixel 域后最小脉宽问题消失，但四路 OSER10 RESET 出现 removal 负余量。改用 pixel 下降沿释放也未解决。LOCAL_CLOCK 实验报告 CT1018，不是有效的时钟改线。

`pixel-domain-reset/impl/pnr/cmd.do` 已明确包含 `-timing` 和 `-correct_hold 1`：工具默认开启保持时间修复。不是此前缺少该开关。额外的 `pixel-domain-reset-hold` 第一次尝试因 Tcl 参数 `-correct_hold` 无效而退出，未产生新实验结果；脚本参数已改为文档中的 `-correct_hold_violation`，无需重复相同默认配置。

`pixel-reset-min-delay` 尝试对四路 RESET 施加 3 ns 最小延时约束。虽然工具返回成功、Setup/Hold 计数为零、MPW 为正，但检查 `.tr` 发现四路 serializer/RESET 不再出现在 recovery/removal 表，例外报告为 `No timing paths to report!`。因此拒绝此结果；它没有证明实际插入延时或修复复位时序。不得据此整板签核，不得合入该约束。

官方 UG304-1.3.8E 第104页将 OSER10 RESET 定义为高有效异步复位。旧 DVI 参考设计直接使用外部复位与 PLL lock，约束也不完整；这不构成删除当前恢复/移除检查的依据。

## 可继续验证的候选

`pll-div2-reset` 使用同一PLL的闲置CLKOUT0生成82.5 MHz，MPW转正，但仍有4个复位恢复端点失败，未集成。

`pll-pixel-activehigh-reset` 将闲置CLKOUT0设为33 MHz（ODIV0=25、fraction=0，PLL VCO、165 MHz串行和CLKDIV像素时钟保持不变），直接生成高有效三级同步复位，避免额外反相。route_option=2时4个恢复端点仍负，最差-0.557ns。

同一设计 `pll-pixel-activehigh-route1` 仅改用文档规定优先时序的route_option=1，50.98秒完成，Setup/Hold端点计数均0；恢复最差+0.102ns、移除+0.351ns、MPW+6.672ns。四个OSER10 RESET端点仍在恢复和移除表内，各12条路径；没有min-delay例外。该候选已通过HDMI功能仿真及异步置位/三级释放检查，随后纳入 `interface-and-telemetry-fix` 待整板验证。隔离通过不代表整板或实板通过。

脚本输入现在固定为 `baseline-inputs/`，逐字复制自最初explicit-generated实验，避免主工程集成后再运行实验时重复改写新PLL参数或复位结构。

`pixel-activehigh-route1` 于03:44完成，22.98秒。Setup计数0、Hold计数4；普通hold为正，但四个OSER10 RESET的removal失败，最差-1.026ns。Recovery最差+4.044ns、MPW+6.672ns。该替代方案不合入主工程。

独立33MHz复位时钟与CLKDIV像素时钟的启动相位还需核对；相同PLL来源不保证分频器任意复位后仍保持唯一33MHz相位。新增55MHz隔离候选只用于诊断：相对165MHz除3、像素除5，静态时序自然覆盖五种整周期相位关系。正在运行的整板输入保持不变；候选未通过前不集成。

## 启动相位核对与局部复位候选

`clkdiv_phase_tb.v` 使用安装工具自带的 `gw5a/prim_sim.v` 中实际CLKDIV模型，扫描RESETN释放相位，CALIB保持1。为避免浮点舍入，测试将165/33MHz比例等比缩放成6/30ns。`clkdiv-phase.log`确认全部五种整快时钟周期相位均可能出现。最初测试夹具没有将每轮起点对齐公共周期，仅覆盖三种相位；调整夹具对齐后五种全部覆盖，不是修改被测原语。

因此此前独立33MHz候选仅按一个像素相位得到的隔离零违例不足以签核。`pll-55-activehigh-route1`覆盖全部相位后，发现四个RESET recovery违例，最差-0.808ns；不能直接合入。

`pll-55-local-reset-route1`将55MHz三级高有效复位同步器按四路OSER10分别复制，用syn_preserve/syn_keep防止被合并。保持原165MHz串行、CLKDIV像素、管脚和全部RESET恢复/移除检查。该隔离工程于03:49:39完成，24.39秒，Setup/Hold计数0；Recovery最差+0.957ns、Removal+0.116ns、MPW+5.055ns。报告中四路各自的复位FF均存在，RESET到pixel及serial双沿的检查保留。它仍只是候选，尚未整板或实板通过；当前整板PNR输入未变更。
