# ACG720 外部 Flash 固化

适用 ACG720 / GW5AT-60B。当前位流和实板验收由 [STATUS.json](../../output/current-firmware/STATUS.json) 维护，最近一次执行的原始记录在 [Flash 审计](../../output/current-firmware/flash/audit.json)。

## 执行条件

源码变更先完成[完整签核](../../docs/contributing.md)：同源回归、原语执行、同次 PNR/STA/SDF/PAD 和最终门均须通过。文档整理无需重编译或烧录。
烧录与重载前关闭电机 VM，确认目标板和下载器；上电保持未 ARM，不模拟本地 S1。

本机 Gowin 为 `C:/Gowin/Gowin_V1.9.12.04_x64`，可用 `GOWIN_HOME` 或 `--programmer` 指定其他安装。
工具读取 Programmer 的 `--help`，识别当前工具的外部 Flash 写入校验操作号，不能将不同器件系列的操作号直接套用。

## 预览与写入

从仓库根目录执行。以下变量从当前状态读取；使用前仍须检查候选签核和物理条件。

```powershell
$status = Get-Content output/current-firmware/STATUS.json -Raw | ConvertFrom-Json
$image = $status.artifact
$expected = $status.artifact_sha256

# 只核对文件和哈希，不访问下载器。
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/program_flash.py --bitstream $image --sha256 $expected

# VM 关闭、目标链路明确且签核通过后，才执行实际写入。
& code/camera-car-control/.venv/Scripts/python.exe -B scripts/fpga/program_flash.py --bitstream $image --sha256 $expected --program
```

脚本复制已核对的完整位流到独立暂存目录，再依次执行外部 Flash 地址0写入/校验、Reprogram、状态就绪和 UserCode 比对。片上监督程序已包含在完整位流中。
写入或校验失败即停查，不盲重试、不降级 SRAM，不修改熔丝、密钥或其他分区。

默认 FT2CH 类型索引为1；索引表示线缆类型，不是第几个 USB 设备。多下载器时指定 `--location` 或仅连接目标下载器；脚本限定单器件链。插拔后不能沿用历史 location 当作当前设备证明。

执行日志写入 `code/camera-car-control/.local/programming/<UTC时间>/`，包含暂存镜像、命令、厂商日志和审计。
归档必要审计后，现存位置由 STATUS 维护。原始日志中的路径是执行时的路径。

## 验收

写入和 UserCode 成功只能证明配置流程完成。显示、传感器、S1启停和运动分别验收。
VM 关闭时将板卡与屏幕真正断电至少10秒，断开可能反向供电的 USB/JTAG，再上电、不重新烧录，才能记录真实冷启动结果。
运行时校准和会话不会因 Flash 固化而保留，上电仍由本地 S1 启动；没有上位机自动 ARM。

[厂商 Programmer 指南](https://cdn.gowinsemi.com.cn/SUG502E.pdf)提供操作背景，实际操作号以所用版本帮助和器件为准。
离线工具测试使用模拟 Programmer，不访问硬件：

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -B -m unittest discover -s scripts/fpga -p test_program_flash.py
```
