# 给下一位AI的提示词

将下面整段复制给下一位AI即可。提示词授权下一位恢复**离线开发**；当前会话仍保持暂停。

---

请接手并继续我的EdgeMind-Robot项目。上一位AI已按我的要求暂停、推送源码并制作交接；我现在授权你从GitHub克隆开始恢复离线开发。

仓库：https://github.com/Tinsiag/EdgeMind-Robot ，分支`main`。先安装/启用Git LFS，克隆并取回LFS实体。源码检查点`87c97b7ceb8018fb3edc88cce0c29f15515d4ec9`；最新交接和打包修正在其后的提交，先使用最新main，不要用旧压缩包覆盖。

```powershell
git lfs install
git clone --branch main https://github.com/Tinsiag/EdgeMind-Robot.git
cd EdgeMind-Robot
git lfs pull
git lfs fsck
```

先阅读根目录`AGENTS.md`、`HANDOFF-20261025.md`和`CLONE-VERIFICATION-20261025.md`，再检查任务工程`code/camera-car-control/a741-fpga-fusion`。交接文档给出了Python、WSL、原厂例程恢复、平台生成和回归命令。原厂38/47/59章已放入`resources/vendor/acg720-examples`，不要再依赖另一台机器的Administrator目录。本机有WSL，直接使用；必要工具缺失可安装。

我要完成图片要求的任务3实时避障、任务4自主导航：障碍检测、减速/停车、自主绕障、起终点及路径点导航。基础能力必须在ACG720/GW5AT-60B的FPGA＋内部PicoRV32裸机软核完成，PC只设置和观察。软核不是Linux。保留现有OV5640、DDR3、HDMI、网口视频和接线，并集成J1/FPC的4.3寸480×272 RGB参数屏；LD06控制H20、接收H14。

当前55组RTL、61项Python回归通过，Flash工具另有9项离线测试通过，也做了独立GitHub克隆恢复检查。但**连续突发障碍绕行诊断失败，不能宣布导航完成**。最新综合在用户暂停时中断，没有当前版本完成的综合网表、整板时序签核或可交付位流；本轮没有烧录、ARM或运动。

请优先复现并修复`output/task34-recheck-20261025/continuous-navigation/continuous_obstacle_tb.v`，用同目录`run.py --bench ... --output ...`运行。原失败日志在`obstacle/run.log`：运动中加入固定圆障碍，停车重规划后最终guard fault=5、两次重规划，未到达目标，根因尚未确认。跟踪首段路径、forward/left/cap/blocked、rotation_clear/min_mm、localized和navigation_phase，不要通过降低保护阈值把失败改成通过。

已有两项修复不要退回：近障碍速度舍入为0时的blocked/有限停车重规划与独立安全转向上限；全零扫描修正跳过整数位姿重设，避免反复丢失Q16小数里程。正式连续直线测试已经覆盖后者。修好新失败后，把场景加入正式回归，再核对全部功能。

用户明确选的是**布线算法一route_option=1**；当前布局也用place_option=1，两者不要混淆。先完成软件检查并冻结RTL、固件和约束，再综合、查看关键路径，最后只对这个冻结版本做整板算法一PNR。不要边改功能边反复跑长时间布线，不要为了出位流关闭时序驱动、hold修复或切掉整组时钟检查。旧51.276MHz只是较早输入的综合估算；旧211条未布通、超时和主动中止是不同轮次，请按交接区分。

导航几何从仓库V4/V5完整3D模型读取，当前CAD前/后/半宽221/70/131mm、旋转半径257mm、雷达前偏164mm；保留用户实测234mm运动学轮距。CAD核对与实车核对分别记录，`physical_geometry_verified=false`。

需要小车开电源时先提醒我。满足软件、几何和整板时序条件后，烧录前关闭电机VM。以后交付FPGA程序必须使用根`scripts/fpga/program_flash.py`显式指定完整.fs及SHA，按外部SPI Flash操作54、0x000000擦写校验、Reprogram，再真实断电重启验证；不能只下载SRAM。默认未ARM，不自动恢复运动任务。地图、标定、IMU校准和会话不会因逻辑固化自动持久化。

稳定130843原始位流归档在当前工作区和Git中仍缺失；期望SHA在交接文档里。不要覆盖、不要把当前源码重编译文件冒称为原130843基线。

请先简要说明接手状态和第一项具体检查，然后按上述顺序动手推进。分别报告仿真、整板时序、实板与断电验证结果，不把其中一种当成全部完成。
