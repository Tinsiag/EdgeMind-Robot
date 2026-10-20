# MPU6050 / MPU6500 独立测试固件

新版本为 `A741-MPU6050-6500-IMU-TEST-MOTOR-LOCKED`。用户2026-10-20 21:06日志读到WHO_AM_I=112（0x70），旧包按MPU6050身份拒绝；新测试版本增加MPU6500专用分支。实际型号以诊断读数和配置校验为依据，不能只凭商品名称确认。主I2C启用，电机控制层拒绝ARM，四路顶层桥输出固定为0；ToF/LD06禁用。仅测试版本允许MPU6500，完整运动路径没有自动放开。

## 接线与边界

| 模块信号 | FPGA球号 | 本版行为 |
| --- | --- | --- |
| VCC / GND | 用户既有3.3 V / 公共地 | 用户报告VCC=3.3 V |
| SCL | L18 | 100 kHz主I2C，只拉低或释放 |
| SDA | M20 | 主I2C，只拉低或释放 |
| XDA / XCL | A1 / B2 | 仅输入，不驱动辅助总线 |
| AD0 | M17 | 仅输入，不驱动；用户测得3.2 V |
| INT | B1 | 输入预留；采样通过轮询INT_STATUS |

用户报告SCL/SDA空闲各3.3 V、AD0=3.2 V，测量时预期地址0x69；现场日志却报告address=104（0x68）。地址和身份是两项不同信息，现有日志不足以解释电压/地址差异，不要求用户因此盲目改线。驱动先试0x68，未响应或身份不支持时再试0x69；之后错误应稳定，样本应持续增加。MPU6050身份为0x68，MPU6500身份为0x70；均不把身份值当成I2C总线地址。

MPU6500新增ACCEL_CONFIG2（0x1D）=3并读回核对，使用相同±2 g、±2000°/s和100 Hz采样配置。温度采用该型号raw/333.87+21；MPU6050仍为raw/340+36.53。未知身份继续拒绝，不跳过校验。依据TDK InvenSense《MPU-6500 Register Map and Descriptions》RM-MPU-6500A-00及对应产品规范；没有启用磁力计、SPI或DMP。

六球号对应CSV的LVCMOS33，保留用户新用途，不按原摄像头网络名交换SCL/SDA。物理排针及Bank实际供电未由CSV测量证明；旧模块原理图已撤销，不作为上拉/下拉依据。不要改接5 V或主动拉低AD0。本测试仅使用已报告接线和电压，不把它升级为全部硬件已验收。

## 下载

1. 电机功率电源VM保持断开。改变接线前断电，确认没有其他I2C主机接在同一总线上。
2. 使用本次归档里的 `A741-MPU6050-6500-IMU-TEST-MOTOR-LOCKED.fs`，核对SHA256、目标GW5AT-LV60PG484AC1/I0及对应result.json。旧纯MPU6050测试包仍会拒绝身份0x70，旧P4禁用包不会采样。
3. 首次用SRAM下载，保留A740恢复包。本轮程序只生成文件，没有自动烧录或发送实板命令。
4. 下载后等待约2秒，再连接上位机。若timing_signed_off=false，本包仍属实验诊断候选，仅用于受监控的无电机静止测试；不能把异常数据排除为软件问题，也不要固化为运动版本。

## 图形上位机测试

使用仓库 `code/camera-car-control/a741/launch.cmd`，不要使用旧打包exe。电脑网卡192.168.0.3/24，FPGA192.168.0.2，千兆网线直连。UDP控制5000/5001，遥测6103，视频6102；不要同时打开多个占用这些端口的上位机。

1. 点击“连接”，连接状态应显示“IMU测试 · 电机锁定”。ToF和雷达无效为本版预期。
2. 点击“IMU诊断”。新上位机显示sensor_model、address_hex、who_am_i_hex；这块现场模块预期可读到MPU6500/0x70，总线地址接受0x68或0x69实际响应。ready和sample_valid应为true、fault为0、sample_sequence在两次查询间增加。无效时三轴和温度显示None，不能把默认零值当测量。
3. 静止观察角速度，手动绕模块Z轴缓慢转动，Z角速度应有响应，反转时符号相反。原始角速度含零偏，静止不要求严格为0。
4. 模块近似水平、完全静止，点击“静止校准”，约64个样本后应成功。无需填机械轮距，不要修改hardware_verified。近似水平检查使用加速度：平放时az约+1或-1 g，ax/ay接近0；幅值有偏差不在本轮自动判定精度。

   当前固件的具体条件为abs(ax)、abs(ay)<0.25 g，abs(az)约0.85～1.15 g。板面正放或倒扣水平都可满足该加速度检查，竖装/倾斜时不能靠校准变成支持任意安装。2026-10-20现场ax=0.778、ay=-0.172、az=-0.641 g、flat_install=false不满足条件；静止假设下约偏离水平51°。把PCB板面水平固定，再观察flat_install=true并校准。新上位机会具体提示姿态原因并保留连接，无需重刷固件或放宽阈值。
5. 校准后手动转动约90°，查看相对航向连续变化；跨±180°时数字回绕为预期。回到起始方向应大致回到原读数。外部角度与漂移尚无验收，不能把读数直接当±5°精度通过。
6. 停止后观察采样序号与错误计数，保存日志。点击任何运动按钮仍会拒绝，电机不会被本测试模式使能。

相对航向未校准时上位机显示“未校准”，但角速度仍可用于验证响应。MPU6050不含磁力计，此处不是绝对罗盘，也未启用DMP。

更新上位机源码后必须关闭旧窗口并重新启动launch.cmd，运行中的Python进程不会自动采用新代码。若诊断日志没有sensor_model、address_hex、who_am_i_hex，可能仍运行旧进程；不能直接用旧温度换算判断MPU6500芯片温度。

## 命令行记录

先关闭图形上位机，避免控制端口5001冲突。在仓库根目录执行：

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -X utf8 code/camera-car-control/a741/host/imu_test.py --seconds 30
```

保持模块静止水平，带校准再记录：

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -X utf8 code/camera-car-control/a741/host/imu_test.py --calibrate --seconds 30
```

工具只发送STOP、配置、查询和可选静止校准，不发送ARM/轮速命令。日志保存在 `a741/.local/imu-tests/*.jsonl`，包含地址、身份、识别型号、采样序号、错误、三轴加速度g、三轴角速度°/s、温度及状态。不同查询依次执行，合并最近值，不承诺严格同一采样时刻。只读key12=6050保留为既有驱动接口族标识，实际型号从key14中的WHO_AM_I识别，不能将key12当实物身份。

## 故障码

| fault | 含义 | 检查 |
| --- | --- | --- |
| 0 | 当前无驱动故障 | 仍需采样序号持续增长且sample_valid为true |
| 1 | I2C未应答、总线超时等传输错误 | SCL/SDA接反、共地、供电、地址、总线被拉低 |
| 2 | 身份不匹配 | 实际芯片、地址响应和读取数据 |
| 3 | 无新数据或数据超时 | 采样状态与数据就绪 |
| 4 | 配置回读不一致 | 总线可靠性、实际寄存器 |

没有接模块时应无效并重试，不得显示旧数据为当前有效。要做无模块对照，可断电后断开模块再重新上电观察，避免带电拔线。更改接线后重新下载/上电、静止校准；不要通过改软件有效标志掩盖故障。

## 构建和交付

```powershell
$py = 'code/camera-car-control/.venv/Scripts/python.exe'
& $py code/camera-car-control/a741/scripts/check.py
& $py code/camera-car-control/a741/scripts/build.py build --imu-test
& $py code/camera-car-control/a741/scripts/audit_imu.py
& $py code/camera-car-control/a741/scripts/archive.py --imu-test
```

工作产物独立在 `.local/gowin-imu-test/`，生成的CST/顶层在 `.local/platform-imu-test/`；不会覆盖旧诊断输出目录。归档保存位流、源码、参数、管脚表、时序、测试和哈希。完整报告以同目录result.json/a741.tr为准，生成位流不等于时序通过。
