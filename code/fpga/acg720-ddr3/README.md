# ACG720 GW5AT-60 DDR3 验证工程

本目录保存 ACG720 / GW5AT-60B 的 DDR3 调试工程。2026-10-08 已按官方第 38 章基线打通 OV5640 → 写 FIFO → DDR3 → 读 FIFO，800×480 RGB565 静态、彩条、实景整帧验证均通过。当前为实景单帧自检，只有 SRAM 配置，不断电保存，连续 HDMI 显示未验证。第 47 章 1280×720 主工程保留作历史。原厂源码、加密 IP、位流和日志保存在被 Git 忽略的 .local/ 下；原始资料包保持不变。

完整排查、实现与复现文档：[DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md](DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md)。

仓库也保存 [工程重建脚本](scripts/README.md)、`rtl/camera_init/` 中自编 SCCB 源码和 [实板验证快照](verification/README.md)。原厂依赖按脚本说明放入本机 `.local` 后，可重建本次三个工作工程。

历史交接记录：[DEBUG-HANDOFF-2026-10-06.md](DEBUG-HANDOFF-2026-10-06.md)。10 月 7 日已按用户要求继续，最新过程见 [DEBUG-SESSION-2026-10-07.md](DEBUG-SESSION-2026-10-07.md)。

2026-10-08 用户调整方向：先以官方第 38 章帧缓冲为基线，再向上接入 TY-OV5640。源码、硬件、电平和逻辑分析仪核对结果见 [FRAMEBUFFER-FIRST-PLAN-2026-10-08.md](FRAMEBUFFER-FIRST-PLAN-2026-10-08.md)。随后完成静态整帧验证，用户确认 `0x41A4` 的 D0～D5 亮、D6 灭、D7 闪：384000 像素 / 768000 字节经两端 FIFO 和 DDR 逐像素一致。详见 [FRAMEBUFFER-TEST-RESULT-2026-10-08.md](FRAMEBUFFER-TEST-RESULT-2026-10-08.md)。官方参考副本保持不变，摄像头彩条测试在独立工程继续。

2026-10-08 接线位置图及采集步骤见 [LOGIC-ANALYZER-WIRING-2026-10-08.md](LOGIC-ANALYZER-WIRING-2026-10-08.md)。P7 正面左下为 1 脚方形焊盘，外排偶数、内排奇数；模块 PWDN 在模块侧采集。本次仅整理接线图，没有编译、下载、实物接线或采集。

## 当前状态（2026-10-08）

| 验证层级 | 已取得的证据 | 结论 |
| --- | --- | --- |
| 本机编译 | 主工程、固定模式 BIST、摄像头 DDR 诊断完成综合、布局布线和位流生成 | 已通过编译流程；尚未完整时序签核 |
| SRAM 下载 | Gowin USB Cable(FT2CH)，FPGA ID 0x0001481B，下载 100% 完成 | 下载成功；未写外部 Flash |
| DDR3 校准 | 10 月 8 日第 38 章整帧版 `0x41A4`，D0/D1/D2 亮 | 新帧缓存基线通过 |
| DDR3 静态整帧读回 | `0x41A4` D3/D4/D5 亮、D6 灭，48000 个读写命令，384000 个像素逐个比较 | 768000 字节链路通过；原 BIST 256 字节通过也保留 |
| 摄像头初始化 | 原主工程复核通过；被动观测版 D2/D4/D5 亮 | 初始化通过，DVP 像素及写 FIFO 输入已有活动 |
| 摄像头像素经 DDR 读回 | 彩条 `0x4FCF`、实景 `0xAF89` 均由用户确认 D0～D5 亮、D6 灭、D7 闪，完整帧 CRC 一致 | 摄像头完整帧链路通过；旧校准失败唯一触发未确定 |
| HDMI 图像 | 没有连接显示器 | 未验证 |

**当前板上运行已通过的实景单帧版 `0xAF89`，用户确认 D0～D5 亮、D6 灭、D7 闪；彩条 `0x4FCF` 和静态 `0x41A4` 也已通过。三版均仅 SRAM 下载，外部配置 Flash 未写，断电会丢失本次配置。** 摄像头版位流、哈希、灯态定义、仿真和时序限制见 [CAMERA-FRAME-TEST-2026-10-08.md](CAMERA-FRAME-TEST-2026-10-08.md)。

- 已通过位流：.local/framebuffer-first/ch38-frame-test/impl/pnr/ch38_frame_test.fs
- SHA256：DD7959D0C266BD507D50DE8FBCF6DE9F9487E5F3B2076F643A168929D81A6222
- User Code / Status：0x000041A4 / 0x70026020
- 本版 D0～D5 均亮、D6 灭、D7 闪；含义与旧摄像头诊断不同，详见整帧验证记录。
- 前一观测版 0x7E20：用户确认 D1 灭，D0/D2/D3/D4/D5 亮。增加探针未解决校准。
- 仅 SRAM 下载，未写 Flash；断电会丢失本次配置。

已定位到源码连接缺陷：`pll_init_bypass=0` 使 DDR 的 mDRP 控制被屏蔽，适配器被综合删除。新帧缓存基线按原厂更新说明，在 PLL 锁定延迟后交出 mDRP 控制权，综合后适配器已保留，实板校准及静态整帧读回已通过。尚未单独做 A/B 测试，不能将旧诊断失败全部归因于这一处。原主工程和已通过 BIST 的位流及源码保持不变。

不能把该诊断版本的 D1 灭直接解释为 DDR 硬件故障。主工程与独立 BIST 曾通过校准，固定模式 BIST 也完成了真实写入/读回；失败诊断的根因仍待定位。

10 月 8 日进一步确认旧 FIFO 诊断存在写入数据量不足（2 个块却要求 8 个块才写）、未等实际写入完成就读、FWFT 比较晚一拍等缺陷；这些发生在校准之后，不能解释当时 D1 灭。证据及限制见 [LEGACY-DDR-DIAGNOSIS-2026-10-08.md](LEGACY-DDR-DIAGNOSIS-2026-10-08.md)。

## 本地工程与工具

| 文件 | 用途 |
| --- | --- |
| .local/framebuffer-first/ch38-frame-test/ch38_frame_test.gprj、build_ch38_frame_test.tcl | 已通过 800×480 静态整帧 DDR 读回 |
| .local/framebuffer-first/ch38-camera-bars/ch38_camera_bars.gprj、build_ch38_camera_bars.tcl | 沿用通过基线，接入 OV5640 彩条、整帧检查与 CRC |
| .local/framebuffer-first/ch38-camera-live/ch38_camera_live.gprj、build_ch38_camera_live.tcl | 关闭彩条，验证实景整帧，其他配置和缓存不变 |
| rtl/framebuffer_camera_test.v、rtl/camera_frame_gate.v | 摄像头完整帧选择、CRC32 和 DDR 命令计数验证 |
| .local/ch47/ov5640_ddr3_hdmi.gprj | 保留的第 47 章 1280×720 历史主工程 |
| build.tcl | 主工程编译入口 |
| .local/bist/ddr3_bist.gprj、build_bist.tcl | 已通过的固定模式 DDR3 BIST |
| .local/camera-ddr/camera_ddr_capture_bist.gprj | 尚未通过的摄像头原生 DDR 接口诊断 |
| .local/camera-ddr/camera_ddr_fifo_bist.gprj | 尚未通过的 F15 FIFO 诊断 |
| .local/camera-ddr/camera_ddr_fifo_bist_b21.gprj | 历史 B21 FIFO 诊断，未通过 |
| .local/main-observe/main_observe.gprj、build_main_observe.tcl | 保留主拓扑的八灯被动观测版，校准未通过 |
| .local/main-mdrp/main_mdrp.gprj、build_main_mdrp.tcl | mDRP 控制权修正版，10 月 7 日已下载，待灯态反馈 |
| rtl/ddr_readback_monitor.v、tests/ddr_readback_monitor_tb.v | 已通过模块仿真的被动读回比较器，尚未接入实板 |
| .local/logs/ | 历史记录与本次交接副本；旧记录须按各构建解释 |

实际成功使用的工具：

- C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe
- C:/Gowin/Gowin_V1.9.12_x64/Programmer/bin/programmer_cli.exe

许可证问题已解除，成功编译是实际证据。原文中的 MAC/临时网卡/许可证失败描述属于历史排查，不是当前阻塞；不要重跑相关脚本，不需要教育版。最初提供的 V1.9.12.04_x64 路径在本轮未找到 gw_sh.exe，以以上可用工具为准。

项目器件为 GW5AT-LV60PG484AC1/I0、GW5AT-60B，B 版本。CST 原厂文件头的 138K 注释不能代替项目实际器件设置。下载器 USB location=546 为 10 月 7 日记录，后续操作前需要重新扫描。

## 已知通过的位流

- 当前实景单帧：.local/framebuffer-first/ch38-camera-live/impl/pnr/ch38_camera_live.fs，User Code 0x0000AF89。
  SHA256：A718EFC364FEB9A6B47AD333686F0518D76A56DAD1955ABBA607262CAE790553
- 彩条和静态整帧：0x4FCF、0x41A4，分别保存在 `.local/framebuffer-first/ch38-camera-bars/`、`ch38-frame-test/`；哈希及证据见完整实现文档。
- 主工程：.local/ch47/impl/pnr/ov5640_ddr3_hdmi.fs，User Code 0x0000D80B。
  SHA256：D3CD6E1D3967B70441F22201E6A95FC143C7A99BDF63DE3F3B619E04EB23E09D
- 固定模式 BIST：.local/bist/impl/pnr/ddr3_bist.fs，User Code 0x00007CCF。
  SHA256：E3A7E06628D7E7600527DE1F8512C7F75EABC1F56067D59ECA29C410E99C5CBD

位流身份/下载状态不表示 DDR 运行结果；校准和比较结果来自用户对相应 LED 的观察。10 月 7 日恢复原主工程后，D0～D3 全亮已再次由用户确认。

## LED 和复位

| 位流 | D0 / M22 | D1 / N22 | D2 / L21 | D3 / K21 |
| --- | --- | --- | --- | --- |
| 主工程 | DDR PLL 锁定 | DDR 校准完成 | 摄像头初始化完成 | camera/HDMI PLL 锁定 |
| 固定模式 BIST | DDR PLL 锁定 | DDR 校准完成 | 读回通过 | 测试失败 |
| 摄像头 DDR 诊断 | DDR PLL 锁定 | DDR 校准完成 | 初始化且捕获事件已接收 | 像素读回通过 |

灯高有效。固定模式 BIST 与摄像头诊断的 D3 含义相反；摄像头诊断 D2 灭不能单独判断 SCCB 失败。

原厂参考/BIST 使用 F15；主工程使用 B21（历史 cam 记录标为 S4），低有效。不要写成“S0/B21”。F15 和 B21 两个诊断版本都只亮 D0，不能确认复位引脚是根因。

## 当前摄像头映射

| 信号 | FPGA 球号 |
| --- | --- |
| RST / SCL / SDA | C14 / B13 / D15 |
| PCLK / HREF / VSYNC | B18 / D14 / C13 |
| D0..D7 | C15 / B15 / B16 / D17 / C17 / E16 / D16 / B17 |

已核对用户提供的 Downloads/cam。SCCB 为 100 kHz 开漏双向，主工程初始化完成包含读取 0x300A=0x56、0x300B=0x40。摄像头硬复位低约 1 ms，释放后约 20 ms 启动配置。

10 月 8 日用户确认模块是 18 针 TY-OV5640，并提供 T-OV5640-PCB-V1.0 针脚图。照片可见振荡器，但其频率未读清；新图纸未给频率，旧记录“25 MHz”尚未独立证实。工作副本不输出 FPGA XCLK，不约束未引出的 PWDN。模块端 PWDN 必须有可靠低电平；用户重新接线后主工程初始化通过，但未取得单独电气测量记录。旧 M20/B2/B1/J2/L18/A1 等映射只作为历史参考。

用户明确确认模块排针支持 3.3 V，后续按此接口规格。新机械图另标 DOVDD=1.8 V，尚无模块电平转换原理图解释该差异；不要把芯片供电标注直接等同于排针电平，也不自动改变 P6。当前 GPIO 映射对应 P7，具体针号和逻辑分析仪接法见 10 月 8 日方案。

## DDR 参数与后续未解决项

按现有资料/IP 配置：MT41K128M16JT-125:K，x16，256 MiB；400 MHz memory_clk，1:4，128-bit 用户接口，BL8，SSTL 1.5 V。用户逻辑使用 DDR IP 的 clk_out。旧主工程 DDR IP 的 clk 接 camera_pll 的 50 MHz 输出；新已通过基线接第 38 章系统 PLL 的 50 MHz 输出，DDR PLL 的 clkin/mdclk 接板载原始 50 MHz，摄像头 PCLK 仅用于采集/写 FIFO。

一帧 1280×720 RGB565 占 1,843,200 字节；新基线 800×480 占 768000 字节。原厂控制器读写地址范围相同，尚无独立多帧乒乓管理。10 月 8 日已通过一次静态整帧读回，但不代表全容量或长期稳定性验证。

10 月 7 日主工程 mDRP 修正版缺少独立灯态反馈。10 月 8 日已验证第 38 章静态整帧、摄像头内部彩条整帧和实景整帧。旧独立诊断的写入门槛、地址范围、一次性捕获事件等问题保留作历史证据，新的整帧验证流程已经绕开并处理这些缺陷；未改写旧诊断文件。

旧工程综合有重复声明、隐式网线、位宽和 mDRP 优化警告；新基线 mDRP 适配器已保留。新工程已增加 SDC，PCLK 在 PNR 中使用 PRIMARY；实景报告仍有 206 setup、56 hold 违反端点，CDC 和完整时序签核尚待完成。实板单帧通过不等于最终视频固件完成。

恢复命令和历史哈希见 10 月 6 日交接记录，新版哈希和日志见 10 月 7 日续调记录。原厂资料、外部 Flash 及无关 PCB 文件未改动。
