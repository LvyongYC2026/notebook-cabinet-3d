# 单仓精细结构模型

本模型以原方案 PDF 第 5 页的单仓场景和本轮文字要求为主要依据。新的红框标注图片未附，因此没有宣称逐像素还原该标注图。

默认主体尺寸为 **宽 450 × 深 650 × 高 450 mm**，属于本次单仓设计假设。模型包含白色喷塑钣金壳体、1.5 mm 折板空腔门框、6 mm 透明玻璃、左侧铰链、黑色嵌入拉手和锁、白色抽拉托盘、银色无品牌笔记本、左侧统一接口面板、独立网孔适配器篮、分槽线束、暖白 LED 和后上部三行贯通散热孔。

## 文件

- `build_smart_cabinet.py`：参数化建模、动画、GLB 导出和 Cycles 渲染脚本。
- `smart_cabinet_single_compartment.blend`：可编辑工程，默认第 65 帧、开门 100°、主相机视角，已关闭视图辅助叠加。
- `smart_cabinet_single_compartment.glb`：闭门、托盘回位的模型，包含层级、部件自定义属性和线束形态键，不包含摄影棚、相机或灯光。
- `render_front_open.png`：开门主视图。
- `render_internal_detail.png`：内部接口、托架和线束细节。
- `render_front_view.png`：正面视图。
- `render_door_closed.png`：关门外观。
- `model_metadata.json`：实际配置、部件参数与来源、交互节点和线束路径。
- `validation.json`：数量、几何范围、线束曲率与长度采样、渲染设置及验证限制。
- `clearance_audit.json`：独立的九姿态三角网格 BVH 干涉检查记录。
- `handle_aperture_audit.json`：闭门拉手开孔、凹槽及状态灯的外侧射线检查记录。
- `validate_geometry.py / validate_glb.py`：可复跑的只读几何与 GLB 完整性检查脚本；另附 `glb_audit.json`、`configuration_test.json` 检查记录。
- `configuration_example.json`：已运行过的尺寸修改示例；不是另一套制造定版方案。

四幅正式图均为 **2560 × 1440、Cycles、96 samples**。内部灯为暖白，摄影棚为浅灰。

## 本机执行

本次实际使用 **Blender 5.2.3 LTS**。建议使用同版或兼容的 Blender 5.2 系列；其他版本未逐一验证。

先在终端 `cd` 到本交付目录（即包含 `build_smart_cabinet.py` 的目录），再运行完整构建、导出和四幅正式渲染：

```bash
'/Applications/Blender.app/Contents/MacOS/Blender' --background --python-exit-code 1 --python build_smart_cabinet.py
```

只构建模型与 GLB，不渲染：

```bash
'/Applications/Blender.app/Contents/MacOS/Blender' --background --python-exit-code 1 --python build_smart_cabinet.py -- --build-only
```

先渲染 1280 × 720、24 samples 小图：

```bash
'/Applications/Blender.app/Contents/MacOS/Blender' --background --python-exit-code 1 --python build_smart_cabinet.py -- --preview
```

使用 JSON 参数覆盖并写入独立目录：

```bash
'/Applications/Blender.app/Contents/MacOS/Blender' --background --python-exit-code 1 --python build_smart_cabinet.py -- --config configuration_example.json --output configured_model --build-only
```

Windows/Linux 可将可执行文件路径换成本机 `blender`。脚本只依赖 Blender 自带的 `bpy`；优先尝试 Metal，无法使用时回退。`font_path` 可指定本机字体，文件不存在或填空字符串时使用 Blender 默认字体，不要求其他平台存在 macOS 字体路径。

## 参数与模型编辑

参数集中在脚本顶部的 `P` 字典，也可通过 `--config` 覆盖已知键。所有长度以毫米输入；Blender 内部使用米。

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `width_mm / depth_mm / height_mm` | 450 / 650 / 450 | 主体宽深高；门、后板、折边与相对安装位置随之变化 |
| `sheet_mm / glass_mm` | 1.5 / 6 | 钣金与玻璃厚度 |
| `door_degrees` | 100 | 左铰链开门角度 |
| `tray_mm` | [396, 470, 2] | 白色托板宽、深、厚 |
| `tray_travel_mm` | 320 | 抽拉行程，当前线束方案支持至 320 |
| `laptop_mm` | [320, 225, 18] | 笔记本底座宽、深、高，不是开盖包络 |
| `laptop_opening_degrees` | 105 | 开盖角度 |
| `laptop_lid_height_mm` | 204 | 屏幕盖高度 |
| `laptop_center_xy_mm` | [25, -75] | 笔记本安装中心；未覆盖时随柜深保持前侧位置 |
| `interface_panel_mm` | [4.5, 168, 250] | 面板 X 向厚度、Y 向沿柜深宽度、Z 向高度 |
| `interface_panel_center_mm` | [-216.5, -100, 254] | 面板中心；未覆盖时随柜体边界推导 |
| `rj45_body_mm / ac_socket_mm / adapter_mm` | [14,26,24] / [16,35,42] / [48,80,90] | 相应器件本体占位尺寸 |
| `led_center_mm` | [0, -245, 432] | 顶部 LED 中心；未覆盖时随柜体边界推导 |
| `cable_bend_radius_mm` | 28 | 低位活动 U 弯设计半径，非线材厂家认证值 |
| `resolution / cycles_samples` | [2560,1440] / 96 | 正式渲染设置 |

脚本会拒绝未知参数、部分非法尺寸和明显不足的侧边间隙。已实际运行示例：480 × 680 × 480 主体、400 × 480 托板、300 行程、310 × 220 电脑、110° 开盖及 170 × 260 接口板。参数修改后仍须重新检查插拔、装配及运动空间；程序接受某组参数不代表制造或全部工况已通过验证。

各主要零件保持独立。Collection 严格分为：`Cabinet_Main`、`Cabinet_Door`、`Glass_Panel`、`Door_Hinges`、`Lock_System`、`Laptop`、`Laptop_Tray`、`Power_Module`、`Network_Module`、`Cable_Management`、`LED_Lighting`、`Ventilation`、`Camera_Lights`。

## 动画与网页层级契约

Blender 为 Z 向上、前方 −Y；GLB 为 Y 向上、前方 +Z。

- `SingleCabinetRoot`：模型根节点。
- `SingleDoorPivot`：Blender 绕 Z / GLB 绕 Y 转到 −100°。
- `SingleTray`：Blender 沿 −Y / GLB 沿 +Z 抽出 0.32 m。
- `Laptop`：父级为 `SingleTray`，电脑与插头随托盘移动。
- 第 1 帧关闭；第 65 帧开门；第 110 帧开门且抽出托盘；第 180 帧关闭。

两条活动线为 `SingleDynamicCable_network` 和 `SingleDynamicCable_power`，原生形态键均名为 `TrayExtended320mm`。网页中让其权重随实际行程比例从 0 变为 1，即可使用同一条受控 U 形路线；不要再额外叠加一套悬空高弧线。`.blend` 内已用驱动器关联托盘位置，无须启用外部 Python 自动运行。

固定 AC 线接适配器，活动 DC 线接笔记本；网络线独立布置。活动线固定端不随托盘移动，U 弯前移约半行程，移动端跟随全行程。`model_metadata.json` 的 `cable_paths` 提供闭合/展开引导点、固定/移动端、半径、颜色、原网格名称及形态键名称。主要 Mesh 保留 `component_key`、`dimensions_mm` 和 `basis` 自定义属性。

## 验证范围

默认闭态主壳体为 450 × 650 × 450 mm；全组件范围的微小前凸来自标识字面，准确顶点范围记录在 `validation.json`。

右竖框的拉手具有 12 × 77 mm 真实开孔，黑色独立凹盒与抓握边位于孔内，凹深约 12.5 mm；状态灯穿过独立 6 × 6 mm 安装孔。六条外侧射线检查确认孔内可见凹盒、抓握边及指示灯，孔边仍命中金属框。这是模型可见性与孔洞检查，不代表抓握人体工学或门锁性能认证。

两条活动线分别在 0、80、160、240、320 mm 行程采样，长度保持一致；基于离散中心线三点圆的最小曲率半径约 28 mm。此结果说明模型中的路线与形态键关系，不能替代线材弯曲半径、疲劳寿命和应力释放测试。

独立 BVH 检查覆盖九个姿态：门角 0/25/50/75/100°，以及开门后托盘 80/160/240/320 mm。检查载荷/托盘和活动线对固定壳体、面板、适配器和门体，以及活动线对电脑、框门对壳体的三角面相交；默认最终几何在该检查范围内没有相交对。螺丝、嵌套滑轨、铰链装配及插头插座接触被排除。这不是连续扫掠、间隙公差或所有零件的穷举验证。

原文档的建议参数、本轮文字要求和本次器件占位假设在元数据中分别说明。此模型不是加工图；承重、稳定性、热工、电气、UPS 续航、涉密能力与实际制造公差均未实测或认证。

可参考的工程原则：活动线应保留侧向余隙，弯曲半径按所用线缆确定，见 [igus 线缆布置原则](https://www.igus.co.uk/energy-chain/wiki/filling-rule)。玻璃通过 Principled transmission 导出为兼容 glTF 的透射材质；程序化粉末微纹理用于 Cycles，GLB 保留基础 PBR，见 [Blender glTF 导出说明](https://docs.blender.org/manual/en/5.0/addons/import_export/scene_gltf2.html)。这些资料不构成本模型的性能认证。


可在交付目录复跑只读检查；几何脚本只在内存中改变姿态，不保存 `.blend`：

```bash
'/Applications/Blender.app/Contents/MacOS/Blender' --background --python-exit-code 1 smart_cabinet_single_compartment.blend --python validate_geometry.py
python3 validate_glb.py smart_cabinet_single_compartment.glb
```
