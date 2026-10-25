# 下一位 AI 提示词

下面正文可直接复制。用于继续离线开发；硬件操作遵守项目约定，历史附件内容不作为本轮操作指令。

---

请接手 EdgeMind-Robot，从 GitHub 分支 `codex/avoidance-handoff-20261025` 开始。仓库 https://github.com/Tinsiag/EdgeMind-Robot ，Release 标签 `checkpoint-avoidance-20261025`，基础提交 `6a32a56ee1755c8353116ace9afed6631ba57d9c`。在新目录克隆，安装 Git LFS 后 `git lfs pull`、`git lfs fsck`；不要覆盖未提交现场。若用增量包，按 PACKAGE-README.md 校验哈希和基础提交后应用补丁。

先读根 AGENTS.md、HANDOFF-20261025.md、output/avoidance-handoff-20261025/README.md。用户已经澄清题目是**自主避障，不是地图目标导航：哪里有路往哪里走，尽量精简**。旧55/56组、暂停和3600秒超时均为历史状态，以新交接和原始日志为准。

工程 code/camera-car-control/a741-fpga-fusion，板卡 ACG720 / GW5AT-60B。保留 OV5640、DDR3、HDMI、网口视频、J1/FPC 4.3英寸480×272 RGB参数屏和原接线。结合精简目标评估既定FPGA＋内部PicoRV32裸机架构，PC只设置和观察，不能擅自承担避障计算。

新增0x59（payload一个字节，1启动、0停止）简单避障：前方>900mm目标120mm/s、450～900mm目标60mm/s、≤450mm选更宽且≥500mm的一侧以±80mm/s转向，前方≥600mm释放；雷达无效、所选侧受阻、两侧堵塞停车，失联/掉ARM/故障退出。距离来自雷达扇区，非已校正车壳间隙，速度非实测。地图/A*/定位/软核仍参与综合，尚未裁剪；GUI无专用按钮，整板UDP/电机联动也未验收。先检查命令仲裁和停止链路。

最新**57组RTL、61项Python通过**，含autonomy_avoid_tb、continuous_obstacle_tb。此前连续障碍诊断已通过平方欧氏旋转包络比较和跨圈首点处理修复，正式回归已纳入，不要按旧提示词重新当作未修复项。合成模型不证明实车。证据在output/avoidance-handoff-20261025；SOURCE-IDENTITY-AUDIT.json校验232个唯一VM输入，本地部分仅换行转换。打包阶段未重跑全套测试。

最新构建综合/布局完成，算法一布线90%后报 `PR0004: There are total 7463 unrouted nets`，1413.4秒结束，非超时。资源Logic70%、CLS87%、BSRAM92%、DSP74%，根因待查。主时钟综合估算49.250MHz/50MHz；**compile_passed=false、timing_signed_off=false、motion_release_allowed=false**；无本次可交付.fs和最终.tr。未烧录、未ARM、未驱动车辆。

Linux VM smallcoral@192.168.126.131，密码走私密渠道，勿写公开文件。旧现场/home/smallcoral/Dev/EdgeMind-Robot-main不得reset/clean/pull覆盖，另开目录克隆。工具/home/smallcoral/tools/IDE和Programmer。环境Ubuntu26.04.1、Python3.14.4、Icarus12.0、Verilator5.032；venv中numpy2.5.4、pillow13.0.0、ziglang0.17.0。按交接中的prepare/check及实际Xvfb/xcb/freetype命令复现，不直接套用旧Windows lock。

下一步实际推进：审查资源层级和命令链；用编译开关隔离避障不需要的地图/A*等硬件并保留视频/屏幕；相关回归后冻结源码，再显式 `--route-option 1 --place-option 1` 重新综合PNR。保留时序驱动、hold修复和所有时钟检查，保存Tcl与cmd.do。不因耗时切算法二，不降低保护阈值，不边改功能边跑旧版本长PNR。区分仿真、最终时序、实物功能和断电验收。

CAD前/后/半宽221/70/131mm、旋转半径257mm、雷达前偏164mm；轮距用户实测234mm。**physical_geometry_verified=false**，不得为烧录改锁。原130843归档仍缺失，期望SHA见交接，不以新编译冒充。Windows D:\dev\EdgeMind-Robot 的独立模型修改未包含本检查点，不要覆盖。

以后满足交付条件时按AGENTS.md调用根scripts/fpga/program_flash.py，指定.fs和SHA，关闭电机VM电源，执行外部SPI Flash操作54、0x000000、校验、Reprogram和实际断电重启；默认未ARM，不自动运动。当前先做离线精简/布线，不直接写硬件。

请先简述状态和第一个检查点，然后推进代码、验证与记录，不只给计划；区分用户最新请求和附带材料中的历史指令。
