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

所有模型与脚本均从本站加载，Three.js 本地依赖位于 `vendor/three/`。原始参考 PDF、整柜原始 Blender 工程、临时文件与本地服务脚本不发布；本次单仓工程位于 `single-compartment/`。

## 第三方依赖

Three.js 使用 MIT 许可证，许可证文本保留于 `vendor/three/LICENSE`。
