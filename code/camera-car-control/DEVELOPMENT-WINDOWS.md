# 本机 A741 开发环境

2026-10-23，在 `C:\Users\sc\Documents\Dev\Hardware\EdgeMind-Robot` 恢复。
源码基线为 Git 提交 `1bb6da92e67c911c5d8a750b2d14af14522029e3`。
环境恢复阶段只运行离线界面、测试和编译，没有下载位流。
后续现场联调见 [Windows 上位机联调记录](a741-imu-motion/verification/WINDOWS-BRINGUP-20261023.md)。

## 工具与依赖

| 工具 | 版本或位置 |
| --- | --- |
| Python | 3.12.14 x64，项目独立环境 `.venv` |
| Python 基础解释器 | `%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` |
| Python 包 | 见 `requirements-dev-lock.txt` |
| Icarus / vvp | 10.2，[FPGAwars 包1.2.1](https://github.com/FPGAwars/toolchain-iverilog/releases/tag/v1.2.1)，仓库 `tmp/vision-motion-tools/bin` |
| Gowin | [官方 V1.9.12.04](https://www.gowinsemi.com.cn/software/1)，`C:\Gowin\Gowin_V1.9.12.04_x64` |
| Programmer | 随 V1.9.12.04 安装，`C:\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin` |
| CoreSLAM | 固定上游提交 `1170285cd42a88300eddd275fc3df36e642e3a2e`，Zig 0.13.0 编译本地 DLL |

Python 环境不继承系统包。基础解释器来自当前本机运行时；移动或删除该解释器后，需要重新创建 `.venv`。
没有修改系统 PATH。`dev.cmd` 只为当前进程设置工具路径及 `GOWIN_HOME`。

## 前一次本机复现结果（任务3/4新增软核与屏幕前）

| 工程 | RTL 测试台 | Python 测试 | 输入哈希 |
| --- | --- | --- | --- |
| `a741-imu-motion` | 25组通过 | 59项通过 | 与当前文件一致 |
| `a741-fpga-fusion` | 40组通过 | 56项通过 | 与当前文件一致 |

这些结果来自本机使用上述工具的实际运行。日志与输入清单位于各工程 `.local/tests/`。

两套工程均完成综合、布局布线和位流生成，实际网表头均为 `V1.9.12.04 (64-bit)(89079)`。
输入与产物哈希核对通过，`sources_changed=false`。

| 工程 | 完整构建 | 耗时 | setup / hold 违例端点 | 时序签核 |
| --- | --- | --- | --- | --- |
| `a741-imu-motion` | 通过 | 747.6秒 | 70 / 31 | 未通过 |
| `a741-fpga-fusion` | 通过 | 1536.0秒 | 1452 / 30 | 未通过 |

位流仅保留为 `.local/` 中的本次开发构建产物。没有生成或替换 `130843` 发布归档，未烧录。
报告同时保留 recovery/removal 和最小脉宽裕量；上表不代表完整时序检查只有 setup/hold。

## 日常入口

在本目录执行；PowerShell 中使用 `./dev.cmd`。

```bat
dev.cmd -Action check -Project all
dev.cmd -Action prepare -Project all
dev.cmd -Action mapping -Project all
dev.cmd -Action test -Project all
dev.cmd -Action build -Project motion
dev.cmd -Action build -Project fusion
dev.cmd -Action launch -Project motion
dev.cmd -Action launch -Project fusion -SensorsOnly
```

`check` 检查依赖；`prepare` 恢复原厂平台；`mapping` 编译建图 DLL；
`test` 运行 RTL 与 Python 回归；`build` 执行综合、布线和位流生成。
两套原有 `launch.cmd` 也可使用。GUI 启动不会自动连接设备。

可通过 `-GowinHome` 与 `-Examples` 指定其他安装目录和例程目录。
例程目录须包含第38、47、59章的 ZIP，结构与下方准备入口一致。
仿真脚本也接受 `GOWIN_HOME`，避免依赖另一台电脑的固定安装路径。

## 原厂例程

本机原始资料位于仓库同级的：

```text
fpga/小梅哥ACG720国产高云FPGA教学开发板资料/02_例程源码/GW5AT60K
```

第38章、第59章原 ZIP 保持不变。第47章在本机仅有解压后的源码，
因此将其 `src/` 原样打包为本地 ZIP，供现有准备脚本读取；没有修改原始资料。
该重新打包的 ZIP 不具有原始 ZIP 的二进制哈希。
来源、重打包标记和 SHA-256 记录在 `.local/environment/example-archives.json`。
准备入口为 `.local/environment/examples/GW5AT60K`。

平台与编译中间产物位于各工程的 `.local/`，不提交到 Git。
编译日志和结果分别在 `.local/gowin-motion-lidar` 与 `.local/gowin-fusion`。

## 本轮适配

- 为两个新增工程补齐 CoreSLAM 的字节保留属性，固定源码恢复为与 Git 和上游清单一致的 LF 字节。
- 建图安装脚本以 LF 写入来源清单，避免 Windows 换行转换造成无意义改动。
- HDMI 仿真使用 `GOWIN_HOME` 选择官方模型；运动工程可找到运动平台生成的编码器文件。
- 运动测试此前仍按500 ms反馈窗口断言，现检查1000 ms窗口前不误停、窗口后锁存故障。
  没有修改电机控制 RTL、保护参数、引脚或标定值。

## 复现边界

`130843` 和历史 `101036` 完整发布归档不在 Git 中，本机尚未恢复。
因此不能执行历史基线位流哈希及归档逐文件比对，也不能将当前源码编译产物称为原 `130843` 固件。
当前维护源码包含归档后的更新。

融合版几何锁与导航锁保持原样。编译完成不等于时序签核或实车验收。
本次复现结果、工具哈希和测试数量见 `.local/environment/restoration-report.json`。

2026-10-24任务3/4的新结果以 `a741-fpga-fusion/verification/TASK3-4-REPORT.md` 为准，
上文的40组RTL、56项Python、旧时序和旧几何锁描述不能当作新版本结果。
`dev.cmd -Action build -Project fusion` 现在启用用户确认的J1/FPC 4.3寸RGB参数屏，
输出目录改为 `.local/gowin-fusion-tft480`。

## WSL工具（2026-10-24）

按用户要求直接使用本机 `Ubuntu-26.04`，从Ubuntu官方软件源安装了
Icarus Verilog 12.0、Verilator 5.032、RISC-V GCC 14.2.0、binutils和CMake。
已有裸机固件的正式镜像仍固定用Zig 0.13.0构建，避免无必要地更换已验证指令镜像。

在融合工程目录运行 `../.venv/Scripts/python.exe -X utf8 scripts/check.py --wsl Ubuntu-26.04`
会将RTL仿真交给WSL，保留Windows Python与本机DLL的上位机测试。
Windows启动WSL可能打印localhost代理未映射提示，Ubuntu官方apt源和本地仿真已可用，
无需为本项目更改全局WSL网络或代理设置。

重复安装副本和两张无效截图的删除被自动命令审核以 `blocked by policy` 拦截，已保留。
具体位置记录在 `.local/environment/cleanup-pending.txt`；无效截图已标记并排除出验证证据。
