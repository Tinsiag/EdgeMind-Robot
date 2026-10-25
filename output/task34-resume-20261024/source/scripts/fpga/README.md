# ACG720 完整程序固化

2026-10-24 起，后续 FPGA 程序交付使用外部 SPI Flash 固化，要求断电保留。
本脚本只适用于当前 **ACG720 / GW5AT-60B**，不适用于其他系列或 138K 板。

## 操作依据

[Gowin Programmer 用户指南 SUG502-2.5.2E](https://cdn.gowinsemi.com.cn/SUG502E.pdf) 第 4.9.3 节列明 Arora V 外部 Flash 操作，54 为擦除、写入和校验；第 4.7 节列出 1 为 Reprogram，74 为状态寄存器读取。本机 Programmer V1.9.12.04 的 `--help` 已逐项核对一致。

板卡配套《第2章 Gowin软件基本开发流程》第 2.10 节、PDF 第 18～19 页，同样明确要求程序固化使用 External Flash Mode 5AT，之后重新上电。新版本 Programmer 称为 Arora V。不要照搬普通系列的操作 9 或内置 Flash 的操作 6。

脚本执行完整 `.fs` → 外部 Flash 启动地址 `0x000000` → 厂商校验 → Reprogram → 读取状态。
不单独下载 SRAM，不更改启动熔丝、密钥、QE 或 Golden Image 地址。操作 54 的擦除范围由厂商工具决定，不能承诺保留同一 Flash 中的额外数据；若以后共用 Flash 保存地图或软核应用，先核对分区与备份方式。
任务3/4的PicoRV32裸机程序通过片内RAM初始化内容包含在完整位流中，发布清单同时记录固件二进制及hex的SHA-256。脚本只写入完整位流；今后若采用独立软核应用分区、额外模型或独立Flash数据文件，需要扩展发布清单和分区处理。

## 用法

从仓库根目录执行，先选定已检查的发布位流及其 SHA-256。以下路径与哈希变量必须指向实际发布文件，不能将 `.local` 中未签核实验产物当作稳定包。

```powershell
$image = 'C:\实际发布目录\完整固件.fs'
$expected = '发布清单中已核对的64位SHA256'

# 预览并核对文件哈希；不启动 Programmer、不访问硬件。
& .\code\camera-car-control\.venv\Scripts\python.exe .\scripts\fpga\program_flash.py --bitstream $image --sha256 $expected

# 关闭电机 VM，确认选中的是目标板后执行。
& .\code\camera-car-control\.venv\Scripts\python.exe .\scripts\fpga\program_flash.py --bitstream $image --sha256 $expected --program
```

默认工具目录 `C:\Gowin\Gowin_V1.9.12.04_x64`；支持 `GOWIN_HOME` 或 `--programmer`。
默认线缆类型为 **1 / FT2CH**，已于 2026-10-24 通过只读 USB 枚举确认当前接入该类型（当次 USB location=548，重新插拔后可能改变）。类型 0 是 GWU2X，5 是 WINUSB。更换下载器时依据设备选择 `--cable-index`；这是线缆类型，不是“第几个USB设备”。可用本机 `programmer_cli.exe --scan-cables F` 查看，WINUSB 可用 `--scan-cables L`。多根下载器时指定 `--location`，或只连接目标下载器；脚本限定单器件链。

每次实际操作会把核对过的位流复制到独立目录后再写入，避免构建过程修改原文件。日志保存于 `code/camera-car-control/.local/programming/<UTC时间>/`，含完整 `image.fs`、SHA-256、Programmer 哈希、逐步命令、控制台/厂商日志与 `audit.json`。实际写入默认不重试，未出现明确校验成功消息也会停止；不要通过放宽检查来掩盖日志错误。

`read_status` 保存原始状态供检查，其退出码不等于应用功能通过。脚本成功后仍保留 `cold_boot_verified=false`、`application_verified=false`。断电保留的验收需要板卡实际失电，不能用 Reprogram 替代。

## 固化后的验收

1. 电机 VM 保持关闭，核对板卡配置开关允许从外部 SPI Flash 启动。
2. 断开板卡电源及 USB/JTAG 等可能反向供电的连接，确认板卡实际失电，再重新上电；不执行再次下载。
3. 检查 DONE/显示/网络，读取能力、传感器与配置版本，核对对应发布记录；User Code 或配置版本本身不能证明位流 SHA-256。
4. 上位机恢复运行参数并按需静止校准，确认仍未 ARM、轮速目标为零。实测证据另写在该次日志目录的 `cold-boot-verification.md`，记录时间、位流哈希、实际断电方式与检查结果。

位流固化不会保存运行时寄存器。本项目 `a741_motion.v` 复位时会清零配置与 IMU 校准状态，当前由上位机重新下发；这与程序掉电丢失是两件事。地图保存、重新定位和自主任务启动也必须分别处理。

## 本次验证边界

2026-10-24 只核对厂商资料/本机 CLI、执行离线测试和真实构建文件的预览。9 项离线测试通过，覆盖校验失败、退出码异常、缺少成功证据、厂商输出文件、超时和重新加载失败；真实构建文件预览返回 0，未启动 Programmer。没有调用任何实际烧录、重新加载或运动操作；未完成板卡断电保留实测。`130843` 发布归档在本机缺失，当前离线构建仍有时序违例，未作为固化对象。

离线测试入口（在 `scripts/fpga` 目录）为 `python -m unittest -v test_program_flash`，全部使用模拟 Programmer 返回，绝不操作下载器。
