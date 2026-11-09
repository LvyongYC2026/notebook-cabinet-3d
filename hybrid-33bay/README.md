# 33仓混合柜数字资产

本版在原18仓布线模型上保留左侧9个开门仓和中央设备仓，重建右侧24个闭盖笔记本抽屉仓。尺寸为设计模型参数，不是生产图纸。

## 文件

- `smart_cabinet_33bay.blend`：可编辑整柜，9个左门、24个右抽屉与原生线缆形态键。
- `smart_cabinet_drawer.blend`：独立右抽屉仓。
- `smart_cabinet_room_and_product.blend`：同一33仓机柜的机要室/产品双场景。
- `scripts/hybrid/`：抽屉与整柜增量建模、中央接线及渲染脚本。
- `scripts/hybrid_room/`：机要室搭建、相机、显示模式及字体。
- `scripts/audit_*.py`：独立资产、保留结构、运动和房间检查。
- `reports/`：本版检查记录及输入文件指纹。
- `renders/`：实际Blender模型渲染。

网页直接使用[整柜GLB](../assets/smart_cabinet.glb)、[整柜参数](../assets/components.json)、[右抽屉GLB](../assets/smart_cabinet_drawer.glb)、[右抽屉参数](../assets/drawer_compartment.json)、[房间GLB](../assets/room_environment.glb)和[房间参数](../assets/room_metadata.json)。左开门仓继续使用[原精细单仓GLB](../assets/smart_cabinet_single_compartment.glb)。

## 结构参数

| 参数 | 本版值 |
|---|---|
| 整柜宽×深×高 | 330×65×185 cm |
| 左/中/右模块宽度 | 135/60/135 cm |
| 左仓 | 3列×3层，9个开门仓 |
| 右仓 | 3列×8层，24个抽屉仓 |
| 右层距/承载区域净高 | 16/13 cm |
| 右承托面离地 | 38、54、70、86、102、118、134、150 cm |
| 闭盖笔记本包络假设 | 30×21×3 cm |
| 抽屉行程 | 32 cm |
| 右前板宽×厚×高 | 44.4×1.6×15.4 cm |
| 独立右单仓外包络 | 45×65×16.2 cm |
| 中央设备仓内部高度 | 68 cm，保持原结构 |

13 cm净高从实际橡胶承托面计量，在电脑承载区域测至最低固定障碍；侧后部适配器、网卡及线束各有独立空间。独立单仓外高16.2 cm含顶板，整柜16 cm层距利用相邻层共用分隔关系，二者不是同一参数。

35 cm为外观水平线。左侧和中央采用随门移动的分段分缝，保留底层托盘扫掠和中央大门；右侧固定底板到35 cm，承托面提升到38 cm避让。原左仓及中央结构除明确记录的外观分缝、网络与供电控制升级外保留。

## 连接与运动

每仓AC插座、适配器留在固定后部；黑色DC与蓝色网线采用受控回弯随抽屉运动。紫色USB短线连接电脑与留柜网卡，网卡随盘。三类活动线分层布置，固定主干与维护门分离。

右侧只允许一个抽屉展开，联锁属于网页交互逻辑；实际产品需配置机械或电气联锁并完成抗倾覆校核。电脑取出前先断开USB/DC并显示停靠状态，抽屉全伸后先抬高再向前取出；归还执行逆序。空仓不省略连接器和收纳结构。

## 重建

开发验证使用 **Blender 5.2.3 LTS**，优先使用同版本。无需额外Python包；脚本通过Blender的`bpy`运行。下载完整仓库并在仓库根目录执行，`blender`替换为本机可执行文件路径：

```sh
blender --background --python hybrid-33bay/scripts/hybrid/build_hybrid.py -- \
  --stage full \
  --base-blend wiring-18bay/smart_cabinet_18bay.blend \
  --base-metadata wiring-18bay/components.json \
  --output hybrid-33bay/output/hybrid_candidate

blender --background --python hybrid-33bay/scripts/hybrid_room/build_room.py -- \
  --base-blend hybrid-33bay/output/hybrid_candidate/smart_cabinet_33bay.blend \
  --output hybrid-33bay/output/hybrid_room_candidate
```

原始基线SHA-256为`81c0fe823ede81c715ebc82dcd3435ecc06cef8a3c73ee331536223e4133d1c0`，生成脚本校验此值。勿把已经改造的33仓模型作为增量源反复叠加。生成流程同时导出GLB和JSON；GLB为Y向上、米制，Blender为Z向上、前方-Y。形态键和对象层级须保留。

集中参数位于`config.py`，支持`--config config.json`覆盖已声明项。当前断言限定3×8抽屉与330×65×185 cm外壳；更改层数、电脑包络或机构尺寸需要同时调整布线、层板、相机、元数据并重新验证，不能只改标签。

机要室显示切换使用`setup_display_modes.py`的`apply_display_mode('ROOM','overview')`或`apply_display_mode('PRODUCT')`；房间与独立产品共用一个CabinetRoot，切换不复制模型。

## 渲染与检查

机要室高分辨率Cycles渲染：

```sh
blender --background hybrid-33bay/smart_cabinet_room_and_product.blend \
  --python hybrid-33bay/scripts/hybrid_room/render_views.py -- \
  --views overview,operation --output hybrid-33bay/renders
```

默认2560×1440；加`--preview`得到1280×720快速预览。产品与抽屉使用`scripts/hybrid/render_preview.py`，末尾加`--final`输出2560×1920、64采样；前3个位置参数为输入blend、输出PNG、`cabinet`或`drawer`。

```sh
blender --background hybrid-33bay/smart_cabinet_33bay.blend \
  --python hybrid-33bay/scripts/audit_hybrid_motion.py -- \
  --output hybrid-33bay/reports/local_motion.json
```

本版报告记录：右抽屉116组采样姿态、左9托盘及17条活动线的17档采样、左9门各21档采样、后门22档采样、固定线路5356组间距比较，以及139处过孔的1251条探针。另测空仓/有电脑状态反转和网页抽屉联锁。所有报告绑定对应文件SHA。

运动检查使用求值后的网格与分档位置，精确排除已声明的插接端点、滑轨啮合及紧固接触，其他真实碰撞必须修复。报告注明覆盖范围和文件SHA，采样通过不等于全行程连续证明。GLB层级、端点、停车态、占用切换及房间安装另行验证。

## Three.js集成

加载与GLB匹配的JSON，使用对象名称及`extras`关联仓位，不应再用只匹配单个数字的仓号正则。A1—A9有门轴与托盘；B1—B24仅由托盘根带动前板、电脑、网卡及USB。右侧无额外门轴。

原生DC/网线形态键按0—32 cm行程插值，不能另外添加重复线缆；停车线与连接线按占用状态切换。单抽屉GLB仅含单仓场景；原左侧透明玻璃材质保持，右侧金属前板不应套用玻璃效果。后维护门在独立产品中可开启，参考房间中受10 cm后部间距限制。

承载、电气保护、网络选型、接口可维护性、线缆疲劳、温升、应急开锁和新增机型适配均需实机确认。H5只是数字展示，不是生产控制或文件上传程序。
