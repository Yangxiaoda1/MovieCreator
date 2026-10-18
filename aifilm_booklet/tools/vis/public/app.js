(() => {
  const config = window.STORYBOARD_CONFIG || {};
  const API = String(config.apiUrl || "").replace(/\/$/, "");
  const DOC_ID = config.docId || "storyboard-review";
  const ASSET_VERSION = config.assetVersion || "";
  const boxes = new Map();
  const timers = new Map();
  const dirty = new Set();
  let currentNotes = {};
  const syncStatus = document.getElementById("syncStatus");
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const array = value => Array.isArray(value) ? value : [];
  const cssEscape = value => window.CSS?.escape ? window.CSS.escape(String(value)) : String(value).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
  const safeId = value => String(value || "candidate").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
  const asset = value => {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (/^(https?:|data:|blob:)/.test(raw) || raw.startsWith("assets/")) return raw;
    return `assets/${raw}`;
  };
  const versioned = url => !url || !ASSET_VERSION ? url : `${url}${url.includes("?") ? "&" : "?"}v=${encodeURIComponent(ASSET_VERSION)}`;
  const setStatus = (text, kind = "") => { syncStatus.textContent = text; syncStatus.className = `sync-status ${kind}`; };
  const setField = (key, text, kind = "") => {
    const node = document.querySelector(`[data-state-for="${cssEscape(key)}"]`);
    if (node) { node.textContent = text; node.className = `save-state ${kind}`; }
  };
  const localKey = key => `${DOC_ID}:${key}`;
  const pills = items => array(items).map(item => `<span class="pill">${esc(item)}</span>`).join("");
  const editor = (key, label, placeholder) => `<label class="editor"><span>${esc(label)}</span><textarea data-note-key="${esc(key)}" placeholder="${esc(placeholder)}"></textarea><small class="save-state" data-state-for="${esc(key)}">可编辑</small></label>`;
  const figure = (src, caption, noteKey) => {
    const url = asset(src);
    if (!url) return `<div class="empty-media">缺少${esc(caption)}</div>`;
    return `<figure class="frame"><img loading="lazy" src="${esc(url)}" alt="${esc(caption)}"><figcaption>${esc(caption)}</figcaption>${noteKey ? editor(noteKey, "参考图修改", "这张参考图是否可用，需要怎么改") : ""}</figure>`;
  };
  const video = (src, label, noteKey) => {
    const url = asset(src);
    if (!url) return `<div class="empty-media">缺少${esc(label)}</div>`;
    return `<div class="video-review"><video controls preload="metadata" src="${esc(versioned(url))}"></video>${noteKey ? editor(noteKey, "视频修改", "这个生成视频是否可用，需要怎么改") : ""}</div>`;
  };
  const audio = (src, label, noteKey) => {
    const url = asset(src);
    if (!url) return `<div class="empty-media">缺少${esc(label)}</div>`;
    return `<div class="audio-review"><p>${esc(label)}</p><audio controls preload="metadata" src="${esc(versioned(url))}"></audio>${noteKey ? editor(noteKey, "参考声音修改", "这段参考声音是否可用，需要怎么改") : ""}</div>`;
  };
  function assetCard(item, group) {
    const url = asset(item.asset);
    return `<article class="asset-card">${url ? `<img loading="lazy" src="${esc(url)}" alt="${esc(item.name)}">` : `<div class="asset-placeholder">${esc(group)}</div>`}<h3>${esc(item.name || group)}</h3><p>${esc(item.description || "")}</p><small>${esc(group)}</small></article>`;
  }

  const isAudioRef = item => {
    const value = typeof item === "string" ? item : `${item?.role || ""} ${item?.type || ""} ${item?.path || item?.asset || item?.src || ""}`;
    return /audio|sound|voice|speech|声音|音色|\.mp3|\.wav|\.m4a|\.aac|\.flac|\.ogg|\.opus/i.test(value);
  };

  function shotReferences(shot) {
    const items = [];
    const seen = new Set();
    const add = (path, role, note) => {
      if (!path) return;
      const key = `${path}|${role || "reference"}`;
      if (seen.has(key)) return;
      seen.add(key);
      items.push({path, role: role || "reference", note: note || ""});
    };
    array(shot.reference_assets).filter(item => !isAudioRef(item)).forEach(item => typeof item === "string" ? add(item, "reference", "") : add(item.path || item.asset || item.src, item.role, item.note || item.description));
    add(shot.start_asset || shot.assets?.start_frame, "start_frame", "实际首帧锚点");
    add(shot.end_asset || shot.assets?.end_frame, "end_frame", "必要尾帧 / 衔接帧");
    add(shot.reference_asset || shot.assets?.reference || shot.assets?.reference_image, "reference", "普通参考图");
    return items;
  }

  function shotAudios(shot) {
    const items = [];
    const seen = new Set();
    const add = (path, role, note) => {
      if (!path) return;
      const key = `${path}|${role || "reference_audio"}`;
      if (seen.has(key)) return;
      seen.add(key);
      items.push({path, role: role || "reference_audio", note: note || ""});
    };
    array(shot.reference_assets).filter(isAudioRef).forEach(item => add(item.path || item.asset || item.src, item.role, item.note || item.description));
    ["reference_audio_assets", "reference_audios", "audio_references", "voice_references", "sound_references"].forEach(key => array(shot[key]).forEach(item => typeof item === "string" ? add(item, key, "") : add(item.path || item.asset || item.src, item.role || key, item.note || item.description)));
    add(shot.reference_audio || shot.audio_reference || shot.voice_reference || shot.sound_reference || shot.assets?.reference_audio || shot.assets?.voice_reference || shot.assets?.reference_sound, "reference_audio", "参考声音");
    return items;
  }

  const promptEditor = (key, label, text) => text ? `<label class="editor prompt-editor"><span>${esc(label)}（直接修改）</span><textarea data-note-key="${esc(key)}">${esc(text)}</textarea><small class="save-state" data-state-for="${esc(key)}">可编辑</small></label>` : "";

  function shotCandidates(shot) {
    const raw = [
      ...array(shot.candidate_videos),
      ...array(shot.video_candidates),
      ...array(shot.candidates)
    ];
    const seen = new Set();
    return raw.map((item, index) => {
      const data = typeof item === "string" ? {path: item} : (item || {});
      const path = data.path || data.asset || data.src || data.video || data.selected_video || "";
      const id = safeId(data.id || data.candidate_id || data.version || `candidate_${index + 1}`);
      return {id, path, label: data.label || `候选 ${index + 1}`, seed: data.seed, prompt_variant: data.prompt_variant || data.variant || "", qc_status: data.qc_status || data.qc, note: data.note || data.description || ""};
    }).filter(item => {
      const key = `${item.id}|${item.path}`;
      if (!item.path || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function candidateCard(shot, item, index) {
    const url = asset(item.path);
    if (!url) return "";
    const noteKey = `${shot.id}_${item.id}_video`;
    const meta = [item.seed ? `seed: ${item.seed}` : "", item.prompt_variant ? `变体: ${item.prompt_variant}` : "", item.qc_status ? `QC: ${item.qc_status}` : "", item.note].filter(Boolean).join(" · ");
    return `<article class="candidate-card" data-shot-id="${esc(shot.id)}" data-candidate-id="${esc(item.id)}">
      <div class="candidate-card__head"><h4>${esc(item.label || `候选 ${index + 1}`)}</h4><small data-candidate-state-for="${esc(`${shot.id}:${item.id}`)}">待选择</small></div>
      ${meta ? `<p class="candidate-meta">${esc(meta)}</p>` : ""}
      <video controls preload="metadata" src="${esc(versioned(url))}"></video>
      <div class="candidate-actions">
        <button type="button" class="button candidate-action" data-candidate-action="select" data-shot-id="${esc(shot.id)}" data-candidate-id="${esc(item.id)}">选为主候选</button>
        <button type="button" class="button candidate-action" data-candidate-action="pass" data-shot-id="${esc(shot.id)}" data-candidate-id="${esc(item.id)}">Pass</button>
      </div>
      ${editor(noteKey, "候选视频修改", "这个候选是否可用，需要怎么改")}
    </article>`;
  }

  function shotCard(shot) {
    const candidates = shotCandidates(shot);
    const preferredVideo = shot.upscaled_video || shot.selected_video || shot.video;
    const frameMode = shot.generation_method || shot.frame_strategy?.mode || shot.generation_mode || "start_frame";
    const refs = shotReferences(shot);
    const audios = shotAudios(shot);
    const refHtml = refs.length
      ? refs.map((item, index) => figure(item.path, `${shot.id} ${item.role}${item.note ? `｜${item.note}` : ""}`, `${shot.id}_ref_${index + 1}`)).join("")
      : `<div class="empty-media">缺少参考图</div>`;
    const audioBlock = audios.length ? `<div><h3>参考声音</h3><div class="audio-list">${audios.map((item, index) => audio(item.path, `${shot.id} ${item.role}${item.note ? `｜${item.note}` : ""}`, `${shot.id}_audio_${index + 1}`)).join("")}</div></div>` : "";
    const candidateBlock = candidates.length ? `<div class="video-block video-block--wide"><h3>MiniMax 候选视频（选择一个主候选，另一个 Pass）</h3><div class="candidate-grid">${candidates.map((item, index) => candidateCard(shot, item, index)).join("")}</div></div>` : "";
    const selectedBlock = preferredVideo ? `<div><h3>最终选中视频</h3>${video(preferredVideo, `${shot.id} 最终选中视频`, `${shot.id}_video`)}</div>` : "";
    const videoBlock = `${candidateBlock}${selectedBlock}`;
    const prompts = [
      promptEditor(`${shot.id}_image_prompt`, "Image Prompt", shot.image_prompt),
      promptEditor(`${shot.id}_video_prompt`, "Video Prompt", shot.video_prompt)
    ].filter(Boolean).join("");
    return `<article class="shot" id="${esc(shot.id)}">
      <header class="shot__head"><div><span class="shot__number">${esc(shot.id)}</span><h2>${esc(shot.location || "未命名场景")}</h2></div><div class="shot__meta"><span class="chip">${esc(shot.duration_sec || "?")} 秒</span><span class="chip">${esc(array(shot.characters).join(" · ") || "无角色")}</span><span class="chip">${esc(frameMode)}</span></div></header>
      <div class="media-grid">${videoBlock}<div><h3>参考图 / 首尾帧</h3><div class="frames">${refHtml}</div></div>${audioBlock}</div>
      <div class="info-grid">
        <div class="info info--wide"><h3>提示词</h3>${prompts || "<p>暂无提示词</p>"}</div>
      </div>
      <div class="requirements"><div><b>必须出现</b><div class="pills">${pills(shot.must_show)}</div></div><div><b>禁止出现</b><div class="pills pills--no">${pills(shot.must_not_show)}</div></div></div>
    </article>`;
  }

  function bindEditors() {
    document.querySelectorAll("textarea[data-note-key]").forEach(box => {
      if (boxes.has(box.dataset.noteKey)) return;
      boxes.set(box.dataset.noteKey, box);
      box.addEventListener("input", () => scheduleSave(box));
    });
  }

  function updateCandidateStates(notes = currentNotes) {
    document.querySelectorAll(".candidate-card").forEach(card => {
      const shotId = card.dataset.shotId;
      const candidateId = card.dataset.candidateId;
      const state = card.querySelector("[data-candidate-state-for]");
      const selected = String(notes[`${shotId}_selected_candidate`] || "");
      const decision = String(notes[`${shotId}_${candidateId}_decision`] || "");
      card.classList.remove("candidate-card--selected", "candidate-card--passed");
      if (selected === candidateId || decision === "main") {
        card.classList.add("candidate-card--selected");
        if (state) state.textContent = "主候选";
      } else if (decision === "pass") {
        card.classList.add("candidate-card--passed");
        if (state) state.textContent = "Pass";
      } else if (state) {
        state.textContent = "待选择";
      }
    });
  }

  function bindCandidateActions() {
    document.querySelectorAll(".candidate-action").forEach(button => {
      if (button.dataset.bound) return;
      button.dataset.bound = "1";
      button.addEventListener("click", () => saveCandidateAction(button));
    });
  }

  function applyNotes(notes, label = "已载入") {
    currentNotes = {...currentNotes, ...notes};
    for (const [key, box] of boxes) {
      if (dirty.has(key) || document.activeElement === box) continue;
      if (Object.prototype.hasOwnProperty.call(notes, key)) {
        box.value = String(notes[key] ?? "");
        setField(key, label, "saved");
      }
    }
    updateCandidateStates(currentNotes);
  }

  async function apiGet() {
    const url = API ? `${API}?docId=${encodeURIComponent(DOC_ID)}` : "api/review-notes";
    const response = await fetch(url, {cache: "no-store"});
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function apiPost(key, value) {
    const url = API || "api/review-notes";
    const updatedBy = localStorage.getItem(`${DOC_ID}:reviewer`) || `reviewer-${Date.now()}`;
    localStorage.setItem(`${DOC_ID}:reviewer`, updatedBy);
    const response = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({docId: DOC_ID, key, value, updatedBy})});
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (!payload.ok) throw Error(payload.error || "保存失败");
    return payload;
  }

  async function saveCandidateAction(button) {
    const shotId = button.dataset.shotId;
    const candidateId = button.dataset.candidateId;
    const action = button.dataset.candidateAction;
    const grid = button.closest(".candidate-grid");
    const updates = action === "select"
      ? [[`${shotId}_selected_candidate`, candidateId], [`${shotId}_${candidateId}_decision`, "main"]]
      : [[`${shotId}_${candidateId}_decision`, "pass"]];
    if (action === "pass" && currentNotes[`${shotId}_selected_candidate`] === candidateId) {
      updates.push([`${shotId}_selected_candidate`, ""]);
    }
    if (action === "select" && grid) {
      grid.querySelectorAll(".candidate-card").forEach(card => {
        const otherId = card.dataset.candidateId;
        if (otherId && otherId !== candidateId) updates.push([`${shotId}_${otherId}_decision`, "pass"]);
      });
    }
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "保存中…";
    try {
      for (const [key, value] of updates) {
        await apiPost(key, value);
        currentNotes[key] = value;
        localStorage.setItem(localKey(key), value);
      }
      updateCandidateStates(currentNotes);
      setStatus(action === "select" ? "主候选选择已保存" : "Pass 结论已保存", "ok");
    } catch (error) {
      console.error("candidate decision save failed", error);
      for (const [key, value] of updates) {
        currentNotes[key] = value;
        localStorage.setItem(localKey(key), value);
      }
      updateCandidateStates(currentNotes);
      setStatus(`远端失败，候选结论已存本机：${error.message || error}`, "warn");
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  async function loadNotes() {
    try {
      const data = await apiGet();
      applyNotes(data.notes || data);
      setStatus(API ? "公网审查意见已同步 · 自动保存" : "本地审查意见已同步 · 自动保存", "ok");
    } catch (error) {
      const notes = {};
      const prefix = `${DOC_ID}:`;
      for (let index = 0; index < localStorage.length; index += 1) {
        const storageKey = localStorage.key(index);
        if (storageKey && storageKey.startsWith(prefix)) {
          notes[storageKey.slice(prefix.length)] = localStorage.getItem(storageKey);
        }
      }
      applyNotes(notes, "本机已载入");
      setStatus(`远端未连接，临时保存到本机：${error.message || error}`, "warn");
    }
  }

  async function saveField(box) {
    const key = box.dataset.noteKey;
    setField(key, "保存中…", "saving");
    try {
      await apiPost(key, box.value);
      dirty.delete(key);
      setField(key, "已保存", "saved");
    } catch (error) {
      console.error("review note remote save failed", error);
      localStorage.setItem(localKey(key), box.value);
      setField(key, "远端失败 · 已存本机", "error");
    }
  }

  function scheduleSave(box) {
    const key = box.dataset.noteKey;
    dirty.add(key);
    setField(key, "编辑中…", "saving");
    clearTimeout(timers.get(key));
    timers.set(key, setTimeout(() => saveField(box), 650));
  }

  async function render() {
    const response = await fetch(`storyboard.json?v=${Date.now()}`, {cache: "no-store"});
    if (!response.ok) throw Error(`分镜数据加载失败：${response.status}`);
    const project = await response.json();
    if (!project || typeof project !== "object" || !Array.isArray(project.shots)) {
      throw Error("storyboard.json 格式错误：缺少 shots 数组");
    }
    document.title = `${project.project_title || "AI Movie Review"} · Review`;
    document.getElementById("projectTitle").textContent = project.project_title || "AI Movie Review";
    document.getElementById("projectDesc").textContent = project.description || "统一展示角色、场景、逐镜参考图和提示词。";
    document.getElementById("eyebrow").textContent = `STORYBOARD REVIEW · EPISODE ${project.episode || 1}`;
    document.getElementById("projectFacts").innerHTML = [[`${project.target_duration_sec || "?"}s`, "时长"], [project.aspect_ratio || "?", "画幅"], [array(project.shots).length, "镜头数"], [project.status || "review", "状态"]].map(([value, label]) => `<div class="fact"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
    if (project.final_video) {
      document.getElementById("finalSection").hidden = false;
      document.getElementById("finalVideo").innerHTML =
        video(project.final_video, "字幕版成片") +
        (project.final_video_no_subtitles ? video(project.final_video_no_subtitles, "无字幕版成片") : "");
    }
    const assets = [
      ...array(project.overview_assets).map(item => assetCard(item, "总览")),
      ...array(project.characters).map(item => assetCard(item, "角色")),
      ...array(project.scenes).map(item => assetCard(item, "场景")),
      ...array(project.props).map(item => assetCard(item, "道具"))
    ];
    document.getElementById("assetList").innerHTML = assets.join("") || `<div class="empty-media">暂无资产</div>`;
    document.getElementById("timeline").innerHTML = array(project.shots).map(shot => `<a href="#${esc(shot.id)}"><b>${esc(String(shot.id || "shot").replace("shot_", ""))}</b>${esc(shot.location || "未命名")} · ${esc(shot.duration_sec || "?")}s</a>`).join("");
    document.getElementById("shots").innerHTML = array(project.shots).map(shotCard).join("") || `<div class="loading">暂无镜头</div>`;
    bindEditors();
    bindCandidateActions();
    await loadNotes();
  }

  document.getElementById("refreshBtn").addEventListener("click", loadNotes);
  bindEditors();
  render().catch(error => {
    console.error("storyboard page initialization failed", error);
    document.getElementById("shots").innerHTML = `<div class="loading">页面初始化失败：${esc(error.message || error)}</div>`;
    setStatus(`页面初始化失败：${error.message || error}`, "error");
  });
  setInterval(() => { if (!dirty.size) loadNotes(); }, 8000);
})();
