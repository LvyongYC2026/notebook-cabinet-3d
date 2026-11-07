# 笔记本智能检测存储柜 · 3D 产品展示

中技安全科技有限公司的智能柜交互展示，使用 Blender 模型与 Three.js，在浏览器中查看外观、内部结构和部件参数。

## 在线演示

https://lvyongyc2026.github.io/notebook-cabinet-3d/

## 功能

- 左右各 9 个电脑仓，共 18 仓；部分仓留空展示承托面与配套结构。
- 点击电脑仓门、服务器仓门和背门查看内部；托盘可抽拉。
- 360° 旋转、缩放、复位与部件尺寸浮层。
- 32 英寸竖屏、黑色舞台光环境、机柜背部散热结构。
- 笔记本开盖、独立适配器收纳、电源与网络检测接口、门锁/门位、照明、风道及活动线束示意。

模型用于产品展示和方案验证；托盘承载、稳定性、温升、断电保持、应急开启以及具体机型包络仍需按实机试验确认。尺寸以页面部件参数和确认后的工程图为准。

## 18 仓精细内构整合版

精细单仓的托盘、接口面板、适配器篮、门锁及分色线路已适配到整柜全部 18 仓。整柜在关门、托盘收回状态下的外包络为 **水平总宽 3300 × 前后深 650 × 总高 1850 mm**。A3、B2、B6 留空，其余 15 仓放置开盖笔电；每仓托盘行程为 320 mm，前门限位为 95°。固定适配器与停车线路留在仓内，活动线路随托盘形变。

[整柜工程与重建说明](refined-18bay/output/cabinet/refined_candidate/README.md)提供最终 Blender 工程、GLB、不可变基线、整合脚本和检查报告。下载仓库后，以 `refined-18bay/` 为项目根目录运行，保留其中的相对目录结构。

[有设备仓预览](refined-18bay/output/cabinet/refined_candidate/previews/refined_A1_detail.png) · [空仓预览](refined-18bay/output/cabinet/refined_candidate/previews/refined_A3_detail.png) · [整柜开门预览](refined-18bay/output/cabinet/refined_candidate/previews/refined_full_open.png)。

## 单仓精细展示与数字资产

[直接打开单仓 3D 展示](https://lvyongyc2026.github.io/notebook-cabinet-3d/?view=single)。单仓设计包络为 **宽 450 × 深 650 × 高 450 mm**；整柜与单仓模型可在页面中切换。

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

所有模型与脚本均从本站加载，Three.js 本地依赖位于 `vendor/three/`。原始参考 PDF、临时日志与本地服务脚本不发布。独立单仓工程位于 `single-compartment/`；精细整柜工程及重建所需的压缩基线位于 `refined-18bay/`。

## 第三方依赖

Three.js 使用 MIT 许可证，许可证文本保留于 `vendor/three/LICENSE`。
