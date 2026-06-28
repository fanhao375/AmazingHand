# Amazing Hand 总览（中文翻译）

> 来源：`docs/AmazingHand_Overview.pdf`（Pollen Robotics SAS，法国波尔多）
> 共 6 页。

---

## 第 1 页：封面

**Amazing Hand**
- 4 根手指（4 fingers）
- 8 自由度（8 dofs）
- 可 3D 打印（3D printable）
- 开源（Open source）

Pollen Robotics SAS，法国波尔多

---

## 第 2 页：手指机构（Finger mechanism）

- 每根手指有 **2 个指节**（2 phalanxes）
- 每根手指由 **2 个电机并联驱动**（2 motors per finger acting in parallel）
- 可实现**屈伸（Flexion/Extension）** 与 **外展/内收（Abduction/Adduction）**
- 通过机械连杆把 2 个指节联动折叠（Mechanical link to fold 2 phalanxes together）
- 采用球头连接拉杆（Ball joint connecting rods）
- 指节外包裹软壳（Soft shells covering phalanxes）
- 可 3D 打印

**并联机构（Parallel mechanism）工作原理：**
- 两个电机（Motor A、Motor B）**同向**转动时 → 产生**屈伸**（Flexion/Extension）
- 两个电机**反向**转动时 → 产生**外展/内收**（Abduction/Adduction）

**关键部件标注：**
- 外展/内收轴（Abduction/Adduction axis）
- 屈伸轴（Flexion/Extension axis）
- 传动连杆（Transmission link）
- 带球头的连接拉杆（Connecting rods with ball joint）
- 软壳（Soft shells）

---

## 第 3 页：整手设计（Hand design）

- 4 根完全相同的手指 + 自定义塑料件
- 拇指可与食指对置（Thumb opposable with Index finger）
- 软质手掌（Soft palm，与手指软壳同种材料）
- 手腕接口适配 Reachy2（Wrist interface suitable for Reachy2）

---

## 第 4 页：技术细节（Technical details）

**运动范围：**
- 单指屈伸：约 **86°**（近节）+ **80°**（远节）
- 手指外展/内收：**-20° ~ +20°**
- 手指间张开角：**6°** / **13.5°**
- 拇指方向：**20°**

**整手尺寸：**
- 高（手指张开）：**195 mm**
- 宽（手掌处）：**105 mm**
- 厚/侧向尺寸：**120 mm**
- 对角（指尖到腕）：**180 mm**

---

## 第 5 页：可实现的部分手势（Some of possible patterns）

可摆出多种手势/姿态，例如各种数字、剪刀手、指向等，……以及更多。

---

## 第 6 页：规格参数（Specifications）

- 8× 智能舵机（Feetech SCS0009）
- 直流供电 5V / 最大电流 3A
- 重量：**400g**
- 负载：最高 **1Kg**
- 适合 3D 打印
- 完全开源
- BOM 成本 **<200€**（装配耗时 5~6 小时）

**易于扩展/改造：**
- 增加第 5 根手指（但会增加整体宽度）
- 让每根手指做成不同长度
- 改变手指的位置
- 增加指尖传感器（取决于具体传感器）
- 更换手腕接口
