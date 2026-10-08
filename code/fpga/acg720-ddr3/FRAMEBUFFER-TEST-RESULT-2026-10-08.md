# 第 38 章整帧 DDR3 验证结果

2026-10-08，用户确认位流 `0x41A4` 的 D0～D5 亮、D6 灭、D7 闪。800×480、RGB565，共 384000 像素 / 768000 字节，经官方写 FIFO → DDR3 → 官方读 FIFO，逐像素比较通过。摄像头在这次测试中保持复位；没有验证摄像头数据或 HDMI 图像。

## 可恢复基线

- 工程：`.local/framebuffer-first/ch38-frame-test/ch38_frame_test.gprj`
- 编译入口：`build_ch38_frame_test.tcl`
- 位流：`.local/framebuffer-first/ch38-frame-test/impl/pnr/ch38_frame_test.fs`
- SHA256：`DD7959D0C266BD507D50DE8FBCF6DE9F9487E5F3B2076F643A168929D81A6222`
- User Code：`0x000041A4`；下载后 Status：`0x70026020`
- 下载器：FT2CH，location 8740，FPGA ID `0x0001481B`；仅 SRAM 下载，未写外部 Flash。
- 复位：S0 / F15，低有效。
- 实板结果原始记录：`.local/framebuffer-first/ch38-frame-test/verified-result-20261008.json`
- 编译与下载日志：`.local/logs/ch38-frame-test-build-20261008.log`、`.local/logs/ch38-frame-test-program-20261008.log`

| 灯 | 0x41A4 的含义 | 用户反馈 |
| --- | --- | --- |
| D0 | 系统 PLL 锁定 | 亮 |
| D1 | DDR PLL 锁定 | 亮 |
| D2 | DDR 校准完成 | 亮 |
| D3 | 收到恰好 384000 个测试像素 | 亮 |
| D4 | 接受 48000 个顺序 DDR 写命令 | 亮 |
| D5 | 恰好 384000 个读 FIFO 像素逐个一致 | 亮 |
| D6 | 溢出、地址/响应错误、超时或比较错误 | 灭 |
| D7 | 原始 50 MHz 时钟心跳 | 闪 |

## 本次修正及证据

1. 保留官方第 38 章时钟拓扑。DDR PLL 使用板载原始 50 MHz 参考，400 MHz memory clock；系统 PLL 输出 50/165 MHz，CLKDIV 输出 33 MHz 用于读 FIFO。UI 为 100 MHz。摄像头 PCLK 不参与 DDR 参考时钟。
2. 根据原厂 [25K/60K DDR 更新说明](https://fpga.cn/forum.php?mod=viewthread&tid=29815)，用 16 拍锁定延迟交出 PLL mDRP 控制权；综合网表中确认适配器保留。旧源码 `pll_init_bypass=0` 的控制连接缺陷已经修正，但未单独做 A/B 实板测试，不能据此认定它是此前所有诊断失败的唯一原因。
3. 第 38 章原生成的两个 FIFO 在本机 Gowin 1.9.12 / 60B 独立综合时报 RP0007，提示当前器件没有 SSRAM。采用资料包第 47 章生成的 FIFO 实现后独立综合、完整综合及布局布线通过。替换前确认 `.ipc`、`fifo_parameter.v`、`fifo_define.v` 逐字节相同：8 KiB、EBR、FWFT、无输出寄存器，写 16→128，读 128→16。配置及哈希见工作副本 `fifo-compatibility.json`。该问题解释本轮编译失败，不是旧板上校准失败的直接证据。
4. 只写一次完整帧，等待全部 DDR 写命令接受后才读。检查 48000 个读写命令的地址序列及响应数量；按 FWFT 语义在 pop 当拍比较 Q。读 FIFO 可暂停，完整比较后停止，避免空读和混入下一帧。

## 验证范围与限制

RTL 仿真覆盖两行的字节回绕、FIFO empty 暂停、最后像素损坏、输入溢出、错误地址、提前读、无请求响应、超时及复位；完整 384000 像素仿真通过。另用实际官方字节数据源和 8→16 拼接模块确认期望序列。

静态图案每行重复，字节值以 256 回绕。这不是全容量 256 MiB、唯一地址图案、长期稳定性或双缓冲验证。摄像头完整帧、实景与 HDMI 显示仍需分别测试。

SDC 已定义板载 50 MHz、读 FIFO 33 MHz、DDR UI 100 MHz 时钟，未创建 CLKDIV 时钟的警告已消除。布局布线仍报告 188 个 setup、98 个 hold 违反端点，涉及跨时钟、私有 PHY 和 HDMI 路径；当前不是完整时序签核。硬件单帧通过不能代替时序和 CDC 审核，也没有用全局 false path 隐藏报告。

原厂参考副本 `official-ch38` 的 278 个非 impl 文件保持逐字节一致。通过的静态工程单独保存；摄像头将使用独立副本，并保持相同 DDR 时钟、FIFO 和调度基线。
