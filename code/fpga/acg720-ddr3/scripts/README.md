# 重建 2026-10-08 通过的帧缓存工程

这些脚本保存本次对官方工程的实际改动方法，不包含原厂加密 IP、许可证、工具安装包或位流。运行只准备源码，不编译、下载，也不生成新的实板通过记录。

先把原厂第 38 章完整工程解压到 `.local/framebuffer-first/official-ch38/`，该目录应直接包含 `uart_ddr3_tft_hdmi.gprj` 和 `src/`。将官方第 47 章的下列依赖放在 `.local/ch47/src/` 对应位置。

- `rd_data_fifo/`、`wr_data_fifo/`，包含 `.v`、`.ipc` 和 `temp/FIFO/` 配置。
- `DVP_Capture/DVP_Capture.v`。
- `camera_init/ov5640_init_table_rgb.v`。

两套 FIFO 配置必须逐字节一致，脚本会检查，不能用不同宽度/深度的 FIFO 顶替。新增 SCCB 主机与初始化控制器在仓库 `rtl/camera_init/`，无需从忽略目录恢复这两份自编源码。

在 `code/fpga/acg720-ddr3` 目录，用 Python 3 的 UTF-8 模式依次运行。

```powershell
$python = 'C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $python -X utf8 'scripts/prepare_frame_test.py'
if ($LASTEXITCODE -ne 0) { throw '静态工程准备失败' }
& $python -X utf8 'scripts/prepare_camera_test.py'
if ($LASTEXITCODE -ne 0) { throw '彩条工程准备失败' }
& $python -X utf8 'scripts/prepare_camera_live.py'
if ($LASTEXITCODE -ne 0) { throw '实景工程准备失败' }
```

这是本机已有的 Python 路径，其他机器应替换为实际 Python 3。脚本会重写对应工作副本源码；摄像头脚本还会生成 `rtl/framebuffer_camera_test.v`。已有通过的位流和源码应先单独保存。脚本不写原厂参考目录，不访问配置 Flash。

准备完成后，用 `build_ch38_frame_test.tcl`、`build_ch38_camera_bars.tcl`、`build_ch38_camera_live.tcl` 分别调用官方 Gowin 工具编译。源码重建在独立临时目录检查过，与本次通过工程的 src 文件逐字节一致，静态 277 文件、彩条和实景各 284 文件。重新编译后的位流仍须重新校验身份并上板测试，不将历史通过记录视为新构建结果。

`audit_camera_live.py` 检查本机彩条/实景源码差异、实景位流哈希及 PNR 时序端点。`verify_recorded_artifacts.py` 检查本机保留的三版位流、原下载日志、实板结果记录和说明文档；两者都需要相应 `.local` 文件，不是在线硬件测量。

历史实板结果也收录在 `verification/2026-10-08/`，便于不携带原厂依赖时查看证据。详细实现、SRAM 断电丢失和未完成的 HDMI/时序项见 [排查与实现文档](../DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md)。
