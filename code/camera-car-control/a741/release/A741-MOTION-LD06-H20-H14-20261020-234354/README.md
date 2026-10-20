# A741 运动+LD06+二维建图实验构建，不能用于运动验收

运动+LD06：雷达CTL H20/DATA H14，电机硬锁解除；无ToF保护。建图在电脑运行，无自主导航。详见docs/MOTION-LIDAR-MAPPING.md。没有烧录/实车验收。
timing_signed_off=false，即使位流生成也不表示时序/实板通过。
此目录为审计快照；上位机请从仓库 code/camera-car-control/a741/launch.cmd 启动。重建时按 sources/ 内的仓库相对路径恢复，原厂 IP 按 provenance 指定 ZIP 导入。
报告以 result.json 和 a741.tr 为准；ACCEPTANCE-PENDING.md 均待实测。

详细接线、下载、上位机、标定和注意事项见 [固件使用说明](docs/FIRMWARE-GUIDE.md)。

位流 SHA256: 1993d3aee9757efd8d29849a9c2c44910f76f8fa1f80de1f23d78ceb1ce83a01
RTL 组数: 21；Python 测试: 26。
