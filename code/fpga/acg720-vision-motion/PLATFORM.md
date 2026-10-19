# 板级支持恢复与集成契约

`rtl/vision_motion_top.v` 是可综合的便携集成顶层，但不是开发板物理顶层。它不实例化不存在的 DDR/PLL/TMDS 黑盒，也没有可直接下载的占位工程。所有端口已连通至控制、ToF、像素和 DDR 用户端口；仿真模型不能放入板级文件清单。

## 需要补齐的原始资料

1. 对应 **GW5AT-60B / GW5AT-LV60PG484AC1/I0** 的第38/47章完整源码，包含 DDR3 IP 及全部加密和生成文件、DDR PLL/mDRP、系统/显示 PLL、HDMI 编码/输出原语及约束。
2. 已使用的 TY-OV5640 初始化 RGB565 寄存器表，保留 scaler 配置、800×480、关闭内部彩条和 DVP 测试，初始化后读取 ID、尺寸及格式等关键寄存器确认。可恢复 `acg720-ddr3` 中的脚本依赖，再将生成的真实初始化文件加入平台；不要运行旧脚本直接覆盖本新工程。
3. 当前 ACG720 板级原理图和空闲扩展针脚，用于 ToF 选脚、Bank VCCIO、上拉和供电核对。未获得这些资料前，本项目保留 ToF 逻辑端口，不提供球号。

## 物理包装层

新建 `.local/platform/acg720_vision_motion_board.v`，顶层模块名固定为 `acg720_vision_motion_board`。物理顶层沿用 `clk`、`stop_n`、`uart_rx/tx`、`left/right_in1/in2`、`left/right_enc_a/b`、`led[7:0]`、`camera_reset_n/sclk/sdat/pclk/href/vsync/data[7:0]` 和 `tof_sda/scl/xshut` 命名。其余 DDR3/HDMI 物理端口按原厂 IP 实例展开，禁止把 user port 接成外部引脚。

包装层负责：

- 用真实 PLL 生成 100 MHz DDR UI（以 IP 的 `clk_out` 为准）、33 MHz 显示和165 MHz TMDS 时钟；50 MHz 控制域使用板载原始时钟。PLL/DDR mDRP 交接以现有通过基线及 IP 文档核对，不能硬绑屏蔽校准控制。
- 按模块时序驱动相机硬复位，稳定后启动 SCCB；`camera_init_done` 只有在配置与读回通过后拉高。不输出未连接的 FPGA XCLK；模块自带振荡器频率需要实测记录。
- `async_reset_n` 上电/按下 S0/PLL 丢锁时异步拉低，所有域共用。DDR 校准完成前允许 reset 释放以启动 UI，但运动必须由感知和视频就绪联锁阻止；运行中校准丢失必须触发整个便携系统复位，不要仅重置 PHY。相机初始化完成前采集逻辑等待。
- `app_*` 对接 GW DDR 原生128位用户接口、1:4、400 MHz memory、BL8；地址以 x16 word 为单位。读数据按命令顺序返回，读返回不能被下游反压。支持命令与写数据独立握手；若所选原厂包装接口不同，必须显式适配并以仿真验证。
- 对接 `video_rgb[15:0]`（R[15:11]/G[10:5]/B[4:0]）、同步延后一拍的 `video_de/hsync/vsync` 到 TMDS 发送；补齐 HDMI OE 和真实端口约束。视频内部时序为800有效＋40前肩＋128同步＋88后肩，480有效＋13前肩＋2同步＋31后肩；外接显示器必须验证是否接受该33 MHz模式。
- 输出电机信号还应与物理 `stop_n`、平台就绪/复位做最终低电平门控。ToF、摄像头和电机 IO 电平与实物供电一致；`tof_sda/scl/xshut` 只拉低或高阻。

## 依赖清单

复制 `platform.example.json` 为 `.local/platform/manifest.json`，逐项补齐真实文件、SHA256 和评审证据：

- `files` 包含全部源文件（包括原厂子模块、ROM、IP `.v/.vo`、CST、SDC），每个文件有 `path`、`sha256`、Gowin `type`；路径相对清单目录。示例不代表完整原厂文件列表。
- 角色至少包含 `ddr3_phy`、`clock_pll`、`tmds`、`camera_init`、`board_wrapper`，恰好一份完整 CST，至少一份 SDC。FIFO 已由本项目提供可综合双口 RAM RTL，无需恢复旧 BSRAM FIFO，但须检查综合实际推断资源。
- `tof_pins` 写已核对的三根球号；若模块没有 XSHUT 或不外接该脚，需要先明确修改平台契约及检查器，不能给一个假球号通过检查。
- `io_review_evidence` 是真实 IO 核对说明及哈希，记录连接器针号、球号、Bank 电压、模块上拉及供电；完成人工核对后设 `io_reviewed=true`。

`check` 只读检查，缺资料返回2；`prepare` 在检查通过后生成 `.local/build` 工程与源码哈希；`build` 再调用 Gowin，目标 User Code=A730。脚本不调用 Programmer，不访问串口/电机/配置Flash。

综合完成不保证时序闭合。`audit` 检查位流身份及 setup/hold/recovery 摘要，摘要缺项也退出失败；即使摘要全零，也继续保留 `timing_signed_off=false`，直到实际管脚、CDC 与 PHY 路径人工审查完成。不要将这个检查器当作完整签核工具。
