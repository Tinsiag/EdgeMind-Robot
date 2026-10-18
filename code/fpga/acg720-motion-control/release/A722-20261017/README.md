# A722：内置标定参数，屏蔽非法AB跳变停车

2026-10-17 按用户要求编译。只屏蔽此前faults=2所对应的编码器非法AB跳变停车；合法AB四倍频计数、测速和PI继续运行，非法转换不产生计数。STOP/DISARM、S0、250ms默认命令TTL及约200ms无反馈故障保持。反馈异常未被修复，计数、测速和角度可能受影响。

## 固件

- `acg720_motion_ready.fs`，User Code `0x0000A722`。
- SHA256：`1177884b8144b666b765b4564e2a7eb75523655661aa635a129864717c2fa963`。
- GW5AT-60B / GW5AT-LV60PG484AC1/I0。Gowin V1.9.12.04构建完成于2026-10-17 23:04:04（Asia/Shanghai）。
- 20实际端口球号/方向/LVCMOS33及User Code检查通过，50MHz setup/hold违例0/0，Fmax51.315MHz。源码哈希见`build-audit.json`，PNR日志见`build-pnr.log`。
- 18项Python及10项静态接线回归通过。本机未找到RTL仿真器，本轮未执行RTL仿真。综合网表D4输出接GND，与屏蔽bit1一致；不作为运动性能验证。
- 本次未下载、未写Flash、未操作VM或串口运动；尚无A722实板结果。

## 复位默认配置

| 参数 | A722值 |
|---|---|
| PWM | 1kHz |
| PI输出上限 | 512/1024，50% |
| 目标斜坡 | 每10ms最多变化50mm/s |
| 左/右CPR | 1469/1471 |
| 左/右轮径 | 66/66整数mm（原始实测66.3mm） |
| 中心轮距 | 121整数mm（原始实测121.4mm） |
| 差速最大轮速 | 400mm/s |
| 每毫度计数Q16 | 491 |
| 上电/复位状态 | DISARMED，目标0，PWM0；机械参数已有效 |

不用逐条set-param即可ARM。50%为默认PI限幅，仍可用参数9改写；直接轮速命令仍未独立实施最大轮速限制。400mm/s是已起动左轮测试时的目标，不是固定输出或最低起动速度。低目标可能仍不足以起动。

源码入口：`rtl/motion_ready_top.v`、`acg720_motion_ready.gprj`、`build_ready.tcl`。共用motion_top参数默认值保留旧行为，仅A722包装顶层开启标定默认值并关闭非法AB故障。

## 上位机使用（COM4为当前用户端口）

VM物理断开、车轮架空，选择SRAM Program下载；独立回读A722。先保持VM断开执行：

```bat
python host/serial_control.py --port COM4 status
python host/serial_control.py --port COM4 arm
python host/serial_control.py --port COM4 status
```

最后应为state=1、faults=0、PWM=0。保持架空、接通VM后可执行双轮1秒测试：

```bat
python host/serial_control.py --port COM4 --duration 1 forward 400
python host/serial_control.py --port COM4 status
```

运动命令结束或异常时CLI尝试STOP，STOP同时DISARM；每次下一个运动命令前需再次arm。运动停止是滑行，串口断开时STOP可能不能送达，依赖TTL并可物理断VM。异常时不自动恢复运动。后退接口为`backward 400`，转向/旋转接口沿用host/README.md；本轮尚未验证其物理方向或精度。

如果运行过startup_test.py，它会在收尾将输出上限设0；继续使用普通CLI前须在停止状态恢复`set-param 9 512`，或VM断开时按S0恢复本版默认参数。普通forward/backward不会自动恢复被运行时命令修改的参数。下载后不上电自转；掉电丢失SRAM，仍须重新确认固件。
