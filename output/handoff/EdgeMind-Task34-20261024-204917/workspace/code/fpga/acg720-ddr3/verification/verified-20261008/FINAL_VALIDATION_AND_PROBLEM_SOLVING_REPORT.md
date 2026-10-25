# ACG720 摄像头实景 → DDR3 帧缓存 → HDMI 连续显示验证交付报告

**报告日期：2026-10-08（Asia/Shanghai）**  
**交付目录：** `/home/tinsiag/Documents/cam/build/ddr3_live_hdmi/verified-20261008`  
**目标器件：** GW5AT-60B / GW5AT-LV60PG484AC1/I0  以及 ACG720 开发板

## 1. 最终验证结论

本目录保存的是已经编译完成、并由用户在实板上验证显示功能的固件：

- HDMI 显示器能够显示 OV5640 摄像头实景画面；
- D6 熄灭，未观察到固件错误指示；
- D7 闪烁，系统心跳正常；
- 摄像头 → DDR3 帧缓存 → HDMI 连续显示链路在本次实板条件下验证通过。

因此，本目录中的 `firmware/ddr3_live_hdmi.fs` 是**实板功能验证通过的 SRAM 下载位流**。它不是只通过仿真的文件，也不是单帧 CRC 自检固件。

位流 SHA256：`b6e3967afc4785ff42cb147c1060a8a3d5e2ad39c560904a4f1e8b8b3d8fd6f8`

照片证据见 `hardware-evidence/hdmi_scene.png`，用户反馈原文见 `hardware-evidence/user-verification.md`。

## 2. 需求、问题与解决路径

### 2.1 原始目标

原始需求是把 TY-OV5640 摄像头实景经过 DDR3 帧缓存后，持续输出到 HDMI 显示器，而不是采集一帧后停止。

### 2.2 早期问题：旧诊断只亮 D0

历史记录显示，旧 DDR/摄像头诊断只亮 D0。不能据此直接判断 DDR 芯片损坏，因为旧流程在 DDR 校准完成前就没有继续推进。源码审查还发现：

1. 旧诊断只产生 16 个 RGB565 像素，即 2 个 128-bit 数据块；适配器的 `wr_bust_len=8` 要求至少 8 个块，写入启动门槛达不到。
2. 状态机用固定延时进入读阶段，没有等待 DDR 实际写命令完成。
3. 读 FIFO 为 FWFT，队首 Q 在 pop 当拍有效；旧代码延迟一拍比较，连续读时可能与下一个像素错位。
4. 一次性 toggle 事件可能在校准等待期间到达而被错过。

**解决方向：** 不再用小样本、固定延时和错位比较判断整条链路，改用完整帧、实际握手和明确的跨时钟状态保持。

### 2.3 第 38 章工程综合失败

官方第 38 章的生成 `rd_data_fifo.v`、`wr_data_fifo.v` 在 GW5AT-60B 当前 Gowin 版本下触发 `RP0007`，提示当前器件没有 SSRAM 资源。

**解决办法：** 采用资料包第 47 章中可在本器件上综合的 BSRAM FIFO 实现，并逐项核对 `.ipc` 配置。最终保持：

- 写 FIFO：16 bit → 128 bit，8 KiB，FWFT，非输出寄存；
- 读 FIFO：128 bit → 16 bit，8 KiB，FWFT，非输出寄存；
- 生成 FIFO 配置与参考配置匹配；
- 最终报告确认 SSRAM=0，BSRAM 使用 38/118。

### 2.4 DDR PLL 与时钟路径

采用第 38 章的 DDR3 基线：原始 50 MHz 作为参考，DDR memory clock 400 MHz，DDR 用户接口 100 MHz；系统 PLL 提供 50 MHz、165 MHz，CLKDIV 产生 33 MHz HDMI 像素时钟。

根据历史记录修正 DDR PLL mDRP 交接：PLL 锁定后等待 16 拍，再通过原始 50 MHz 域登记 `pll_stop` 边沿并交出 mDRP 控制，避免初始化控制被优化或过早交接。

### 2.5 摄像头初始化与整帧捕获

沿用官方 RGB565 初始化表，并使用 800×480 配置：`5001=A3` 启用 scaler、`503D=00` 关闭内部测试、追加 `4741=00` 关闭 DVP 测试。摄像头 ID、格式、尺寸和测试开关进行读回检查。

采集端启动时跳过前 10 帧，之后逐行检查：800 像素、480 行、384000 个 RGB565 像素。短行、长行、奇数字节、额外行、VS 边界异常和 FIFO 满均不发布为有效帧。

### 2.6 连续 HDMI 显示

新增双 DDR 帧区管理：一块只写、一块只读显示。完整帧写完并确认 DDR 命令/数据握手后，等待 HDMI 帧间空白，停止旧读事务、等待旧读返回、清空读 FIFO，再切换显示区。没有新帧时重复上一帧，避免显示撕裂。

仿真已覆盖：完整 800×480 帧、跨时钟 FIFO、DDR 命令/数据独立停顿、帧切换、坏帧丢弃、欠载恢复和显示区保护。

## 3. 编译和测试证据

最终编译目录为：`build/ddr3_live_hdmi/20261008T202857`。Gowin 综合、布局布线、位流生成返回 0，无 ERROR；完整结果见 `firmware/build-result.json` 和 `pnr-report/`。

仿真日志位于 `tests/`，包括：

- FIFO/帧区切换保护；
- 短行、长行、奇数字节、额外行、溢出和 VS 边界检查；
- HDMI 欠载和下一帧恢复；
- 完整管线多帧显示；
- 800×480 摄像头配置事务和读回门控。

Git 关键提交及历史摘要位于 `git-history/`：

- `a1c4aa2`：新增 DDR3 双帧连续 HDMI 固件与实板反馈；
- `052e0f1`：分类 DDR3 live 时序违反；
- `b5fbaf5`：记录时序闭合实验。

## 4. P&R 时序遗留问题：功能通过不等于时序闭合

最后一次正式交付位流对应的 P&R 报告是：`pnr-report/ddr3_live_hdmi.tr`。
报告摘要仍为：

- **101 个 setup 违反端点**；
- **29 个 hold 违反端点**。

因此，本次结论必须严格写成：**功能实板验证通过，但完整静态时序报告尚未闭合。**

进一步分析发现：

1. 一部分 setup/hold 路径是 `camera_pclk ↔ ui100`、`pixel33 ↔ ui100` 的异步 FIFO 指针和单 bit 同步器路径；工具默认会分析 CDC。隔离实验加入精确异步时钟组后，摘要由 101/29 降为 76/18，但不能因此直接把所有 CDC 路径隐藏。
2. 最差 setup 约 **-2.189 ns**，集中在 Gowin DDR PHY 的 DLL step、DQS 和校准内部路径。这些是生成的专用 PHY 逻辑，不能直接修改网表或用全局 false path 掩盖。
3. 展开报告还有大量 reset recovery 违反，最差约 **-6.392 ns**，主要涉及 DDR PHY reset/校准与 400 MHz 时钟关系。reset recovery 需要单独解决。
4. 将所有 PLL 输出简单改成 generated clock 的隔离实验结果更差，为 143 setup、60 hold、176 recovery，因此没有把该实验约束用于最终位流。

### 待解决事项

- 对真实异步时钟域、FIFO 同步级和单 bit mailbox 做精确 CDC 约束与结构审查；
- 按 Gowin 官方同器件 DDR3 基线核对 PHY 配置、mDRP、reset 和 P&R 选项；
- 解决或解释 DDR PHY 内部 setup/hold/recovery 路径；
- 对各时钟域实行异步拉低、同步释放的 reset 方案；
- 重新 P&R 后进行 HDMI 实景、D6/D7、长时间运行和复位实测。

在上述事项完成前，不应把本位流称为“完整时序签核通过”，也不应直接写入配置 Flash 作为最终量产固件。

## 5. 目录文件说明

- `firmware/ddr3_live_hdmi.fs`：最终实板功能验证位流；
- `pnr-report/`：最后一次正式 P&R 报告及时序研究；
- `hardware-evidence/`：HDMI 实景照片和用户验证记录；
- `tests/`：仿真通过日志；
- `git-history/`：Git 提交和历史记录；
- `SHA256SUMS`：位流校验值。

本目录只保存证据和已编译产物，不执行 programmer，不修改配置 Flash。
