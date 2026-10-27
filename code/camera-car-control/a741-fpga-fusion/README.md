# EdgeMind 基础摄像头 / 姿态 / 避障工程

2026-10-28 暂停交接：以根 [HANDOFF-20261028.md](../../../HANDOFF-20261028.md) 和 [NEXT-AI-PROMPT-20261028.md](../../../NEXT-AI-PROMPT-20261028.md) 为当前入口。800 屏锁电机位流已恢复视频/文字；运动版三次 PNR 失败，未生成位流。用户要求当前只打包和上传 GitHub，以下命令仅供日后明确恢复后使用。

活动现场为本目录，器件 ACG720 / GW5AT-LV60PG484AC1/I0，工具 Gowin V1.9.12.04。用户已恢复完整实现，并于2026-10-28明确切换到官方800×480/33MHz。当前入口见根 [TFT800-20261028.md](../../../TFT800-20261028.md)。新候选需单独完成时序与实板验证；旧HANDOFF、480位流及其烧录记录均为历史证据。

## 当前功能

- OV5640 输出 800×480 RGB565，经 DDR3 完整帧双缓冲显示到原 J1 TFT。
- MPU6050/6500 采样：共享迭代 CORDIC 估计加速度横滚/俯仰，陀螺积分提供偏航，四行文字叠加在视频上。横滚/俯仰与偏航分别判断有效性。
- LD06 在 FPGA 内执行基础避障，保留编码器反馈、轮速 PI、PWM、ARM/STOP、失联与故障停车；PicoRV32 运行裸机监督程序。
- 网口仅设置、遥测与调试。电脑不计算避障。HDMI、网口视频、地图、A*、定位匹配、航点、手动转角与航向保持均已移除。

横滚/俯仰会受线加速度影响，偏航会漂移；不是完整 AHRS 或绝对航向。雷达阈值是扇区距离，不是车壳净空；速度是控制目标，不是实测车速。

## 接线与屏幕时序

沿用原摄像头、DDR3、IMU、LD06、电机、RJ45 和 J1 接线。官方首选参考为用户指定的`fpga/小梅哥ACG720国产高云FPGA教学开发板资料/02_例程源码/GW5AT60K`第28章，以及配套新版TFT_V3.0手册。用户指定800×480/33MHz；实测95×55mm接近新版4.3寸800屏，但尺寸不能独立确认型号。旧480参考保留作回归历史，当前构建仅生成800版本。

| 接口 | FPGA 球号 |
| --- | --- |
| TFT PCLK / DE / HS / VS / BL | AB20 / AB22 / V19 / Y19 / AB21 |
| TFT R[4:0] | N14 P16 R17 N15 L6 |
| TFT G[5:0] | T18 N17 P17 P15 R16 N13 |
| TFT B[4:0] | U17 U18 P14 R14 R18 |
| IMU SCL / SDA | L18 / M20 |
| LD06 CTL / DATA | H20 / H14 |

固定33 MHz PLL、50%占空比，1056×525扫描。采用官方扫描范围`[215,1015)×[34,514)`，输出整体延迟两像素与文字流水线对齐；RGB/DE在PCLK下降沿更新，按新版面板上升沿采样，硬件以ODDR转发时钟。默认12帧约201.6ms后背光常亮。50MHz控制逻辑与33MHz显示使用完整快照握手跨域。ToF未接入，兼容遥测字段保持无效。

## 调试与停止

`launch.cmd` 启动调试面板，`launch.cmd --sensors-only` 禁止 ARM 和运动。电脑地址192.168.0.3，FPGA192.168.0.2；控制UDP5000/5001，遥测6103。没有6102视频和6104地图入口。

连接先STOP、核对能力和配置，不自动校准、ARM或启动。按需启动雷达、静止校准，再显式ARM、显式启动避障。停止清除待执行动作并发送STOP和DISARM。连接失败关闭控制与遥测接收；旧状态显示过期，不能当作硬件当前状态。界面停止响应时工作线程结束控制会话，FPGA租期继续提供独立失联保护。

避障扇区按已确认的270°安装偏移及顺时针方向转换到车体朝向，网口原始点云角度保持不变。前方>900 mm目标120 mm/s，450～900 mm为60 mm/s，≤450 mm选更宽且≥500 mm的一侧，以±80 mm/s转向；前方≥600 mm结束转向。雷达无效、两侧堵塞或所选侧受阻立即给零目标。失联、掉ARM、CPU/电机故障结束本次控制，恢复信号不会自动重启。重复启动不会重置正在进行的转向。

原始左右轮速命令0x11仅供调试，不能抢占避障。旧0x42/0x45/0x47转角和航向控制已从接收协议与计算模块删除。CPU、停止、编码器、IMU和雷达保护不因精简而放宽。

## 当前离线流程

从本目录运行，禁止使用命中商店占位符的裸 `python`：

```powershell
& ../.venv/Scripts/python.exe -X utf8 -u scripts/check.py --wsl Ubuntu-26.04
& ../.venv/Scripts/python.exe -X utf8 scripts/build.py prepare --fusion --tft800 --screen-test --display-diagnostic --route-option 1 --place-option 1
& ../.venv/Scripts/python.exe -X utf8 scripts/build.py build --fusion --tft800 --screen-test --display-diagnostic --route-option 1 --place-option 1 --timeout 1800
```

`--fusion/--tft800` 只生成当前基础功能，旧`--tft480`不再接受。上述诊断输出在 `.local/platform-basic-tft800-screen-test-diagnostic` 和 `.local/gowin-basic-tft800-screen-test-diagnostic`。`screen-test` 将四个电机物理输出硬接GND；`display-diagnostic`强制要求该锁，启动五色后恢复视频/文字。普通构建没有这项物理锁，不属于试屏候选的运动签核范围。

布局算法1、布线算法1、时序驱动和hold修复显式保留。`build-timeline.jsonl` 记录日志接收时刻（可能受工具输出缓冲影响）；`scripts/report_resources.py` 提取层级资源、DSP原语、关键路径与连接数量，并保留源码/报告SHA。综合结果不提供实际CLS时写null，不能用LUT/2推算CLS。旧 `.local/gowin-fusion*` 属于历史版本。

CAD参数核对与实物验证分开：`navigation_geometry_verified=true`、`physical_geometry_verified=false`。本轮离线验证不代表上车签核；最终布线时序、实物显示、完整Flash固化和真正断电保持须分别验收。
