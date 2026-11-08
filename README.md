# 笔记本智能检测存储柜 · 3D 产品展示

中技安全科技有限公司的智能柜交互展示，使用 Blender 模型与 Three.js，在浏览器中查看外观、内部结构和部件参数。

## 在线演示

https://lvyongyc2026.github.io/notebook-cabinet-3d/

## 功能

- 左右各 9 个电脑仓，共 18 仓；部分仓留空展示承托面与配套结构。
- 点击电脑仓门、服务器仓门和背门查看内部；托盘可抽拉。
- 360° 旋转、缩放、复位与放大的科技风参数浮窗。
- 整柜及单仓尺寸标注可开关，展示总体尺寸与 32 cm 托盘抽出空间；页面长度统一使用 cm（厘米）。
- 柜内可视化电源、网线和 USB 网卡接线，支持后侧主干总览与单仓 USB 接线聚焦。
- 约 81.3 cm 对角线竖屏、黑色舞台光环境、机柜背部散热结构。
- 笔记本开盖、独立适配器收纳、电源与网络检测接口、门锁/门位、照明、风道及活动线束示意。

模型用于产品展示和方案验证；托盘承载、稳定性、温升、断电保持、应急开启以及具体机型包络仍需按实机试验确认。尺寸以页面部件参数和确认后的工程图为准。

## 尺寸标注、参数与布线方案

尺寸标注可在整柜与单仓模式中独立查看。整体外包络对应关门、托盘收回状态；托盘行程 **32 cm**，当前模型全抽后突出柜面 **24.75 cm**、柜后缘至盘前缘 **89.75 cm**，不含门扇和人员空间。标注保留布局位置，旋转时不反复换边，重叠时平滑避让。实时行程最多显示一位小数，固定标签宽度避免数字挤动布局。部件参数浮窗使用更大字号和科技风 HUD 样式，页面长度统一显示为 cm（厘米）。

布线模型展示笔记本 USB → 托盘网卡 → 仓口 → 交换机 → 服务器，并区分固定 AC、活动 DC、蓝色以太网和紫色 USB 短线。网卡留柜随盘，空仓及借出后网线保持连接；USB电脑端停靠随盘卡座，DC电脑端停靠固定卡座。后侧主干安装在固定框架，维护门可独立开启。

“布线方案”面板提供“在柜内查看布线”和“查看单仓 USB 接线”入口；点击单路网络主干可查看对应仓位、交换机端口与设计长度。公开 H5 不读取或上传笔记本文件。实际上传服务、器件选型及电气和热工验证仍待实施。

[布线版整柜与单仓工程](wiring-18bay/README.md)包含本版 Blender、GLB、增量脚本与检查说明。历史工程目录保留原版；页面仅在显示时换算单位，原始元数据和三维坐标继续使用各自计量单位。

## 上一版18仓精细内构工程

精细单仓的托盘、接口面板、适配器篮、门锁及分色线路已适配到整柜全部 18 仓。整柜在关门、托盘收回状态下的外包络为 **水平总宽 330 × 前后深 65 × 总高 185 cm**。A3、B2、B6 留空，其余 15 仓放置开盖笔电；每仓托盘行程为 32 cm，前门限位为 95°。该历史版本采用原生RJ45接入；最新留柜USB网卡及停车逻辑见布线版工程。

[整柜工程与重建说明](refined-18bay/output/cabinet/refined_candidate/README.md)提供最终 Blender 工程、GLB、不可变基线、整合脚本和检查报告。下载仓库后，以 `refined-18bay/` 为项目根目录运行，保留其中的相对目录结构。

[有设备仓预览](refined-18bay/output/cabinet/refined_candidate/previews/refined_A1_detail.png) · [空仓预览](refined-18bay/output/cabinet/refined_candidate/previews/refined_A3_detail.png) · [整柜开门预览](refined-18bay/output/cabinet/refined_candidate/previews/refined_full_open.png)。

## 单仓精细展示与数字资产

[直接打开单仓 3D 展示](https://lvyongyc2026.github.io/notebook-cabinet-3d/?view=single)。单仓设计包络为 **宽 45 × 深 65 × 高 45 cm**；整柜与单仓模型可在页面中切换。

[完整单仓工程与使用说明](single-compartment/)包含 Blender 工程、GLB、参数化生成脚本、元数据与高清渲染图。

高清渲染：[开门主视](single-compartment/render_front_open.png) · [正视图](single-compartment/render_front_view.png) · [闭门图](single-compartment/render_door_closed.png) · [内部细节](single-compartment/render_internal_detail.png)。

单仓尺寸与器件造型属于方案设计假设，几何检查范围和复现方式见交付目录的说明；机械承载、电气和热工仍需实机验证。

## 本地运行

需要使用 HTTP 静态服务器，不能直接以 `file://` 打开页面。

```sh
python3 -m http.server 8765
```

浏览器访问 `http://127.0.0.1:8765/`。

## 部署

本仓库为无构建步骤的静态站点，使用相对资源路径。GitHub Pages 设置为从 `main` 分支的根目录发布。`.nojekyll` 禁用 Jekyll 处理。

所有模型与脚本均从本站加载，Three.js 本地依赖位于 `vendor/three/`。原始参考 PDF、临时日志与本地服务脚本不发布。历史单仓工程位于 `single-compartment/`；历史整柜工程及压缩基线位于 `refined-18bay/`；本次增量工程位于 `wiring-18bay/`。

## 第三方依赖

Three.js 使用 MIT 许可证，许可证文本保留于 `vendor/three/LICENSE`。
