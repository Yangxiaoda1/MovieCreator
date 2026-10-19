# 外骨骼警察_男资产 QC 记录

## 已检查项

- 风格：写实、真实感、电影质感，未按卡通 / 二次元 / 插画 / 玩具风格生成。
- 主体一致性：资产组保持黑色圆顶头盔、全黑镜面面罩、黑色肩甲、胸甲、战术服、步枪、护膝、战术靴等核心识别点。
- 三视图：`01_front.png`、`02_side.png`、`03_back.png` 直接从用户原图三视图裁切整理，主体一致性最高。
- 补充资产：`05_helmet_closeup.png`、`06_breach_pose.png`、`07_damaged_state.png` 基于原图生成，需后续使用时继续对照 `00_original_three_view.png`。
- 音色参考：已使用用户指定的干净 `Speech` 文件，位于 `audio_references/speech_clean/`，没有保留混合原始音频。
- 用途记录：已写入 `generated_asset_manifest.json` 和 `audio_references/speech_reference_manifest.json`。

## 注意项

- 后续提示词必须持续强调：black rounded tactical helmet、full black glossy visor、no face reveal、black exoskeleton/riot armor、black rifle、realistic cinematic style、subject consistency first。
- 状态变化只能增加灰尘、雨痕、轻微划痕或装备磨损，不能露脸、换头盔、换服装颜色或移除步枪。
- 与其他角色同框时，按暂定身高约 `1.85m`、装备后宽肩厚重进行比例 QC。
