# 02｜S07–S14 视频、Speech、口型与画面锁定

## 覆盖阶段

```text
S07 H3 候选前准备，不生成低清测试视频
S08 按集 H3 候选生成与逐 shot 网页审查
S09 候选 QC、逐 shot 选择与粗剪
S10 Turbo 8 steps 最终镜头确认 / 必要重跑
S11 Speech 定稿，H3 Ref2VA 原生对白为准，效果不好最多重生成 2 次并择优
S12 H3 原生对白音画同步 QC
S13 最终 picture lock
S14 SeedVR2 超分或经验证的高分辨率方案
```

---

## H3 总策略

当前 H3 视频生成采用用户指定的 MiniMaxH3 Turbo 版本，默认 `8 steps` 采样，作为本项目当前交付路径。除该指定 Turbo workflow 外，不得静默切换其他压缩、量化、蒸馏或 LoRA 权重。文件名命中以下标记时，必须确认是否为当前指定 Turbo workflow，否则只用于非交付测试或工作流验证：

```text
pruned int8 nvfp4 awq convrot lightning lora
```


质量阶梯：

```text
静态分镜审查通过
→ S07 H3 候选前准备，不生成低清测试视频
→ S08 MiniMaxH3 Turbo，8 steps，按 episode 生成候选
→ S09 逐 shot QC、选择与粗剪
→ S10 Turbo 8 steps 最终镜头确认 / 必要重跑
```

分辨率策略：

- 候选默认：`1024×576`
- 候选细节难判断：`1280×720`
- 普通最终镜头：`1024×576` + SeedVR2 2× 得到 `2048×1152` 中间母版
- 近景对白、复杂动作、道具接触、关键转折：`1280×720`，按项目需要再超分或统一交付规格
- 极关键英雄镜头：仅经 A/B 确认后使用 `1344×768`
- 最终交付默认统一为 `1920×1080`；`2048×1152` 只作为超分中间母版或用户明确要求的 2K 版本，交付前需等比缩放 / 居中裁切到 `1920×1080` 并重新检查构图、字幕和边缘
- 超分不能修复脸崩、手崩、口型错误、身份漂移、动作变形或场景结构错误

H3 原生工作流参考：

```text
UNETLoader
→ CLIPLoader(type=minimax)
→ MiniMaxH3ImageToVideo 或 MiniMaxH3ReferenceToVideo
→ BasicGuider + RandomNoise
→ KSamplerSelect(res_multistep)
→ BasicScheduler(simple, stage_steps, denoise=1.0)
→ SamplerCustomAdvanced
→ 视频和音频 VAE Decode
→ CreateVideo(24fps)
→ SaveVideo
```

规则：帧数满足 `17k+5`；`124` 帧约 5 秒，`362` 帧约 15 秒；H3 `video_prompt` 必须写到约 `100–300` 个中文字，尽量丰富具体，使用"身份与场景约束 → 开场状态 → 动作主体锁定 → 分时动作和运镜 → 表情 / 情绪 → 道具与接触关系 → 对白 / 声音 → 结尾状态 → 必须出现 / 禁止出现内容 → 排除项"。有对白镜头必须额外写清说话者在画面中的位置、朝向、嘴部是否清晰可见、台词起止时间、语速、停顿、情绪、头部 / 嘴部动作，以及其他角色保持闭嘴或仅做无声反应，优先让 H3 Ref2VA 一次生成画面和原生 Speech。每个 shot 的视频描述都要尽可能丰富，不能只写一句笼统动作描述。多人镜头必须写清执行动作的是谁，使用位置、开场姿态、接触物、服装 / 身份特征和非主体限制消歧，例如 shot 必须明确"左侧偏中、双手按桌并俯身的指挥官"依次完成撑桌俯身 → 站直 → 搓下巴 → 回头看屏幕，右侧站立人员不得抢动作。视频生成必须符合客观规律，人物运动、物体受力、重力、速度、尺度、透视、光影、因果关系、动作连续性和空间关系都要合理。

---

## S07 H3 候选前准备

只做正式候选前的非生成检查：

- 确认 S06 已明确通过，角色 / 场景 bible、剧本、shot plan、分镜和参考图已锁定
- 开始前先清理旧 GPU / 生成相关进程，防止残留任务占卡或阻塞：

```bash
pkill -f start.sh
pkill -f see_gpu.sh
pkill -f train_gpu_50.py
bash <PROJECT_ROOT>/aifilm_booklet/tools/dist_stop_gpu.sh
```

- 确认 MiniMaxH3 Turbo workflow、模型路径、8 steps 采样参数、参考图路径、输出目录、帧数、分辨率、prompt 字段齐全
- 确认队列、端口、GPU、显存、磁盘和日志路径可用
- 确认不会写入或覆盖已通过 QC 的产物

准备检查通过后，直接进入 S08 正式候选生成。

---

## S08 按集候选生成与逐 shot 网页审查

采用 MiniMaxH3 Turbo 版本，默认 `8 steps` 采样；每个 shot 默认生成 `2` 个 MiniMax 候选结果，改为“同目标双 prompt 变体候选”：两版必须基于同一版已确认参考图、同一剧情目标、同一台词 / Speech 要求、同一关键动作与连续性约束、同一帧数与同一分辨率，但允许在不违背批注的前提下，为候选 B 设计受控 `video_prompt` 变体，例如动作幅度、表演细节、镜头距离、节奏停顿、起止姿态或情绪强度的小差异；候选 A 默认更稳、更贴近主 prompt，候选 B 默认提供可比较的替代解法。两个候选都必须保存各自最终实际 prompt、variant note、seed / candidate id；不得为了凑候选改变角色身份、场景、台词、关键情节点或用户未要求修改的已确认内容。这里的 `2` 仅指视频候选数量，不代表每个 shot 只能使用两张参考图。每个 shot 可以输入一张或几张参考图，必须按 `reference_assets` 逐张传入并在 prompt 中说明用途；简单镜头可只用一张，身份、场景、道具、姿态或风格需要联合约束时使用几张。有说话 / 可见对白的 shot 必须使用 Ref2VA 输入方案；没有说话的 shot 按 `frame_strategy` 执行：`start_frame` 用一张实际首帧约束，并可附加几张普通参考图；`start_plus_end_frame` 用一张首帧 + 一张尾帧约束，并可附加几张普通参考图；`reference_only` 用一张或几张普通参考图生成且不把它们当首帧；`Ref2VA non-dialogue` 用一张或几张参考图、参考视频或其组合驱动无对白画面。

按当前 `<PROJECT_ROOT>/output/script_episodeN.md` 分集执行；`02_video_speech_picturelock.md` 阶段只读取并处理当前 episode 中已经列出的 shot。全片维护一个统一审查网页，网页内部按 episode 分区展示本集 shot 的参考图、提示词、候选版本和候选结论。默认每集结束后向用户汇报本集结果，并申请是否开启下一集；若用户明确要求一次性生成多集，则可连续处理用户指定的多个 episode，但仍必须在统一审查网页中按 episode 分区记录。

输出：

```text
<PROJECT_ROOT>/output/video_raw/candidates/
```

生成完一个 episode 之后，就在统一审查网页的对应 episode 分区增加条目：参考图、参考声音、提示词、两个候选视频、候选版本、各自 prompt 变体说明、seed、关键信息、QC 状态、主候选选择和另一个候选的 `pass` 结论。

是否通过仍以最新公网审查 API、用户明确确认和内部 QC 共同判断。如果有问题，必须写明问题、时间码 / 帧位、处理建议和是否需要重生成。每次交互后必须读取公网审查 API 的最新原始数据，以 `updatedAt`、全片意见、参考图下方意见、参考声音下方意见、视频下方意见和提示词正文修改为准；与本地返修记录比较后，只针对新增或变化的意见修改 prompt、执行计划和网页说明。

---

## S09 候选 QC 与粗剪

每镜先完整解码，再抽首 / 中 / 尾帧；关键动作、近景、对白、道具接触镜头展开 `8–12` 帧。

检查：

- 动作是否完成
- 人物身份、年龄、服装和体型
- 角色比例、脚底接地、与场景稳定参考物的相对尺度
- 手脚、道具和接触关系
- 多余人物、重复人物和瞬移
- 反轴、闪烁、冻结和坏帧
- 相邻镜头动作、视线、位置、方向和光线
- 对白时段说话者是否正脸、侧脸、背面或被遮挡

只重做失败镜头。H3 输出略长时，不能用 `ffmpeg -t` 直接截尾；应先保留完整生成动作。选中候选规范化到准确时长后输出：

```text
<PROJECT_ROOT>/output/video_raw/selected/shot_*.mp4
<PROJECT_ROOT>/output/video_raw/picture_lock_preview.mp4
```

`picture_lock_preview` 只是粗画面锁定，不是最终成片。

---

## S10 Turbo 8 steps 最终镜头确认 / 必要重跑

已通过 S09 QC 的候选可作为最终镜头来源；需要重跑或修复时，仍采用 MiniMaxH3 Turbo 版本，默认 `8 steps` 采样。除非用户明确要求，不切换到 35 / 50 steps 或完整非 Turbo 权重。英雄近景、复杂动作和关键转折若 Turbo 结果不满足，再单独向用户说明问题并请求是否改用更高成本方案。

返修时必须同步五处执行真相：公网最新意见、`revision_notes_by_shot.json`、完整 `video_prompt` / 参考图解析、实际 `shot_plan_h3.json` / 执行 plan、`storyboard.json` / 网页说明。生成前打印最终送入模型的 prompt；若只改说明文档而没有更新生成器读取的 `shot_plan` 或 prompt 文件，禁止开跑。

输出：

```text
<PROJECT_ROOT>/output/video_raw/final_h3/
```

所有 shot 最终视频生成完成后，必须同步到统一审查网页中：放上每个 shot 对应的视频文件，便于逐镜查看，不只生成最终合成片。单镜返修只重生成失败镜头，但重生成后必须重建该镜 `selected/` 与 `picture_lock/` 文件、全片 picture lock、字幕版、无字幕版、manifest、QC 报告和公网资源；不得只替换单镜网页视频而遗漏受影响下游产物。

---

## 长任务执行与多卡调度

所谓"后台执行"统一改为 `tmux` 会话中执行，不使用不可见的裸后台任务。会话名必须包含 `minimax`、当前 episode 和阶段，例如 `minimax_ep01_candidates`。

`tmux` 会话中必须先进入项目根目录并激活 `minimaxh3` 环境：

```bash
tmux new-session -s minimax_ep01_candidates
cd /apdcephfs_gy2/share_302507476/xiaodayang/aimovie
source /apdcephfs_gy2/share_302507476/xiaodayang/miniconda3/bin/activate minimaxh3
source <PROJECT_ROOT>/aifilm_booklet/tools/source_aimovie_env.sh
```

生成命令必须把日志写入 `<PROJECT_ROOT>/output/others/`，并实时打印进度。进度至少包含：当前 episode、当前 shot、已完成 / 总数、当前输出文件、最近错误，目前是第几步。建议所有生成脚本输出类似：

```text
[episode 01][shot 003][candidate 1/2][done 5/20] output=<PROJECT_ROOT>/output/video_raw/candidates/episode01/shot_003_cand01.mp4 operation_steps=13
```







---

## S11 Speech

`Speech` 只指人物对白、旁白、广播等可懂人声，但记录时必须分清来源：`on_screen_character` 是画面内人物，`voice_over` 是旁白 / 画外音，`broadcast` 是广播，`device_voice` 是电话 / 电视 / 对讲机声音；不能写成“人物或广播”这种混合描述。默认使用 H3 Ref2VA 原生 speech，不另生成替代人声。

流程：

```text
清理角色参考音色
→ 单次 Ref2VA 生成同镜多角色画面与原生对白
→ 提取原生音轨
→ ASR / 听感 / 说话角色归属 / 音画同步 QC
→ 原生音轨合格时直接作为 speech stem
→ 原生对白不佳时完善 H3 / Ref2VA prompt，最多重生成 2 次
→ 在初版和重生成版本中选择台词、音色、说话者归属、情绪、起止和口型综合最优的一版
```

原生 speech 合格时必须保留并进入最终混音；后期声音制作只补 Sound / Foley 和 Music。原生对白效果不好时，优先通过改进 H3 / Ref2VA prompt 修正；prompt 必须精确描述画面内谁在说话、嘴部可见性、台词起止、语速、停顿、情绪、头部 / 嘴部动作和其他角色闭嘴。同一问题镜头最多重生成 `2` 次，必须保留初版和所有重生成版本的 seed、prompt、原生音轨与 QC 结论，并选择综合效果最好的一版。

Ref2VA prompt 要求：固定 `(S1)`、`(S2)`；每句用 `<d>[Chinese] ...</d>`；明确开始时间、说话人、说话人当时的头部朝向、嘴部是否可见、口型开合状态、语速 / 停顿 / 情绪，明确其他角色闭嘴或只做无声反应；明确 `Only clean character dialogue is audible. No ambient sound, no Foley, no sound effects, no non-diegetic music.`

补充硬规则：

- 只有 `<d>[Chinese] ...</d>` 是可朗读正文；角色名、制作说明和 continuity 不得写成潜在台词
- `source_type`、`on_screen`、`lip_sync_required` 分开记录；可见电视主播不能按纯画外广播处理
- 被误读成旁白的说明必须从所有 prompt 字段中删除或改写，不能只追加否定词
- 多人口型失败时，可拆成短 H3 原生段并使用说话人隔离构图；每段保留自身原生音轨和 QC 记录

必须生成：

```text
<PROJECT_ROOT>/output/audio/speech_manifest.json
```

记录每句的 `shot_id`、说话角色、目标台词、实际 ASR、开始 / 结束、来源音轨、是否分离 / 降噪、音画同步 QC 和通过状态。

---

## S12 H3 原生对白音画同步 QC

所有可懂人声均以 H3 Ref2VA 原生 speech 为准，不跑外部口型模型，也不另生成替代人声。

检查重点：

- 对白起止与嘴部开合一致
- 闭唇音、停顿和情绪与画面动作一致
- 说话者归属正确，非说话角色不跟嘴
- 台词没有漏字、改词、吞尾音或被剪断
- 原生音轨没有未授权背景音乐、环境声或音效污染
- 音频流真实可听，不能因为容器存在 AAC stream 就判定有声
- ASR 没有检测到角色标签、制作说明、旧 continuity、重复句或其他额外 Speech
- 原始候选、selected shot 和最终成片对应区间的 ASR、首尾和说话人一致
- 近音字争议结合高质量 ASR 与人工听检，不能只凭单一转写
- 非说话者闭嘴要求按实际 Speech 时间段检查，不能只看一张中间帧

未通过时回到 S11：完善 H3 / Ref2VA prompt 后最多重生成 `2` 次，并在初版与重生成版本中选择综合效果最好的一版。必须记录每次重生成的原因、seed、prompt、原生音轨路径和 QC 结论。

---

## S13 最终 picture lock

最终画面锁定版由：

- 有对白镜头：通过 H3 原生对白音画同步 QC 的 `selected/`
- 无对白镜头：已选候选

输出：

```text
<PROJECT_ROOT>/output/video_raw/picture_lock/shot_*.mp4
<PROJECT_ROOT>/output/video_raw/picture_lock.mp4
```

---

## S14 超分

输入当前最终 picture-lock 源文件：

```bash
bash <PROJECT_ROOT>/aifilm_booklet/tools/run_seedvr2_upscale.sh \
  <PROJECT_ROOT>/output/video_raw/picture_lock/shot_001.mp4 \
  --scale 2
```

优先 H3 稳定原生分辨率 + SeedVR2 2×；不默认强行 H3 2K。SeedVR2 只能在用户明确确认最终画面版后执行；"画面锁定"表示每个 `selected/shot_*.mp4` 的动作主体、动作过程、运镜、构图、连续性、口型和准确时长都已通过 QC，之后不再修改 H3、关键帧、剪辑点或原生对白。返修或 H3 原生对白重生成后，只废弃并重新超分受影响镜头，再重拼超分 picture lock 和最终片。

检查人脸、嘴、牙齿、眼睛、手指、细线、文字、闪烁和色彩漂移。

输出：

```text
<PROJECT_ROOT>/output/resolution/picture_lock.mp4
```

---

## 本项目经验补充：视频生成、返修与超分

### 1. 避免"动态图片感"

以下做法容易产生"动图"或动态海报感：

- 只做缓慢数字推拉
- 整张画面一起平移
- 主体几乎静止，仅云雾、灯光或粒子变化
- 动作没有明确起点、过程和终点

改进 Prompt 时应至少加入两类真实运动：

- **主体运动**：人物重心和肢体变化、车辆位移、空间站旋转、对接器靠近、火箭离台
- **空间运动**：前景快速移出、中景和背景形成不同速度的视差，或固定机位下主体穿越画面

需要固定镜头时，应明确"镜头不动，运动来自主体"，避免模型用镜头晃动代替动作。

### 2. 动作主体消歧

多人镜头的 Prompt 应使用位置、姿势、服装、接触关系共同锁定主体。例如：

```text
动作主体只能是画面左侧偏中、双手按桌并俯身的人
不是右侧原本站立的人
其余人物只做克制辅助动作，不得抢占主体
```

复杂动作按时间顺序写成 3–5 段，并在生成后抽取对应阶段帧检查。

### 3. 保留完整生成动作，不硬截尾

H3 输出常比目标时长多出少量帧。旧做法直接：

```bash
ffmpeg -i raw.mp4 -t 6 ...
```

可能把"落地、回头、分离"等动作结尾裁掉。推荐：

1. `ffprobe` 获取实际时长
2. 计算 `speed = source_duration / target_duration`
3. 视频使用 `setpts=PTS/speed`
4. 音频使用合法范围内的 `atempo=speed`
5. 最后再限制为目标时长并检查首尾帧

### 4. Prompt 源必须只有一个执行真相

返修后要同步：

```text
公网最新意见
→ revision_notes_by_shot.json
→ video_generation_prompts.json / 参考图解析文档
→ shot_plan_h3.json 的实际 video_prompt
→ 生成 workflow
→ storyboard.json 的 revision_note
```

生成前应打印最终送入模型的 prompt，防止"文档已改、执行计划仍旧"的情况。

### 5. 单镜返修的下游依赖

单个 shot 重生成后，至少重新执行：

```text
selected shot QC
→ 该镜 1920×1080 picture-lock 规范化
→ 全片 picture lock 重拼
→ 字幕版 / 无字幕版重建
→ manifest 与 QC 更新
→ 网页镜头和最终片同步
```

其余已通过镜头不重复生成，但不能只替换网页中的单镜文件而忘记最终合成片。

### 6. SeedVR2 超分实践

- **进入条件**：用户明确确认最终画面版本；所有 `selected/shot_*.mp4` 已通过动作、运镜、身份、连续性、口型、解码和时长 QC；picture lock 的镜头顺序与时长已冻结。只完成内部 QC、用户尚未确认，不能视为内容锁定。
- **执行粒度**：以锁定后的 `selected/shot_*.mp4` 为唯一输入，一镜一任务执行 SeedVR2 2×；`1024×576` 源镜头超分得到 `2048×1152 / 24fps` 逐镜中间母版，禁止直接把整片合成文件作为唯一超分任务。
- **逐镜验收**：每个超分镜头必须可完整解码；中间母版按实际超分结果记录分辨率和帧率，`1024×576` 源镜头对应 `2048×1152 / 24fps`，最终交付版默认再统一到 `1920×1080 / 24fps`；时长误差小于 `0.05s`，并抽查首、中、尾和关键动作阶段，确认无新增脸崩、手崩、结构变形、闪烁、色偏或动作截断。
- **记录字段**：manifest 至少保存输入路径及 SHA-256、模型和 VAE、scale、seed、ComfyUI 端口、workflow、开始 / 完成时间、原始输出、规范化输出、输出 SHA-256、`ffprobe` 和 QC 状态。
- **断点续跑判定**：仅当该镜 `status=completed`、输出存在且可完整解码、分辨率和时长 QC 通过，并且当前输入 SHA-256 与 manifest 记录一致时才跳过。不能只凭"目标文件存在且大于某个大小"判断完成。
- **输入失效规则**：如果某镜后续重做 H3、关键帧、口型或剪辑，即使文件名不变，只要输入哈希变化，该镜原超分结果立即失效；只重做受影响镜头，随后重拼超分 picture lock、字幕版、无字幕版并更新 manifest。
- **最终合成**：20/20 逐镜均通过后，严格按锁定 shot 顺序拼接超分 picture lock，挂载已确认的最终音轨和词级字幕，再检查全片分辨率、帧率、120 秒时长和完整解码。
- 逐镜超分比直接处理 120 秒整片更容易多卡并行、准确恢复、定位失败和保持镜头时长
- 超分输出也可能有轻微时长差异，应保留完整超分动作并等速适配到 shot 目标时长
- 超分后重点检查脸、手、细线、舱体结构、红灯闪烁、字幕边缘、色彩漂移和镜间闪变
- 超分必须在内容最终确认后进行；任何 H3 或口型返修都会使对应超分镜头失效

### 7. 长任务调度

- 四卡并行时采用线程队列，每张卡对应独立 ComfyUI 端口
- 每个 shot 完成后立即落盘并原子更新 manifest
- 恢复任务时先核对输入 SHA-256，再按上述断点条件决定跳过或重做
- 进度汇报使用"完成数 / 总数、运行镜头、失败数"，不要只说"仍在后台"
- 开跑前检查端口队列为空、GPU 可用和磁盘空间；结束后确认 `completed == shot_count` 且 `failed == 0`

### 8. 原生 Speech 来源与有效性

每个带 Speech 的最终 shot 应维护来源链：

```text
最终 selected shot
→ 使用的 H3 原始候选或原生分段候选
→ 每个候选的 seed / prompt / workflow / SHA-256
→ 候选原生音轨 ASR 与听检
→ selected shot ASR
→ 最终成片对应区间 ASR
```

建议生成 `native_speech_manifest.json`。构建流程若读取替代人声或外部 lip-sync 产物，应立即失败。

音轨存在不等于有有效 Speech，至少检查：

```bash
ffprobe -v error -show_streams -show_format shot.mp4
ffmpeg -i shot.mp4 -vn -af volumedetect -f null -
ffmpeg -i shot.mp4 -vn -af silencedetect=n=-45dB:d=0.15 -f null -
```

目标对白区间必须非全静音、无异常削波，并经 ASR 和听检确认完整。

### 9. 口型与嵌套屏幕策略

非说话者反复跟嘴时，优先让其脸、嘴、倒影或监控画面不入画；说话人使用单人近景。将错误对象排除出画面，通常比继续堆叠否定词稳定。

电视、监控或手机中的人物既要身份稳定又要口型同步时，可独立生成动态“屏幕内容层”，再合成回外层场景。要求：

- 同一主播、同一脸、同一服装、同一演播室和同一机位
- H3 原生 Speech 与可见嘴型同步
- 屏幕内容持续动态，不得冻结

最终 Speech 必须来自该内容层的 H3 原生音轨；合成前后检查身份、动态和完整 ASR。
