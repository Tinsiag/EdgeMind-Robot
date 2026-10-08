# OV5640 → 官方帧缓存整帧验证

采用已通过的第 38 章 DDR 基线，DDR 参考来自原始板载 50 MHz，400 MHz memory clock / 100 MHz UI；保留系统 PLL 50/165 MHz 及 33 MHz 读 FIFO 时钟。摄像头 PCLK 仅用于官方 DVP_Capture 和写 FIFO，不给 DDR 提供参考时钟。现有 P7 接线未改变。

## 彩条版下载记录

- 工程：`.local/framebuffer-first/ch38-camera-bars/ch38_camera_bars.gprj`
- 编译：`build_ch38_camera_bars.tcl`，综合、布局布线、位流生成完成。
- 位流：`.local/framebuffer-first/ch38-camera-bars/impl/pnr/ch38_camera_bars.fs`
- SHA256：`5C13FEA6833E57650914D20B5983ED79A3BC3F629AAC3DCAD06833C74970BD92`
- SRAM 下载成功；User Code `0x00004FCF`，Status `0x70026020`。
- 下载器 FT2CH / location 8740，15 MHz JTAG。未写外部 Flash。
- 用户确认 D0～D5 亮、D6 灭、D7 闪，摄像头内部彩条的完整帧检查及 DDR 读回 CRC 已通过。原始结果保存为工作副本 `verified-result-20261008.json`。
- 复位 S0 / F15，低有效；摄像头复位 C14。

| 灯 | 本版含义 |
| --- | --- |
| D0 | 系统 PLL 锁定 |
| D1 | DDR PLL 锁定 |
| D2 | DDR 校准完成 |
| D3 | 摄像头初始化：ID 0x5640 和 7 个关键寄存器读回一致 |
| D4 | 48000 个顺序 DDR 写命令完成 |
| D5 | 800×480 完整帧通过检查，384000 个读回像素 CRC 一致，且无其他测试错误 |
| D6 | 摄像头配置、帧尺寸、FIFO 溢出、DDR 命令/响应、超时或 CRC 错误 |
| D7 | 原始板载时钟心跳 |

D0～D5 亮、D6 灭、D7 闪为预期通过状态；与旧摄像头诊断及静态 `0x41A4` 的 D3 定义不同。

## 配置和数据验证

DDR 校准后，摄像头硬复位保持低约 1 ms，释放后等约 20 ms，再以 100 kHz SCCB 配置。采用此前初始化成功的 253 项官方 RGB 表，保留 PLL、裁剪、HTS/VTS、缩放与 DVP 设置，将尺寸参数设为 800×480，`0x503D=0x80` 开启内部彩条。模块振荡器频率尚未测得，不据旧表注释承诺帧率。

写表后读回 ID `0x300A/0x300B`，并核对 `0x3808..0x380B` 的 800×480、`0x4300=0x61`、`0x501F=0x01`、`0x503D=0x80`。只有全部一致才亮 D3。RGB 表常量赋值块在本地副本增加 addr 显式敏感项，避免 Icarus 对常量-only `always @*` 不执行的仿真陷阱；原资料与旧工程未改。

官方 DVP_Capture 在配置完成后复位释放并舍弃前 10 帧。camera_frame_gate 等完整帧边界，逐行检查 800 个有效像素、480 行，共 384000；任何短行、长行或错误边界拒绝通过。

采集端按接受进入写 FIFO 的像素计算 CRC32（反射多项式 0xEDB88320，初值及最终异或均 0xFFFFFFFF，高字节先入）。只写一次完整帧。等待全部写命令被接受及完整帧检查通过，发出 48000 个顺序读命令，按官方 FWFT 读 FIFO 的 pop 当拍计算读回 CRC。采集 CRC 在帧完成前已经冻结，以同步完成标志建立稳定多位数据传递。CRC 一致是整帧传输验证，不等于逐像素色彩/HDMI 显示验证，CRC 本身也存在碰撞可能。

## 已执行检查与限制

- 采用实际官方 DVP_Capture 的仿真，完整 384000 像素通过；CRC 与 Python zlib 独立金值 `0xCC8B28AB` 一致。
- 两行测试覆盖异步时钟、FIFO empty 暂停、读回末像素损坏、短行和写 FIFO 满。错误不能报 pass。
- 配置控制器使用实际 ROM 和事务级 SCCB 模型，确认 253 次写、2 次 ID 读、7 次配置读；坏彩条或尺寸读回不报 init_done。该模型不验证电气 SCCB 时序。
- PNR 中 camera_pclk 使用 PRIMARY；BSRAM 35/118、SSRAM 0，mDRP 适配器保留。
- PCLK 暂按保守 100 MHz（10 ns）约束；报告本域 Fmax 108.954 MHz，读域 52.450 MHz，UI 185.056 MHz。总报告仍有 205 setup、56 hold 违反端点，未完整时序/CDC 签核，未以全局 false path 隐藏。
- 无 HDMI 显示器参与，没有验证连续视频、乒乓缓冲、长期运行或全 DDR 容量。

日志位于 `.local/logs/ch38-camera-bars-build-20261008.log`、`ch38-camera-bars-program-20261008.log`、`ch38-camera-full-sim-20261008.log`、`ch38-camera-ctrl-sim-20261008.log`。静态整帧位流 `0x41A4` 和其源码/哈希单独保留。

## 实景帧继续验证

彩条版通过后，建立独立 `.local/framebuffer-first/ch38-camera-live/ch38_camera_live.gprj`，编译入口 `build_ch38_camera_live.tcl`。相对彩条版只将实际表中的 `0x503D` 从 `0x80` 改为 `0x00`，并将该寄存器读回期望改为 `0x00`；DDR 时钟、FIFO、尺寸、格式、完整帧检查和 CRC 逻辑均保持一致。沿用全部灯态含义，实景结果由对应位流的单独反馈确认。

实景版综合、布局布线和 SRAM 下载已完成。当前板上为：

- 位流：`.local/framebuffer-first/ch38-camera-live/impl/pnr/ch38_camera_live.fs`
- SHA256：`A718EFC364FEB9A6B47AD333686F0518D76A56DAD1955ABBA607262CAE790553`
- User Code / Status：`0x0000AF89` / `0x70026020`
- 用户确认 D0～D5 亮、D6 灭、D7 闪，关闭彩条的实景完整帧检查及 DDR 读回 CRC 通过；S0 可重新触发整帧测试。结果保存为实景工作副本 `verified-result-20261008.json`。
- 两个源码差异已经逐文件核对并保存在 `build-audit-20261008.json`，其余 src 文件字节一致。
- 实景表的配置读回控制器仿真通过；时序报告 206 setup、56 hold 违反端点，仍未完成签核。
- 日志：`.local/logs/ch38-camera-live-build-20261008.log`、`ch38-camera-live-program-20261008.log`、`ch38-camera-live-ctrl-sim-20261008.log`。

当前只缓存并检验一帧，不提供已验证的连续 HDMI 视频。仅 SRAM 下载，断电会丢失当前 FPGA 配置；配置 Flash 未改写。完整实现和复现文档见 [DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md](DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md)。
