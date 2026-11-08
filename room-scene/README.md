# 机要室与智能柜双模式工程

本工程按参考三视图搭建机要室，并复用现有 18 仓智能柜。房间模式与产品模式使用同一个 `CabinetRoot`，不复制或重建柜体；原有 18 仓布局、空仓 A3 / B2 / B6、门体、320 mm 托盘行程和随动线缆保持原资产定义。

最终独立空间审计、独立环境导出审计、全新输出目录重建和五幅 2560×1440 Cycles 渲染已完成。两份独立审计状态均为 `passed`；受检文件哈希和检查范围汇总于 `validation.json`，逐文件交付清单见 `delivery_manifest.json`。

## 文件与依赖

公开仓库中的房间工程位于 `room-scene/`；以下命令从仓库根目录执行，并将新生成的文件写入 `rebuilt-room/`。发布包根目录同时提供已验证的模型、元数据与审计报告。

| 文件 | 用途 |
| --- | --- |
| `room-scene/scripts/room/config.py` | 房间尺寸、布局、相机和标识文字的集中参数 |
| `room-scene/scripts/room/build_room.py` | 从已有柜体资产构建完整房间工程并导出环境 |
| `room-scene/scripts/room/metadata.py` | 按配置生成网页坐标、相机及布局元数据 |
| `room-scene/scripts/room/metadata_template.json` | 组件、分组与交互契约模板，须与脚本一起保留 |
| `room-scene/scripts/room/setup_display_modes.py` | 构建与渲染脚本依赖的模式切换模块，也会嵌入工程内 Text |
| `display_modes.py`（工程内 Text） | Blender 的 `ROOM / PRODUCT` 显示切换 |
| `room-scene/scripts/room/render_views.py` | 房间透视、正交与操作空间示意图渲染 |
| `room-scene/smart_cabinet_room_and_product.blend` | 已交付的可编辑完整双模式工程 |
| `room-scene/room_environment.glb` | 已交付的房间环境，供网页与现有机柜组合 |
| `room-scene/room_metadata.json` | 已交付的坐标映射、相机、分组、参数与限制 |
| `room-scene/independent_room_installation_audit.json` | 最终房间安装空间审计，绑定受检工程 SHA256 |
| `room-scene/independent_room_export_audit.json` | 环境 GLB 坐标、包络、分组及隔离导出检查 |
| `room-scene/validation.json` | 已发布文件的交付检查汇总；重新构建不会自动生成新验证结论 |

构建依赖唯一柜体源 `wiring-18bay/smart_cabinet_18bay.blend`，其基线 SHA256 为 `81c0fe823ede81c715ebc82dcd3435ecc06cef8a3c73ee331536223e4133d1c0`。房间脚本不能仅凭自身重新生成该机柜；必须同时保留柜体源文件。它也不覆盖原柜体 GLB、参数文件或已发布的单仓资产。

使用本机 Blender 5.2.3 LTS。以下命令从公开仓库根目录执行，`blender` 应指向本机 Blender 可执行文件；macOS 可将其替换为 `/Applications/Blender.app/Contents/MacOS/Blender`。

## 构建与渲染

```sh
cd /path/to/repository
blender --background --python room-scene/scripts/room/build_room.py -- \
  --base-blend wiring-18bay/smart_cabinet_18bay.blend \
  --output rebuilt-room
```

指定不同的输入、输出目录或 JSON 参数文件时，将脚本参数放在 `--` 之后：

```sh
blender --background --python room-scene/scripts/room/build_room.py -- \
  --base-blend wiring-18bay/smart_cabinet_18bay.blend \
  --output rebuilt-room \
  --config /path/to/room_config.json
```

`--config` 为可选项，参数名称和米制单位见 `room-scene/scripts/room/config.py`；不要把网页显示的厘米值直接填入米制参数。当前布局生成器仅支持净尺寸 **5100 × 3000 × 2800 mm**（配置值 `[5.10, 3.00, 2.80]` m），其他房间尺寸会明确报错。它不是任意尺寸房间的自动布局器；要适配其他尺寸，须先修改布局代码、家具与净空约束，再重新验证。其他获支持参数变更后也须重新构建与校验，不能沿用上一版检查结论。

构建时由 `metadata.py` 读取同目录的 `metadata_template.json` 生成输出，不要求 `rebuilt-room/` 中预先存在元数据文件。已在全新输出目录实际重建，生成完整的 9 个组件定义、5 组网页相机及室内边界，导出的环境 GLB 不含柜体副本。请保留上述两个元数据源文件及字体资源；整体交付检查汇总见 `validation.json`。

房间视图批量渲染：

```sh
blender --background rebuilt-room/smart_cabinet_room_and_product.blend \
  --python room-scene/scripts/room/render_views.py -- \
  --views overview,front,side,top,operation \
  --output rebuilt-room/renders
```

五幅正式渲染为 `overview`、`front`、`side`、`top`、`operation`，分辨率均为 2560 × 1440。`overview` 为整体透视；`front`、`side`、`top` 使用真实正交相机。侧视图为侧向正交展示，不是带封口面的实体剖面；剖切隐藏墙体或工作台时，会同时隐藏其附属标牌、盆栽及安防示意，避免留下悬空附属物。

`operation` 为柜前操作空间示意：只读渲染时，将 18 扇前仓门按现有 95° 限位打开、托盘按既有 320 mm 行程全抽出，并显示原定 1200 mm 操作区边界。该临时姿态不会保存回输入 `.blend`。本轮输出房间视图，不重复生成此前的机柜产品宣传图。

## 重建后复跑独立审计

构建命令只生成模型、环境 GLB、元数据和构建报告；不会自动生成最终验收汇总。以下命令同样从仓库根目录执行，先记录原柜体基线，再检查新工程和新环境导出：

```sh
blender --background wiring-18bay/smart_cabinet_18bay.blend \
  --python room-scene/scripts/audit_room_installation.py -- \
  --baseline-out rebuilt-room/cabinet_source_geometry.json

blender --background rebuilt-room/smart_cabinet_room_and_product.blend \
  --python room-scene/scripts/audit_room_installation.py -- \
  --baseline rebuilt-room/cabinet_source_geometry.json \
  --output rebuilt-room/independent_room_installation_audit.json

blender --background --python room-scene/scripts/audit_room_export.py -- \
  --glb rebuilt-room/room_environment.glb \
  --metadata rebuilt-room/room_metadata.json \
  --output rebuilt-room/independent_room_export_audit.json
```

先完成前述构建以创建 `rebuilt-room/`。核对新报告状态、文件哈希和检查范围后再决定是否发布；包内 `room-scene/validation.json` 只对应已交付的冻结文件，不能作为新构建的验收结论。网页交互和渲染外观仍需另行检查。

## Blender 模式切换

打开完整 `.blend` 后，在 Text Editor 中选择并运行工程内的 `display_modes.py`，注册模式切换界面，然后使用 3D 视图侧栏的 **Room Display** 面板切换模式。也可在加载该脚本后调用：

```python
apply_display_mode('ROOM')
apply_display_mode('PRODUCT')
```

- `ROOM`：显示房间与室内灯光，柜体根节点位置为 `(2.55, 2.575, 0)` m。
- `PRODUCT`：隐藏全部房间环境，显示产品摄影棚，柜体根节点回到 `(0, 0, 0)` m。

两种模式的柜体比例均为 `(1, 1, 1)`。切换只改变显示环境、相机与柜体安装位置，不改变柜体网格、节点层级、门铰链、托盘行程或线缆驱动。前、右墙与吊顶分别保留可切换分组；完整工程仍保留建筑几何。

## 坐标与网页组合

完整 Blender 工程采用室内左前角地面为原点，X 向右、Y 向后、Z 向上，单位为米。机柜正面朝向 `-Y`。

网页保持现有柜体模型位于原点、比例为 1。`room_environment.glb` 只导出房间，不包含机柜副本、摄影棚、相机或灯光对象。导出时先把房间全局坐标减去柜体安装位置，再进行 glTF 的 Y 向上转换：

```text
室内全局 Blender 点：(Xr, Yr, Zr)
柜局部 Blender 点：  (Xr − 2.55, Yr − 2.575, Zr)
柜局部 glTF 点：     (Xr − 2.55, Zr, 2.575 − Yr)
```

房间环境根节点为 `RoomEnvironmentRoot`。室内净空间在柜局部 glTF 中的范围为 `min = [-2.55, 0, -0.425]`、`max = [2.55, 2.8, 2.575]` m；这不是包含墙厚、楼板厚度的建筑外包络。网页应读取元数据中的实际分组和相机参数，不再给房间叠加一次柜体安装偏移。

## 布局依据与设计假设

| 项目 | 当前布局 |
| --- | --- |
| 室内净尺寸 | 5100 × 3000 × 2800 mm |
| 柜体关闭外形 | 3300 × 650 × 1850 mm，来自既有柜体资产 |
| 柜体安装范围 | X 900–4200、Y 2250–2900、Z 0–1850 mm |
| 柜前操作区 | X 900–4200、Y 1050–2250 mm，名义深度 1200 mm |
| 柜后至后墙 | 100 mm |
| 柜体左右至侧墙 | 各 900 mm；另标示各 300 mm 的预留侧边维护带 |
| 工作台 | 左前角，台面 600 × 1200 mm，台高 750 mm |
| 座椅 | 停放于左前方，不进入上述柜前操作区；实际包络须以验证结果为准 |
| 门洞 | 右侧墙前端，X = 5100、Y = 100–1000 mm，洞口 900 × 2100 mm |
| 房门方向 | 前端铰链，向室内左侧开启 |

上述房间、家具、墙厚、吊顶、门禁和监控位置属于参考图设计假设，不是施工图、疏散规范验收或涉密场所认证。门洞尺寸不等于门叶实体外包络。参考图中房门名义扫掠与操作区相隔 50 mm，实际门厚、把手和开启状态应按模型检查结果说明。

房间仅采用“机要室”“涉密设备管理区”“保密管理要求”等可校对短标识，不复制参考图中的失真文字，也不编造政策条文。

## 操作空间与维护限制

320 mm 是托盘的移动行程，不等于托盘伸出柜面 320 mm。当前柜体几何中，托盘收回前缘在柜面内 72.5 mm；最大抽出后，实际突出柜面为 **247.5 mm**。因此，1200 mm 操作区内的几何余量为 **952.5 mm**，尚未扣除柜门开启扫掠。

参考 SVG 的“1200 − 320 = 880 mm”是运动范围示意，不能替代实际前缘测量。最终独立空间审计按室内全局坐标测得：

| 检查对象 | 最前缘 Y | 至操作区前界 Y = 105 cm 的剩余深度 |
| --- | --- | --- |
| 前部门体采样扫掠（18 扇仓门至 95°、设备门至 105°） | 170.392 cm | 65.392 cm |
| 全抽出托盘组件（包含笔电及相连部件） | 200.25 cm | 95.25 cm |

这里的余量为沿房间 Y 轴的几何距离，不代表整个区域的有效通行宽度或疏散合规结论。前门扫掠余量与托盘余量不可相加；网页托盘尺寸标注只取托盘金属件，完整动作检查另包含托盘上的关联部件。具体测量记录见 `independent_room_installation_audit.json`，整体汇总见 `validation.json`。

**100 mm 后距不能开启现有后维护门进行正常检修。** 房间模式应禁止后维护门动作；查看后侧布线时，网页切回独立整柜模式。实际安装后的后侧检修需要先移柜，不能通过修改房间净尺寸或缩小柜体来掩盖这一限制。

最终独立审计对照原柜体源检查了 2949 个对象，几何、子层级、形态键及局部变换基准保持一致；完整工程只有一个柜体根节点，比例为 `(1, 1, 1)`。前部门体按 21 个开度比例、托盘按 0–320 mm 每 20 mm 共 17 个位置检查，与所纳入的 260 个环境实体均未发现表面相交；家具与房门未进入关闭状态的柜前操作区或柜体安装包络。房间共有 400 个环境网格，碰撞检查排除了地面接触及净空辅助标记。

上述结果绑定完整工程 SHA256 `b675489723e516baaff241c562fe4fbaaa937b3270db8072cb20916e7d6dfca5`，审计状态为 `passed`。模型若重新构建或修改，应对新的文件重新执行检查，不能沿用该哈希的结论。抽样几何检查不能替代连续运动、公差、承重、散热、电气、防火、门禁覆盖或工程合规验证。

环境 GLB 的独立导出审计确认唯一 `RoomEnvironmentRoot`、319 个网格节点、柜局部 glTF 坐标与含墙厚外包络一致；未导出柜体副本、摄影棚、相机或灯光。该结论绑定 GLB SHA256 `4551a01314efc90ae119f9b36d7156e3c74c05b99b78cdbf63ee62a7a9ddde62` 与对应元数据，详见 `independent_room_export_audit.json`。

## 字体与许可

房间中文标识使用 `room-scene/scripts/room/assets/room_signage_subset.ttf`，派生自 Google Fonts 官方 [Noto Sans SC](https://github.com/google/fonts/tree/main/ofl/notosanssc)，按 [SIL Open Font License 1.1](https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/OFL.txt) 分发；同目录的 `OFL.txt` 必须随字体保留。

构建脚本直接加载随源码分发的字体子集；`font_path` 默认相对于 `room-scene/scripts/room/` 解析。子集已固定为 Regular 400，并命名为 **Room Signage Subset Regular**。它仅包含当前 `SIGN_TEXTS` 所需的 29 个汉字及 95 个可打印 ASCII 字符。新增汉字时，须从官方完整字体重新生成子集或指定具有相应授权的完整字体，并检查缺字；不要依赖本机系统字体才能正确显示标识。
