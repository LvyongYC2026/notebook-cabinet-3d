闭盖笔记本外观增量（Blender 5.2，独立输出）

范围
  在冻结的玻璃/金属抽屉双方案模型上，为右侧24个电脑组件及抽屉单仓
  添加银色拉丝盖板、深灰圆角下壳、双后铰链、前开盖凹口和侧面细节。
  B2/B6/B20的备用电脑及新增细节继续initial_hidden，不改变空仓。
  Laptop/Tray根、原USB/DC口、网卡、活动线、固定布线、导轨、前板方案均保留。
  只替换 *_LaptopBase、*_LaptopClosedLid、两只 *_LaptopHinge 的网格数据；
  新对象名称为 <仓号>_Style_*，全部直接挂在对应Laptop根下。
  外观名义包络30 × 21 × 3 cm；原有接口突出与接线位置不变。
  所有细节均为外观示意，不代表真实接口、电热或强度认证。

输入
  --input 指向冻结的 hybrid_glass_candidate 包，包含整柜三文件和
  single_drawer/ 下的单仓三文件（blend、GLB、JSON）。
  input_manifest.json锁定六文件的SHA256，构建前逐项验证。
  脚本不会保存或覆写任何输入文件；输出必须是另一个目录。
  每个输出blend旁的textures/保留相对路径贴图，贴图同时内嵌在blend和GLB内。

准备
  将Blender可执行文件加入PATH，下例使用通用命令blender。
  assets/ 已包含PNG纹理（材质使用内嵌色彩与ORM两张贴图），正常Blender构建无需Python第三方库。
  可选重新生成纹理：安装Pillow后运行
    python3 scripts/laptop_style/generate_texture.py
  该步骤只读取随包的assets/brand_subset.ttf，无系统字体或网络依赖。
  字体为本地已有Noto Sans SC的4字子集；授权见assets/OFL.txt。
  盾牌图案由脚本绘制，拉丝纹理使用固定随机种子，可重复生成。

构建（从项目根执行）
  blender --background --python-exit-code 1 --threads 4 --python scripts/laptop_style/build_style.py -- --input output/hybrid_glass_candidate --output output/hybrid_glass_styled --expected-input scripts/laptop_style/input_manifest.json
  可先在末尾添加 --only single 或 --only whole，仅生成一个模型。
  完整构建写build_report.json；单模型分别写build_report_single/whole.json。
  报告列出精确旧节点改动、新节点数量、端口与非外观对象指纹、局部包络和输出SHA256。
  窄开孔审查：
    blender --background --python-exit-code 1 --python scripts/laptop_style/audit_apertures.py -- output/hybrid_glass_styled/single_drawer/smart_cabinet_drawer.blend output/hybrid_glass_styled/aperture_audit.json
  隐藏方案的Blender矩阵缓存可能未求值，保留检查使用原始TRS、父逆矩阵及其递归世界矩阵。

透视预览（只读，不保存blend）
  blender --background --python-exit-code 1 --threads 4 --python scripts/laptop_style/render_preview.py -- output/hybrid_glass_styled/single_drawer/smart_cabinet_drawer.blend output/hybrid_glass_styled/preview_laptop_perspective.png
  在末尾加 --drawer 查看抽屉环境，加 --final 输出2560 × 1920、96采样。
  整柜图将输入换为smart_cabinet_33bay.blend并加--whole --final；只打开B24抽屉。
  渲染相机为真实透视，摄影棚地面/灯光仅存在该次渲染内存中，不进入GLB。

交付原则
  build_report只表示脚本内守恒检查通过。最终还需独立资产差分、运动/取放
  碰撞审查、实际GLB原生形态键与前板切换回归，以及浏览器视觉验收。
  模型源码、PNG纹理、字体子集与OFL均为相对路径；无需个人电脑绝对路径。

材质导出说明
  银盖使用同一预打包ORM图的G/B通道提供粗糙度与金属度。Blender 5.2导出器
  因检测到两个shader socket，可能提示使用第一个sampler；两者实际是同一image
  node、UV与sampler，GLB内嵌单一ORM图。该提示不涉及贴图丢失或浏览器错误。
