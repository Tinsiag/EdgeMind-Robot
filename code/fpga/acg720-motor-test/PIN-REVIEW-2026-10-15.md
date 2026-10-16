# 2026-10-15 新接线与 A71A 输出代码复核

结论：未发现当前 A71A 源码、引脚约束、综合输出连接和实际布线报告中的选脚、方向、A/B 通道或遗漏使能错误。没有因此修改 RTL/CST，也没有重新烧录或试转。这个结论不证明实板焊接、模块插接、GPIO 实际电压或驱动模块工作正常。

## 四根控制输出逐段对应

P7 按用户确认的 FPGA 正面朝上、USB 左上，从靠 USB 第一对金属针起数列；上排靠板边、下排靠芯片。六根彩线排为 R，四根线排为 L。

| 操作 / 端口 | FPGA 位置 | 球号 | 底板接口 | 原电源板原理图中的模块端 |
| --- | --- | --- | --- | --- |
| S1 / left_in1 | 第3列下，P7-5 | A18 | L-1 / LAIN1 | U3-3，AIN1 |
| left_in2，恒低 | 第3列上，P7-6 | A19 | L-2 / LAIN2 | U3-4，AIN2 |
| S2 / right_in1 | 第4列下，P7-7 | F13 | R-5 / RAIN1 | U6-3，AIN1 |
| right_in2，恒低 | 第4列上，P7-8 | F14 | R-6 / RAIN2 | U6-4，AIN2 |

R-1/2 是编码器 B/A，仍接 P7-10/9=E14/E13，作为输入；L-7/8 接 P7-3/4=A15/A16，作为输入。程序没有将这四个编码器 IO 配置为电机控制输出。

原电源板原理图的输出路径：左 U2-2/1=LAOUT1/2 到左电机六针座 6/1；右 U4-2/1=RAOUT1/2 到右电机六针座 6/1。控制和电机座均使用 A 通道。未用 B 输入为 L-3/4、R-7/8，不替代 A 输入。这里核对的是图纸，不把旧 KiCad 排列问题套用到用户现板。

## 输出逻辑和构建证据

`raw_keys={~right_key_n,~left_key_n}`，单独 S2 为 `2'b10`。初始化和释放去抖完成、S0 松开后，S2 使 `right_in1=1`、`right_in2=0`，最长 2 秒；松键、S0、双键立即撤销。按 AT8236 原厂真值表，10 对应 OUT1=H、OUT2=L，不需要 TB6612 式独立 PWM/STBY 引脚。

实际综合网表 `impl/gwsynthesis/acg720_bridge_probe.vg` 中：

```verilog
OBUF right_in1_obuf (.O(right_in1), .I(led_d[2]));
OBUF led_2_obuf     (.O(led[2]),    .I(led_d[2]));
OBUF right_in2_obuf (.O(right_in2), .I(GND));
```

D2 与 right_in1 的两个输出缓冲器共享内部信号，故没有“只亮 D2、忘了给 F13 使能”的逻辑缺口。不同物理 IO 的实际电压仍可能受 IO 供电、外部钳位、接触或硬件损坏影响，内部共享不能代替测量。

原厂 P7 图第11页与管脚表重新核对；8根信号与 CST、实际 PNR 报告的球号和方向一致。A71A 原位流 SHA256 为 `B8D3DE04C7500B1B90E066FCEBB27C489F2C10F88401ACA3A18284EBD088DD32`，所有构建源码哈希及 PNR 报告与既有归档完全一致；原已审查21端口、50MHz setup/hold违例0/0。本次重新运行 A71A 两项仿真及静态引脚回归10项，均通过，没有改动原归档日志。

本轮只读回读 operation_index=73，默认2.5MHz及1.5MHz各一次均以错误码50退出，没有返回 User Code，不能声称本轮重新确认了板上版本。最后成功回读仍为此前 A71A；未复位或重新下载。

## 当前未解决的部分

用户确认两个电机已拔下，D2亮约2秒时模块AOUT仍0V；这是已收到的输出异常。此前AIN1=1.6V、AIN2约0V是在VM断开、A71B的PWM条件下得到，不能充当VM接通、A71A恒定使能时的实际输入电压证据。模块本体和底板对输出的影响尚未分离验证，因此不能从软件复核直接定为模块损坏，也不能把问题报告成已修复。

核对证据：`verification/2026-10-15/confirmed-wiring-code-review-20261015.json`，含原厂表、图纸、CST、网表、PNR报告哈希。复核脚本为 `output/fpga-diagnostics/pin-review-20261015/review_pinmap.py`。

一手资料：本机 ACG720-138&60K 通用原理图及管脚表；用户原电源板 `C:/Users/sc/Downloads/2/SCH_Schematic1_2026-10-09.pdf`；用户 AT8236 模块接口图 `doc/电机/2.png`；[AT8236-S409-V1.1 第2～5页](https://datasheet.lcsc.com/datasheet/pdf/d8c76808c9e9a8c1969b3dbfc127e078.pdf?productCode=C2827823)。
