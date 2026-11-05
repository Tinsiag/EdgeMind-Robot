# A745 FPGA小车工程

摄像头、DDR、TFT、本地运动保护与4A视觉任务的活动源码。
当前实板及待验收项见[项目状态](../../../docs/project-status.md)。

## 使用

- [本地按键与三种模式](docs/README-MODES-AND-TARGET-74513.md)。
- [视频、NPU与部署](host/README-video.md)。
- [错误码和故障快照](../../../docs/troubleshooting.md)。

本地S1启停，S0复位；公共GND保留。
左轮LAIN1/2对应A18/A19，右轮RAIN1/2对应F13/F14。
模式3网络任务受本地会话及全部安全联锁约束，不能网络ARM。

## 源码

| 目录 | 内容 |
| --- | --- |
| `rtl/` | 顶层、视频、模式、导航、任务、显示与收发 |
| `lib/` | 传感器、编码器、姿态、CPU及执行器叶模块 |
| `vendor/` | 原厂板级IP及匹配参考模型 |
| `constraints/` | 活动引脚与时序约束 |
| `firmware/` | 片上监督程序与初始化数据 |
| `config/` | 几何、标定和接线依据 |
| `host/` | 4A视频/NPU/任务服务及主机工具 |
| `tests/` | RTL、协议、几何与真实回放测试 |

## 显示

TFT按800×480/33MHz扫描，HUD按480×272实拍安全区布置为32列。
AB22为DE，AB21为背光；摄像头使用P7 TY-OV5640自带晶振接法。
ED10最多八个绿色框在场消隐原子更新，过期清框；HUD在最上层。

| LED | 含义 |
| --- | --- |
| D0 | 系统/显示时钟锁定 |
| D1 | 摄像头初始化成功 |
| D2 | PHY初始化成功 |
| D3 | DDR就绪 |
| D4 | 至少一帧完整视频 |
| D5 | 摄像头/DDR错误 |
| D6 | 视频输入溢出 |
| D7 | 运动故障 |

## 构建与签核

命令由[开发指南](../../../docs/contributing.md)维护。
时钟、DDR和接口依据见[时序说明](docs/TIMING-CLOSURE.md)。
生成板级副本在 `.local/platform/`，当前主构建在 `.local/gowin-a745-autonomous/`。
[原始来源](REFERENCE-SOURCES.json)及 `vendor/board/ORIGIN.json` 保留。

主位流必须经过同源回归、原语模型、同次PNR/STA/SDF/PAD和最终门。
[固化工具](../../../scripts/fpga/README.md)完成外部Flash校验、重载和就绪检查。
生成位流或Flash就绪均不代表运动、实屏或真实冷启动已验收。
