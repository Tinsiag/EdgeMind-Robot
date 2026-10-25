# 给下一位 AI 的交接说明

记录时间：2026-10-24，北京时间。工作区为 `C:\Users\sc\Documents\Dev\Hardware\EdgeMind-Robot`。

**用户已要求暂停开发并打包交接。所有编译、RTL测试进程已停止；等待用户让下一位AI继续后再恢复。没有烧录、Reprogram、ARM或驱动电机。**

## 用户目标与不能遗漏的要求

1. 优先完成图片中的任务3和任务4。任务3为LD06实时障碍检测、自动减速/停车和自主绕障。任务4为指定场景起终点自主移动、障碍避让和路径点导航。
2. 基础功能在FPGA和内部裸机软核上计算。PC只做设置与观察，不承担导航计算。不把任务换成外部Linux/Nav2。PicoRV32软核已经集成，并非运行Linux。
3. 使用已有OV5640摄像头、DDR3、HDMI及网口视频工程与接线。当前接J1/FPC的是用户确认的4.3寸480×272 RGB屏，用于显示运行参数。
4. 用户要求从仓库3D模型读取几何。V4/V5完整装配已核对，不能用下壳STL冒充整车包络。
5. 后续交付必须使用外部SPI Flash完整固化并校验、Reprogram和实际断电重启验证。SRAM下载、只生成.fs不算完成。
6. **需要小车通电时先提醒用户。** 用户于本轮特别要求。烧录/重载前电机VM必须关闭；默认未ARM，不自动恢复运动任务。
7. 用户允许使用本机WSL和安装缺少的工具；不希望无效长等待。优先用现成工具，按具体关键路径修复，再做整板布局布线。
8. 遵守根AGENTS.md。不要重置已有工作区修改；不少修改在本次任务前已存在。当前没有授权创建子代理/新聊天，没有要求提交Git或创建PR。

## 当前实现

- 主实验工程 `code/camera-car-control/a741-fpga-fusion`；尚未验收、未替换原稳定固件。
- LD06投影到车体/地图坐标，前后车体净距、扫描完整性/300ms过期、近点立即禁止输出，250～600mm限速、≤250mm停车。曲线与旋转还要求全周净空。
- 停车约300ms、记录障碍、地图膨胀、A*重规划、可靠定位后恢复，最多7次。未知格不可通行，不穿障碍角点。
- 栅格A*、局部扫描匹配、路径跟踪、起终点及最多16个有序航点。实际PicoRV32运行920字节RV32I裸机程序，8KiB片内RAM；不依赖外部控制心跳执行明确启动的任务。
- CPU心跳100ms看门狗、控制权仲裁、STOP与传感器/电机故障优先。退出任务撤销ARM，防止正常控制权释放被误记外部TTL超时。
- 主机客户端/GUI增加航点设置、顺序显示与执行，单目标/返回入口使用板内任务。PC不计算新的导航路径。
- TFT显示轮速目标/反馈、姿态、净距、位姿、航点进度、CPU、导航原因、匹配质量、相机/DDR/网口状态。仿真图见同目录`tft480-simulation.png`，不是实物照片。

## 几何与固件身份

- CAD保守外廓：轴中点向前221mm、向后70mm、左右半宽131mm；旋转半径257mm。LD06向前偏164mm。
- 模型轮距约214.161mm，用户实测运动学轮距234mm继续保留，并据差异加宽碰撞包络。
- `navigation_geometry_verified=true`只代表CAD核对；`physical_geometry_verified=false`。精确扫描高度未知；CAD光学窗口约185.681～198.281mm，不能称作扫描平面。
- 复现脚本`scripts/geometry_from_model.py`，读取V4/V5 STEP、parameters.json、verification.json并核对哈希。
- PicoRV32上游提交`ef203c2b0a3fb793280f5114941416c425c5b461`，保留ISC许可。固件二进制SHA为`d8696588e9110ad1e65884aaef5195b92cb6c9ccb793e7fbc4bb3d882d3c9b07`；hex SHA为`3b9d8f2fafbd662da0011d1abb72b8559b714b49b8a6c97289fc70590d8dce18`。
- 原用户确认基线`A741-MOTION-LD06-H20-H14-20261022-130843`在本机缺少原始归档。期望.fs SHA为`e492146beb969e5ff97aaa2608b677f6ebab5b22354768cca6f55c5a8b15fe8e`。不能重新编译后冒称原基线，不能拿旧101036替代。

## 验证状态，必须区分新旧输入

当前工作区的最新完整回归已经通过：**49组RTL、61项Python/主机测试全部通过**，记录在`code/camera-car-control/a741-fpga-fusion/.local/tests/result.json`，时间为2026-10-24 22:14:54（北京时间）。该记录的输入哈希与当前源码一致，包含新增的`pi_target_limit_tb`以及`ddr_framebuffer_tb`。`hardware_tested=false`，所以这只是离线仿真/主机验证，不代表实板通过。

`output/handoff/EdgeMind-Task34-20261024-204917/evidence/tests/result.json`中的48组RTL、61项主机测试是20:34左右的旧快照；交接包在20:49生成，不能覆盖当前工作区的49组结果。包内单项日志可能混合时刻，后续若脱离原工作区仍需重新核对源码哈希。

实际软核+核心仲裁+房间定位+A*/跟踪器联动、三邻近航点、外部TTL过期和任务期间禁止改图已经在此前回归通过。CAD房间使用实际257mm半径、164mm雷达前偏，验证暂停/重规划/恢复转向。夹具是合成扫描与静态位姿，不代表实车连续运动、到达精度或制动距离。

原Flash脚本9项离线测试通过。没有实际写Flash或断电测试。没有完整录制传感器回放，不能把GUI模拟会话日志当成真实传感器录制。

## 时序问题及已做修复

此前整板布局布线曾长时间停在Routing Phase 0，最近一次在19:09主动停止，耗时2788.6秒。没有新可交付位流。不能继续盲等。

逐轮综合诊断（均为布线前估算，不是STA签核）

- 最初sys目标50MHz，估算18.350MHz、65级，前净距到tracker限速。改为定宽、约分及流水，硬停车仍立即生效。
- 随后30.733MHz、42级，tracker绝对值/轮距乘法。分离绝对值、乘法、除法启动。
- 随后37.386MHz、36级，位姿门控经安全限速进入tracker。安全模块改用门控前的意图轮速，tracker限速另寄存；最终停止门控保留。
- 随后43.966MHz。原视频32位跳帧/帧块计数器成为最差路径。共享DVP和DDR模块按实际范围缩窄，长帧像素计数饱和；原DDR背压与双缓冲测试通过。
- 屏幕格式化先采样字段，PANEL_LAYOUT=1时位置译码增加一级寄存；HDMI像素延迟保持原样。TFT模块估算53.233→75.734MHz，改前改后输出帧逐像素一致。
- 当前源码对应的最新整板仅综合已完成（约438秒，`compile_passed=true`），产物是综合网表，不是可烧录位流：`code/camera-car-control/a741-fpga-fusion/.local/gowin-fusion-tft480/impl/gwsynthesis/a741.vg`，SHA-256为`d0ca2b7f14e22da6908ffce76a1cbfa6bf2a9707e8d00692393d8e88ab9b88c5`。这是布线前估算，`timing_signed_off=false`、`hardware_programmed=false`、`motion_release_allowed=false`。
- 该综合估算的`clk`为 **48.433MHz**（目标50MHz、29级）；camera约110.917MHz，rgmii约143.973MHz，pixel约54.832MHz。最差路径是DDR fclkdiv时钟域`ui_reset/pipe_2_s0→video/input_fifo/empty_s0`，估算余量**-2.018ns**；另有DDR初始化跨时钟路径约-0.725ns、tracker约-0.647ns、pixel/视频CDC约-0.494ns。均不是布局布线后的STA签核。

最新、尚未整板重新验证的改动

1. PI新增`TARGET_LIMIT_ENABLED`参数和`target_limit`端口。融合模式在tick同时采样原始目标/上限，下一阶段限幅；保留零目标当次采样及最终硬件禁止。默认参数0保留旧PI行为。新pi_target_limit_tb验证tick一致性、正负限幅、零目标/上限及处理中禁用。
2. travel先采样绝对值和有效轮径，再乘法；有效轮径限于18位。Q16正负/溢出定向回归通过。单模块估算146.089MHz。
3. DDR将`read_blocks<BLOCKS`寄存为blocks_remaining。最后一个已接受读由read_outstanding保持到返回，注册的界限在下一次申请前已更新，打断仲裁到FIFO empty的组合链。DDR定向及视频测试通过。
4. 最新motion模块单独综合约75.860MHz。单模块结果不能代替整板。

交接包中的`evidence/gowin-fusion-tft480/result.json`仍是此前被人工停止的旧运行（returncode=4294967295，约58.487秒），不能拿它判断当前状态。当前源码对应的完成记录是上面的`.local/gowin-fusion-tft480/result.json`；旧的`.local/gowin-fusion-tft480-synth`网表也不要在未核对哈希前复用。

历史记录在`.local/gowin-fusion-tft480/history`、`.local/routing-stopped-20261024-1909`等目录。更老`.local/gowin-fusion/impl/pnr/a741.tr`来自2026-10-23，不能当本轮时序证据。

## 下一步建议

用户恢复后，先核对`.local/tests/result.json`与`.local/gowin-fusion-tft480/result.json`的输入哈希，再针对`-2.018ns`路径和DDR初始化/CDC路径修复。修复后重跑49组/61项回归和整板仅综合，再检查新的具体路径，确认时序签核后才进入PNR。保留原时钟、timing-driven与hold修复，不切断整个时钟组来掩盖问题。现有MAC FIFO CDC例外仅针对源码核对过的第一级同步器和握手保持总线；未知DDR校准/恢复路径仍需核对。

在融合工程目录运行

```powershell
& '..\.venv\Scripts\python.exe' -X utf8 scripts/check.py --wsl Ubuntu-26.04
& '..\.venv\Scripts\python.exe' -X utf8 scripts/build.py synth --in-place --fusion --tft480 --route-option 2 --place-option 1 --timeout 900 --examples '..\.local\environment\examples\GW5AT60K'
# 检查综合关键路径和输入哈希后，才复用当前已完成网表
& '..\.venv\Scripts\python.exe' -X utf8 scripts/build.py pnr --fusion --tft480 --route-option 2 --place-option 1 --timeout 1800 --examples '..\.local\environment\examples\GW5AT60K'
```

build.py会自动记录综合频率、路径、报告哈希；PNR复用核对包括初始化固件在内的输入。开始PNR前另存本次synth result/build.log，避免覆盖综合证据。脚本不会自动签核时序或解除运动发布锁。`report_task34.py`拒绝运行中或输入过时的记录，也区分仅综合与完整工具流程。

本机工具：Gowin `C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe`；WSL Ubuntu-26.04内Icarus12、Verilator5.032、RISC-V GCC；Windows项目venv含Zig0.13、GUI/测试依赖。CAD大场景用Verilator，其他夹具Icarus，日志逐项记录。不要把WSL localhost代理警告当失败。临时编译物用/var/tmp，WSL重启会清/tmp。

待完成：整板setup/hold/recovery/removal/最小脉宽及I/O预算签核、传感器录制回放、实物屏幕/摄像头并行验证、实车定位/制动/绕障/航点精度、Flash完整固化和真正断电验证。

## 固化入口

满足交付检查、明确提醒用户供电并确认电机VM关闭后，使用根`scripts/fpga/program_flash.py`，显式给.fs路径及SHA。固定Arora V操作54、地址0x000000、写入校验成功后Reprogram及状态读取。失败停止，不自动重试、不降级SRAM。实际断电需排除USB/调试器等反向供电。运行时地图/标定/任务不会仅靠配置Flash自动保存，不能自动恢复运动。

目前不要烧录任何旧.fs。包内没有本轮可交付位流。
