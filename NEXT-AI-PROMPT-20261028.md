# 下一位 AI 提示词（2026-10-28 暂停快照）

你正在接手 `C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot`。用户刚要求清理并暂停，先不要继续综合、布局布线、烧录、ARM、开启电机 VM 或做网络运动测试。本轮用户明确授权的动作只有：整理、打包、提交并推送 GitHub；这些已完成后仍保持暂停。当前完整恢复包为 `output/EdgeMind-Robot-handoff-20261028.zip`，其校验记录为 `output/EdgeMind-Robot-handoff-20261028-VERIFY.json`。

第一步只读：

1. `AGENTS.md`
2. `HANDOFF-20261028.md`
3. 本文件
4. `output/handoff-20261028/CONTENTS-SHA256.json`
5. `output/flash-tft800-reburn-20261028/STATUS.json`
6. `output/motion-tft800-20261028/STATUS.json`
7. `output/handoff-20261028/PACKAGE-README.md`
8. `output/EdgeMind-Robot-handoff-20261028.zip.sha256`

当前板上最后确认的是 800×480／33 MHz、UserCode `0xA741` 的 screen-test 位流，SHA-256 为 `d5e558ad68ac665f889fcec651262714e52e40774853e5368c51f0fc2a1ad62b`。Flash 操作 54@0x000000、校验、Reprogram、wakeup/DONE 和 UserCode 已通过；用户确认摄像头画面与文字恢复。四路电机输出在该位流中物理接 GND，VM 保持关闭，没有 ARM。完全断电后的摄像头初始化问题按用户要求暂缓。

用户接口屏幕的关键硬件结论：接的是 40 针用户 FPC，不是裸屏 J2；FPGA AB22→用户 J1-33 是 DE，AB21 是背光，AB20 是 PCLK，V19/Y19 是 HS/VS。先前白屏/滑动来自 DE 与其他线误接，修正后 480 色块和 800 摄像头/文字均能显示。不要交换 DE/背光、不要翻转排线、不要把 J2 脚号套到 J1。官方例程目录是 `C:/Users/sc/Documents/Dev/Hardware/fpga/小梅哥ACG720国产高云FPGA教学开发板资料/02_例程源码/GW5AT60K`；800×480/33MHz 与旧 AC620 480×272/5MHz 是不同配置，边界不可混用。

运动版本还没有可烧录位流：算法一/布局一、timing-driven、hold 修复下，完整 motion PNR 三次都报 `PR0004`，即使报告“0 unrouted nets”也属于工具失败；没有 `.fs`、没有最终 STA/SDF。第一次388.1406秒、综合网表 `db92ce25…7db9d`；第二次请求复用但工具自动重新综合，414.5501秒，`synthesis_reused=false`、网表变为 `1eedc07b…ff82b`；第三次才真正复用第二次网表，253.1352秒。第三次加入 `CLOCK_LOC "core/sensors/lidar/n7598_14" LOCAL_CLOCK`，该使能移出PRIMARY但 `ui_n` 随后取代它，PRIMARY仍8/8，仍失败。第三次是工具自行报错退出，不是人工中断；该假设未证实，不要继续盲目加 CLOCK_LOC。

恢复开发时遵守：

- 目标仍是 OV5640→DDR3→TFT、IMU 姿态文字、LD06 基础避障、编码器闭环/停止保护、网口设置遥测调试；不恢复 HDMI、网口视频、地图、A*、定位匹配、航点或 PC 避障。
- 恢复后先做源码/RTL/Python/安全/显示回归，再检查 motion 的全局时钟自动提升、高扇出 CE/复位、`ui_n`/LD06 使能、screen-test 与 motion 网表差异。一次只做一个有证据的等价优化。候选是遥测宽缓冲/选择与CE、LD06包缓冲重复寄存、ms_tick扇出、PI算术；保留停止保护，不能用false path/多周期掩盖问题。
- 固定显式 `--route-option 1 --place-option 1`；不要因耗时切算法二；不要用 false path、多周期、降低频率或隐藏时序问题。
- 只有同次 PNR、STA、SDF、动态电机 OBUF、网络/传感器和停止保护检查均完成后，才选择具体 `.fs`。用 `scripts/fpga/program_flash.py` 完整写外部 SPI Flash，VM 关闭，默认不 ARM。用户过去已给持续烧录授权，但本次暂停优先，不能自行恢复。
- 实板运动顺序必须是：VM 关闭只读检查 → 轮子架空 → IMU/LD06/编码器状态 → STOP/失联/编码器故障 → 短时低速 → 再开启基础避障。不要直接落地运行。

仓库目前包含大量已跟踪精简源码变更和新增证据；不要 `reset/clean/pull` 覆盖它们。d5原构建的111个输入在 `output/tft800-official-20261028/source-snapshot-d5/` 精确留档；三个motion attempt也各自留档。`.fs/.vg/.bin/.binx/.db/.p/.pr/.vvp`通常按 `.gitignore` 处理，`.vo/.sdf`未被该规则忽略；完整ZIP把真实位流和忽略产物按相对路径打入包。用户没有再次明确“继续”前，保持暂停。不要把 `output/handoff-20261028.zip`（小阅读包）误当完整恢复包。
