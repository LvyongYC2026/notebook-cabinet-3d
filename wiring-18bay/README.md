# 18仓柜与单仓：可视化布线增量工程

本版在已交付的精细整柜、单仓基础上增加 USB 网卡、随盘 USB 短线和后侧固定布线。整柜保持左右各9仓，A3、B2、B6留空；外形为330×65×185 cm。独立单仓为45×65×45 cm。所有器件外形、线槽截面和孔洞尺寸属于设计假设，不是厂家定型参数。

## 连接关系与动作

- 数据：笔记本 USB → 托盘固定 USB 以太网网卡 → 蓝色活动网线 → 固定仓口 → 后侧数据主干 → 24口交换机 → 柜内服务器。
- 供电：进线与保护/检修隔离设计 → 18路受控支路 → 固定仓插座 → 固定适配器 → 黑色活动 DC 线 → 笔记本。
- UPS 后备优先面向服务器、交换机与控制器；本模型不承诺18台笔记本的后备时长。
- 网卡留在托盘上。空仓及电脑借出后，蓝色网线仍连接网卡并随盘形变；紫色 USB 电脑端停靠托盘卡座，黑色 DC 电脑端停靠固定卡座。
- 抽盘行程32 cm；当前模型实际突出柜面24.75 cm，柜后缘至盘前缘89.75 cm，不包含开门及人员空间。
- 后侧固定线路安装在固定框架，不挂在维护门上。查看布线时隐藏可拆盖板；模块保持原位，防止分离动画把固定线缆拉断。

本 H5 展示结构与连接方案，不包含真实文件上传服务。USB 网卡需要与机型及驱动兼容；实际文件传输仍需在指定服务器部署经确认的接收服务。

## 文件组织

```text
wiring-18bay/
  README.md
  scripts/integrate_wiring_visuals.py
  scripts/audit_wiring_routes.py
  scripts/audit_wiring_motion.py
  scripts/audit_rear_wiring_motion.py
  scripts/audit_wiring_separation.py
  scripts/audit_wiring_meshes.py
  scripts/render_wiring_detail.py
  smart_cabinet_18bay.blend
  smart_cabinet.glb
  components.json
  wiring_model_report.json
  delivery_validation.json
  delivery_manifest.json
  preview_fixed_rear_inspection.png
  single/
    smart_cabinet_single_compartment.blend
    smart_cabinet_single_compartment.glb
    model_metadata.json
    wiring_model_report.json
    preview_usb_wiring_2560.png
```

页面直接加载仓库根目录 assets/ 中的两个 GLB 与参数文件。历史 single-compartment/、refined-18bay/ 目录保留上一版资产，便于比较与重建；本目录是新布线版本。

## Blender 与参数调整

使用 Blender 5.2.3 LTS 的 bpy API。脚本顶部 P 定义网卡外形、线缆半径、固定主干与托盘行程参数。脚本依赖原模型的对象名称和父子层级，修改原结构时应同时更新端接坐标及检查脚本。

从下载的 GitHub 仓库根目录重建整柜（将 blender 替换为本机程序路径）：

```sh
blender --background --python wiring-18bay/scripts/integrate_wiring_visuals.py -- --mode cabinet --base-blend refined-18bay/output/cabinet/refined_candidate/smart_cabinet_18bay.blend --base-metadata refined-18bay/output/cabinet/refined_candidate/components.json --output rebuilt-wiring
```

重建单仓：

```sh
blender --background --python wiring-18bay/scripts/integrate_wiring_visuals.py -- --mode single --base-blend single-compartment/smart_cabinet_single_compartment.blend --base-metadata single-compartment/model_metadata.json --output rebuilt-wiring
```

新增对象按用途独立命名，放在 Wiring_Visuals Collection；相同静态零件共享网格以减少GLB体积，节点和拾取身份独立；网卡与 USB 两种姿态由各自托盘父组承载。原生蓝色网线使用 TrayExtended320mm 形态键。Blender 用托盘位移驱动形态键，网页按实际托盘位置同步。

## Three.js 接口

GLB 使用米制、Y轴向上、+Z为前方。网页将长度统一显示为 cm，原始参数仍用 mm。

- component_key、bay_id：拾取参数与仓位归属。
- cable_paths.keep_connected_when_empty：留柜网卡的蓝色网线保持连接。
- usb_connections：连接态、停靠态节点及端接信息。
- wiring_view：固定主干部件、可拆盖板与布线查看入口。
- wiring_design：固定路径、开孔及设计假设，不作为电气合格证明。

门盘联锁继续生效：门达到规定开度后允许抽盘，收盘完全结束后允许关门。借还演示先切换USB/DC的停靠状态，再移动电脑；电脑归位后恢复连接。

## 验证范围

以交付检查报告为准。几何检查包括多个中间抽盘位置、端接对齐、形态键端环、固定路线与板件孔洞及门体的关系，以及固定线缆两两外包络间距。网页检查包括整柜/单仓切换、空仓、开关门、抽盘、借还、参数浮窗、尺寸稳定跟随和后侧布线查看。

这些检查不能替代线材动态弯曲寿命、机型插拔、托盘承载/稳定性、温升、电气保护和样机验收。线径、额定电流、保护器、接地及器件型号需在工程定型时确认。

可独立复跑检查（从仓库根目录运行，检查不保存模型）：

```sh
blender --background wiring-18bay/smart_cabinet_18bay.blend --python wiring-18bay/scripts/audit_wiring_routes.py
blender --background wiring-18bay/smart_cabinet_18bay.blend --python wiring-18bay/scripts/audit_wiring_motion.py
blender --background wiring-18bay/smart_cabinet_18bay.blend --python wiring-18bay/scripts/audit_rear_wiring_motion.py
blender --background wiring-18bay/smart_cabinet_18bay.blend --python wiring-18bay/scripts/audit_wiring_meshes.py
blender --background --python wiring-18bay/scripts/audit_wiring_separation.py -- --metadata wiring-18bay/components.json
```

固定线缆间距检查使用 Blender 自带 NumPy。它检查模型几何包络，不给出 EMC 或绝缘规范的符合性结论；共同配电端子的接合范围单独记录。

## 产品预览

[后侧固定线路](preview_fixed_rear_inspection.png) · [单仓 USB 接线高清预览](single/preview_usb_wiring_2560.png)。后侧图为布线检视视角，网页中可交互开门查看。

复现单仓高清渲染：

```sh
blender --background wiring-18bay/single/smart_cabinet_single_compartment.blend --python wiring-18bay/scripts/render_wiring_detail.py
```

输出到模型同目录；渲染脚本仅调整当前会话的镜头与姿态，不覆盖原模型。
