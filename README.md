# aifilm

用本地开源模型 + 一个 AI 编程助手，把一份中文剧本做成带原生对白、配乐、字幕的 AI 短片。

- **视频 + 对白**：MiniMax-H3 Turbo（Ref2VA，一次生成画面与原生 Speech，8 steps）
- **图像资产**：gpt-image-2（角色 / 场景 / 道具 / 首帧 / 参考图）
- **超分**：SeedVR2 3B（2×，逐镜）
- **声音**：HunyuanVideo-Foley（环境 / 动作声）、ACE-Step 1.5（纯器乐配乐）、Whisper（ASR / 词级字幕）
- **审查**：CloudBase 公网审查页，逐镜批注、双候选选择

整个流程是 `S01–S19` 的规范化流水线，写在 [`aifilm_booklet/`](aifilm_booklet/production_steps.md) 里。执行方式是：把 booklet 放进项目目录，让 AI 编程助手（CodeBuddy / Codex / Claude Code 等）读 booklet、按阶段写脚本并调用本地模型。[`examples/car_chat/`](examples/car_chat/) 是一部已完成短片（3 集 / 20 shot / 约 3.6 分钟）的输入和当时实际跑过的 pipeline 脚本，可以用来对照复现。

---

## 目录

```text
aifilm_github/                  ← 即 <WORKSPACE>，所有项目、ComfyUI、权重都放在它下面
├── README.md
├── aifilm_booklet/             流程规范 + 工具（新项目时整个复制进项目目录）
│   ├── production_steps.md     主索引：S01–S19、全局硬规则、确认门禁、交付标准
│   ├── 01_planning_assets_review.md    S01–S06 剧本 / shot plan / 资产 / 审查页
│   ├── 02_video_speech_picturelock.md  S07–S14 H3 候选 / 原生 Speech / picture lock / 超分
│   ├── 03_audio_delivery_qc.md         S15–S19 Foley / 配乐 / 混音 / 字幕 / 交付 QC
│   ├── 04_remake_workflow.md           复刻专项
│   └── tools/                  gpt-image-2 网关、SeedVR2、ACE、Foley、审查页模板 vis/、爬虫
├── setup/                      环境安装、模型下载、ComfyUI 启停、新建项目、自检
│   ├── install.sh
│   ├── download_models.py  +  models.json
│   ├── start_comfyui.sh / stop_comfyui.sh
│   ├── new_project.sh
│   ├── check_env.py
│   ├── aimovie_api.env.example
│   └── requirements.txt
└── examples/car_chat/          样例项目《车上聊天》
    ├── input/                  剧本、角色三视图 + 音色参考、场景图
    └── pipeline/               当时实际执行的 6 个核心脚本
```

运行后会在 `<WORKSPACE>` 下多出（均已 `.gitignore`）：

```text
ComfyUI/  third_party/  models/  output/  logs/  run/  .secrets/  interaction_xxx<剧名>/
```

---

## 1. 环境要求

| 项 | 要求 |
|---|---|
| GPU | NVIDIA，**4 × 80GB+**（已验证 4 × H20 96GB；H800 / A100-80G 同级可用）。单卡也能跑，只是 H3 候选和超分串行会很慢 |
| 磁盘 | 权重约 **70 GB**；一部 3 分钟短片的中间产物约 **25–30 GB** |
| CUDA / 驱动 | 支持 CUDA 12.8（torch 2.9.1+cu128） |
| 系统命令 | `conda`、`git`、`ffmpeg`/`ffprobe`（需 libx264）、`tmux`、`curl` |
| Node | Node.js ≥ 18 + CloudBase CLI：`npm i -g @cloudbase/cli`（只用于公网审查页） |
| API | gpt-image-2 图像网关（OpenAI images 兼容接口）；腾讯云 CloudBase 环境（公网审查页） |

---

## 2. 模型（需自行下载，`setup/download_models.py` 一键完成）

| 用途 | 文件 | HF 仓库 | 放到 |
|---|---|---|---|
| H3 主模型 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (20.9G) | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) | `ComfyUI/models/diffusion_models/` |
| H3 文本编码 | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` (15.7G) | Comfy-Org/MiniMax-H3 | `ComfyUI/models/text_encoders/` |
| H3 视频 VAE | `minimax_h3_video_vae_fp16.safetensors` (5.2G) | Comfy-Org/MiniMax-H3 | `ComfyUI/models/vae/` |
| H3 音频 VAE | `minimax_h3_audio_vae_fp32.safetensors` (0.6G) | Comfy-Org/MiniMax-H3 | `ComfyUI/models/vae/` |
| **H3 Turbo LoRA** | `minimax_h3_turbo_v4_step600_ema.safetensors` (0.8G) | [larryvrh/MiniMax-H3-Turbo-Lora](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora) | `ComfyUI/models/loras/` |
| SeedVR2 | `seedvr2_3b_int8_convrot.safetensors` (3.5G) | [Comfy-Org/SeedVR2](https://huggingface.co/Comfy-Org/SeedVR2) | `ComfyUI/models/diffusion_models/` |
| SeedVR2 VAE | `seedvr2_ema_vae_fp16.safetensors` (0.5G) | Comfy-Org/SeedVR2 | `ComfyUI/models/vae/` |
| ACE-Step 1.5 | `acestep_v1.5_turbo.safetensors` (4.8G) | [Comfy-Org/ace_step_1.5_ComfyUI_files](https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files) | `ComfyUI/models/diffusion_models/` |
| ACE 文本编码 | `qwen_0.6b_ace15.safetensors` / `qwen_4b_ace15.safetensors` | 同上 | `ComfyUI/models/text_encoders/` |
| ACE VAE | `ace_1.5_vae.safetensors` | 同上 | `ComfyUI/models/vae/` |
| Foley（可选） | `hunyuanvideo_foley_xl.pth` / `synchformer_state_dict.pth` / `vae_128d_48k.pth` | [tencent/HunyuanVideo-Foley](https://huggingface.co/tencent/HunyuanVideo-Foley) | `models/HunyuanVideo-Foley/` |
| Foley 运行时 | `google/siglip2-base-patch16-512`、`laion/larger_clap_general` | HF 自动缓存 | `~/.cache/huggingface` |
| ASR | openai-whisper `small` | 自动下载 | `~/.cache/whisper/` |

代码依赖（`setup/install.sh` 固定到验证过的 commit）：

| 仓库 | commit |
|---|---|
| [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)（原生含 H3 / SeedVR2 / ACE-Step 1.5 节点） | `15eb748b` |
| [Larryvrh/ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo)（Turbo LoRA / Sampler 节点） | `4274783a` |
| [Tencent-Hunyuan/HunyuanVideo-Foley](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley)（可选） | `df7b005b` |

---

## 3. 安装

```bash
git clone <this-repo> aifilm && cd aifilm          # 以下 <WORKSPACE> 即此目录

# 3.1 conda 环境 minimaxh3 + ComfyUI + H3 Turbo 节点（加 --with-foley 同时装 Foley 独立环境）
bash setup/install.sh --with-foley

# 3.2 下载权重（约 70GB；国内可先 export HF_ENDPOINT=https://hf-mirror.com）
conda activate minimaxh3
python setup/download_models.py
python setup/download_models.py --check            # 校验大小

# 3.3 填凭据（install.sh 已从模板生成）
vim .secrets/aimovie_api.env                        # gpt-image-2 网关、CloudBase

# 3.4 起 ComfyUI：GPU0–3 → 8188–8191，ACE → 8192（默认与 GPU2 共卡）
bash setup/start_comfyui.sh                         # GPUS="0 1 2 3" ACE_GPU=2 可改

# 3.5 自检：命令 / 包 / 节点 / 权重 / 凭据 / 端口
python setup/check_env.py
```

`check_env.py` 全部通过再往下走。

---

## 4. 复现样例《车上聊天》

### 4.1 建项目

```bash
bash setup/new_project.sh "interaction_9<车上聊天>" --example car_chat
cd "interaction_9<车上聊天>"
```

项目目录必须直接位于 `<WORKSPACE>` 下：pipeline 按 `项目目录/..` 找 `ComfyUI/` 和 ComfyUI 的 `output/`。

### 4.2 按阶段执行

长任务都放在 `tmux` 里，日志写进 `output/others/`（booklet 硬规则）：

```bash
tmux new -s minimax_car_chat
conda activate minimaxh3
source aifilm_booklet/tools/source_aimovie_env.sh
```

| 阶段 | 命令 | 产物 |
|---|---|---|
| S01–S04 剧本 / bible / 分集 / shot plan | `python pipeline/build_preproduction.py` | `output/script_tot.md`、`script_episode{1,2,3}.md`、`output/others/shot_plan.json`、`shot_plan_h3.json` |
| S05 图像资产（gpt-image-2） | `python pipeline/generate_static_assets.py` | `output/images_prepare/` |
| S06 审查页 | `python pipeline/build_review_site.py` → 按 [`tools/vis/README.md`](aifilm_booklet/tools/vis/README.md) 校验并 `tcb` 部署 | `output/vis/`、公网审查地址 |
| — | **用户在公网审查页确认**（booklet 唯一确认门禁） | |
| S07–S08 H3 双候选 | `python pipeline/generate_h3_candidates.py --ports 8188 8189 8190 8191 2>&1 \| tee output/others/minimax_all_candidates.log` | `output/video_raw/candidates/`（20 shot × 2） |
| S09–S19 选片 / picture lock / Foley / 配乐 / 混音 / 字幕 / QC | `python pipeline/finalize_movie.py 2>&1 \| tee output/others/minimax_postproduction.log` | `output/final/movie_final.mp4`、`movie_final_no_subtitles.mp4`、`manifest.json`、`output/others/movie.zh-CN.srt`、`qc_report.md`、`contact_sheet.jpg` |
| S14 SeedVR2 2×（画面确认后） | `python pipeline/upscale_final_selected.py --servers http://127.0.0.1:8188 http://127.0.0.1:8189 http://127.0.0.1:8190 http://127.0.0.1:8191` | `output/resolution/seedvr2_2x/` |

S06 之后每一轮公网批注，按 booklet 的返修规则（读最新 API → 改 prompt → 只重生成目标 shot → 重建下游）处理。返修脚本是 AI 助手按每轮批注临时写的，样例中没有收录。

> 生成模型带随机性，复现的是**流程和质量水准**，不会逐帧还原原片。

---

## 5. 做一部新片

```bash
bash setup/new_project.sh "interaction_10<剧名>"
```

1. 角色素材放 `input/roles/<角色名>/`（三视图、正 / 侧 / 背、`角色定义.md`、可选 `*_Speech音色参考*.wav`）
2. 场景放 `input/scenes/<场景名>/`，其他参考放 `input/other/`
3. 剧本写 `input/script.md`，末尾保留「严格遵循 `<PROJECT_ROOT>/aifilm_booklet` 中的步骤和规则」
4. 在项目目录打开 AI 编程助手，发给它：

```text
读取 aifilm_booklet/production_steps.md，按 S01–S19 执行当前项目，剧本在 input/script.md。
```

助手会在项目里自己写 `pipeline/` 脚本；`examples/car_chat/pipeline/` 可以作为它的参考实现。

---

## 6. 换机器时要注意的地方

`aifilm_booklet/` 基本保持原样，只补了缺失文件、加了环境变量入口。下面几处写的是原作者机器的路径或项目专用值，属于「运行前确认属于当前项目」的模板（booklet 原文就是这么要求的）：

| 位置 | 现状 | 处理 |
|---|---|---|
| `01_planning_assets_review.md`（S05 生图）、`02_video_speech_picturelock.md`（长任务执行） | `cd /apdcephfs.../aimovie`、`source .../miniconda3/bin/activate minimaxh3` | 理解为 `cd <WORKSPACE>` + `conda activate minimaxh3` |
| `tools/generate_foley_batch.py` | `ROOT` / `REPO` / `MODEL_DIR` 和 10 条 `PROMPTS` 是旧项目的 | 改为 `REPO=<WORKSPACE>/third_party/HunyuanVideo-Foley`、`MODEL_DIR=<WORKSPACE>/models/HunyuanVideo-Foley`，prompt 按当前 `shot_plan.json` 写；用 `conda activate aifilm-foley` 运行 |
| `tools/generate_ace_music.py` | `OUTPUT` / `WORKFLOW` 路径是旧项目的 | 改为当前 `<PROJECT_ROOT>/output`；样例里 `finalize_movie.py` 自带配乐生成，可直接参考 |
| `tools/dist_stop_gpu.sh` | 依赖 `pdsh` + `NODE_IP_LIST`（集群用） | 单机可跳过，只做 `pkill` 那几步 |
| `tools/gpt_image_gateway.py` | 默认 endpoint 是内网网关，鉴权为 `Bearer {id}:{key}?provider=...` | 用 `.secrets` 里的 `AIMOVIE_IMAGE_ENDPOINT` 覆盖；接其他 OpenAI 兼容服务时按需改鉴权头 |
| `tools/source_aimovie_env.sh` | 强制要求 `ELEVENLABS_APP_ID/KEY` 非空 | 流程不用外部 TTS，填 `unused` 即可 |

相对原始 booklet 的改动（仅此 3 处）：

1. **新增** `tools/seedvr2_upscale.py`：`run_seedvr2_upscale.sh` 依赖它，原目录缺失；默认 ComfyUI / output 路径按 `<WORKSPACE>` 推导（可用 `AIFILM_WORKSPACE` 覆盖）
2. `tools/run_seedvr2_upscale.sh`：conda 路径改为可用 `CONDA_ACTIVATE` / `CONDA_ENV` 覆盖，默认值不变
3. **删除** `tools/crawler/bilibili.com_cookies.txt`（账号凭据）和 `__pycache__/`；爬虫需要时用 `--cookies <自己的文件>` 或 `--cookies-from-browser chrome`

样例 `examples/car_chat/` 相对原项目的改动：`build_review_site.py` 的 CloudBase `envId` / 桶名 / `apiUrl` / `docId` 改为从 `CLOUDBASE_*` 环境变量读取；`upscale_final_selected.py` 改为调用 booklet 里的 `seedvr2_upscale.py`；输入 manifest 中的绝对路径替换为 `<WORKSPACE>/`。

---

## 7. 注意事项

- **凭据**：只提交 `setup/aimovie_api.env.example`。`.secrets/`、cookies、`cloudbaserc.json` 都在 `.gitignore` 里。每个项目用独立的 CloudBase `docId`，不要复用别的项目的 `envId`、`apiUrl`、桶名
- **素材版权**：`examples/car_chat/input/` 里的角色音色参考 wav 截自其他作品，公开发布前请确认授权，或换成自己录的
- **Windows**：项目目录名里的 `<>` 在 Windows 上非法，Windows / WSL 挂载盘上请换成别的命名
- **术语**：Speech = 可懂人声（只来自 H3 原生）；Sound / Foley = 非人声音效；Music = 配乐；Mix = 最终混音。流程不使用外部 TTS 或口型模型

## License

本仓库代码与文档：按需补充。第三方模型与代码遵循各自许可证（MiniMax-H3、SeedVR2、ACE-Step、HunyuanVideo-Foley、Whisper、ComfyUI）。
