# 33仓智能柜：透明玻璃 / 金属抽屉双方案

本版本在上一版33仓数字资产上增加透明抽屉前板，保留原金属方案。网页默认玻璃，可通过底部“抽屉前板方案”菜单切换；机要室、整柜、右侧抽屉单仓使用同一选择。左侧开门单仓保持原结构。

[下载本版全部工程、模型、参数及高清图](https://lvyongyc2026.github.io/notebook-cabinet-3d/downloads.html)。下载页恢复完整原始文件，文件名及模型内容不因传输方式改变。

## 结构与接口

- 整柜仍为330 ×65 ×185 cm，左9个开门仓、右24个抽屉仓。底部35 cm外观水平线、中央设备仓、空仓A3/B2/B6/B20及32 cm抽拉行程不变。
- 右抽屉前板包络44.4 ×1.6 ×15.4 cm。玻璃实体41.8 ×0.6 ×10.6 cm，可视窗口41.4 ×10.2 cm；与左侧玻璃使用同一材质。
- 透明前板采用白色金属周框、橡胶垫条、可拆压条及紧固件。顶部金属握持带安装黑色嵌入式把手，开口11.2 ×2.4 cm；拉力经金属前框及连接耳传到托盘，玻璃不承受直接握持拉力。
- 两方案共用随盘金属连接耳，弥合原前板下回边与托盘前桥的装配间隙。原导轨、电脑、供电与线缆几何保持不变。
- 固定后部电源插座连接独立适配器，活动DC线接电脑；蓝色RJ45网线连接随盘USB网卡；紫色USB短线连接电脑USB口与网卡USB口。上游经交换机接服务器，不把两台USB主机直接连接。页面可点击相关接口查看说明。
- 闭盖电脑依据参考图增加银色拉丝上盖、深色圆角底壳、双铰链、前缘开盖凹口、侧面USB/音频/散热细节及中技安全标识。保持30 ×21 ×3 cm名义包络和原接线位置，空仓中的备用电脑随原占用状态隐藏。
- 电源及网络活动段沿原受控线束路径随抽屉运动。右模块一次展开一个抽屉。切换面板时不重建线缆，不改变取放和空仓状态。

所有尺寸均是当前数字资产的设计参数/假设。玻璃选型、焊接和紧固工艺、承载、抗倾覆、温升、电气及具体机型兼容性仍需实机工程验证。

## 文件

| 路径 | 内容 |
|---|---|
| 下载：`smart_cabinet_33bay.blend` | 可编辑整柜，包含两种抽屉前板 |
| 下载：`smart_cabinet_drawer.blend` | 独立抽屉单仓，包含两种前板 |
| 下载：`smart_cabinet_room_and_product.blend` | 机要室/产品双场景，使用同一整柜 |
| `scripts/hybrid_glass/` | 增量参数化建模和渲染脚本 |
| `scripts/laptop_style/` | 闭合笔记本外观增量脚本与材质 |
| `scripts/hybrid_glass_room/` | 房间生成、视图控制、渲染、字体与许可证 |
| `source_metadata/` | 冻结的上一版33仓元数据，用于可靠重建 |
| `reports/` | 资产保留、面板运动、房间和网页验证报告 |
| 下载页“产品渲染” | 当前玻璃方案整柜、抽屉、笔记本及机要室高清图 |
| `downloads/` | 原始工程与渲染的传输清单和数据分片 |
| `release_manifest.json` | 本次发布文件大小与SHA-256清单 |

当前网页GLB与元数据通过根目录`assets/*.manifest.json`及分片提供，下载页恢复完整文件。根目录旧`assets/*.glb`/JSON保留作上一版资产，当前网页不会把它们作为缺片时的回退。旧33仓源模型保留在`hybrid-33bay/`；重建本版请使用该目录原生模型和这里冻结的`source_metadata/`。

## 重建与参数

使用Blender 5.2.3 LTS及其自带Python。以下命令在仓库根目录执行，`blender`可替换为本机可执行程序路径。输出目录由参数指定，不覆盖历史工程。

```sh
blender --background --python hybrid-33bay-glass/scripts/hybrid_glass/build_glass_fronts.py -- \
  --base-blend hybrid-33bay/smart_cabinet_33bay.blend \
  --base-metadata hybrid-33bay-glass/source_metadata/components.json \
  --single-blend hybrid-33bay/smart_cabinet_drawer.blend \
  --single-metadata hybrid-33bay-glass/source_metadata/drawer_compartment.json \
  --output output/glass

# Freeze this rebuild's intermediate input hashes.
python3 - <<'PYMANIFEST'
from pathlib import Path
import hashlib, json
root=Path('output/glass')
names=['smart_cabinet_33bay.blend','smart_cabinet.glb','components.json',
       'single_drawer/smart_cabinet_drawer.blend',
       'single_drawer/smart_cabinet_drawer.glb','single_drawer/drawer_compartment.json']
(root/'style_input_manifest.json').write_text(json.dumps({n:{'bytes':(root/n).stat().st_size,
    'sha256':hashlib.sha256((root/n).read_bytes()).hexdigest()} for n in names},indent=2))
PYMANIFEST

blender --background --python hybrid-33bay-glass/scripts/laptop_style/build_style.py -- \
  --input output/glass --output output/styled \
  --expected-input output/glass/style_input_manifest.json

blender --background --python hybrid-33bay-glass/scripts/hybrid_glass_room/build_room.py -- \
  --base-blend output/styled/smart_cabinet_33bay.blend \
  --output output/glass_room
```

玻璃建模脚本会核验四个冻结源文件SHA，防止重复叠加前板。笔记本外观脚本另校验本次中间输入清单；随包`input_manifest.json`记录发布时的中间资产，重新保存的Blender二进制文件可能不同，应先检查中间模型，再生成本次重建清单。`config.py`集中定义前板、玻璃、周框和握持带参数；也可传入`--config parameters.json`。允许的参数范围有明确检查，超出当前装配包络应先调整构造并重新验证。

Blender中，场景自定义属性`drawer_front_mode`：`1`显示玻璃，`0`显示金属。每种前板的对象通过驱动器控制视口和渲染可见性；共享连接耳始终保留。切换后刷新场景帧以更新驱动器。`Drawer_Front_Variants`集合集中存放新增部件，前板与原抽屉均绑定到同一托盘。

房间工程的文本块`setup_display_modes.py`可注册Room Display侧栏，切换ROOM/PRODUCT和各房间镜头。原33仓机构动画及线缆驱动保留。

## 渲染与GLB

```sh
blender --background --python hybrid-33bay-glass/scripts/hybrid_glass/render_preview.py -- \
  output/styled/smart_cabinet_33bay.blend output/styled/render_cabinet_glass.png cabinet --final

blender --background --python hybrid-33bay-glass/scripts/hybrid_glass/render_preview.py -- \
  output/styled/single_drawer/smart_cabinet_drawer.blend output/styled/render_drawer_glass.png drawer --final

blender --background output/glass_room/smart_cabinet_room_and_product.blend \
  --python hybrid-33bay-glass/scripts/hybrid_glass_room/render_views.py -- \
  --views overview --output output/glass_room/renders
```

两阶段建模命令自动输出GLB、JSON和构建报告；网页使用`output/styled/`最终资产。拉丝与标识使用已打包PNG/ORM纹理，可由`generate_texture.py`和随包OFL字体重建（需要Pillow）。坐标单位米，Blender Z向上导出为glTF Y向上；原机械层级及线缆形态键保留。导出包含两种前板，GLB本身没有统一的初始隐藏标准，因此不要直接同时显示两个前板。

本站`front-variants.js`读取元数据`drawer_front_variants`，按组件根节点在首帧前执行互斥可见性；`initial_hidden`保留默认状态。其它Three.js项目集成时也应处理此契约，并保留玻璃材质、透明排序、形态键和托盘父子关系。元数据内部计量单位不变，界面统一换算成cm。

本站`asset-loader.js`对六项新运行资产读取相应`.manifest.json`，依序获取同源分片、逐片校验SHA-256、无损解压，并验证完整文件长度与SHA后才解析模型/参数。下载页使用同一解码器恢复原文件。清单缺失、分片损坏、解压失败时显示错误，不会静默展示上一版模型。恢复传输所用代码及报告与建模报告分别保留；数字资产内容仍与原冻结SHA完全一致。

## 验证范围

报告采用两阶段差分：前板阶段保留全部原模型几何；电脑外观阶段仅替换整柜96个及单仓4个指定外壳/铰链网格，并增加对应外观细节。原接口、层级、线缆和形态键保持一致。前板及共享连接耳检查覆盖两方案各17档抽拉和实际连接点；最终房间检查基于外观更新后的完整模型，网页回归覆盖三视图、借还、空仓和运行中的方案切换。几何采样检查不等同于连续运动证明或制造验收。

原金属版的完整布线、端点、空仓及机构报告仍在`../hybrid-33bay/reports/`。旧版渲染可参看`../hybrid-33bay/renders/`。字体采用随包SIL OFL许可证，Three.js许可证位于仓库`vendor/three/LICENSE`。
