# 当前机械设计

主要入口为 [V5 屏幕/传感器装配](chassis/v5-rgb-touch-display/README.md)，包括完整FreeCAD装配、STEP、第三层板STL与孔位图、离线查看器及重建/验证脚本。

`hardware/` 保留板卡、电机和电源板原始机械资料。`chassis/v4-lidar-imu/` 中的基础装配、网格缓存、参数、核验数据和STEP仍是V5重建及导航几何来源；这些必要输入不是待删除备份。导航包络的准确来源SHA见A745的config/geometry.json，原几何没有在本次清理准备中修改。

V1/V2/V3的完整旧版本、重复导出、归档ZIP及CAD自动备份已列入用户要求的清理清单。已执行强制清理，结果见根目录PROJECT-CLEANUP.md。

装配中的屏幕安装孔位、接口和部分板卡高度仍包含试摆参考，制作依据以V5说明与实际测量为准。厂商原始模型及Three.js许可保持原样。
