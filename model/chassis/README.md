# 当前底盘装配

打开 [V5 完整装配说明](v5-rgb-touch-display/README.md)。主要文件为EdgeMind_Chassis.FCStd、EdgeMind_Assembly.step、ThirdDeck.stl及查看模型.html。

V5的build_model.py读取v4-lidar-imu/EdgeMind_Chassis.FCStd和verification.json；export_model.py读取该目录preview-meshes.json。parameters.json和EdgeMind_Assembly.step还用于当前FPGA导航几何来源核对。这五个文件必须保留。查看器使用V5自己的vendor目录和本目录viewer_template.html，无须V1目录。

旧版本整包和根目录历史生成脚本列入清理清单；强制清理已经执行。不要将旧装配当作新版本交付。
