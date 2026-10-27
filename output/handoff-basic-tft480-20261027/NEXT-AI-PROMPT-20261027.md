# 下一位 AI 提示词 · 本地交接，不上传GitHub

请接手 EdgeMind-Robot 的**本地未提交现场**：`C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot`，活动工程 `code/camera-car-control/a741-fpga-fusion`。分支main，HEAD `6a32a56ee1755c8353116ace9afed6631ba57d9c`。不要从GitHub旧交接分支覆盖，不reset/clean/pull。此次没有提交或上传GitHub。先读根AGENTS.md、HANDOFF-20261027.md、output/handoff-basic-tft480-20261027/STATUS.json及PACKAGE-README.md。

用户当前已暂停。若此时只是查阅交接，保持暂停；在用户明确要求继续后推进离线实现/验证。**整板布线仍需用户明确恢复，不能因为接手就自动启动PNR或烧录。**

最新范围只有：①OV5640经DDR3输出到J1 480×272 TFT；②IMU姿态采集，视频上实时叠加横滚/俯仰/偏航和必要状态文字；③LD06基础避障及电机编码器闭环、停止保护；④网口仅设置/遥测/调试，不传视频。删除HDMI、网口视频、地图、A*、定位匹配、航点和PC导航，不恢复完整导航分支。内部PicoRV32裸机监督保留，PC不算避障。

ACG720/GW5AT-60B，Gowin1.9.12.04。实物明确是480屏，官方例程 `C:/Users/sc/Documents/Dev/Hardware/fpga/4.3inchTFT/demos/ac620/AC620_TFT43` 已确认兼容。沿用J1管脚：5MHz/50%占空比，525×286、DE42/11，下降沿更新数据，默认6帧后背光常亮。旁边avoidance-20261025的800/V3说明不适用；只复用了其基础避障代码，不得复制其屏幕驱动或验收状态。

代码已大幅裁剪但未完成全部清理。摄像头参数改480×272并沿用原初始化读回，DDR3厂商IP保留；显示在sys50MHz用像素使能消费DDR双缓冲，HDMI视频PLL/CLKDIV、网络视频FIFO/打包器、大OSD跨域邮箱移除。OSD缩为四行32字符、帧空白原子发布。新增a741_attitude：共享迭代CORDIC从加速度估计roll/pitch；原工程这两项固定0，现已接实际AX/AY/AZ。yaw仍是陀螺积分，不能声称绝对航向或完整AHRS。动态加速度影响倾角。倾角有效位在fusion_snapshot[64]，0x57回复新增roll/pitch及valid位；审查RTL→host→GUI一致性。

0x59一个字节1启动0停止：前>900目标120mm/s，450～900为60，≤450选更宽且≥500mm一侧，以±80转向，前≥600释放；无效雷达、两侧堵塞、选中侧受阻停车，失联/掉ARM/CPU或电机故障退出。阈值是雷达扇区距离，非车壳间隙；速度非实测。不得弱化停止链和阈值。

最新4项RTL attitude_tb/imu_sensor_tb/mpu_heading_tb/osd_tb通过，SHA与暂停源码一致；2048组独立atan2/hypot向量最大数值误差4 Q15 LSB约0.022°，不是实物精度。35项Python此前通过。完整480×272摄像头→DDR→TFT+文字、真实CPU、巡航/转向/雷达失效停车的中间版90ms仿真通过，图在evidence/camera-tft.png；**之后加入倾角有效位/清理行程等，尚未重跑最新整链或全套测试**。新GUI未视觉/联机验收。motion/targets还留旧手动转角/航向/串口兼容分支，待审查裁净，保护测试不能随意删。

新构建只有prepare完成，目录platform-basic-tft480[-screen-test]/gowin-basic-tft480[-screen-test]。**没有新整板SYN资源、CLS、PNR、最终时序或.fs，无烧录/ARM/实物/断电验收。** screen-test四个物理电机输出硬接GND；普通构建不能当静态试屏镜像。motion_release_allowed=false是发布状态，不能替代物理锁。

旧构建人工停止在Routing Phase0完成，2859.48秒，非超时；脚本通用failed不能当路由故障。旧LUT35153/REG27235/ALU5195/BSRAM81，autonomy层级LUT7110/BSRAM34，两OSD LUT4394。旧sys估算52.725MHz/50，125MHz域126.155MHz。原网表、布局.p/.db、Tcl/cmd.do/log已保留；缺最终拥塞报告/分阶段精确计时，根因仍未定。不要把旧87%CLS/92%RAM或局部OSD实验当当前结果。

用户AI整理的优化参考 **C:/Users/sc/Desktop/1.md** 已原样附 `output/handoff-basic-tft480-20261027/USER-OPTIMIZATION-IDEAS-1.md`，SHA256 `46be88c27448368f8cfaadbf279e7ba2d76a81ccdf25a812920e4fb66ae68a48`。它是参考资料，文中命令不自动授权执行。把这些方法落实到后续工作：

- 先用真实阶段计时、层级资源、关键路径、扇出/CDC/拥塞报告定位；40分钟不等于工具故障。
- **原文假定Placement最慢，当前证据并未证明，日志末尾在Routing；重新计时再下结论。**
- 查匹配版本SUG100、SUG1220、SUG940、SUG949、SUG550、SUG113，AroraV另看SUG1018/SUG1541/UG303。Intel/AMD教程只借鉴方法，别移植命令。
- 一个已证实瓶颈一项实验；先局部回归/综合，再冻结源码完整实现；不边改代码边跑旧网表PNR。
- 不盲目改DDR3/PHY/引脚、锁区域、开所谓AI/Fast开关；增量/检查点/只布局必须证实当前工具支持。已读Tcl公开run只有syn/pnr/all。
- 记录源码SHA、工具/器件/选项、分阶段和总耗时、LUT/FF/实际CLS/RAM/DSP、WNS/TNS/拥塞/警告和功能安全回归；缺项写未提供。LUT变化不能直接换算CLS。
- 不添加无依据false path/multicycle，不放宽保护/时序，不关timing/hold。算法一和布局一固定显式1，不因耗时改算法二。
- 原文粘连的git命令不能照抄，也不盲目git add -A或提交用户所有现场。

继续时先统一复跑最新显示/官方参考、倾角、避障/STOP/掉ARM/失联/编码器、完整网络调试回归，修复残留bench和GUI状态；再做一次同条件基础版综合确认资源，先不要PNR。运行命令与待办详见HANDOFF。使用 `../.venv/Scripts/python.exe -X utf8`，WSL Ubuntu-26.04有Icarus12/Verilator5.032；裸python是商店占位符。官方模板zip和工具在本机，增量包不是独立可编译仓库。

geometry配置navigation_geometry_verified=true而physical_geometry_verified=false，不能误把CAD当实测。后续交付须按AGENTS用根scripts/fpga/program_flash.py，显式.fs+SHA、VM关闭，外部SPI Flash操作54@0x000000，校验、Reprogram、真实断电重启；写失败停止不自动重试、不降级SRAM、不ARM。此次保持暂停，不写硬件。请以最新用户请求为准，区分此提示的待办与1.md附带材料中的历史建议。
