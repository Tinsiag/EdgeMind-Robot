# 480屏Flash试验（用户于2026-10-26追加授权）

用户在已告知时序未签核、未烧录的情况下要求“先烧录试试”，随后明确确认电机VM关闭、FPGA/屏幕与下载器通电。此次只观察480×272屏幕，默认未ARM，不下发运动。四路电机输出额外在生成顶层中硬接0，保留已有摄像头、DDR、HDMI、网口、传感器及导航代码，几何和发布状态不解锁。

构建命令（工程目录）：

```powershell
../.venv/Scripts/python.exe -X utf8 scripts/build.py build --fusion --tft480 --screen-test --route-option 1 --place-option 1 --timeout 5400
```

独立生成平台为 `.local/platform-tft480-screen-test`，独立构建目录为 `.local/gowin-fusion-tft480-screen-test`，不会将原正常构建路径内20261025的旧.fs作为本次修改位流。保留timing驱动与correct_hold=1，并核对真实cmd.do里的route=1、place=1。

硬锁已用实际生成顶层检查：强制global_n有效且四个内部电机请求遍历16种组合，物理输出始终0；同一夹具用于未加锁顶层时按预期失败，防止错误刺激导致假通过。夹具位于本目录 `screen_motor_lock_tb.v`，仅以Icarus -i忽略不相关黑盒IP验证顶层直连关系，不将其当作整板功能仿真。综合后的四个电机OBUF.I再次核对为GND，见 `MOTOR-LOCK-NETLIST.json`。

2026-10-26烧录前只读检测：FT2CH/location548，器件GW5AT-60B/0x0001481B，状态0x70022020。读取状态不等于新固件加载或实屏通过。用户供电确认后保持该连接，烧录时显式指定已归档.fs与SHA，不依据mtime挑选“最新文件”。

构建完成后 `archive_bench.py` 核对全部输入SHA、最终.fs、综合网表、四个OBUF和cmd.do，再保存至 `bench-image-20261026`。根 `scripts/fpga/program_flash.py` 执行操作54@0x000000擦除/写入/校验，再Reprogram和Read Status；失败停止，不自动重试，不改SRAM方式。

本文件的构建、烧录、实屏和冷启动最终结果由后续记录补充；当前不能凭构建动作宣称Flash或实屏成功。断电验收需实际断开电源和USB/JTAG等反供电，再从Flash上电，用户观察与工具状态分别记录。
