# 本轮接续记录

本轮继续任务3/4与现有摄像头、DDR3、HDMI、网口视频、480×272参数屏集成。所有操作均为离线检查；未写Flash、未Reprogram、未ARM。

当前阻塞：2026-10-24 23:10:53启动的PNR在23:40:53达到1800秒上限，`run_state=timed_out`、`compile_passed=false`、`sources_changed=false`。最后日志为`[60%] Routing Phase 0 completed`，没有本轮`.fs`或最终`.tr`，不能交付、烧录或进入上电验收。工具进程已退出。

已完成：完整回归50组RTL和61项主机测试通过；Flash工具9项离线测试通过。整板综合主时钟预估50.153 MHz（目标50 MHz），不是布线后的时序签核。回归197个输入及构建126个输入哈希均与当前文件一致。未知时序用空对象/null表示，不代表零违例。

本轮修复：FIFO读写使能与指针运算解耦；DDR连续令牌遇背压时等待最后写入完成再处理帧尾；跟踪器绝对值和方向比较分拍；射线映射先锁存坐标再算初始误差；IMU有符号增量与航向累加分拍。新增/扩展仿真验证这些边界，并在实际软核导航夹具中并行运行合成摄像头、DDR、HDMI像素链、网口视频和TFT。

`before/`保留接手输入，`round1/`至`round3/`保留各轮综合证据，`changes.patch`只表示本轮相对接手内容的差异，不撤销仓库原有修改。`changed-source-hashes.json`记录本轮文件身份。`pnr-constraint-rejected/`记录已修正的约束对象不匹配失败。

`pnr-timeout/`保存本轮完整综合/布局中间文件、日志、Tcl、CST、SDC、配置及最终失败记录；网表SHA-256为`2326c1a10f404c7f98671c0db600f95dc1f2d321e37172e136b69864b1d6e71b`，它不是可烧录位流。`tests/`保存50组RTL日志、主机日志及输入哈希，`source/`保存修改后的源文件/文档；`synthesis-resource-hotspots.json`仅统计模块综合资源，不能据此声称已定位布线拥塞根因。

当前报告为[任务3/4报告](../../code/camera-car-control/a741-fpga-fusion/verification/TASK3-4-REPORT.md)及[机器记录](../../code/camera-car-control/a741-fpga-fusion/verification/TASK3-4-RESULTS.json)。实板流程与待测栏见[任务3/4验收记录](../../code/camera-car-control/a741-fpga-fusion/verification/TASK3-4-ACCEPTANCE.md)。

尚待解决的离线问题：先定位整板布线长时间无法完成的原因，取得当前源码的完整路由结果；随后审查setup/hold/recovery/removal/最小脉宽、RGMII外部预算和DDR校准/动态相位。当前已使用布局算法1（优先可布通）、路由算法2（提高速度）、原时钟及hold修复；不应只换成无界等待、停用时序驱动或切断整组时钟。厂家示例中没有SDC文件也不构成排除DDR时序的依据。旧2026-10-23报告的数值不能填成本轮结果。

原稳定130843位流未恢复，未用本轮源码重新冒称该基线。CAD几何哈希已核对；实物几何、真实传感器录制、制动/定位/绕障/航点、完整Flash固化和真实断电保留仍需实板验证。

用户要求本轮在需要上电时停下提示。供电/Flash操作前须关闭电机VM；按`scripts/fpga/program_flash.py`显式指定完整.fs与SHA-256，不能把生成文件当作已固化。
