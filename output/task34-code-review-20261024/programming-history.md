# 以前的烧录方法核对

2026-10-25，按用户要求检索项目源码、隐藏构建目录、烧录日志、Git历史及两份交接压缩包。只读取记录和Programmer帮助，没有连接或操作硬件，也没有恢复已暂停的布局布线。

以前实际使用的是USB/JTAG临时下载到SRAM：Gowin Programmer的`--operation_index 2`（等价于`--run 2`）。它需要已经生成的完整`.fs`文件；断电后失效，不写配置Flash。

可复核证据：

- `code/fpga/acg720-motor-test/verification/2026-10-16/sram-left-static-reprogram-20261016.log`：目标GW5AT-60B，操作SRAM Program，100%完成，耗时5.02秒，User Code=0x0000A71D、Status=0x70022020。
- 同目录`left-static-reprogram-evidence-20261016.json`明确记录`reused_previously_verified_bitstream=true`、`rebuilt_this_turn=false`、`flash_written=false`。当次很快，是因为复用了提前编译好的位流。
- `code/fpga/acg720-motor-test/verification/2026-10-15/left-static-build-program-evidence-20261015.json`记录该位流此前已完成实际PNR、管脚检查及仿真；它是历史电机诊断程序，不是本次应烧入的导航程序。
- `code/fpga/acg720-ddr3/DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md`同时保存先运行`gw_sh.exe`编译、再扫描下载器并用操作2下载`.fs`的命令。
- 本机`C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe --help`确认操作2为SRAM Program，操作73/74分别读取User Code/Status。换USB端口后须重新扫描下载器，不照搬历史location=8740。

历史命令形式（仅示意，尚未选定本次下载文件或扫描当前下载器）：

```text
programmer_cli.exe --device GW5AT-60B --operation_index 2 --fsFile <已核验完整位流绝对路径> --cable-index <扫描结果> --location <扫描结果> --frequency 15MHz
```

当前文件状态：

- 本次新程序`.local/gowin-fusion-tft480/impl/pnr/a741.fs`不存在，布局布线已按用户要求暂停。综合/回归通过不能代替位流。
- 用户确认的130843原文件（期望SHA-256为`e492146beb969e5ff97aaa2608b677f6ebab5b22354768cca6f55c5a8b15fe8e`）在当前项目、文档原Administrator路径和Git历史中均未找到。两份交接ZIP各1251项，均无`.fs`或130843归档条目。
- 当前IMU运动工作区构建位流SHA-256为`967e9385a607bc702f1b3b75c20049a7975d92396e575ffe9225ea9cb59429a0`；旧融合构建位流为`93b142a3fd8be013552944b3e826e3978810f31112d1740107034a3696f34a98`。二者都不是130843，也不包含本轮的新代码，未擅自替换下载。

结论：可以按用户本轮要求使用以前的SRAM临时下载方式，跳过Flash固化；但烧入本次新代码仍须先完成布局布线并生成对应`.fs`。当前无需给板卡上电，未烧录、未ARM、未运行电机。
