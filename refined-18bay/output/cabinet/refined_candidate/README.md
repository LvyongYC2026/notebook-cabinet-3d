# 18 仓精细内构整合版

本次将已完成的独立单仓细节适配到原整柜，保留 3300 × 650 × 1850 mm 外包络、32 英寸竖屏、左右各 3 × 3 仓、设备舱及三扇后维护门。A3、B2、B6 为空电脑仓，其余 15 仓有电脑；空仓仍保留固定接口、适配器与停车线座。

每仓采用 376 × 470 × 2 mm 白色托盘、300 × 210 × 18 mm 无品牌笔电、105° 开盖和 320 mm 抽拉行程。接口面板、网口、AC 接口、适配器篮与分色线路沿用精细单仓结构，通过实际安装垫柱接到整柜隔板。整柜前门限位为 95°，用于相邻仓同时开门和抽盘避让；独立单仓原模型不受此修改影响。

承托面仍为 350 / 800 / 1250 mm。相邻仓共用水平板，保持承托面以上 420 mm 参考净高；轨道与前横梁已适配抽拉空间。器件与结构调整均为模型设计值，不是制造实测。

## 文件与运行依赖

- `smart_cabinet_18bay.blend`：压缩保存的可编辑整柜，默认第 65 帧展示 A1、A3 开门。
- `smart_cabinet.glb`：网页模型，闭门、托盘回位，含交互节点、部件属性及 30 条原生形态键活动线。
- `components.json`：部件尺寸、来源、门限位、活动及停车线路数据。
- `refined_model_report.json`、`refined_clearance_audit.json`：模型说明与限定范围的几何检查记录。
- `previews/`：有设备仓、空仓和整柜预览。
- `delivery_manifest.json`：交付文件的尺寸与 SHA256。

组合脚本为项目根目录下 `scripts/integrate_refined_bays.py`。它依赖现有整柜基线和独立单仓建模脚本，**不能仅凭这一份组合脚本从零恢复全部整柜**：

1. `output/cabinet/refinement_baseline/smart_cabinet_18bay_before_refinement.blend`
2. `output/cabinet/refinement_baseline/components_before_refinement.json`
3. `single_compartment/build_smart_cabinet.py`

原始基线单独保留；不得用已经整合的最终文件覆盖它，否则框架调整会重复执行。默认运行只写 `output/cabinet/refined_candidate/`，不覆盖网页文件或正式模型。

本次使用 Blender 5.2.3 LTS。在项目根目录执行：

```bash
'/Applications/Blender.app/Contents/MacOS/Blender' --background --python-exit-code 1 --python scripts/integrate_refined_bays.py
```

也可指定交付目录中的文件位置；Windows/Linux 将 Blender 路径改为本机 `blender`：

```bash
blender --background --python-exit-code 1 --python scripts/integrate_refined_bays.py -- \
  --base-blend /path/to/smart_cabinet_18bay_before_refinement.blend \
  --base-metadata /path/to/components_before_refinement.json \
  --single-builder /path/to/build_smart_cabinet.py \
  --output /path/to/refined_candidate
```

默认重建会重新生成适配模板。`--reuse-template` 仅供同一配置下的本地调试；修改尺寸后应省略此项。组合参数在脚本顶部 `CONFIG` 中集中定义，当前检查结论只覆盖本次配置。

## 交互与验证

`Bay_A1…B9` 为每仓原点，`DoorPivot_*` 为前门，`Tray_*` 沿 glTF +Z 抽出 0.32 m，`Laptop_*` 仅在 15 个有电脑仓存在。动态线在 Bay 根节点下，使用 `TrayExtended320mm` 形态键；停车线与端插头通过 `initial_hidden` 和元数据切换。空仓线路与适配器固定，不随托盘运动。

Blender 第 1 帧关闭，第 65 帧 A1/A3 开门，第 110 帧抽盘，第 170 帧回位关闭，第 240 帧设备门展示，第 300 帧后维护门展示。

只读复查命令：

```bash
blender --background --python-exit-code 1 output/cabinet/refined_candidate/smart_cabinet_18bay.blend --python scripts/validate_refined_bays.py
```

检查包含 167 个单仓及全柜组合姿态、固定主要器件对层板/隔板，以及 30 条线缆独立驱动。报告明确排除了嵌套滑轨、紧固件和插接装配接触；不等同于连续扫掠、公差、载荷、热工、电气、疲劳寿命或其他认证。

为便于分发，整柜与基线内嵌了“当前模型使用字符 + ASCII”的中文字库子集；已有铭牌与文本对象保持可编辑。新增未包含的汉字时，请在 Blender 的文本字体设置中指定完整中文字体。未删减模型几何、层级或形态键。
