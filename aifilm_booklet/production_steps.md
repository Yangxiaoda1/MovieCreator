# AI 电影制作流程索引

> 本文件是主入口，只保留阶段顺序、进度判断和应读取的细节文件。  
> 不依赖 `<PROJECT_ROOT>/script.md` 判断进度。执行或回答“做到哪里了”时，先看本文件、`<PROJECT_ROOT>/output/others/pipeline_state.json` 和实际产物。  
> 细节拆成少量扁平文件，全部位于 `<PROJECT_ROOT>/aifilm_booklet/`，不再按很多 Skill 文件夹拆分。

`<PROJECT_ROOT>` 指当前项目目录，`interaction_xxx<剧名>/` 等命名；执行命令时需替换为真实目录名。

---

## 00. 初始化
<PROJECT_ROOT>/
|-aifilm_booklet
    |-...
|-input（建立空的子文件夹）
    |-roles
    |-scenes
    |-other
    script.md

初始化只负责建立当前项目的输入 / 输出骨架，不生成剧本、不补写设定、不读取 `<PROJECT_ROOT>/` 外素材。

## 0. 全局硬规则

- 只使用 `<PROJECT_ROOT>/` 目录内的剧本、角色、场景和素材
- 剧本来源为 `<PROJECT_ROOT>/input/script.md`
- 严禁读取、引用、合并或复用 `<PROJECT_ROOT>/` 外的其他项目剧本、分镜、角色设定、场景设定或媒体素材
- 不移动、不覆盖用户输入文件；所有新产物进入 `<PROJECT_ROOT>/output/`
- 不把密钥写入日志、网页、manifest、提示词或媒体元数据
- 恢复任务时先读状态和现有产物，只继续未完成阶段
- 已通过 QC 的产物不重复生成
- 外部脚本参考统一看 `<PROJECT_ROOT>/aifilm_booklet/tools/`
- 统一审查网页默认做 CloudBase 公网部署，本地预览仅作为上线前检查 / fallback；最小可参考模板统一看 `<PROJECT_ROOT>/aifilm_booklet/tools/vis/`，新项目的 `<PROJECT_ROOT>/output/vis/` 应优先从该模板复制和改造，不直接复用其他项目的真实环境配置、日志或素材
- 每轮返修前必须读取公网审查 API 最新数据，以返回的 `updatedAt`、全片意见、参考图下方意见、参考声音下方意见、视频下方意见和提示词正文修改为准；不得依赖旧截图、本地缓存或过期 `review_notes.json`；必须与本地返修记录做差异比较，只处理真正新增或变化的内容
- 生成图片或视频时，PE（Prompt Engineering）必须尽量丰富具体，包含角色身份、外观、服装、场景空间、光线色调、镜头景别、机位、运镜、分时动作、情绪、道具、连续性、必须出现 / 禁止出现内容和负面约束，不要只写一句笼统描述
- 动作描述必须同时写清“做什么”和“谁来做”：多人镜头用画面位置、姿势、接触物、服装 / 身份特征锁定动作主体，并写明非主体保持什么状态；复杂动作按 3–5 段顺序写清开始、过程和结束
- 避免“像动图”：不能只依赖整图推拉、局部漂移或灯光变化；视频 prompt 必须包含主体位移、重心变化、肢体动作、前后景视差、物理因果和明确开始 / 结束状态
- 生图时提示词必须明确加入 `no text, no watermark, no logo`；输出图像不得包含水印、平台标识、乱码文字、字幕或无关文字元素
- S05 所有资产建设都按“资产 Bible + 可视参考包 + 用途记录”组织：角色不止三视图，还应按剧情需要补全全身比例、脸部近景、关键表情 / 动作、固定服装、饰品、随身道具和状态变化；场景记录全景、轴线 / 方向、出入口、光源、关键细节和稳定比例参考物；道具记录外形、材质、尺寸、状态变化和交互方式；声音记录来源、类型、音色、语速、情绪和可用参考片段。后续用到什么资产就提前生成或整理什么资产，包括 Ref2VA 参考图、`start_frame` / `start_plus_end_frame` 所需首帧、必要尾帧 / 衔接帧、`reference_only` 所需普通参考图；不要无目的泛生成，也不要等到视频生成时才临时补关键图片
- 每个 shot 的参考图可以是一张，也可以是几张，数量按镜头约束需要决定，不设“每镜只能一张”的限制。简单镜头可只用一张主要首帧或普通参考图；涉及角色身份、场景结构、关键道具、服装、动作姿态、比例或风格联合约束时，应组合使用几张参考图。每张图必须标明用途，避免堆入重复、冲突或无关参考图
- `start_frame` 的“首帧”通常只有一张实际首帧锚点，但可以同时附加几张角色 / 场景 / 道具 / 风格参考图；附加图片不得冒充首帧。`start_plus_end_frame` 使用一张实际首帧和一张必要尾帧，也可再附加几张普通参考图。`reference_only` 可以使用一张或几张普通参考图
- 可视化审查中必须标注每个 shot 的生成方式：有说话 / 可见对白的 shot 必须用 Ref2VA；没有说话的 shot 按 `frame_strategy` 在 `start_frame`、`start_plus_end_frame`、`reference_only` 或 `Ref2VA non-dialogue` 中选择；`reference_only` 是参考图生成，不要求伪装成首帧，但必须标明“参考图，非首帧”
- 每个 shot 默认生成 `2` 个 MiniMaxH3 Turbo 候选结果，改为“同目标双 prompt 变体候选”：两个候选必须基于同一版已确认参考图、同一剧情目标、同一台词 / Speech 要求、同一关键动作与连续性约束、同一帧数与同一分辨率，但允许在不违背批注的前提下，为候选 B 设计受控 `video_prompt` 变体，例如动作幅度、表演细节、镜头距离、节奏停顿、起止姿态或情绪强度的小差异；候选 A 默认更稳、更贴近主 prompt，候选 B 默认提供可比较的替代解法。两个候选都必须记录各自最终实际 prompt、variant note、seed / candidate id；不得改变角色身份、场景、台词、关键情节点或用户未要求修改的已确认内容。公网审查页必须并排或分组展示两个候选，支持选择一个作为主候选，并把另一个标记为 `pass`
- 视频生成必须符合客观规律：人物运动、物体受力、重力、速度、尺度、透视、光影、因果关系、动作连续性和空间关系都要合理，不得出现无剧情依据的瞬移、穿模、漂浮、尺寸突变、反物理运动或前后状态矛盾
- 术语必须区分：`Speech` 指人物对白、旁白、广播等可懂人声，但记录时必须分清 `on_screen_character`、`voice_over`、`broadcast`、`device_voice` 等来源，不能写成“人物或广播”这种混合描述；`Sound / Foley` 指环境声、动作音效、机械声、脚步、风声、爆炸等非人声声音；`Music` 指配乐和氛围音乐；`Mix` 指最终混音。本册不另生成替代人声；`Speech` 默认来自 H3 Ref2VA 原生对白
- 有说话 / 可见对白的 shot 默认保留 H3 Ref2VA 原生 `Speech`，原生 speech 合格时直接作为 speech stem；后期声音制作默认只补 `Sound / Foley` 与 `Music`，再与原生 `Speech` 混音。原生对白效果不好时，优先通过更完备的 H3 / Ref2VA prompt 修正：写清谁在说话、嘴部是否可见、台词起止、语速、停顿、情绪、头部 / 嘴部动作和其他角色闭嘴；同一问题镜头最多重生成 `2` 次，并在初版与重生成版本中选择综合效果最好的一版
- `Speech` 来源是硬门禁：音轨存在不等于有效原生人声；候选必须通过来源、响度、ASR、听检、说话者和口型检查。不合格时只能改 prompt 后重生成，不得使用替代人声或外部口型模型补救
- 最新公网批注覆盖旧 prompt。执行前必须删除被新意见推翻的旧 action、camera、dialogue、sound 和 continuity，形成唯一无冲突的最终 prompt
- 只有 `<d>[Chinese] ...</d>` 中的文字允许成为 Speech；声音来源、人物是否可见和是否需要口型必须分开记录
- 多人口型反复失败时，优先使用说话人隔离构图或 H3 原生分段生成，非说话者的脸 / 嘴不入画
- 每轮单镜返修前先保存所有 `selected/shot_*.mp4` 的 SHA-256；完成后只允许目标 shot 哈希变化。若其他已确认 shot 发生变化，必须停止部署并回滚
- H3、超分、Sound、Music、混音等长任务不要只说“后台执行”；必须在 `tmux` 会话中运行，会话名包含 `minimax` 和当前 episode / 阶段，并持续打印进度，方便判断是否卡住
- 长任务开始前必须先清理旧 GPU / 生成相关进程：`pkill -f start.sh`、`pkill -f see_gpu.sh`、`pkill -f train_gpu_50.py`、`bash <PROJECT_ROOT>/aifilm_booklet/tools/dist_stop_gpu.sh`
- H3 输出略长时不得直接截尾
- 返修必须同步公网意见、返修记录、完整 prompt、实际执行 plan、`shot_plan` 和 storyboard / 网页说明
- 单镜返修只重生成失败镜头，但必须重建所有受影响下游产物：该镜 picture-lock 文件、全片合成片、字幕版、无字幕版、manifest、QC 和公网资源
- 字幕必须依据最终音轨做 ASR / word timestamps 词级对齐；不得按 shot 边界或旧剧本估算
- 最终 QC 不能只检查总时长、解码、音轨存在和文件哈希；必须逐 shot 验证：每个 shot 在最终混音 / 成片对应区间有可听音频，Speech 没有被切头切尾或截断，Music 没有异常长静音断层，公网 shot 与最终成片对应区间同源，前端实际解析出的视频 URL 正确可访问且不是旧缓存
- SeedVR2 只能在用户明确确认最终画面版后执行，且必须按 shot 管理、逐镜记录 manifest、逐镜验收；任一镜头后续内容返修，只废弃并重做该镜超分结果，再重建超分 picture lock 和最终片
- SeedVR2 断点续跑只能在 `status=completed`、输出可完整解码、分辨率与时长合格、当前输入 SHA-256 等于 manifest 记录时跳过；记录缺失、输入变化或 QC 未过必须重做
- 复刻项目必须先执行 `PySceneDetect` 生成候选切点和前后帧对照图，再确认真实剪辑 / 转场；`PySceneDetect` 结果只作参考，不能把机位、景别、人物、动作或声音变化误当成切镜
- 测试视频、低清预览、`picture_lock`、临时混音不得称为最终成片

---

## 1. 进度判断格式

```text
现在做到 SXX：阶段名称。
当前具体状态：pipeline_state.json 的 stage/status，或根据产物反推。
已完成：列出已存在且通过检查的关键产物。
下一步：列出接下来要做的 1–3 件事。
注意：门禁、缺素材、QC 未过、用户确认未完成、需重生成或最终文件未解码。
```

---

## 2. 细节文件索引

| 阶段 | 内容 | 读取文件 |
| --- | --- | --- |
| S01–S06 | 输入审计、故事方案、角色 / 场景 bible 草案、剧本、shot plan、图像资产、分镜网页、统一用户确认 | `<PROJECT_ROOT>/aifilm_booklet/01_planning_assets_review.md` |
| S06 网页模板 | 默认公网审查部署、审查页前端、CloudBase HTTP API、静态托管配置模板、本地预览 fallback | `<PROJECT_ROOT>/aifilm_booklet/tools/vis/README.md` 与 `<PROJECT_ROOT>/aifilm_booklet/tools/vis/` |
| S07–S14 | H3 候选前准备、候选、逐 shot 网页审查、候选 QC、最终镜头、H3 原生 Speech 定稿、原生对白同步 QC、picture lock、超分 | `<PROJECT_ROOT>/aifilm_booklet/02_video_speech_picturelock.md` |
| S15–S19 | Sound、Music、串轨清理、混音、字幕、最终 QC、manifest、contact sheet、交付 | `<PROJECT_ROOT>/aifilm_booklet/03_audio_delivery_qc.md` |
| 复刻专项 | 原视频逐镜拆解、复刻剧本、人物与音色建模、多图参考、H3 原生 Speech、独立 Foley / ACE Music、相似度 QC | `<PROJECT_ROOT>/aifilm_booklet/04_remake_workflow.md` |

当用户提出“复刻、重制、尽量还原、照原片生成”等要求时，必须先读取 `04_remake_workflow.md`，再按 S01–S19 执行；专项规则与通用规则同时生效。

---

## 3. S01–S19 流水线

```text
S01 输入审计与恢复
→ S02 故事梗概、导演方向、角色 / 场景方案
→ S03 角色 / 场景 bible 草案，不单独停顿
→ S04 完成完整剧本、按集拆分剧本、continuity bible、shot plan
→ S05 角色、场景、道具、Ref2VA 参考图、按策略所需首帧 / 普通参考图 / 必要尾帧与比例 QC
→ S06 分镜网页与统一用户确认
→ S07 H3 候选前准备
→ S08 按当前 episode 进行 H3 候选生成与逐 shot 网页审查
→ S09 候选 QC、逐 shot 选择与粗剪
→ S10 Turbo 8 steps 最终镜头确认 / 必要重跑
→ S11 Speech 定稿，H3 Ref2VA 原生对白为准，效果不好最多重生成 2 次并择优
→ S12 H3 原生对白音画同步 QC
→ S13 最终 picture lock
→ S14 SeedVR2 超分或经验证的高分辨率方案
→ S15 Sound / Foley
→ S16 Music
→ S17 串轨清理、三路 stem 与最终混音
→ S18 字幕
→ S19 最终 QC、manifest、contact_sheet 与交付
```

---

## 4. 统一确认门禁

只保留一次用户确认：`S06 分镜网页与统一用户确认`。

`S06` 一次性确认：

- 角色
- 场景
- 剧本
- `shot plan`
- 分镜
- 角色 / 场景 / 道具参考图
- 每个 shot 的生成方式和全部对应展示图：参考图可以是一张或几张；`start_frame` / `start_plus_end_frame` 必须展示唯一的实际首帧锚点，其他角色 / 场景 / 道具 / 风格图分别标明用途；`reference_only` 可展示一张或几张普通参考图，但每张都必须标明“不是首帧”
- 严格连续性镜头的必要尾帧 / 衔接帧
- 每个 shot 在网页中对应展示的参考图、用途、提示词和待确认项
- Ref2VA 输入方案

S06 页面必须能看到完整静态审查内容，但逐镜区只展示参考图 / 首尾帧 / 普通约束图、参考声音及其用途、`image_prompt`、`video_prompt` 和必要元信息；不展示重复的 Ref2VA / H3 Prompt，也不要再拆成“画面、动作、运镜、对白 / 声音”等卡片。提示词本身做成可直接修改的编辑区，其中 Video Prompt 使用较大的编辑框，不再单独设置“提示词返修意见框”；每张参考图下方放一个可编辑框，每段参考声音下方放一个可编辑框；进入 S08 后，生成视频区展示每个 shot 的两个 MiniMax 候选，每个候选下方放一个可编辑框，并提供主候选选择与另一个候选 `pass` 的记录入口。若任一 shot 缺少其生成方式要求的对应参考图 / 参考声音，未展示全部实际输入素材及其用途，或角色 / 场景 / 道具参考图缺失且未明确标为用户待补充，则不得进入第一次交互确认。

搭建 `<PROJECT_ROOT>/output/vis/` 时默认按公网审查部署处理，优先参考 `<PROJECT_ROOT>/aifilm_booklet/tools/vis/`：先复制最小模板，再替换 `public/storyboard.json`、`public/assets/`、`public/cloudbase-config.js` 和 `cloudbaserc.json`。必须配置 CloudBase HTTP API 与静态托管，生成可分享公网审查地址；本地预览只用于上线前检查或公网异常 fallback。不得复制其他项目的真实 `envId`、`apiUrl`、桶名、部署日志或素材。

部署前必须依次执行 `python sync_public.py`、`python validate_vis.py`、
`node --check public/app.js` 和 `find public/assets -type l`；任一校验失败都
不得进入 S06。每次部署递增 `assetVersion` 和静态资源 query 版本，部署后
必须执行真实 DOM 初始化测试及 API GET / OPTIONS / POST 测试，不能只以
首页或资源返回 HTTP 200 判定成功。

用户明确确认后，角色 / 场景 bible、剧本、shot plan、分镜和参考图同时锁定，才能进入 `S07 H3 候选前准备`。页面能打开、意见为空、用户只说“看到了”都不算确认。

---

## 5. 初始剧本分集规则

`10 个 shot` 的限制要在初始剧本阶段完成，而不是到视频生成时才临时切批。

在 `S04` 输出剧本时必须同时生成：

```text
<PROJECT_ROOT>/output/script_tot.md
<PROJECT_ROOT>/output/script_episode1.md
<PROJECT_ROOT>/output/script_episode2.md
<PROJECT_ROOT>/output/script_episode3.md
...
```

规则：

- `script_tot.md` 是完整总剧本和全片总 shot plan
- 每个 `script_episodeN.md` 是一集，通常 `1–2` 分钟
- 每集不超过 `10` 个 shot
- 每镜通常 `3–15` 秒，只承载一个主要动作
- 每镜必须推进情节、传递信息、塑造人物、建立情绪或完成转折
- 后续 `S05–S14` 默认按 episode 推进：先完成 `script_episode1.md` 对应资产、候选、QC、Speech、picture lock，再汇报并申请是否开启下一集
- 全片维护一个统一审查网页，网页内部按 episode 分区展示各集 shot 的参考图、参考声音、提示词、两个候选版本、各自 prompt 变体说明、seed、主候选选择和另一个候选的 `pass` 结论
- 所有 shot 最终视频生成完成后，除形成最终合成片外，还必须同步到统一审查网页中，每个 episode / shot 都要放上对应两个候选视频和最终选中视频
- 每集结束后必须把本集 shot 加入审查网页，补齐逐 shot 参考图、提示词、两个候选视频、主候选 / pass 结论，汇报本集已完成、存在问题和建议重生成项
- 未经用户明确同意，不自动启动下一集；若用户明确要求一次性生成多集，则可连续处理用户指定的多个 episode，但仍按 episode 分区记录和汇报

---

## 6. 最终完成标准

以下文件全部真实存在、可完整解码并通过 QC，才算完成：

```text
<PROJECT_ROOT>/output/final/movie_final.mp4
<PROJECT_ROOT>/output/final/movie_final_no_subtitles.mp4
<PROJECT_ROOT>/output/final/manifest.json
<PROJECT_ROOT>/output/others/movie.zh-CN.srt
<PROJECT_ROOT>/output/others/qc_report.md
<PROJECT_ROOT>/output/others/contact_sheet.jpg
```

---
