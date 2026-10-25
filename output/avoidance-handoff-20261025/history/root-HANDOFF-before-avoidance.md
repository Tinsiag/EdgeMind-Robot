# EdgeMind-Robot 交接：从 GitHub 克隆开始

更新于2026-10-25，北京时间。用户09:44:48要求暂停开发、推送所有工作并交接。当前没有本轮编译或仿真进程，没有烧录、ARM或运动。下一位收到用户明确的继续指令后再恢复开发；不能把这份文档当作上电或运动指令。

源码检查点为`87c97b7ceb8018fb3edc88cce0c29f15515d4ec9`，本文及克隆检查记录在其后的文档提交中。当前主线是`main`，仓库为公开仓库。

用户可直接复制[下一位AI提示词](NEXT-AI-PROMPT-20261025.md)；发送该提示词即向下一位明确授权恢复离线开发。实际拉取检查见[独立克隆验证](CLONE-VERIFICATION-20261025.md)。

## 1. 先从 GitHub 获取完整项目

在Windows PowerShell执行。先安装Git和Git LFS；目标目录由接手者选择。

```powershell
git lfs install
git clone --branch main https://github.com/Tinsiag/EdgeMind-Robot.git
cd EdgeMind-Robot
git lfs pull
git lfs fsck
git log -1 --oneline
git merge-base --is-ancestor 87c97b7ceb8018fb3edc88cce0c29f15515d4ec9 HEAD
```

最后一条应返回0。大模型、预览和归档使用LFS；如果STEP或ZIP实际只有几行`version https://git-lfs.github.com/spec/v1`，说明还没有取回实体。本文后续命令均从新克隆的仓库根开始。不要用旧交接压缩包覆盖这个新克隆。

本次推送包含当前源码、V4/V5完整模型、原厂构建输入、早期交接包、诊断源码和日志。Python虚拟环境、Gowin/WSL安装、密钥及可重建的编译数据库/网表/仿真程序保留本地；`.gitignore`明确列出这些缓存。未将历史实验位流当作发布固件上传。

## 2. 当前事实与证据

| 项目 | 当前结论 |
| --- | --- |
| 正式离线回归 | **55组RTL、61项Python通过**；暂停时全部已记录输入哈希仍匹配 |
| 连续直线运动 | 已修复零扫描修正反复丢失Q16小数里程；正式回归已覆盖 |
| 连续突发障碍绕行 | **失败，尚未修复**；独立诊断未计入55组通过 |
| 当前版本综合 | 用户暂停时中断，247.63秒；没有当前版本综合通过结果 |
| 当前版本PNR/整板时序 | 尚未完成；`timing_signed_off=false` |
| 硬件 | 本轮未上电、烧录、ARM或运动；实际摄像头/屏幕/传感器/导航并行仍待实板验收 |
| Flash和断电保留 | 脚本已实现；本轮未执行写入或真实断电验证 |

最新正式材料：

- [任务3/4报告](code/camera-car-control/a741-fpga-fusion/verification/TASK3-4-REPORT.md)、[机器结果](code/camera-car-control/a741-fpga-fusion/verification/TASK3-4-RESULTS.json)。
- [暂停进度及过程区分](code/camera-car-control/a741-fpga-fusion/verification/TASK3-4-PROGRESS.md)。
- [55组测试原始证据](code/camera-car-control/a741-fpga-fusion/verification/handoff-20261025/evidence/tests/)、[源文件身份](code/camera-car-control/a741-fpga-fusion/verification/handoff-20261025/SOURCE-IDENTITY.json)。
- [本次复查总记录](output/task34-recheck-20261025/README.md)。

历史记录中的绝对路径和SHA描述当时Windows工作区。新克隆可能发生Git换行转换，忽略目录也需要恢复，不能直接用历史绝对路径通过验收；按下面命令重新生成本机结果。旧50/52/54组报告、03:16位流和单模块Fmax均不能替代当前版本验证。

## 3. 恢复开发环境

本机已验证Python **3.12.14 x64**、Gowin **V1.9.12.04 (89079)**、WSL **Ubuntu-26.04**、Icarus **12.0**、Verilator **5.032**、Zig **0.13.0**。新机器先安装Python、Gowin及WSL；Gowin安装和设备许可由接手者准备。现有机器无需重装这些工具。

```powershell
py -3.12 -m venv code/camera-car-control/.venv
$repo = (Get-Location).Path
$py = Join-Path $repo 'code/camera-car-control/.venv/Scripts/python.exe'
& $py -m pip install -r code/camera-car-control/requirements-dev-lock.txt

# 只恢复源文件，不会启动Programmer或连接小车。
& $py scripts/handoff/restore_environment.py --check
& $py scripts/handoff/restore_environment.py

$env:GOWIN_HOME = 'C:\Gowin\Gowin_V1.9.12.04_x64'
wsl -l -v
# 仅当WSL里尚未安装仿真工具时执行：
wsl -d Ubuntu-26.04 --exec sudo apt-get update
wsl -d Ubuntu-26.04 --exec sudo apt-get install -y iverilog verilator build-essential
```

原厂第38/47/59章归档位于[resources/vendor/acg720-examples](resources/vendor/acg720-examples/README.md)，按manifest校验再复制到原准备脚本使用的`.local/environment/examples/GW5AT60K`。第47章是由原始`src/`本地重打包，38/59章保持原ZIP字节。恢复脚本遇到已有不同内容会停止，保留接手者文件。

准备平台和裸机镜像，再编译主机建图DLL：

```powershell
Push-Location code/camera-car-control/a741-fpga-fusion
# hdmi_tb使用此目录下的原厂编码器模型，这一步不可省略。
& $py -X utf8 scripts/build.py prepare --motion-lidar
& $py -X utf8 scripts/build.py prepare --fusion --tft480 --route-option 1 --place-option 1
& $py -X utf8 scripts/build_mission.py
& $py -X utf8 scripts/setup_mapping.py
& $py -X utf8 -u scripts/check.py --wsl Ubuntu-26.04
Pop-Location
& $py -m unittest discover -s scripts/fpga -p 'test_*.py' -v
```

预期55组RTL与61项Python通过，根目录Flash工具另有9项离线测试；失败时保留`.local/tests`日志，先修复环境差异。当前任务不需要用旧Windows Icarus包，RTL交给WSL，主机测试仍在Windows Python执行。WSL的localhost代理提示本机出现过，不影响离线仿真；不要仅为这条提示改全局网络。

## 4. 接手后首先复现的功能失败

在仓库根执行，需要上节Python、Gowin仿真库和WSL依赖；不需要小车供电。

```powershell
& $py -X utf8 output/task34-recheck-20261025/continuous-navigation/run.py `
  --bench output/task34-recheck-20261025/continuous-navigation/continuous_obstacle_tb.v `
  --output output/task34-recheck-20261025/continuous-navigation/reproduced-by-next-ai
```

原始失败记录在[obstacle/run.log](output/task34-recheck-20261025/continuous-navigation/obstacle/run.log)和[result.json](output/task34-recheck-20261025/continuous-navigation/obstacle/result.json)。模型为理想差速底盘，输入随真实模型位姿变化的编码器增量、IMU朝向及逐点房间雷达；行驶到x≥175mm时，在世界坐标(756,25)加入半径60mm圆障碍，目标(1525,25)。该场景没有轮胎打滑、惯性、真实噪声或测量延迟，不能代替实车。

观察到前净距约256mm、平移速度舍入到0，停车后进入重规划，最终guard fault=5、两次重规划，未到达目标。fault=5在guard中表示定位丢失时不允许旋转恢复。尚未确认根因；下一步应记录重规划路径首段、tracker的forward/left/cap/blocked、rotation_clear/min_mm、localized与各navigation_phase切换。首段方向与零平移速度下转向判据是待核对线索，**不是已证实结论或已完成修复**。禁止通过降低净空阈值或放宽定位判据把失败改成“通过”。

已完成的两项功能修复：

1. 静态近障碍导致跟踪限速舍入为0时，显式`blocked`触发有限次数停车重规划；旋转上限独立，仍要求完整有效扫描及旋转净空。回归为`cad_stalled_navigation_tb`和`path_tracker_directional_tb`。
2. 扫描匹配每次零修正仍调用整数位姿重设，会丢弃Q16小数，模型前进约278mm后丢定位。现在跳过全零修正；`continuous_navigation_tb`连续行驶900.6mm，在目标1025mm前99.4mm处按100mm容差停车，模型与里程估计差<1mm。这是模型比较，不能写成实车定位精度。

## 5. FPGA结构与必须保留的硬件

平台为小梅哥 **ACG720 / GW5AT-60B**。任务3/4按用户要求在FPGA＋内部PicoRV32完成：软核是用FPGA逻辑实现的RISC-V处理器，运行RV32I裸机C航点任务，8KiB RAM、当前程序920字节；没有Linux。雷达保护、位姿、地图、局部匹配、A*及路径跟踪均在板内，PC用于设置和观察。

保留现有 **OV5640、DDR3、HDMI、网口视频**工程与管脚，结合LD06与IMU；LD06控制H20、接收H14。用户确认的 **J1/FPC 4.3寸480×272 RGB屏**已集成参数显示。不要换成删除视频的简化工程。HDMI现在使用55MHz、四路局部复位；隔离STA通过，但仍缺当前整板STA和实板验证。

几何来自完整V4/V5装配：前/后/半宽 **221/70/131mm**，旋转半径 **257mm**，雷达前偏 **164mm**。用户实测运动学轮距保留 **234mm**，CAD轮距214.161mm另行记录。`navigation_geometry_verified=true`是CAD审计，`physical_geometry_verified=false`是实车未量测，二者不可混淆。详情见`config/geometry.json`及`model/chassis`。

源码及用法见[任务3/4说明](code/camera-car-control/a741-fpga-fusion/docs/TASK3-4.md)，实板记录使用[验收表](code/camera-car-control/a741-fpga-fusion/verification/TASK3-4-ACCEPTANCE.md)。

## 6. 等功能检查完成，再做一次冻结版本的算法一整板构建

用户明确选择 **route_option=1**；同时采用 **place_option=1**，两者分别核对。默认布线值及`dev.ps1 -Project fusion`已设为1，仍显式写参数。保留时序驱动、hold修复和所有时序检查。

当前没有可复用的、对应最新55组源码的完成综合网表。先修复上面的连续绕障问题并完成回归，再执行：

```powershell
Push-Location code/camera-car-control/a741-fpga-fusion
$gw = Join-Path $env:GOWIN_HOME 'IDE/bin/gw_sh.exe'
& $py -X utf8 -u scripts/build.py synth --fusion --tft480 --in-place `
  --route-option 1 --place-option 1 --timeout 900 --gowin $gw
# 必须先检查综合成功、源码/固件/网表SHA及关键路径，再运行PNR。
& $py -X utf8 -u scripts/build.py pnr --fusion --tft480 `
  --route-option 1 --place-option 1 --timeout 3600 --gowin $gw
Pop-Location
```

运行中不修改RTL、固件、约束、生成平台或构建脚本，不启动另一个改写输入的构建。检查最终Tcl和`impl/pnr/cmd.do`中的真实参数。构建脚本现对相同生成内容保留时间戳，18个文件连续两次prepare的内容及时间戳一致；该修复尚未完成“综合→缓存PNR”全链验证，仍须确认日志实际直接读网表，不能声称未验证的缓存已复用。

历史必须区分：

- 更早算法一/布局一在05:14结束，6448秒，PR0004 **211条未布通**。
- 仅HDMI隔离快照的整板尝试1800秒超时，最后Routing Phase 0；发生过自动重复综合，不是已通过PNR。
- 09:23的主工程算法一PNR在883.40秒因发现小数里程缺陷主动停止，没有位流；不是该轮工具宣告布线失败。
- 最新修复后的综合在247.63秒时按用户暂停指令中断。51.276MHz/50MHz是此前源码综合估算，不能引用为当前源码或整板结果。

时序遗留还包括DDR初始化路径审查、RGMII实际I/O预算、拥塞及主时钟资源。`ddr-native-constraints-candidate.sdc`是未合入的审查候选；不得整体切断时钟组。RGMII旧min=-0.5/max=2.0ns预算存在模式混用疑点，不能仅改数字宣布实物时序通过。原厂文档、精确60B明文仿真网表及审查在`output/task34-resume-20261024/tool-docs`和`output/task34-lightweight-20261025`。

## 7. 烧录、断电和稳定基线

用户要求需要小车开电源时先提醒。当前无可交付的新位流。得到相应继续指令并满足几何、软件和整板时序条件后，先关闭电机VM，再通过仓库`scripts/fpga/program_flash.py`显式指定完整`.fs`和SHA-256；它固定外部SPI Flash操作 **54**、地址 **0x000000**，擦写校验成功后Reprogram并读取状态。不能只下载SRAM，失败不能自动重试或降级。

必须真实断电重上电，断开USB/JTAG等所有反向供电后核对Flash启动、版本、视频/屏幕/传感器，默认未ARM、不自动恢复任务。Flash保存逻辑与软核初始化；运行时地图、标定、IMU校准及会话不会自动持久化。

用户确认的稳定基线为`A741-MOTION-LD06-H20-H14-20261022-130843`，期望SHA-256：

```text
e492146beb969e5ff97aaa2608b677f6ebab5b22354768cca6f55c5a8b15fe8e
```

**该原始归档在当前本机及新克隆中缺失**。保留其身份，不覆盖，不把当前源码重编译产物称为原基线。旧文档中的Administrator绝对路径是历史位置，不代表已经恢复。

## 给下一位AI的最短任务说明

先克隆main并取回LFS，阅读根`AGENTS.md`与本文。保持用户暂停状态，先完成接手检查。收到继续开发指令后，用第4节复现连续突发障碍失败，定位并补正式回归；全部软件检查完成后冻结版本，再综合并用算法一做一轮整板PNR。没有时序、几何和实板证据，不烧录或运动；需要供电先提醒用户。当前已有摄像头和RGB屏必须一并保留。
