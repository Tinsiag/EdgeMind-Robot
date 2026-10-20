# A741 交付索引

仓库选定交付为 [A741-MOTION-LD06-H20-H14-20261020-234354](A741-MOTION-LD06-H20-H14-20261020-234354/README.md)，源码、固件、参数、测试、报告与SHA-256一起保存；其余早期诊断或重复构建包保留本机，未全部发布。旧A740包独立保留。

| 项目 | 当前值 |
| --- | --- |
| 固件 | [A741-MOTION-LD06-H20-H14.fs](A741-MOTION-LD06-H20-H14-20261020-234354/A741-MOTION-LD06-H20-H14.fs) |
| 位流 SHA-256 | `1993d3aee9757efd8d29849a9c2c44910f76f8fa1f80de1f23d78ceb1ce83a01` |
| 接口 | MPU6050/MPU6500兼容采样；LD06 CTL H20 / DATA H14；电机硬锁解除，保留运行联锁 |
| 电脑端 | 摄像头、雷达、里程遥测、CoreSLAM局部二维地图与导出 |
| ToF | 未接入、无球号绑定，无前向测距停车保护 |
| 验证 | 21组RTL/26项Python通过；静态引脚/输出审计通过 |
| 实板 | 本交付没有烧录，电气/雷达/地图/运动/30分钟并发未验收 |
| 时序 | `timing_signed_off=false`；setup/hold端点70/25，主时钟Fmax48.959 MHz低于50 MHz目标 |

生成位流不代表运动可验收；H14/USB_PA3复用隔离还需检查。不能把串口雷达GUI的纸板实测作为这个FPGA变体的通过证据。详细问题见[构建报告](../verification/MOTION-LIDAR-MAPPING-20261020.md)，操作见[建图说明](../docs/MOTION-LIDAR-MAPPING.md)。

该包为不可变快照，使用当前仓库 `../launch.cmd` 启动上位机。重建需本机原厂ZIP/加密IP及Gowin工具链，依赖版本和哈希见包内provenance；这些厂商原始文件未重分发。LGPL地图内核源码、许可及接口适配器随包提供。
