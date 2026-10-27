# 480×272屏幕兼容性修改与离线检查（2026-10-26）

用户在本会话明确确认“我们实物就是480屏……就参考我发你的例程”，本次按480×272 RGB565处理。用户选择修正驱动与兼容性，反馈已有内容但有偏移、闪烁或花屏。当前工作区为 `C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot`。旁边独立目录的800×480/V3交接与本次确认冲突，不采用其分辨率、源码或硬件验收结论；本次没有修改该独立现场。

**当前完成的是480屏源码、相关仿真和整板综合；没有生成本次可交付位流、烧录或实屏验收，不能声称已经修好实物显示。** 保留原OV5640、DDR3、HDMI、网口视频、传感器、导航与J1球号，没有改线、ARM或发起运动。原连续突发障碍诊断失败仍属于导航遗留，不在本次屏幕修改中宣称修复。

## 原厂例程对照

参考目录为用户指定的 `../fpga/4.3inchTFT/demos/ac620/AC620_TFT43`，主要读取 `rtl/TFT_CTRL_480_270_16b.v`、`NIOS_TFT43.v`、`mysystem.qsys`、实际生成的 `mysystem_altpll_0.v`、QSF和 `software/test/TFT_API.h`。来源SHA及扫描参数见 [REFERENCE-AUDIT.json](REFERENCE-AUDIT.json)。参考工程不存在新的交接Markdown；机器人交接分别读了当前根20261025交接/提示词及旁边工作区20261026交接/提示词，以用户本轮480确认决定屏幕型号。

| 项目 | AC620例程实际内容 | 本次ACG720处理 |
| --- | --- | --- |
| 有效分辨率/总扫描 | 480×272 / 525×286 | 沿用 |
| HS/VS | `h>40` / `v>9`，低41时钟/10行 | 沿用低有效及宽度 |
| DE起点 | (42,11)，实际后沿只有1时钟/1行 | 保留(43,12)，符合AT043TN24要求的至少2时钟/2行后沿 |
| 像素时钟 | 名为Clk9M，PLL实际50MHz×1÷10=5MHz | 50MHz固定五分频为10MHz，位于规格书5..12MHz范围 |
| RGB | RED=0xF800、GREEN=0x07E0、BLUE=0x001F | 保留RGB565与原ACG720物理球号，不复制Cyclone IV引脚 |
| 背光 | 顶层由独立PWM控制，驱动内PWM未接出 | 启动等待后常亮，不引入周期闪烁 |
| 平台 | Cyclone IV、Nios II、SDRAM framebuffer | 保留ACG720与现有状态渲染/视频系统 |

例程注释与PLL配置不一致，不能只按Clk9M名字认定频率；5MHz配525×286全帧为约33.30Hz，低于AT043TN24表中59.94Hz最小帧率。本次没有照搬这个配置。规格书来源为用户资料夹的AT043TN24 PDF及仓库同型号规格书；扫描表在标注页8～10，电源时序在标注页7。[power-sequence.png](power-sequence.png)是原PDF页面渲染，不是实拍。

## 本次修改

`a741_tft480_panel.v`把原平均9MHz、100/120ns周期交替的相位累加时钟改为固定10MHz；PCLK高40ns、低60ns，每像素100ns，帧率约66.600Hz。RGB/DE/HS/VS仍只在下降沿改变，上升沿采样；逻辑建立/保持分别60/40ns，原10ns端口预算保留，没有取消时序检查。固定周期消除了一个待验证的兼容因素，尚未证明它就是实物问题的根因。

默认背光延迟从6帧改为11个完整帧，约165.165ms，覆盖规格书T4至少160ms的LED启动等待；只在帧首消隐像素启用并保持常亮。启动计数器按参数宽度生成，支持超过15帧的延迟；在任意有效画面期间复位会立即熄灯、清空RGB/DE，恢复后重新等待。此项不代表硬件VDD/DISP以及关机T5/T6顺序已测量。

状态页面的内容、颜色、RGB位顺序、字符流水和HDMI逻辑未修改。新增 `tft480_timing_tb` 以端口采样独立检查完整帧每个像素的同步/DE边界、消隐黑色、固定时钟、建立/保持、有效区复位、默认11帧与17帧背光等待。该测试在WSL使用Verilator，避免解释器运行多帧导致60秒墙钟超时；原页面像素回归仍使用Icarus。

## 验证与交付边界

| 层次 | 本轮结果 |
| --- | --- |
| 相关RTL | 8组通过：两组480屏、OSD、HDMI、视频、摄像头采集、传感器、CPU/导航/视频/TFT并行 |
| 主机Python | 61项通过 |
| 页面比较 | 改前/改后480×272完整有效画面逐像素一致；PPM SHA均为78c3f6fa6e62fc8d4a2564ee6e21c396beeab3bed726db5b535ff4dbcdfd78ea |
| 整板综合 | 315.620秒通过，编译输入哈希保持一致；sys估算51.276/50MHz，属于本轮新结果 |
| 整板时序 | **未签核**；综合报告仍列DDR初始化路径-0.725ns等负余量，不能用sys Fmax替代审查 |
| PNR/位流 | 本轮未运行；保留route=1、place=1选择，不能把旧cmd.do或旧.fs当作本次产物 |
| Flash/实屏/断电 | 本轮均未执行，待相应交付条件通过后验证 |

记录见 [RESULTS.json](RESULTS.json)、[tests](tests)、[FRAME-COMPARISON.json](FRAME-COMPARISON.json) 和 `synthesis-result.json` / `synthesis-build.log` / `synthesis-build.tcl`。本轮综合网表SHA为 `9360a638c4fe7360536bf27ae8ebf6ba7968822a86882970fb6ff73ae3781007`，它不是可烧录.fs。报告中的负余量不能通过关闭时序驱动、hold修复或切掉整个时钟组来隐藏。

[screen480-simulation.png](screen480-simulation.png)为RTL输出的仿真参数页，非实屏照片。

## 复现

在当前仓库工程 `code/camera-car-control/a741-fpga-fusion` 执行：

```powershell
$env:GOWIN_HOME='C:/Gowin/Gowin_V1.9.12.04_x64'
../.venv/Scripts/python.exe -X utf8 scripts/build.py prepare --fusion --tft480 --route-option 1 --place-option 1
../.venv/Scripts/python.exe -X utf8 scripts/check.py --wsl Ubuntu-26.04 --only tft480_panel_tb --only tft480_timing_tb --only mission_navigation_tb --only osd_tb --only hdmi_tb --only video_tb --only video_capture_tb --only sensors_tb
../.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
../.venv/Scripts/python.exe -X utf8 scripts/build.py synth --in-place --fusion --tft480 --route-option 1 --place-option 1 --timeout 900
```

在仓库根运行 `code/camera-car-control/.venv/Scripts/python.exe -X utf8 output/screen480-compat-20261026/compare_frames.py` 可重新产生改前/改后画面比较（改前取当前HEAD，不能在提交修改后继续把新HEAD当旧基准）。综合结束后运行同目录 `collect_evidence.py` 收集日志和身份，不访问硬件。

后续先解决/审查现有整板时序及导航交付条件，再对冻结输入执行算法一PNR。新固件通过交付条件后按根AGENTS用 `scripts/fpga/program_flash.py` 显式指定完整.fs/SHA，确认VM关闭，执行外部SPI操作54@0、校验、Reprogram及真实断电重启。当前没有完成这些步骤，不以源码或综合通过代替固化完成。
