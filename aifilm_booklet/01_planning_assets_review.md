# 01｜S01–S06 前期方案、资产与统一确认

## 覆盖阶段

```text
S01 输入审计与恢复
S02 故事梗概、导演方向、角色 / 场景方案
S03 角色 / 场景 bible 草案，不单独停顿
S04 完成完整剧本、按集拆分剧本、continuity bible、shot plan
S05 角色、场景、道具、Ref2VA 参考图、按策略所需首帧 / 普通参考图 / 必要尾帧与比例 QC
S06 分镜网页与统一用户确认
```

---

## S01 输入审计与恢复

读取：

```text
<PROJECT_ROOT>/input/script.md
<PROJECT_ROOT>/input/roles/
<PROJECT_ROOT>/input/scenes/
<PROJECT_ROOT>/input/others/
<PROJECT_ROOT>/output/others/pipeline_state.json
<PROJECT_ROOT>/output/
```

记录故事、角色、音色、场景、道具、目标时长、画幅、语言、风格、GPU、磁盘和已有产物。若状态文件缺失或不可信，用实际产物反推。只继续未完成阶段。

硬规则：只使用 `<PROJECT_ROOT>/` 内素材；不从其他项目目录找替代剧本、角色、场景或媒体。

---

## S02 故事方案

提取：世界观、时代、地点、人物关系、主角目标、阻碍、代价、转折、主题、情绪曲线和结局。

把心理描写转成动作、表情、对白、环境或声音。可以从开场吸引力、信息密度、情绪节奏、冲突悬念和传播记忆点优化，但不得捏造现实事件或破坏人物逻辑。

---

## S03 角色 / 场景 bible 草案

整理但不单独停顿确认：

- 角色身份、年龄、脸、发型、体型、服装、随身物
- 角色关系、声线、语速、说话方式
- 场景出入口、轴线、道具位置、时间、光线、空间关系
- 时代、美术风格、色彩、镜头和声音风格

这些内容在 `S06` 统一确认前都属于待确认草案。

---

## S04 完整剧本、分集剧本、continuity bible、shot plan

输出到：

```text
<PROJECT_ROOT>/output/script_tot.md
<PROJECT_ROOT>/output/script_episode1.md
<PROJECT_ROOT>/output/script_episode2.md
<PROJECT_ROOT>/output/script_episode3.md
...
```

`script_tot.md` 是完整总剧本和全片总 shot plan；`script_episodeN.md` 是按集拆分后的执行单元。

分集规则：

- 每集通常 `1–2` 分钟
- 每集不超过 `10` 个 shot
- 每镜通常 `3–15` 秒，只承载一个主要动作
- 每镜必须推进情节、传递信息、塑造人物、建立情绪或完成转折
- 每个 shot 的描述必须尽可能丰富，`picture`、`action`、`camera`、`dialogue`、`sound`、`continuity_in/out`、`image_prompt`、`video_prompt` 都要具体到可执行，不写空泛句
- `action` 不只写“做什么”，还必须写清“谁来做”：用画面位置、开场姿势、接触物、服装 / 身份特征锁定动作主体，明确其他人物不得抢动作或只做辅助反应，并按开始状态 → 触发 → 主动作 → 次级响应 → 结束状态拆段
- 为避免“动态海报感”，`video_prompt` 必须包含主体位移、重心变化、肢体动作、前后景视差、物理因果和明确开始 / 结束状态；不要只写镜头推拉、局部漂移、云雾灯光变化
- 后续资产、视频、候选审查、Speech、picture lock 默认按集推进
- 每集完成后汇报“第*集已完成，请求开启下一集的制作”，如果用户说一次生成K集，则生成K集再交互。

Shot plan 结构：

```json
{
  "id": "shot_001",
  "duration_sec": 8,
  "location": "地点",
  "characters": ["角色"],
  "picture": "什么画面",
  "action": "动作主体是谁、按秒发生什么、非主体保持什么状态、动作结束到什么姿态",
  "camera": "景别、机位、运镜、前后景视差或固定机位约束",
  "dialogue": [{"speaker": "角色", "text": "台词", "start": 1.2, "end": 3.8}],
  "sound": {"speech": "", "ambience": "", "foley": "", "music": ""},
  "continuity_in": "入镜状态",
  "continuity_out": "出镜状态",
  "must_show": [],
  "must_not_show": [],
  "image_prompt": "",
  "video_prompt": "",
  "reference_assets": [
    {"path": "图片路径", "role": "start_frame | end_frame | character | scene | prop | style | action", "note": "该图具体约束什么"}
  ],
  "frame_strategy": {"mode": "start_frame", "end_frame_required": false, "end_frame_reason": "仅当严格连续性需要时填写"}
}
```

中文规范：用中文标点；普通陈述句结尾不加 `。`；问号和感叹号按语气保留；语音情绪标签不进字幕。

---

## S05 图像资产与关键帧

环境：

```bash
cd /apdcephfs_gy2/share_302507476/xiaodayang/aimovie
source /apdcephfs_gy2/share_302507476/xiaodayang/miniconda3/bin/activate minimaxh3
source <PROJECT_ROOT>/aifilm_booklet/tools/source_aimovie_env.sh
export AIMOVIE_IMAGE_MODEL=gpt-image-2
```

图像 provider 轮换：

```text
azure_openai → naci_default → openai（Open AI）→ azure_openai
```

规则：

- 所有资产建设都按“资产 Bible + 可视参考包 + 用途记录”组织，不只为凑单张图。角色、场景、道具、声音和逐 shot 参考都必须记录身份 / 结构 / 状态 / 用途 / 禁用项，并写入 `generated_asset_manifest.json` 或对应 bible，供后续 prompt、生成、QC 和网页审查复用
- 每个主要角色必须具备独立角色 Bible 和完整视觉参考包：正面、侧面、背面三视图是最低门槛，还应按剧情需要补全全身比例参考、脸部近景、关键表情 / 动作参考、固定服装、鞋子、饰品、随身道具和不同剧情状态变化；同时具备音色参考或明确标记待补充
- 若 `<PROJECT_ROOT>/input/roles/角色名/` 下缺少任一基础角度，必须在 S05 自动补生成，不得覆盖用户原图，并记录到 `<PROJECT_ROOT>/output/others/generated_asset_manifest.json`
- 若缺少音色参考，必须在 `generated_asset_manifest.json` 和 S06 审查网页中标记为待补充 / 待确认；没有可靠音色参考时，不得强行冒充已确认角色音色
- GPT Image 2 统一 `--quality medium`
- S05 按实际需要提前生成或整理静态图片资产：后续用到什么图片就生成什么图片，包括角色完整视觉参考包、角色表情 / 动作参考、场景全景、轴线 / 方向、关键细节、稳定比例参考物、剧情会涉及的状态变化、道具图、Ref2VA 参考图、`start_frame` / `start_plus_end_frame` 所需首帧、必要尾帧 / 衔接帧、`reference_only` 所需普通参考图；不要无目的泛生成，也不要等到视频生成时才临时补关键图片
- 每个 shot 的参考图可以是一张，也可以是几张，按实际约束复杂度决定。简单镜头可使用一张主要首帧或普通参考图；需要同时锁定角色身份、服装、场景结构、关键道具、动作姿态、比例或美术风格时，应组合几张参考图。不得为了凑数量重复添加，也不得混入构图、身份或风格互相冲突的图片
- `start_frame` 的实际首帧锚点通常是一张，但可同时附加几张角色 / 场景 / 道具 / 风格参考图；这些附加图必须明确标为普通约束图，不能称作首帧。`start_plus_end_frame` 使用一张实际首帧和一张必要尾帧，可再附加几张普通约束图。`reference_only` 可以使用一张或几张普通参考图
- 每张输入图都必须在 `shot plan.reference_assets` 和 `generated_asset_manifest.json` 中记录路径、`role` 与具体用途；多图编辑或 Ref2VA prompt 必须按图片编号逐张说明，例如 `Image 1: character identity`、`Image 2: location geometry`、`Image 3: prop design`
- 第一次交互（S06）前必须完成可审查静态资产闭环：`start_frame` / `start_plus_end_frame` shot 必须有一张明确的实际首帧参考图；`reference_only` shot 可无首帧，但必须有一张或几张普通参考图并逐张标明“参考图，非首帧”及用途；`frame_strategy.end_frame_required=true`、转场、接动作、出入画、道具状态或空间位置强连续的 shot 必须有必要尾帧 / 衔接帧；主要角色、主要场景和关键道具必须有参考图；这些图片必须写入 `generated_asset_manifest.json` 并同步到 `<PROJECT_ROOT>/output/vis/public/assets/`，供网页逐项展示
- 生成组图时，如果使用参考图或参考视频，必须先提取并记录其详细美术风格，再生成统一风格的组图；美术风格至少包含时代 / 类型、角色造型、服装材质、场景空间、色彩体系、光线方向、镜头语言、构图比例、材质质感、运动氛围、特效表现、禁用元素，并写入 `<PROJECT_ROOT>/output/others/art_style_bible.md` 或 `generated_asset_manifest.json`
- 图像 PE 必须尽量丰富具体，写清角色身份、年龄、脸、发型、体型、服装、道具、场景空间、光线、色调、构图、镜头方向、动作状态、连续性要求、必须出现 / 禁止出现内容和 `no text, no watermark, no logo`
- 多图编辑必须说明每张图用途
- 大多数镜头使用一张或几张参考图组合约束，常见组合是角色参考图 + 场景参考图 + 一张实际首帧或普通静态参考图；简单镜头也可以只用一张
- 不默认每镜首尾双关键帧
- 尾帧只用于严格连续性：转场、接动作、出入画、道具状态、空间位置或导演明确要求
- `shot plan` 必须标注 `frame_strategy`：`reference_only`、`start_frame`、`start_plus_end_frame` 或 `transition_bridge`

文生图示例：

```bash
python <PROJECT_ROOT>/aifilm_booklet/tools/gpt_image_gateway.py \
  --prompt "电影画面提示词，no text, no watermark, no logo" \
  --out <PROJECT_ROOT>/output/images_prepare/shot_001_start.png \
  --size 1536x864 --quality medium
```

参考图编辑示例：

```bash
python <PROJECT_ROOT>/aifilm_booklet/tools/gpt_image_gateway.py --edit \
  --image <PROJECT_ROOT>/input/roles/角色名/正面.png \
  --image <PROJECT_ROOT>/input/scenes/场景名/全景.png \
  --prompt "Image 1: character identity. Image 2: location. Preserve identity, wardrobe and geometry. 描述本镜。 No text, no watermark, no logo." \
  --out <PROJECT_ROOT>/output/images_prepare/shot_001_start.png \
  --size 1536x864 --quality medium
```

缺失资产可自动补齐，但不得覆盖用户原图；补图写入：

```text
<PROJECT_ROOT>/output/others/generated_asset_manifest.json
```

多角色项目必须建立：

```text
<PROJECT_ROOT>/output/images_prepare/character_lineup.png
<PROJECT_ROOT>/output/others/character_scale_bible.json
<PROJECT_ROOT>/output/others/character_scale_qc.json
```

比例规则：同景深角色相对身高、肩宽和头身比偏差，除已记录透视解释外，不得超过 `8%`。

图像 QC 两轮：

1. 逐图检查脸、年龄、体型、服装、手脚、动作、道具来源、场景结构、空间关系、比例、光线、文字和水印
2. 相邻镜头并排检查身份、机位方向、光线色调、道具状态、出入画方向和角色尺度连续性

静态参考输入有错时，先修普通参考图、首帧或必要尾帧，再重做视频。

---

## S06 分镜网页与统一确认

网页目录：

```text
<PROJECT_ROOT>/output/vis/
├── public/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── cloudbase-config.js
│   └── assets/
│       ├── characters/          # 角色三视图、表情 / 动作、音色参考标记图
│       ├── scenes/              # 场景全景、轴线、关键方向、细节
│       ├── props/               # 道具参考图
│       ├── shots/               # 每个 shot 的首帧、普通参考图、必要尾帧 / 衔接帧
│       ├── audio/               # 每个 shot 的参考声音、音色参考或原片声音片段
│       └── reference/           # 用户输入参考素材、关键帧、参考声音或 contact sheet
├── app.py
├── run_vis.sh
├── sync_public.py
├── review_notes.json
└── cloudbaserc.json
```

`public/assets/` 必须是真实文件，不用软链接。

最小可参考模板统一维护在 `<PROJECT_ROOT>/aifilm_booklet/tools/vis/`：包含默认公网审查部署、审查页前端、`storyboard.json` 示例、`sync_public.py`、CloudBase HTTP API、静态托管配置和本地预览 fallback。新项目搭建 `<PROJECT_ROOT>/output/vis/` 时优先复制该模板，再按当前项目替换数据、素材和云端配置。

进入第一次交互前，S06 页面必须已经具备完整静态审查内容，不能只有文字说明或占位图：

- 总览区展示参考素材、故事方案、角色 / 场景 / 道具总览和资产完整性状态
- 角色区展示每个主要角色的完整视觉参考包：正面、侧面、背面三视图、全身比例、脸部近景、关键表情 / 动作、固定服装和随身道具；缺音色参考时必须标红为“待用户补充 / 待确认”
- 场景区展示每个主要场景的场景 Bible 与可视参考包：全景、轴线 / 方向、关键细节、稳定比例参考物、出入口、光源和允许变化状态
- 道具区展示会影响剧情或动作连续性的关键道具参考图，并标明外形、材质、尺寸、状态变化、交互方式和禁用变形
- 逐镜区按 episode / shot 展示：该镜使用的全部参考图及逐图用途、实际首帧或普通参考图、必要尾帧 / 衔接帧、`image_prompt`、`video_prompt` 和必要元信息；不要展示重复的 Ref2VA / H3 Prompt，也不要展示“画面、动作、运镜、对白 / 声音”等拆分卡片；提示词本身可直接修改，其中 Video Prompt 使用较大的编辑框；每张参考图下方放一个可编辑框；进入 S08 后，每个 shot 默认展示两个 MiniMax 候选视频，并支持选择一个作为主候选、将另一个标记为 `pass`
- 逐镜区必须明确标注生成方式：有说话 / 可见对白的 shot 标为 `Ref2VA dialogue`；无说话 shot 才可标为 `start_frame`、`start_plus_end_frame`、`reference_only` 或 `Ref2VA non-dialogue`
- `start_frame` / `start_plus_end_frame` shot 必须展示真实首帧参考图，并将其他附加参考图分别标明角色 / 场景 / 道具 / 风格等用途；`reference_only` shot 可无首帧，但必须展示其使用的一张或几张普通参考图并逐张标明“参考图，非首帧”；`frame_strategy.end_frame_required=true` 或强连续镜头必须同时展示尾帧 / 衔接帧
- 如果任一生成方式必需的图片缺失，不得进入第一次交互；应先回到 S05 补齐，或在用户明确要求“暂缺也可审查”时把缺失项醒目标红并阻止进入 S07

网页一次性展示并确认：角色 / 场景 / 道具参考图、每个 shot 使用的一张或几张参考图及逐图用途、实际首帧或普通参考图、必要尾帧 / 衔接帧、参考声音及用途、`image_prompt`、`video_prompt` 和生成方式。逐镜页面不展示重复的 Ref2VA / H3 Prompt，也不再放画面、动作、运镜、对白 / 声音的拆分展示和修改框；提示词正文直接可编辑，其中 Video Prompt 使用较大的编辑框；每张参考图下方放一个可编辑框，每段参考声音下方放一个可编辑框；进入 S08 后，生成视频区必须展示每个 shot 的两个 MiniMax 候选，用户可选择一个作为主候选并把另一个 `pass`，每个候选下方仍保留修改意见框；全局区只保留整体确认。

同步、本地预览与公网部署：

```bash
cd <PROJECT_ROOT>/output/vis
python sync_public.py
python validate_vis.py
node --check public/app.js
find public/assets -type l
VIS_PORT=8080 ./run_vis.sh
```

`validate_vis.py` 是 S06 强制门禁：必须确认 `storyboard.json` 结构正确、
所有 `assets/...` 引用均存在、JSON 中没有残留绝对路径或
`output/...` / `input/...` 本地路径、`app.js` 语法正确且
`ASSET_VERSION` 已定义、脚本加载顺序正确、`public/assets/` 无软链接、
正式 CloudBase 配置无占位值。任一 error 未清零，不得部署或请求用户确认。

`S06` 默认要完成 CloudBase 公网审查部署：静态网页发布到公网地址，审查意见通过 `storyboardReviewApi` 自动保存；本地预览只作为上线前检查或公网异常 fallback。

每次公网部署必须递增 `assetVersion` 及 `index.html` 的静态资源 query
版本号；部署后必须在真实 DOM 环境执行一次初始化测试，确认镜头卡和媒体
元素数量符合 storyboard、页面无“初始化失败”、控制台无 JavaScript
错误，并以页面 Origin 实测 API 的 GET / OPTIONS / POST。只看到 HTTP 200
不算通过。

公网审查 API 是用户意见的唯一最新来源。每轮返修或继续制作前，必须重新读取 API 返回的原始 JSON，记录 `updatedAt`、全片意见、参考图下方意见、视频下方意见、提示词正文修改和用户标识；与本地 `review_notes.json`、`revision_notes_by_shot.json`、执行计划和 storyboard 说明逐项比较，只处理真正新增或变化的意见。不得用旧截图、浏览器缓存或本地旧文件替代公网 API 数据。

确认门禁：公网页面资源能加载，审查意见能保存；必须等待用户明确确认。页面能打开、意见为空、用户只说“看到了”，都不算确认。确认后，角色 / 场景 bible、剧本、shot plan、分镜和参考图同时锁定，才能进入 `S07`。

CloudBase 公网审查细节默认参考 `<PROJECT_ROOT>/aifilm_booklet/tools/vis/README.md`、`cloudbaserc.template.json` 和 `functions/storyboardReviewApi/`，再结合当前 `<PROJECT_ROOT>/output/vis/` 内实际配置和脚本；不得把其他项目的真实 `envId`、`apiUrl`、桶名或部署日志写入模板。

---

## 本项目经验补充：前期规划、关键帧与审查意见

### 1. 关键帧必须为动作留下空间

- 首帧不能已经处于动作末态。例如坠落镜头应让天体“刚进入画面”，海啸镜头应从相对平静海面开始。
- 需要“伸出、靠近、升空、分离”的镜头，首帧必须处在动作开始之前，并给运动方向保留足够画面空间。
- 如果参考图本身不支持动作，应先重绘首帧，不要期待视频模型自动纠正错误初态。

### 2. Shot plan 要明确动作主体

多人镜头不能只写“他站起来”或“人物回头”，至少描述：

```text
主体在画面中的位置
开场姿态和接触物
服装或身份特征
其他人物应保持什么状态
分阶段动作顺序
动作结束时的朝向和姿态
```

本项目 shot_012 的有效写法是：“左侧偏中、双手按桌并俯身的指挥官，依次完成撑桌俯身 → 站直 → 搓下巴 → 回头看屏幕；右侧站立人员不得抢动作。”

### 3. 复杂动作必须拆成可核验阶段

“火箭发射”“空间站对接”“海浪冲毁道路”等描述过于笼统。应拆为：

- 开场状态
- 动作触发
- 主运动
- 次级响应
- 结束状态

这样既方便生成，也方便按首、中、尾及关键帧检查是否真的完成。

### 4. 公网意见是持续变化的数据

- 每轮工作开始先读取审查 API，而不是只读本地 `review_notes.json`
- 保存本轮返回的原始 JSON、`updatedAt` 和 `updatedBy`
- 将全局确认、参考图下方意见、参考声音下方意见、视频下方意见和提示词正文修改聚合成返修记录
- 与本地旧记录做差异比较，只处理新增或变化项
- 页面字段为空不代表删除意见，需结合更新时间和用户语义判断

### 5. 网页应帮助用户准确指认问题

多人镜头最好在参考图说明或提示词中标注“左侧按桌人物”“右侧白衣保安”等可辨识位置，避免“他”“这个人”等歧义。逐镜页面应按生成策略展示首帧或普通参考图、必要尾帧、视频（已有时）和提示词，让用户主要检查参考图是否齐全、用途是否正确、提示词是否准确。

### 6. 最新批注不是附加条件，而是新的执行真相

用户更新同一 shot 的意见时，不能把新句简单追加到旧 prompt 末尾：

```text
最新批注
→ 对比当前 shot plan
→ 删除旧冲突条款
→ 生成唯一最终 prompt
→ 打印并保存真正送入模型的 prompt
```

以时间最新、语义最具体的意见为准。被推翻的内容必须从 `shot_plan.json`、最终 prompt、storyboard 和实际 workflow 中同步删除。

若用户要求公网入口固定，则只向用户返回该入口；内部仍需执行缓存绕过和远端哈希验证。
