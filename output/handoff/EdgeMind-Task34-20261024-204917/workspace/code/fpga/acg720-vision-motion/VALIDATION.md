# 实际验证记录 — 2026-10-18

本次实现只进行本机文件、仿真、Python 回归和**综合阶段**检查。未连接串口控制电机、未调用 Programmer、未生成板级位流、未写 SRAM/Flash。

## 已通过

| 检查 | 结果与覆盖 |
|---|---|
| 便携系统顶层展开 | Icarus 对 `vision_motion_top` 成功编译展开，无缺模块 |
| 新增 RTL 仿真 | 15 个 testbench：双时钟 FIFO/mailbox、RGB565 连续采集/预热/坏帧恢复、黑线提取与转向、PWM 周期锁存和换向空白、运动反馈及无反馈/反向故障、ToF 初始化/校准/状态/超时、I²C 波形/NACK/卡钟、停车仲裁、串口端到端协议、OSD与欠载恢复 |
| 视频端到端 | 小分辨率及 **800×480 两个完整帧**：真实模拟 DVP 字节输入，跨相机/UI/像素时钟，经 DDR 行为存储模型后逐像素比较；命令/写数据分别停顿，保护显示区、坏帧与待显示区 |
| 原运动 RTL | 原工程 14 个 testbench 回归通过，原 RTL 文件未修改 |
| Python 上位机 | 38 项，包括原27项和新增11项能力、格式、限速、取消、启动异常停车与旧固件兼容 |
| 构建依赖检查 | 6 项测试，覆盖缺清单、未核对示例、哈希过期、未知ToF和重复球号等 |
| 原接线静态检查 | 10 项通过 |
| GUI 检查 | 隐藏窗口实例化与控件状态；新能力关闭补偿、断开恢复旧设置，无串口打开 |
| Gowin 综合 | V1.9.12.04，GW5AT-60B，`run syn` 成功；输出网表及综合报告，源码哈希与最终 RTL 一致 |
| 板级构建保护 | 缺 `.local/platform/manifest.json` 时明确返回2；未生成板级工程或下载产物 |

最终综合便携逻辑资源：**8440 logic（6900 LUT＋1540 ALU）/59904，4882 registers/60780，10 BSRAM/118，0 latch**。这些不包含尚未恢复的 DDR PHY、PLL、相机初始化和 HDMI 物理层，不能当作整机最终资源预算或Fmax。

综合日志中唯一警告为 `NL0002`：组合配置 ROM 的模块层级在优化中被展开/消除；功能配置字节通过 ROM 哈希和 ToF 仿真检查，不能将层级消除直接解释为测距逻辑消失。未执行P&R，没有已验证的50MHz裕量。

## 证据和复现

原始日志、综合报告、源文件身份及运行清单位于 [verification/2026-10-18](verification/2026-10-18/manifest.json)。`rtl-results.json`包含源码和testbench的SHA256；综合结果明确 `pnr_run=false`、`bitstream_generated=false`、`hardware_tested=false`、`timing_signed_off=false`。测试过程中如文件发生变化，入口拒绝签发成功清单，须在稳定快照重新运行。

复现步骤见 README。可选综合检查：

```powershell
python -X utf8 -B code/fpga/acg720-vision-motion/scripts/synthesis_check.py --gowin C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe
python -X utf8 -B code/fpga/acg720-vision-motion/scripts/check_legacy_rtl.py --iverilog <iverilog.exe路径> --vvp <vvp.exe路径>
```

综合检查生成的 `.local/synthesis` 仅用于资源可行性，不调用布局布线和位流生成，不得用于下载。Icarus仿真使用行为DDR和事务级ToF传感器模型；I²C电气时序另由独立RTL测试检查，不代表传感器实测。

## 尚待完成的硬件环节

- 恢复原厂视频IP和相机初始化表，实现并核对物理包装层和全部管脚/Bank/电源；确认ToF模块接口。
- 完整综合、P&R、CDC和reset recovery审查；使用官方DDR PHY约束解决时序问题。
- 架空方向/闭环/STOP/失联/堵转验证；ToF距离、摄像头视野和黑白阈值标定。
- 三圈循线、十次障碍停车及至少100mm余量、人工重启、30分钟实景显示及冷启动测试。

上述不以本次仿真替代。首版不声称通过完整赛题验收或提供单颗前向ToF之外的环境覆盖。
