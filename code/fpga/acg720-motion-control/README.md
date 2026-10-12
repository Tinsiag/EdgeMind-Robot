# ACG720 双轮运动控制工程

更新日期：2026-10-13。对应选题三基础任务 2：前进、后退、差速转向、定点旋转和编码器反馈闭环；PC 经 ACG720 板载 CH340E 的 Type-C 串口发送目标。

## 当前状态

本目录是**独立工程初版**，已经建立 RTL、Gowin 工程、约束、仿真和 Python CLI，尚未下载或进行实车闭环标定。以下验证是数字逻辑与构建证据，不能等同于完整任务验收；已发现的联调问题见末节。

| 项目 | 当前证据与边界 |
| --- | --- |
| FPGA | `GW5AT-LV60PG484AC1/I0`，GW5AT-60B，50 MHz |
| PWM / 调度 / 控制 | 20 kHz PWM，1 kHz 毫秒时基，100 Hz 采样与 PI 更新 |
| Gowin | V1.9.12 完成综合、P&R、位流生成；最后报告 Fmax 50.013 MHz，setup/hold 违例均为 0，最差 setup slack +0.005 ns，裕量很小 |
| ModelSim | 既有记录中六个测试输出 PASS；编码器、PI、UART 回环、协议解析、测速和顶层烟测。覆盖范围有限，PI 测试有端口位宽告警 |
| Python | 语法检查、完整帧编码/解析检查通过；实际 COM 口和运动期间遥测未验证 |
| 实物 | 未验证前后退、转向、旋转角度、断线停车、负载响应、电流或制动距离 |

`impl/`、本地仿真输出、Python 缓存和 `.gprj.user` 不提交。最后位流 User Code 配置为 `0xA720`，构建输出在 `impl/pnr/acg720_motion_control.fs`，**不是已经通过实车验收的固件**。

## 工程与硬件入口

| 路径 | 职责 |
| --- | --- |
| `acg720_motion_control.gprj` / `build.tcl` | 器件、显式编译清单、构建和 User Code |
| `rtl/motion_top.v` | UART 命令、参数、双轮控制及故障状态整合 |
| `rtl/uart_rx.v` / `uart_tx.v` / `motion_protocol.v` / `motion_status_tx.v` | 字节收发、CRC 帧解析和状态回复 |
| `rtl/quadrature_decoder.v` / `encoder_counter.v` / `wheel_speed_estimator.v` | AB 三级同步、四倍频、累计计数和测速 |
| `rtl/wheel_pi_controller.v` / `at8236_motor_driver.v` | 轮速 PI、斜坡、PWM 和桥方向切换 |
| `rtl/differential_drive.v` / `rotate_controller.v` | 差速目标、编码器旋转目标与完成判定 |
| `constraints/` / `tests/` | 全部引脚、20 ns 时钟约束和 testbench |
| [上位机说明](host/README.md) | 协议、参数 ID、CLI 和单位 |
| [实施与验收计划](MOTION-CONTROL-PLAN.md) | 剩余修复、标定及测试顺序 |

| 信号 | FPGA 球号 | 接线 |
| --- | --- | --- |
| `clk` / `stop_n` | Y18 / F15 | 50 MHz / S0，低有效 |
| `uart_rx` / `uart_tx` | J21 / M15 | 板载 CH340E；115200 8N1 |
| 左 IN1 / IN2 | A13 / A14 | P7-1/2 → L-1/2 |
| 左编码器 A / B | A15 / A16 | P7-3/4 ← L-7/8 |
| 右 IN1 / IN2 | F16 / E17 | P7-31/32 → R-5/6 |
| 右编码器 A / B | D20 / C20 | P7-33/34 ← R-2/1 |

IO 为 LVCMOS33，实物 Bank 电压及编码器高电平需为 3.3 V。电机 VM 独立供电并共地。AT8236 两 IN 接法为 `PWM,0` / `0,PWM`，停止为 `0,0` 滑行；不能复用 TB6612 的独立 PWM/STBY 接法。电源板 USB-C 是供电口，不能替代 CH340E 串口。

实际针序见 [ACG720 与现板接线](../../../doc/电机/ACG720与现有电源板接线_2026-10-10.md)，电机规格见 [电机资料核对](../../../doc/电机/拟用电机资料核对.md)。[开环测试工程](../acg720-motor-test/README.md)的 A712/A713 有实物反馈；本目录的初版没有沿用它们的实车通过结论。摄像头/DDR、IMU、ToF 和软核暂不集成。

## 构建与检查

从仓库根目录执行，按本机安装位置调整工具路径：

```powershell
cd code/fpga/acg720-motion-control
& 'F:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe' './build.tcl'
python host/serial_control.py scan
```

P&R 报告在 `impl/pnr/acg720_motion_control_tr_content.html` 和 `.rpt.txt`。检查实际球号、方向、3.3 V IO、20 ns 时钟、setup/hold 违例数；不能仅依据工具退出码判定时序通过。当前 false path 是外部异步输入约束，不代表已经完成 CDC 或上电复位验证。

已有 Icarus 脚本 `tests/run_iverilog.ps1` 依赖 PATH 中的 `iverilog`/`vvp`，只运行编码器、PI 和顶层三个测试。ModelSim 复现可在独立本地目录建立 `work`，显式列出 `.gprj` 中 RTL 和六个 testbench 编译，逐个 `vsim -c -do "run -all; quit -f"`；同时检查 PASS、fatal 和进程返回值。

## 单位和实现约定

- 累计计数：signed32、AB 四倍频。两侧前进应统一为正，但顶层目前把两个 `invert` 固定为 0，尚无串口方向参数。
- 速度：mm/s；10 ms 窗口。换算为 `abs(delta) × diameter_mm × 3142 / (CPR × sample_ms)`，32 拍整数除法后恢复符号；3142 近似 pi×1000。中间值最后截取 32 位，尚需溢出范围检查。
- PI：固定 `Kp=1`、每次更新 `Ki=1/16`；有积分限幅，尚未完成条件积分抗饱和。内部有 16 位截取及 signed 比较问题，不能把 32 位接口当成全范围保证。
- PWM：幅值以 1024 为满量程；默认 PI 限幅 1000，不等同于 100% PWM。`00` 只禁止桥输出，不能证明车体机械瞬停。
- 转向：协议传 int32 mrad/s，当前实现仅使用低 16 位；轮距也截取 16 位。偏置用 `/2048` 近似设计公式 `/2000`，存在约 2.34% 的比例偏差及符号运算待核对。
- 旋转：协议角度为毫度。参数 ID 6 虽名为 `counts_per_degree_q16`，实际是**每毫度计数 Q16**；理论比例 `round(wheel_base_mm × CPR × 65536 / (360000 × diameter_mm))`。这是对称轮组初始值，左右不一致和打滑需实测修正。完成门限为两轮误差 ≤4 counts，实测速度绝对值 <20 mm/s。

## 已知联调问题与交接优先级

以下来自 2026-10-13 源码核对，属于待修复项；此前“完成运动控制”的表述仅能解释为已建立实现初版。

1. `motion_status_tx` 的 start/busy 握手未等待上一字节请求被接受，存在跳字节问题；完整 35 字节 UART 回复尚无引脚级验收。Python 分包解析也会丢失独立收到的 `AA` 同步前缀。
2. `motion_protocol` 只检查 payload 长度上限和 CRC，未验证版本、各命令精确长度、序号重复、参数范围及半帧超时；`SET_PARAM` 未限制 DISARMED，也允许零值标记有效。7/8 是保留 ID，不实现 Kp/Ki 设置。
3. S0 直接作为异步复位，释放未同步；上电初值、异步输出禁止和复位恢复尚待验证。`HELLO` 改写状态但不解除 armed，状态显示可能与输出许可不一致。
4. 无脉冲超时从静止开始累计；静止后启动会继承超时。累计非法计数未被 `CLEAR_FAULT` 清除，故障可能立即再锁存；任一轮零目标时也可能触发全车反馈超时。
5. `STOP` 清 armed/目标，但未取消旋转状态机或待提交差速命令；重新 ARM 前必须保证旧动作被撤销。重复 `ROTATE` 会在完成后再次启动，且旋转期间参数仍读取可变 payload；CLI 目前每 50 ms 重发 ROTATE，不能当作只执行一次的旋转心跳。
6. `SET_WHEEL_SPEED` 未限速；16 位 PI 的负值比较、积分、停止输出和换向等待零速尚待测试。PWM duty 并非完整周期锁存，桥死区不等同于车轮已停住。
7. CLI 只有单次端口连接，没有交互 `connect`/重连；运动时不读状态和 CSV，Ctrl+C/异常也没有 finally STOP。电压测量、目标轮速遥测、碰撞联锁和堵转电流检测未实现。

先完成这些端到端修复与仿真，再开展架空单轮标定、闭环整定和落地四动作验收。时序通过只覆盖当前构建，修改源码/参数后必须重新 P&R。
