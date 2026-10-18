# 公网审查网页最小模板

这是从 `<PROJECT_ROOT>/output/vis` 实例抽出的最小可参考模板，用于 S06/S14 统一审查页：默认公网部署到 CloudBase 静态托管，并通过 HTTP 云函数收集意见；本地预览只作为上线前检查或 fallback。页面逐镜只展示参考图 / 首尾帧 / 普通约束图及其用途、Image Prompt、Video Prompt、每个 shot 的两个 MiniMax 候选视频和必要元信息，不展示“画面、动作、运镜、对白 / 声音”等拆分卡片，也不展示重复的 Ref2VA Prompt / H3 Prompt；提示词正文直接可编辑，其中 Video Prompt 使用较大的编辑框；每张参考图下方有一个可编辑框，每个候选视频下方有一个可编辑框，并可选择一个作为主候选、将另一个标记为 `pass`。

## 目录

```text
vis/
├── public/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── cloudbase-config.js
│   └── storyboard.json
├── functions/
│   └── storyboardReviewApi/
│       ├── package.json
│       ├── server.js
│       └── scf_bootstrap
├── app.py
├── run_vis.sh
├── sync_public.py
├── validate_vis.py
└── cloudbaserc.template.json
```

## 默认公网部署流程

1. 把本目录复制到当前项目的 `<PROJECT_ROOT>/output/vis/`，或直接参考文件结构创建。
2. 把真实审查数据写入 `public/storyboard.json`，素材放入 `public/assets/`。`frame_strategy.mode=reference_only` 的镜头使用 `reference_asset`，页面会标注“参考图，非首帧”；`start_frame` / `start_plus_end_frame` 才使用 `start_asset` 作为首帧约束。逐镜数据重点填写 `reference_assets`、`reference_audio_assets` / `reference_audios` / `audio_references`、`image_prompt`、`video_prompt` 和 `candidate_videos`。每个 shot 默认填入两个 MiniMax 候选：`candidate_videos: [{id, path, seed, prompt_variant, prompt, qc_status, note}, ...]`；候选 A/B 必须是同目标双 prompt 受控变体，`prompt_variant` / `note` 写清“稳版”或“替代解法”的差异点；页面会保存 `${shot_id}_selected_candidate`、`${shot_id}_${candidate_id}_decision=main|pass` 和每个候选的视频意见。`ref2va_prompt` / `h3_prompt` 可留在生产数据中，但审查页不单独展示，避免与 Video Prompt 重复；也不要依赖页面展示 `picture`、`action`、`camera`、`dialogue`、`sound` 拆分字段。
3. 复制 `cloudbaserc.template.json` 为 `cloudbaserc.json`。
4. 替换：
   - `your-cloudbase-env-id`
   - `your-bucket-name`
   - `deployPath`
   - `public/cloudbase-config.js` 里的 `docId`、`apiUrl` 和 `assetVersion`
   - 云函数环境变量：`STORYBOARD_CLOUDBASE_ENV_ID`、`STORYBOARD_CLOUDBASE_BUCKET`、`STORYBOARD_DEFAULT_DOC_ID`
5. 在 `functions/storyboardReviewApi/` 下安装依赖。
6. 用 CloudBase CLI 部署云函数和静态托管，得到可分享的公网审查地址。

示例命令仅作参考，按当前账号环境调整：

```bash
cd <PROJECT_ROOT>/output/vis
python sync_public.py
python validate_vis.py
node --check public/app.js
find public/assets -type l
npm --prefix functions/storyboardReviewApi install

# 首次创建 HTTP API 路径时使用 --path；如果提示 Path is used，说明路径已存在，后续重部署不要再带 --path。
tcb fn deploy storyboardReviewApi --httpFn --path /storyboard-api --dir functions/storyboardReviewApi --force -e your-cloudbase-env-id

# 后续只更新函数代码时使用这个命令，保留既有 /storyboard-api 路径。
tcb fn deploy storyboardReviewApi --httpFn --dir functions/storyboardReviewApi --force -e your-cloudbase-env-id

# 静态托管。用户打开的是这个页面地址，不是 API 地址。
tcb hosting deploy public /storyboard-review -e your-cloudbase-env-id --concurrency 10 --retry-count 5 --retry-interval 2000
```

`sync_public.py` 会把 `storyboard.json` 中的本地项目路径改写为
`assets/...` 并只复制实际引用的文件，支持 `output/video_raw/`、
`output/audio/`、`output/resolution/`、`output/final/`、
`output/images_prepare/` 及输入角色 / 场景目录。不要在 JSON 中保留
`/绝对路径`、`output/...` 或 `input/...`；部署后浏览器无法访问它们。

`validate_vis.py` 是部署门禁。存在任一错误时不得部署或进入 S06
确认；模板占位配置会作为 warning 输出，正式部署前也必须消除。

## 本地预览 fallback

公网部署前可本地检查页面和素材加载；公网异常时也可临时 fallback 到本地保存。

```bash
cd <PROJECT_ROOT>/output/vis
VIS_PORT=18080 ./run_vis.sh
```

本地预览时保持 `public/cloudbase-config.js` 的 `apiUrl` 为空，本地意见会保存到 `review_notes.json`。

## 每次部署必须遵守

1. `public/app.js` 使用 `ASSET_VERSION` 时，必须先用
   `const ASSET_VERSION = config.assetVersion || "";` 定义；不能依赖未声明的全局变量。
2. 每次部署都更新 `cloudbase-config.js` 的 `assetVersion`，并同步更新
   `index.html` 中 CSS、配置和 JS 的静态 query 版本号，避免 CDN / 浏览器继续使用旧文件。
3. 每个项目使用唯一 `docId`。可复用已验证的共享 API，但必须用独立
   `docId` 隔离意见；如果要独立部署函数，则使用唯一函数名和 HTTP path，
   避免覆盖其他项目。
4. API 使用
   `https://<env>-<uin>.<region>.app.tcloudbase.com/<path>`。不要使用旧
   `service.tcloudbase.com` 形式。
5. 不要在函数代码中手写 CORS 响应头；CloudBase HTTP 网关会添加 CORS，
   重复添加可能形成非法的多值响应头。
6. 静态托管完成后，不只检查 HTTP 200。必须用真实浏览器或 JSDOM 执行
   页面初始化，确认镜头卡、资产、图片、音频、视频数量符合
   `storyboard.json`，页面没有“初始化失败”，控制台没有 JavaScript 错误。
7. 用页面来源执行 API 的 GET、OPTIONS、POST 检查，确认读取和保存均成功。

## 易错点和排查

### 1. 页面地址和 API 地址不同

- 用户审查页：CloudBase 静态托管地址，例如 `https://<env>-<uin>.tcloudbaseapp.com/<deployPath>/`
- 自动保存 API：HTTP 云函数地址，例如 `https://<env>-<uin>.<region>.app.tcloudbase.com/storyboard-api`

不要把 API 地址当成可视化页面发给用户。API 直开只用于健康检查；有些 CloudBase 网关会给函数响应追加 `content-disposition: attachment`，浏览器可能显示为空白或下载文件，但这不代表审查页不可用。

### 2. `远端失败 · 已存本机`

前端出现这个提示，说明 POST 到 `apiUrl` 失败或浏览器拒绝读取响应。常见原因：

- `public/cloudbase-config.js` 的 `apiUrl` 没有换成当前环境的 `/storyboard-api`
- `docId` 和云函数默认文档不一致
- 云函数未部署、匿名访问未开启，或 `STORYBOARD_CLOUDBASE_BUCKET` 配错
- CORS 响应头冲突：不要在云函数里手写 `access-control-allow-origin: *`，CloudBase 网关会追加自己的 CORS 头；两者合并可能变成 `https://...tcloudbaseapp.com,*`，浏览器会判定无效
- 页面或 JS 被 CDN / 浏览器缓存，部署后需强刷或无痕打开

排查命令：

```bash
API="https://<env>-<uin>.<region>.app.tcloudbase.com/storyboard-api"
PAGE_ORIGIN="https://<env>-<uin>.tcloudbaseapp.com"

curl -i -H "Origin: $PAGE_ORIGIN" "$API?docId=<docId>"
curl -i -X OPTIONS \
  -H "Origin: $PAGE_ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" \
  "$API"
curl -i -X POST \
  -H "Origin: $PAGE_ORIGIN" \
  -H "Content-Type: application/json" \
  -d '{"docId":"<docId>","key":"deployment_test","value":"ok","updatedBy":"debug"}' \
  "$API"
```

`Access-Control-Allow-Origin` 必须是单一来源或合法值，不能是逗号拼接的多个值。

### 3. 文件格式和缓存

- `*.jpg` 文件内容必须真的是 JPEG；如果 AI 生图返回 PNG，不要直接改扩展名，应转码后再部署
- 更新图片 / 视频 / JS 后，给 URL query 版本号递增，例如 `?v=20260916-r3`
- 部署后用 `curl -H "Cache-Control: no-cache"` 或无痕窗口验证

注意：模板里不放真实环境密钥、私有日志、未授权素材和用户隐私。
