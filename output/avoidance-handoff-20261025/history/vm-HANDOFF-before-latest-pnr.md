# EdgeMind-Robot 交接（2026-10-25）

## 当前工作区

- Linux 虚拟机 SSH：`smallcoral@192.168.126.131`
- 项目：`/home/smallcoral/Dev/EdgeMind-Robot-main`
- Git 基线：`6a32a56`，分支 `main`
- 当前工作区有未提交源码、固件、报告和连续导航诊断输出；不要执行 `git reset`、清理或覆盖这些修改。

## 已完成验证

- RTL：**56 组通过**。
- Python/主机：**61 项通过**。
- Flash 工具离线测试：**9 项通过**。
- GUI 布局检查通过。
- 连续障碍导航通过：最终位置约 `(1476.08, -25.49)`，`replans=1`、`rotation_clear=1`、`blocked=0`，完成定位恢复并到达目标。结果见 `output/task34-recheck-20261025/continuous-navigation/reproduced-by-next-ai-with-trace/result.json` 和 `run.log`。这是合成理想运动模型仿真，不是实车验收。

## PNR 结果

按用户指定的算法一执行：

```text
route_option=1
place_option=1
correct_hold=1
timing=enabled
```

综合阶段完成，`clk` 综合估算约 `50.540 MHz / 50 MHz`。PNR 在 `3600.0716 s` 超时，日志停在 `Routing Phase 0 completed`。

- `.local/gowin-fusion-tft480/result.json`：`run_state=failed`、`mode=pnr`、`timed_out=true`、`compile_passed=false`
- `.local/gowin-fusion-tft480/impl/pnr/a741.log`：PNR 日志
- 当前无可交付 `.fs`
- 当前无最终 `.tr`
- `timing_signed_off=false`
- `hardware_programmed=false`

综合估算不等于整板 STA；本轮没有整板时序签核。

## 硬件边界

本轮未烧录、未上电、未 ARM、未驱动电机，未验证实物 RGB 屏、传感器录制回放或断电重启。`physical_geometry_verified=false`。原始 `A741-MOTION-LD06-H20-H14-20261022-130843` 位流归档缺失，不能宣称已恢复原基线。

Linux Gowin IDE/Programmer 已安装在 `/home/smallcoral/tools/IDE` 和 `/home/smallcoral/tools/Programmer`，许可证已配置；CoreSLAM 库已生成到 `code/camera-car-control/a741-fpga-fusion/.local/mapping/edgemind_slam.so`。工具就绪不代表位流或硬件验收完成。

## 后续规则

如继续工作，保持算法一和布局一，保持时序驱动、hold 修复和时钟检查；不要切换算法二来掩盖超时，不要在未核对输入哈希时复用旧网表，不要烧录旧 `.fs`。若需要给小车上电，必须先提醒用户并确认电机 VM 已关闭。
