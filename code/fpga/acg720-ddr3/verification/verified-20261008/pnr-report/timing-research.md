# DDR3 Live HDMI 时序研究（2026-10-08）

对象：`build/ddr3_live_hdmi/20261008T202857/impl/pnr/ddr3_live_hdmi.tr`。
本研究是只读分析和隔离 P&R 实验，不改写已验证位流，也没有下载硬件。

## 当前结论

原始交付报告的摘要为 **101 setup、29 hold 违反端点**。这不是一个可以用“功能已通过”直接忽略的结果；但它也不等于 130 条都属于用户逻辑的真实同步数据错误。Gowin 的报告同时打印了代表性最差路径，默认只有 25 条；扩展为 1000 条后，负 setup 代表路径为 33 条、负 hold 代表路径为 29 条，另有 114 条负 recovery 代表路径。摘要端点计数与打印代表路径不是同一统计口径。

已用 Gowin Timing Constraints Guide 核对：工具默认会分析 CDC 路径；官方建议对确实异步的时钟使用 `set_clock_groups -asynchronous` 或有针对性的 `set_false_path`。本工程的 camera PCLK、DDR UI 100 MHz、HDMI pixel 33 MHz 是独立时钟域，FIFO/单 bit handshake 已使用同步级，故它们不应被当作普通同步路径签核。

## 路径分类

### 1. 需要用 CDC 约束表达意图的路径

原始报告中主要包括：

- `reader/fifo_inst/Small.*`：`pixel33 ↔ ui100` 读 FIFO 指针同步，负 setup 约 20 条代表路径。
- `writer/fifo_inst/Big.*`：`camera100 ↔ ui100` 写 FIFO 指针同步，负 hold 约 10 条代表路径。
- `engine/tick_s_0_s0`、`engine/blank_s_0_s0`、`video/ready_s_0_s0`：HDMI 帧边界与 DDR/UI 的单 bit 同步。
- `capture/req_s_0_s0`：DDR/UI 对摄像头 PCLK 的请求同步。

这些路径的目的就是进入异步域的第一级同步器。若实际 CDC 结构正确，不能通过把逻辑频率调低来修复；应该在确认同步级和复位策略后，用 `set_clock_groups -asynchronous` 表达不相关时钟关系，并继续对同步器/异步 FIFO 做 CDC 检查。

### 2. DDR PHY 内部路径

原始最差 setup：约 **-2.189 ns**，来自 DDR PHY 内部 `u_dll → dll_step_base_*`，并有 `read_rclksel_conf → u_dqs` 等路径；hold 还有约 16 条 PHY 内部路径，recovery 绝大多数也落在 PHY 内部复位/校准路径。

这些节点属于 Gowin 生成的加密/专用 DDR PHY，不是本工程可以安全重写的 RTL。应优先使用与器件、DDR 型号、400 MHz、1:4 比例匹配的官方 IP/约束和官方推荐 P&R 选项；不能对这些路径直接加全局 false path，也不能手改生成网表。

### 3. Reset recovery

扩展报告的负 recovery 代表路径达到 114 条，最差约 **-6.392 ns**，主要是 `reference50 → DDR 400 MHz PHY` 的 reset/recovery。它不是 setup/hold 数据通路，但说明异步复位解除时序没有闭合。

用户逻辑应保证每个时钟域的复位**异步拉低、同步释放**，并避免用未经本域同步的 `calibrated`/PLL 状态直接作为异步复位释放。DDR PHY 的 reset 则必须遵循其 IP 接口和官方时序，不能用顶层简单替换。

## 隔离实验

### 实验 A：仅增加真实异步用户时钟组

在基线副本上只加入：

```tcl
set_clock_groups -asynchronous -group [get_clocks {camera100}] -group [get_clocks {ui100}]
set_clock_groups -asynchronous -group [get_clocks {pixel33}] -group [get_clocks {ui100}]
```

未改变 RTL、器件、引脚、DDR IP 或 P&R 选项。实验结果：

| 指标 | 原始约束 | 异步时钟组实验 |
|---|---:|---:|
| setup 违反端点 | 101 | 76 |
| hold 违反端点 | 29 | 18 |
| 代表性负 setup | 33 | 10 |
| 代表性负 hold | 29 | 18 |
| 代表性负 recovery | 114 | 112 |
| 最差 setup | -2.189 ns | -2.189 ns |
| 最差 hold | -0.961 ns | -0.462 ns |
| 最差 recovery | -6.392 ns | -6.392 ns |

这证明至少一部分原始违反确实是工具对 CDC 的默认分析，并非普通同步路径；同时也证明异步分组**不能解决 DDR PHY 和 reset recovery**。该约束目前只在隔离实验副本中，未并入已交付工程、未重新生成交付位流。

### 实验 B：把 PLL 输出都建模为 generated clock

这个实验仅修改时钟约束，把 ref50、serial165、pixel33、400 MHz 和 UI 100 MHz 声明成生成时钟，没有添加异步例外。结果反而为 **143 setup、60 hold、176 recovery**，因此不能直接采用该约束模型；它改变了工具对专用 PHY 时钟关系的解释，却没有证据证明这些关系和 IP 内部实际时序一致。

## 建议的下一步顺序

1. 保留当前已上板通过的 SRAM 位流，不用实验约束重新下载。
2. 先确认 FIFO 的每个跨域同步级、单 bit mailbox 的脉冲/电平协议和 reset release；为真正异步的 camera/UI/pixel 时钟加入精确的异步时钟组，并重新跑 P&R。
3. 对 reset recovery 做域内同步释放；DDR PHY reset 继续遵循 IP 生成逻辑，不做全局例外。
4. 使用官方第 37/38 章同器件 DDR 工程作为对照，比较其 DDR 约束、PHY 配置、P&R 选项和 recovery 报告。如果官方基线同样有内部 PHY 负路径，应向 IP/工具约束方向处理；如果官方基线闭合，再逐项比较本工程顶层 reset/PLL 连接。
5. 只有在 setup/hold/recovery 的报告解释清楚并重新实板验证画面、D6/D7、长时间运行后，才能称为时序风险已收敛。

## 证据文件

- 基线扩展报告：`expanded-baseline.json`
- 异步时钟组隔离实验：`async-groups.json`
- 生成时钟模型隔离实验：`generated-clock-model.json`
- 原始交付位流目录：`build/ddr3_live_hdmi/20261008T202857`

没有运行 programmer，没有改写配置 Flash。
