# 03｜S15–S19 声音、音乐、混音、字幕与交付

## 覆盖阶段

```text
S15 Sound / Foley
S16 Music
S17 串轨清理、三路 stem 与最终混音
S18 字幕
S19 最终 QC、manifest、contact_sheet 与交付
```

---

## S15 Sound / Foley

本阶段不生成替代人声。`Speech` 来自 S11：H3 Ref2VA 原生 speech 合格时直接保留为 speech stem；原生对白效果不好时回到 S11 完善 H3 / Ref2VA prompt 并最多重生成 `2` 次，在初版与重生成版本中选择综合效果最好的一版。S15 只负责 `Sound / Foley`：环境声、动作音效、机械声、脚步、风声、爆炸等非人声声音。

S15–S17 只能读取通过 S11 / S12 的 H3 原生 Speech；若有漏字、截断、增词、静音或口型问题，必须退回 S11，不能在本阶段替换人声。

Sound 使用最终 `picture_lock` 或最终逐镜画面，一镜一文件。

Prompt 必须包含：

```text
画面发生什么
环境和动作声
材质、距离、空间和节奏
排除：No speech, no dialogue, no narration, no music
```

规则：

- 严格裁到镜头时长并按顺序拼接
- 声音空间符合室内外、门前门后和远近
- 用户指定保留的原版音效优先复用
- Foley 可能根据口型生成含混人声，必须用 ASR 或人声检测检查
- 检出可懂人声时，优先重写 prompt 重生成；仍存在时做人声分离

命令示例：

```bash
CUDA_VISIBLE_DEVICES=1 python <PROJECT_ROOT>/aifilm_booklet/tools/generate_foley_batch.py --steps 50 --force
```

运行前确认视频目录、shot 列表、prompt 和模型路径属于当前项目。

输出：

```text
<PROJECT_ROOT>/output/audio/sound/raw/shot_*.wav
<PROJECT_ROOT>/output/audio/sound/processed/
<PROJECT_ROOT>/output/audio/sound/manifest.json
<PROJECT_ROOT>/output/audio/sound_stem.wav
```

---

## S16 Music

Prompt 描述类型、乐器、速度、调性、情绪弧线、剧情转折和对白期间的稀疏编配。

纯器乐要求：

```text
lyrics 置空
strictly instrumental
no voice, no vocals, no singing
no humming, no chanting, no spoken words
```

规则：

- 使用覆盖完整 picture lock 的统一配乐和连续音乐时间线；不得逐 shot 单独配乐、切镜重启或逐镜淡入淡出
- 音乐主题、节奏与情绪发展跨镜头连续；确需换段时按剧情节点衔接并平滑交叉淡化，不按 shot 边界生硬拼接
- 仅全片首尾淡入淡出，检查中段无异常长静音；对白侧链压低采用平滑恢复，避免逐句抽吸式音量跳变
- 转折与剧情对齐
- 即使指定纯器乐，也必须做 ASR
- 检出人声时重生成或做人声分离

命令示例：

```bash
CUDA_VISIBLE_DEVICES=2 python <PROJECT_ROOT>/aifilm_booklet/tools/generate_ace_music.py
```

运行前修改时长、乐器、情绪弧线、转折和输出前缀，确认属于当前项目。

输出：

```text
<PROJECT_ROOT>/output/audio/music/raw/
<PROJECT_ROOT>/output/audio/music/manifest.json
<PROJECT_ROOT>/output/audio/music_stem.wav
```

---

## S17 串轨清理与混音

Sound 或 Music 检出人声：

```text
确认不是 ASR 幻觉
→ 检听疑似时间段
→ 优先重生成
→ 仍存在时做人声分离
→ 只保留非人声或 instrumental stem
→ 再检查
```

Speech 必须是唯一可懂人声来源。

按 `speech_manifest.json` 最终时间码合成：

```text
<PROJECT_ROOT>/output/audio/speech_stem.wav
<PROJECT_ROOT>/output/audio/sound_stem.wav
<PROJECT_ROOT>/output/audio/music_stem.wav
<PROJECT_ROOT>/output/audio/final_mix.wav
```

混音规则：

- Speech 始终最清楚
- Speech 出现时，Sound 和 Music 侧链压低约 `3–6 dB`
- 环境声不能完全消失
- Music 不得压住对白
- 无重复对白、削波和长静音
- 逐 shot 检查最终混音对应区间：除剧本明确静默的镜头外，每个 shot 都必须有可听音频，不能只依赖“整片有音轨”作为通过依据
- 按 `speech_manifest.json` 和最终成片时间码核对 Speech 起止，不能切头、切尾、吞尾音或在 shot 拼接处截断
- 检查 Music stem 和 final mix 的波形 / 响度曲线，不能存在无剧情依据的异常长静音断层或突然掉声
- 最终约 `-16 LUFS`
- true peak 不高于 `-1.5 dBTP`

未通过逐 shot 可听音频、Speech 截断、Music 长静音、响度、削波、对白清晰度、串轨人声检查，不进入字幕和最终导出。

---

## S18 字幕

字幕以最终实际 Speech / 最终混音为准，不照抄旧剧本，也不得按 shot 边界、旧剧本估时或平均语速估算。

必须先对最终音轨执行 ASR / word timestamps 词级对齐，修正识别文字但保留真实时间戳；对争议时间点抽帧核验嘴型和画面动作后再烧录。

规则：

- 一条只表达一个主要意思
- 中文句中用逗号
- 普通陈述句结尾不加句号
- 问号和感叹号按语气保留
- 不显示情绪标签
- 与对白和动作同步
- 烧录前准备中文字体，例如 `Noto Sans CJK SC`
- 抽帧确认中文不是方框、无乱码、无缺字、不遮挡关键动作，并在手机和桌面端可读

输出：

```text
<PROJECT_ROOT>/output/others/movie.zh-CN.srt
```

---

## S19 最终 QC 与交付

默认最终交付规格：

```text
1920×1080
24fps
H.264 High
yuv420p
AAC-LC 48kHz 双声道
```

说明：SeedVR2 2× 可能先产出 `2048×1152` 等中间母版；除非用户明确要求交付 2K / 原生超分尺寸，最终字幕版和无字幕版都统一等比缩放 / 居中裁切到 `1920×1080`，并重新检查构图、字幕安全区、解码、哈希和公网资源一致性。

最终检查：

- 字幕版和无字幕版均可完整解码
- 音视频流、时长、分辨率、帧率和编码正确；默认最终交付为 `1920×1080 / 24fps`，若交付 2K / 原生超分尺寸必须有用户明确要求并在 manifest 中记录
- 无持续黑帧、长冻结和意外静音
- 叙事、人物、动作、道具和连续性正确
- `character_scale_qc.json` 对所有关键帧和视频抽帧均为通过
- 可见对白通过 H3 原生 speech 音画同步 QC
- 原生对白效果不好时已按 S11 最多重生成 `2` 次并择优
- Speech 清楚且与目标台词 / 说话角色一致
- 原生 Ref2VA 音轨无未授权背景音乐、环境声或音效污染
- Sound 和 Music 无可懂串轨人声
- 字幕内容、时间和中文字体正确
- 最终响度和 true peak 达标
- 逐 shot 音频完整性通过：每个 shot 的最终混音 / 成片对应区间都有可听音频，明确静默镜头除外
- Speech 完整性通过：按 `speech_manifest.json`、ASR word timestamps、波形和听检确认未被切头、切尾或在拼接处截断
- Speech 来源通过：最终 selected shot 和最终成片对应区间中的可懂人声，可追溯到已选 H3 Ref2VA 原始候选；构建日志和 manifest 不得引用替代人声文件
- Music 连续性通过：配乐 stem 和 final mix 不存在无剧情依据的异常长静音断层、突然掉声或未记录的空白段
- 公网资源一致性通过：前端实际解析出的最终视频 URL、逐 shot 视频 URL 均正确可访问、可播放，且不是旧缓存、占位文件或过期路径
- 公网 shot 与最终成片同源：每个公网 shot 的来源文件、哈希 / manifest 记录、生成批次与最终成片对应时间区间能追溯一致
- `manifest.json` 不记录密钥

检查命令：

```bash
ffprobe -v error -show_streams -show_format <PROJECT_ROOT>/output/final/movie_final.mp4
ffmpeg -v error -i <PROJECT_ROOT>/output/final/movie_final.mp4 -f null -
```

同样检查无字幕版。

生成：

```text
<PROJECT_ROOT>/output/final/movie_final.mp4
<PROJECT_ROOT>/output/final/movie_final_no_subtitles.mp4
<PROJECT_ROOT>/output/final/manifest.json
<PROJECT_ROOT>/output/others/qc_report.md
<PROJECT_ROOT>/output/others/shot_audio_qc.json
<PROJECT_ROOT>/output/others/public_asset_qc.json
<PROJECT_ROOT>/output/others/contact_sheet.jpg
```

除最终合成片外，还必须把所有最终 shot 视频同步到统一审查网页中：每个 shot 都要放上对应视频，方便逐镜回看和定位问题。

公网发布后不能把 CLI “部署成功”当成验收通过：必须绕过缓存下载公网 `storyboard.json`、最终片和关键 shot 文件，核对本地 / 远端 SHA-256，对公网成片执行 `ffprobe` 和完整 `ffmpeg -v error ... -f null -` 解码，并更新 `assetVersion`，防止浏览器继续使用旧视频。还必须在真实浏览器读取前端运行后最终解析出的 `src` / URL，确认最终片和每个 shot 视频 URL 指向本轮资源；对照 `manifest.json` 与 `storyboard.json` 记录，确认公网 shot 视频与最终成片对应区间同源。

`manifest.json` 记录输入、精确权重、seed、prompt、workflow、镜头选择、H3 原生对白重生成与择优结论、返修、三路声音、字幕、哈希和 QC，不记录密钥。

---

## 返修流程

```text
定位 shot 或时间码
→ 判断源头
→ 修复源头
→ 重做受影响的下游内容
→ 再做完整检查
```

源头可能是剧本、关键帧、H3、剪辑、Speech、原生对白同步、超分、Sound、Music、混音或字幕。

已通过 QC 的产物不重复生成；保留旧版本和修改说明；同一错误重复出现时修改 prompt、模型或工作流，不盲目重复相同 seed。只重做失败源头，但必须重建所有受影响下游产物；若内容返修改变任何镜头画面、时长、口型或剪辑点，必须同步重建 picture lock、字幕版、无字幕版、manifest、QC 和公网资源，并按需要废弃该镜超分结果。

---

## 完成标准

以下文件全部真实存在并通过 QC，才算完成：

```text
<PROJECT_ROOT>/output/final/movie_final.mp4
<PROJECT_ROOT>/output/final/movie_final_no_subtitles.mp4
<PROJECT_ROOT>/output/final/manifest.json
<PROJECT_ROOT>/output/others/movie.zh-CN.srt
<PROJECT_ROOT>/output/others/qc_report.md
<PROJECT_ROOT>/output/others/contact_sheet.jpg
```

最终汇报只说明发现的问题、导演取舍、已完成修改、QC 结果、分镜网页和最终成片路径。未真正完成时必须明确说明。

---

## 本项目经验补充：字幕、版本、QC 与公网交付

### 1. 字幕以最终音轨的词级时间戳为准

本项目早期按镜头区间安排字幕，出现字幕内容提前或滞后的问题。最终采用：

```text
最终混音
→ faster-whisper + VAD + word timestamps
→ 修正明显识别错误，但保留识别时间
→ 生成 SRT
→ 烧录
→ 对争议时间点逐帧抽查
```

不要用旧剧本时间、shot 边界或平均语速替代最终音轨对齐。

### 2. 内容返修后保留音轨，重建视频封装

当镜头时长和总时间线不变时，可保留已经确认的 `final_mix.wav` 和词级 SRT；替换画面后重新拼接 picture lock，再封装原音轨并烧录字幕。若镜头时长发生变化，则字幕、声音和所有后续时间码都必须重新计算。

### 3. 交付前必须保留确认版

在进行单镜返修、字幕重烧或超分前，备份：

```text
最终字幕版
最终无字幕版
manifest
storyboard.json
cloudbase-config.js
```

文件名或目录应包含日期和变更原因。新版本未通过远端验证前，不删除用户已满意的版本。

### 4. 超分版应使用独立文件名

推荐同时保留：

```text
movie_final.mp4                         # 用户确认的普通高清版
movie_final_seedvr2_2x.mp4              # 超分字幕版
movie_final_seedvr2_2x_no_subtitles.mp4 # 超分无字幕版
```

网页确认超分版无误后，再将 `storyboard.json.final_video` 指向超分文件。这样可快速回滚，避免覆盖唯一母版。

### 5. QC 不只检查“文件能播放”

最终检查至少包含：

- 20/20 逐镜可完整解码
- 每镜分辨率、帧率和目标时长准确
- picture lock 总时长准确
- 字幕版和无字幕版均完整解码
- 视频、音频流参数正确
- 关键动作阶段抽帧正确
- 每 6 秒或每镜中帧 contact sheet 无黑帧、坏帧和明显内容漂移
- 超分前后关键帧对比，确认不是单纯锐化过度或产生新伪影
- manifest 中记录模型、scale、源文件、输出文件、哈希和 QC

### 6. 公网部署采用“资源先行，元数据最后”

为避免网页先指向尚未上传完成的大视频：

```text
先上传新视频和 contact sheet
→ 验证资源存在
→ 上传 storyboard.json
→ 最后上传 cloudbase-config.js / 更新 assetVersion
```

大文件部署完成后不能只相信 CLI 成功提示，还必须：

1. 使用 cache-busting query 或 `Cache-Control: no-cache` 下载公网文件
2. 比较本地和远端 SHA-256
3. 对下载后的公网成片执行 `ffprobe`
4. 用 `ffmpeg -v error -i remote.mp4 -f null -` 完整解码
5. 检查公网 `storyboard.json` 的状态、最终视频路径和返修说明

CloudBase CLI 的列表校验可能因路径格式或缓存产生假阴性；以实际公网下载、哈希一致和完整解码作为最终依据。

### 7. 缓存与版本号

每次影响网页视频、分镜数据或配置的发布，都更新：

```javascript
assetVersion: "日期-变更名-rN"
```

网页视频 URL 应附带该版本号。用户反馈“没有变化”时，先核对远端哈希和资源版本，再判断是否生成或部署失败。

### 8. Speech 来源与三层 QC

混音前为每个带人声 shot 记录：

```json
{
  "shot_id": "shot_008",
  "speech_source": "h3_ref2va_native",
  "candidate_paths": ["..."],
  "candidate_sha256": ["..."],
  "asr_qc": "pass",
  "lip_sync_qc": "pass"
}
```

构建流程发现替代人声、外部 lip-sync 或旧成片对白来源时应停止。Foley 和 Music 混入前也要通过无人声检查。

ASR 必须比较：

```text
H3 原始候选原生音轨
→ 最终 selected shot
→ 最终成片对应时间区间
```

三层的内容、顺序、首尾和说话人应一致。近音字争议使用更高质量 ASR 和人工听检复核。

### 9. 固定公网入口

用户要求固定公网地址时，只向用户返回该入口；内部仍正常覆盖资源，并使用 cache-busting、远端 SHA-256 和完整解码验证更新是否生效。
