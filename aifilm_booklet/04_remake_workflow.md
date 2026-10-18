# 04｜电影 / 视频复刻专项攻略

## 1. 适用范围

当用户要求“复刻、重制、尽量还原、照着参考片重新生成”时，在正常 `S01–S19` 流程之外，必须同时执行本文件。

复刻不是只模仿色调或抽几张图重新生成，而是对原视频进行完整逆向拆解，再重建：

```text
故事与信息
→ 镜头结构
→ 人物视觉身份
→ 人物音色与表演
→ 场景和道具
→ 动作与运镜
→ Speech / Foley / Music
→ 剪辑、混音和字幕
```

参考视频必须位于当前 `<PROJECT_ROOT>/input/` 内，并确认属于用户自有、已授权或允许处理的素材。

---

## 2. 复刻硬规则

- 必须逐 shot 分析原视频，不能只按固定时间间隔机械切分
- 必须先理解每个 shot 讲了什么，再写复刻剧本和生成提示词
- 原视频的镜头数量、切点、时长、景别、构图、动作、对白、声音和叙事作用都要记录
- 不因 AI 生成方便而随意改写剧情、人物关系、动作顺序或镜头功能
- 每个 shot 可以使用一张或几张参考图；数量由身份、场景、道具、姿态、首尾状态和风格约束决定
- 有可见对白的 shot 必须使用 H3 Ref2VA 原生 Speech；原生 speech 合格时直接作为 speech stem，不另生成替代人声。优先通过更精确的 Ref2VA / H3 prompt 修正原生对白与表演，写清谁在说话、嘴部可见性、台词起止、语速、停顿、情绪、头部 / 嘴部动作和其他角色闭嘴
- 原生对白效果不好时，同一问题镜头最多重生成 `2` 次；必须保留初版和所有重生成版本的 seed、prompt、原生音轨与 QC 结论，并选择综合效果最好的一版
- H3 原始候选和带对白的 selected 审查文件必须保留原生音轨，不能在 Speech QC 前用 `-an` 删除
- 后期声音制作默认指补 `Foley / Sound` 与 `ACE Music`，再与原生 `Speech` 做最终混音；不得另生成替代人声
- 原生 Speech 的来源、有效性、返修和 QC 按 `02_video_speech_picturelock.md` 执行；混音来源审计按 `03_audio_delivery_qc.md` 执行
- 最新批注覆盖旧 prompt；电视 / 监控中的可见播报员须同时记录声音来源、可见性和口型要求
- Foley / Sound 与 ACE Music 必须独立生成、独立检查、独立输出 stem
- 原视频完整混合音轨只能作为听觉分析、时间对齐和音色参考，不能默认直接替代 `Speech + Foley + Music` 标准流程
- 只有用户明确要求“直接保留原声”时，才允许把原视频完整音轨用于最终成片，并必须在 manifest 和 QC 报告中明确记录
- 原视频自带字幕、水印、平台标识或乱码文字不能进入生成参考资产；应先重绘或清理
- 复刻目标是叙事、人物、表演、镜头和声音的高一致性，不是逐像素复制压缩噪声、水印或平台 UI

---

## 3. 第一步：完整审计参考视频

先提取并记录：

- 文件路径、SHA-256、时长、分辨率、帧率、编码、音频采样率和声道
- 画幅比例、黑边、裁切和镜头方向
- 是否存在烧录字幕、水印、平台标识、片头片尾或重复画面
- 主要角色、次要角色、旁白、广播和画外音
- 主要场景、关键道具、服装和状态变化
- 音乐段落、环境声、动作音效、对白和静默区间
- 原片是否有镜间闪变、坏帧、音画不同步或剪辑错误

建议输出：

```text
<PROJECT_ROOT>/output/others/remake_source_media_info.json
<PROJECT_ROOT>/output/others/remake_source_analysis.md
<PROJECT_ROOT>/output/others/remake_pyscenedetect_candidates.csv
<PROJECT_ROOT>/output/others/remake_cut_candidates.json
<PROJECT_ROOT>/output/frames_review/remake_contact_sheet.jpg
<PROJECT_ROOT>/output/frames_review/remake_cut_candidate_contact_sheet.jpg
<PROJECT_ROOT>/output/audio/asr/remake_source_words.json
```

参考片含对白时，应先提取音频并执行带 word timestamps 的 ASR。ASR 结果只能作为草稿，必须结合原声听辨和画面字幕人工修正。

---

## 4. 第二步：逐 shot 拆解

### 4.1 切点原则

复刻时必须先执行 `PySceneDetect` 生成候选切点，再人工校正；`PySceneDetect` 结果只能作为参考，不能直接当作最终 shot map。

推荐命令：

```bash
scenedetect -i <PROJECT_ROOT>/input/reference.mp4 detect-adaptive list-scenes save-images
```

必要时可追加 `detect-content` 对照，但两类结果都只作为候选：

```bash
scenedetect -i <PROJECT_ROOT>/input/reference.mp4 detect-content --threshold 27 list-scenes save-images
```

正式镜头切点只以真实剪辑 / 转场为准，候选判断包括：

- 画面硬切、叠化、闪白、遮挡转场
- 明确的剪辑点或后期拼接点
- 通过转场导致场景、人物或时间发生变化

以下情况不能单独作为切镜依据，即使 `PySceneDetect` 报出候选也必须人工排除：

- 同一连续镜头内的机位运动、推拉摇移、变焦或景别变化
- 同一镜头内人物进入 / 离开画面、动作阶段变化或信息重点变化
- 同一连续镜头内音乐、音效或环境声变化
- 闪光、爆炸、遮挡、快速运动、屏幕大面积亮度变化造成的误检

必须导出每个候选切点前后帧对照图，人工确认后再写入正式 `remake_shot_map.json`。不要为了凑固定时长，把一个完整长镜头切断，也不要把两个真实转场分隔开的镜头合并。

### 4.2 每镜必须回答的问题

对每个 shot 逐项回答：

1. 这个镜头在讲什么？
2. 它推进了什么剧情或信息？
3. 画面主体是谁？其他人物在做什么？
4. 开始状态、触发、主要动作、次级反应和结束状态是什么？
5. 景别、机位、焦段感、运镜和前后景视差是什么？
6. 角色的脸、发型、体型、服装、位置、视线和情绪是什么？
7. 场景的空间结构、出入口、光源和关键道具在哪里？
8. 谁在说话？是正脸、侧脸、背面、画外音还是广播？
9. 环境声、动作音效和音乐分别是什么？
10. 如何承接上一镜，如何进入下一镜？

### 4.3 逐镜分析结构

建议写入：

```json
{
  "id": "shot_001",
  "source_start": 0.0,
  "source_end": 5.2,
  "duration_sec": 5.2,
  "narrative_function": "本镜传递的信息和剧情作用",
  "picture": "人物、场景、构图、光线和关键物体",
  "action": "动作主体与开始、过程、结束",
  "camera": "景别、机位、运镜、焦点和视差",
  "dialogue": [],
  "sound": {
    "speech": "",
    "ambience": "",
    "foley": "",
    "music": ""
  },
  "continuity_in": "",
  "continuity_out": "",
  "must_show": [],
  "must_not_show": [],
  "reference_assets": [],
  "frame_strategy": {
    "mode": "reference_only",
    "end_frame_required": false
  }
}
```

输出：

```text
<PROJECT_ROOT>/output/others/remake_shot_map.json
<PROJECT_ROOT>/output/others/remake_shot_analysis.md
```

---

## 5. 第三步：把分析写成可执行复刻剧本

复刻剧本不能只是原视频内容摘要。每个 shot 必须包含模型可执行的信息：

- 精确时长和原片时间码
- 地点、时间、天气和环境状态
- 角色身份、服装、位置和开场姿势
- 动作主体和非主体限制
- 按顺序描述的分时动作
- 镜头景别、机位、运镜、焦点和视差
- 台词、说话人、起止时间和是否可见嘴部
- Speech、Foley、环境声和 Music 的设计
- 上一镜入点和下一镜出点
- 必须出现、禁止出现和负面约束
- 图像 prompt、视频 prompt 和所有参考图用途

复刻剧本仍须输出：

```text
<PROJECT_ROOT>/output/script_tot.md
<PROJECT_ROOT>/output/script_episode1.md
<PROJECT_ROOT>/output/script_episode2.md
...
<PROJECT_ROOT>/output/others/continuity_bible.md
<PROJECT_ROOT>/output/others/shot_plan.json
```

如果原片镜头密集，可按叙事段落拆 episode，但不得改变原始镜头顺序和全片时间线。

---

## 6. 第四步：人物视觉建模

每个主要人物建立独立角色 Bible：

- 身份、性别和年龄感
- 正脸结构、侧脸轮廓、肤色和面部特征
- 发型、发色、眼镜、胡须和妆容
- 身高、体型、肩宽、头身比和人物间比例
- 固定服装、鞋子、饰品和随身道具
- 常用表情、动作习惯和身体姿态
- 不同剧情状态下允许发生的变化

主要人物至少准备：

```text
正面三视图参考
侧面三视图参考
背面三视图参考
全身比例参考
脸部近景
关键表情 / 动作参考
固定服装和道具参考
```

建立：

```text
<PROJECT_ROOT>/output/others/character_bible.md
<PROJECT_ROOT>/output/images_prepare/character_lineup.png
<PROJECT_ROOT>/output/others/character_scale_bible.json
<PROJECT_ROOT>/output/others/character_scale_qc.json
```

复刻时人物不能只在单镜内相似，还要跨镜保持脸、年龄、发型、体型和服装一致。

---

## 7. 第五步：人物音色建模

逐个识别所有 `Speech` 来源，不把旁白、广播混称为人物。必须按类型分开记录：

- `on_screen_character`：画面内对白人物
- `voice_over`：旁白 / 画外音
- `broadcast`：广播
- `device_voice`：电话、电视或对讲机声音
- `crowd_speaker`：群体中需要辨识的主要说话人

每个说话来源记录：

- 性别和年龄感
- 音高、音色厚薄、明亮度和气息感
- 语速、停顿、重音和尾音
- 情绪强度和说话方式
- 口音、咬字和特殊习惯
- 可用的干净音色参考片段及时间码

输出：

```text
<PROJECT_ROOT>/output/others/voice_bible.json
<PROJECT_ROOT>/output/audio/voice_references/
```

音色参考应尽量：

- 单人说话
- 无音乐或音乐很弱
- 无明显混响、噪声和其他人物重叠
- 至少包含足够长的连续语句
- 保留原始采样率版本，并另存清理后的标准参考版本

H3 Ref2VA 原生 Speech 应模仿角色音色和说话表演。返修只通过改进 Ref2VA / H3 prompt 与重生成解决：明确说话者、画面位置、嘴部可见性、台词起止、语速、停顿、情绪、头部 / 嘴部动作和其他角色闭嘴。原生 Speech 出现漏字、改词、音色漂移、说话者错误或音画不同步时，同一问题镜头最多重生成 `2` 次，并在初版与重生成版本中选择综合效果最好的一版。

---

## 8. 第六步：场景与道具建模

主要场景必须记录：

- 平面关系、出入口和人物活动区域
- 摄影轴线和常见机位
- 墙面、地面、门窗和大型结构
- 主光源、辅光源、色温和时间
- 关键道具的位置、尺寸和状态
- 前后镜头中允许变化和不得变化的内容

关键道具必须记录：

- 外形、材质、颜色、尺寸和磨损状态
- 与人物的比例
- 被谁拿、放在哪里、如何运动
- 前后镜头的状态变化

输出：

```text
<PROJECT_ROOT>/output/others/scene_bible.md
<PROJECT_ROOT>/output/others/prop_bible.md
<PROJECT_ROOT>/output/images_prepare/scenes/
<PROJECT_ROOT>/output/images_prepare/props/
```

---

## 9. 第七步：为每个 shot 准备参考图

每个 shot 可以使用一张或几张参考图。

常见参考类型：

- `start_frame`：唯一的实际首帧锚点
- `end_frame`：严格连续性所需的尾帧
- `character`：人物身份、脸、服装或比例
- `scene`：场景结构、光线和空间关系
- `prop`：关键道具外形和状态
- `action`：动作姿态或人物接触关系
- `style`：色彩、材质和摄影风格

简单镜头可以只用一张；复杂镜头可组合几张，例如：

```text
Image 1：实际首帧和构图
Image 2：主角身份和固定服装
Image 3：场景空间结构
Image 4：关键道具造型
```

所有图片写入 `shot_plan.reference_assets`：

```json
[
  {
    "path": "output/images_prepare/shot_001_start.png",
    "role": "start_frame",
    "note": "锁定实际首帧构图、机位和人物位置"
  },
  {
    "path": "output/images_prepare/characters/doctor_front.png",
    "role": "character",
    "note": "锁定医生脸部、年龄、发型和服装"
  }
]
```

原视频抽帧如果带字幕、水印、平台标识或错误文字，必须先清理或重绘，不能直接作为最终生成锚点。

---

## 10. 第八步：视频提示词与 H3 生成

视频 prompt 应尽可能贴近原镜头，并按以下顺序编写：

```text
参考图 / 参考视频的用途
→ 人物与场景身份
→ 开场状态
→ 动作主体锁定
→ 分时动作
→ 运镜和视差
→ 表情与情绪
→ 道具和接触关系
→ 对白与声音约束
→ 结束状态
→ 必须出现
→ 禁止出现
```

复刻 shot 使用参考视频时，应明确：

- `<Video 1>` 是原镜头的动作、运镜、构图和节奏参考
- `<Picture 1>`、`<Picture 2>` 等分别约束什么
- `<Audio 1>` 是音色 / 表演参考还是需要复制的音频
- 哪些内容完全保留，哪些内容需要替换或清理

每个 shot 默认生成两个 MiniMaxH3 Turbo 候选，改为“同目标双 prompt 变体候选”：两个候选保持同一版已确认参考输入、同一剧情目标、同一台词 / Speech 要求、同一关键动作与连续性约束、同一帧数与同一分辨率，但允许在不违背批注的前提下，为候选 B 设计受控 prompt 变体，例如动作幅度、表演细节、镜头距离、节奏停顿、起止姿态或情绪强度的小差异；候选 A 默认更稳、更贴近主 prompt，候选 B 默认提供可比较的替代解法。公网审查中选择一个作为主候选，另一个标记为 `pass`。两个 H3 原始候选都必须保留：

```text
视频流
原生 Speech / 原生音频流
完整模型输出时长
seed
prompt
参考输入
workflow
```

不得在 Speech 提取和 QC 前用 `-an` 删除原生音轨。若需要纯画面 picture-lock 文件，应另外生成无音频派生版本。

对白 shot 生成前保存最终实际 prompt，并按 `02_video_speech_picturelock.md` 检查可朗读正文、批注冲突、说话人可见性和口型。电视新闻等嵌套屏幕人物可独立生成动态内容层，但最终 Speech 必须来自该 H3 候选自身的原生音轨。

---

## 11. 第九步：标准声音复刻

标准声音流程是：

```text
H3 Ref2VA 原生 Speech
→ 独立 Foley / Sound
→ 独立 ACE Music
→ 三路 stem 混音
```

术语固定：`Speech` 是人物对白、旁白、广播等可懂人声；`Foley / Sound` 是环境声、动作音效、机械声、脚步、风声、爆炸等非人声声音；`Music` 是配乐和氛围音乐；`Mix` 是把三路 stem 做音量、空间、响度和淡入淡出的最终混音。

### Speech

- 使用 H3 Ref2VA 原生 Speech，不另生成替代人声
- 原生 Speech 合格时直接作为 `speech_stem.wav`
- 检查台词准确性、音色、说话角色、情绪、起止和口型
- 检查有效响度、额外 Speech，以及候选、selected shot、最终成片区间的三层一致性
- 原生 Speech 不佳时，先完善 Ref2VA / H3 prompt 并最多重生成 `2` 次
- 必须保留初版和所有重生成版本的 seed、prompt、原生音轨与 QC 结论，并选择综合效果最好的一版
- 多人嘴型难以稳定时使用说话人隔离的 H3 原生分段，每段独立通过 QC

### Foley / Sound

逐镜生成：

- 环境底噪
- 脚步、衣料、道具接触和机械声
- 空间混响和远近关系
- 剧情需要的冲击、警报、交通、雨水或生物声

必须排除可懂人声和音乐。

### ACE Music

按全片情绪曲线独立生成：

- 类型、乐器、速度和调性
- 每个叙事段落的进入、发展、转折和结束
- 对白期间保持稀疏
- 严禁歌词、哼唱和可懂人声

最终必须真实存在：

```text
<PROJECT_ROOT>/output/audio/speech_stem.wav
<PROJECT_ROOT>/output/audio/sound_stem.wav
<PROJECT_ROOT>/output/audio/music_stem.wav
<PROJECT_ROOT>/output/audio/final_mix.wav
```

不得用两个静音占位 stem 加一条原片混合音轨冒充三路声音制作。

---

## 12. 第十步：逐镜 QC 与相似度检查

每个 shot 至少检查首、中、尾帧。复杂动作、对白、人物接触和关键道具镜头检查 `8–12` 个阶段帧。

### 画面检查

- 镜头讲述的信息是否与原片一致
- 人物身份、年龄、脸、发型、服装和体型
- 场景结构、道具位置和比例
- 动作主体、动作顺序和结束状态
- 景别、机位、方向、运镜、速度和视差
- 光线、色调、天气和材质
- 是否出现字幕、水印、平台标识或乱码
- 是否有手脚错误、穿模、瞬移、冻结或反物理运动

### 声音检查

- 台词是否准确
- 音色和情绪是否接近目标角色
- 说话者归属和口型是否正确
- 每个 shot 在最终混音 / 成片对应区间是否真正有可听音频，不能只检查整片存在音轨
- Speech 是否被切头、切尾、吞尾音，或在 shot 拼接处被截断
- Foley 是否匹配动作、材质和空间
- Music 是否匹配原片情绪和转折，是否存在无剧情依据的异常长静音断层
- 是否有串轨人声、重复对白或音乐压住对白

建议维护逐镜相似度记录：

```json
{
  "shot_id": "shot_001",
  "story_match": "pass",
  "composition_match": "pass",
  "character_match": "pass",
  "action_match": "pass",
  "camera_match": "pass",
  "speech_match": "pass",
  "foley_match": "pass",
  "music_match": "pass",
  "continuity_match": "pass",
  "issues": []
}
```

只重做失败镜头，但必须重建受影响的 picture lock、声音、字幕、最终片、manifest、QC 和公网资源。

---

## 13. 公网审查页面

复刻项目的统一页面必须简化展示，逐镜只放：

- 原片信息和复刻目标的必要摘要
- 角色 / 场景 / 道具参考图
- 每个 shot 的原片时间码、生成方式和必要元信息
- 一张或几张参考图及逐图用途
- 参考声音及逐段用途
- `image_prompt`、`video_prompt`，提示词正文直接可编辑，其中 Video Prompt 使用较大的编辑框；不展示重复的 Ref2VA / H3 Prompt，也不单独放返修意见框
- 每个 shot 的两个 MiniMax 候选视频、主候选选择、另一个候选的 `pass` 结论，以及选中视频、最终成片和无字幕版（已有时展示）
- 每张参考图下方一个可编辑框，每段参考声音下方一个可编辑框，每个候选视频下方一个可编辑框
- 全局确认 / 其他说明

逐镜页面不要再展示“画面、动作、运镜、对白 / 声音”等拆分卡片，也不要放逐字段修改框或单独的提示词返修框。

部署后必须在真实浏览器执行前端，不能只检查文件返回 `200`。至少验证：

```text
JavaScript 无运行时错误
storyboard 正常加载
镜头数量正确
最终视频正常显示
参考图没有缺失
前端最终解析出的实际视频 URL 正确、可访问、可播放，且不是旧缓存或占位路径
公网每个 shot 视频与最终成片对应区间同源：来源文件、生成批次、哈希 / manifest 记录和时间码能对应
审查意见 GET / POST / GET 持久化成功
```

---

## 14. 复刻完成标准

除正常 S19 文件外，还必须具备：

```text
<PROJECT_ROOT>/output/others/remake_source_analysis.md
<PROJECT_ROOT>/output/others/remake_shot_map.json
<PROJECT_ROOT>/output/others/character_bible.md
<PROJECT_ROOT>/output/others/voice_bible.json
<PROJECT_ROOT>/output/others/scene_bible.md
<PROJECT_ROOT>/output/others/prop_bible.md
<PROJECT_ROOT>/output/others/remake_similarity_qc.json
```

完成时必须确认：

- 每个原片 shot 都有对应复刻 shot
- 原片与复刻版总时间线对应
- 主要人物完成视觉建模和音色建模
- 每镜参考图数量合理、用途明确
- H3 原生 Speech 已提取并通过 QC；不合格镜头已按最多 `2` 次重生成择优并记录最佳版本
- Foley 和 ACE Music 已独立生成并通过人声污染检查
- 三路 stem 和最终混音真实存在
- 每个 shot 的最终混音 / 成片对应区间都有可听音频，明确静默镜头除外
- Speech 没有被切头、切尾、吞尾音或在 shot 拼接处截断
- Music 没有无剧情依据的异常长静音断层
- 字幕按最终音轨词级对齐
- 字幕版、无字幕版和所有逐镜文件完整解码
- 公网页面前端实际解析出的最终片和逐 shot 视频 URL 正确，且公网 shot 与最终成片对应区间同源
- 公网审查页在真实浏览器环境初始化成功

若以上任一项缺失，不得声称“完全按照 booklet 完成复刻”。
