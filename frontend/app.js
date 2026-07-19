const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
let dashboardTimer = null;
let libraryTimer = null;
let librarySnapshot = null;
let activeLibraryKind = "drafts";
let currentChoices = [];
let selectedLibraryItem = null;

const routeNames = {
  "scene-development": "场景开发",
  "longform-planning": "长篇规划",
  "source-ingest": "旧文导入",
  "style-engineering": "文风工程",
  "character-and-world-assets": "人物与世界资产",
  "review-and-audit": "审查与审计",
  "export-and-release": "导出与发布",
};

const sectionNames = {
  drafts: "正文草稿",
  characters: "人物设定",
  world: "世界观设定",
  scenes: "场景设定",
  branches: "推演分支",
  style: "文风挂载",
  reviews: "审查证据",
  word_budget: "字数预算",
  rhythm: "节奏衔接",
  canon_patches: "写回候选",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function api(path, options = {}) {
  const token = localStorage.getItem("lewApiToken") || "";
  const authHeader = token ? { "X-LEW-API-Token": token } : {};
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...authHeader, ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let body = text;
  try { body = JSON.parse(text); } catch {}
  if (!response.ok) {
    throw new Error(typeof body === "object" ? body.detail || "请求失败" : body);
  }
  return body;
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  form.querySelectorAll("input[type=checkbox]").forEach((item) => {
    data[item.name] = item.checked;
  });
  return data;
}

function setSharedProjectRoot(value) {
  if (!value) return;
  $$("input[name=project_root]").forEach((item) => { item.value = value; });
}

function setSharedStyleLibraryRoot(value) {
  if (!value) return;
  $$("input[name=style_library_root]").forEach((item) => { item.value = value; });
}

function sharedProjectRoot() {
  return $("#dashboardForm")?.project_root.value || $("#libraryForm")?.project_root.value || $("#configForm")?.project_root.value || $("#styleForm")?.project_root.value || "";
}

async function loadHealth() {
  try {
    const health = await api("/health");
    $("#healthDot").classList.add("ok");
    $("#healthText").textContent = "本地服务已连接";
  } catch {
    $("#healthDot").classList.remove("ok");
    $("#healthText").textContent = "API 未连接";
  }
}

async function loadConfig() {
  const cfg = await api("/config");
  const profileName = cfg.active_profile || "deepseek";
  const profile = (cfg.profiles && cfg.profiles[profileName]) || {};
  const defaults = cfg.defaults || {};
  const form = $("#configForm");
  form.active_profile.value = profileName;
  form.api_base.value = profile.api_base || cfg.api_base || "";
  form.model.value = profile.model || cfg.model || "";
  form.api_key_env.value = profile.api_key_env || cfg.api_key_env || "DEEPSEEK_API_KEY";
  form.api_key.value = "";
  form.api_key.placeholder = profile.api_key_set || cfg.api_key_available ? "已保存，留空则不修改" : "可直接填写 API Key";
  form.temperature.value = profile.temperature ?? cfg.temperature ?? 0.4;
  form.max_tokens.value = profile.max_tokens ?? cfg.max_tokens ?? 4000;
  form.timeout.value = profile.timeout ?? cfg.timeout ?? 120;
  form.project_root.value = defaults.project_root || "";
  form.style_library_root.value = defaults.style_library_root || "";
  setSharedProjectRoot(defaults.project_root || "");
  setSharedStyleLibraryRoot(defaults.style_library_root || "");
  renderConfig(cfg);
}

async function saveConfig() {
  const data = formData($("#configForm"));
  const profileName = data.active_profile || "deepseek";
  const payload = {
    active_profile: profileName,
    profiles: {
      [profileName]: {
        provider: "http-chat",
        api_base: data.api_base,
        model: data.model,
        api_key_env: data.api_key_env,
        api_key: data.api_key,
        temperature: Number(data.temperature),
        max_tokens: Number(data.max_tokens),
        timeout: Number(data.timeout),
      },
    },
    defaults: {
      project_root: data.project_root,
      style_library_root: data.style_library_root,
      scene: "scenes/scene_0001.yaml",
      chapter_id: "chapter_0001",
      workflow_mode: "scene-loop",
    },
  };
  const saved = await api("/config", { method: "POST", body: JSON.stringify(payload) });
  setSharedProjectRoot(data.project_root);
  setSharedStyleLibraryRoot(data.style_library_root);
  renderConfig(saved.effective || saved);
  toast("配置已保存。");
}

function renderConfig(cfg) {
  const profileName = cfg.active_profile || "deepseek";
  const profile = (cfg.profiles && cfg.profiles[profileName]) || {};
  const defaults = cfg.defaults || {};
  const keyReady = profile.api_key_set || cfg.api_key_available;
  $("#configPreview").classList.remove("empty");
  $("#configPreview").innerHTML = `
    <div class="summary-row"><span>当前配置</span><b>${escapeHtml(profileName)}</b></div>
    <div class="summary-row"><span>模型</span><b>${escapeHtml(profile.model || cfg.model || "未设置")}</b></div>
    <div class="summary-row"><span>API 地址</span><b>${escapeHtml(profile.api_base || cfg.api_base || "未设置")}</b></div>
    <div class="summary-row"><span>默认项目</span><b>${escapeHtml(shortPath(defaults.project_root || "未设置"))}</b></div>
  `;
  $("#envPreview").innerHTML = `
    <div class="key-state ${keyReady ? "pass" : "warn"}">${keyReady ? "密钥已设置" : "密钥未设置"}</div>
    <p>${keyReady ? "可以使用真实模型通道。页面不会显示密钥明文。" : "请填写 API Key，或设置对应环境变量。"}</p>
  `;
}

async function loadDashboard() {
  const form = $("#dashboardForm");
  const root = form.project_root.value || $("#configForm").project_root.value || $("#styleForm").project_root.value;
  if (!root) throw new Error("请先填写当前项目目录。");
  setSharedProjectRoot(root);
  $("#dashboardStatus").textContent = "正在刷新";
  const [result, library] = await Promise.all([
    api(`/workflow/dashboard?project_root=${encodeURIComponent(root)}`),
    api(`/project/library?project_root=${encodeURIComponent(root)}`).catch((error) => ({ ok: false, error: error.message || String(error) })),
  ]);
  if (library.ok !== false) librarySnapshot = library;
  renderDashboard(result, library);
  return result;
}

function renderDashboard(result, library = null) {
  const dashboard = result.dashboard || {};
  const summary = result.summary || dashboard.summary || {};
  const actions = result.next_actions || [];
  const routes = result.route_audits || [];
  const blocking = Number(summary.blocking_count || 0);
  const stateBlocked = Number(summary.state_blocked_count || 0);
  const pending = Number(summary.pending_task_count || 0);
  const missing = Number(summary.missing_expected_count || 0);
  const totalTrouble = blocking + stateBlocked + pending + missing;

  $("#dashboardHeadline").textContent = totalTrouble
    ? `项目还不能放心交付，优先处理 ${totalTrouble} 类阻塞信号。`
    : "项目状态很干净，可以进入下一步创作或发布检查。";
  $("#dashboardNarrative").textContent = dashboardNarrative({ blocking, stateBlocked, pending, missing, actions });
  $("#dashboardStatus").textContent = dashboard.generated_at ? `已刷新 ${formatTime(dashboard.generated_at)}` : "已刷新";

  const metrics = [
    ["已就绪路线", summary.ready_count ?? 0, "可以继续使用的正式流程"],
    ["流程门禁", blocking, "需要先修复的硬阻塞"],
    ["状态阻塞", stateBlocked, "状态机判断还没走完"],
    ["待办任务", pending, "需要平台 Agent 处理的 sidecar"],
    ["缺失产物", missing, "预期文件还没写齐"],
    ["下一步", summary.next_action_count ?? actions.length, "面板建议的行动数"],
  ];
  $("#dashboardSummary").innerHTML = metrics.map(([label, value, note]) => `
    <article class="metric ${Number(value) ? "attention" : ""}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(note)}</small>
    </article>
  `).join("");

  $("#dashboardRoutes").classList.toggle("empty", !routes.length);
  $("#dashboardRoutes").innerHTML = routes.length ? routes.map(renderRouteCard).join("") : "暂无流程数据";

  $("#dashboardNextActions").classList.toggle("empty", !actions.length);
  $("#dashboardNextActions").innerHTML = actions.length ? actions.slice(0, 12).map(renderActionCard).join("") : "目前没有新的下一步建议。";

  const events = result.recent_events || [];
  $("#dashboardEvents").classList.toggle("empty", !events.length);
  $("#dashboardEvents").innerHTML = events.length ? events.slice(-10).reverse().map(renderEvent).join("") : "暂无事件记录。";

  renderDashboardProse(library);
  renderDashboardEvidence(result, { dashboard, summary, actions, routes, events });
}

function renderDashboardProse(library) {
  const target = $("#dashboardProse");
  if (!target) return;
  if (!library) {
    target.className = "completed-prose empty";
    target.innerHTML = "正在等待作品档案数据。";
    return;
  }
  if (library.ok === false) {
    target.className = "completed-prose empty";
    target.innerHTML = `作品正文暂时没有读到：${escapeHtml(library.error || "未知错误")}`;
    return;
  }
  const completed = library.completed_prose || {};
  const items = Array.isArray(completed.items) ? completed.items : [];
  if (!items.length) {
    target.className = "completed-prose empty";
    target.innerHTML = `
      <article class="completed-empty">
        <b>还没有已完成正文</b>
        <p>等候选稿通过正式审查并晋升，或章节导出/发布后，这里会自动出现正文预览。</p>
      </article>
    `;
    return;
  }
  const primary = items[0];
  const others = items.slice(1, 4);
  const metrics = primary.metrics || {};
  target.className = "completed-prose";
  target.innerHTML = `
    <article class="completed-main">
      <div class="completed-cover">
        <span>正文</span>
        <b>${escapeHtml(metrics.chinese_content_chars || 0)}</b>
        <small>中文内容字数</small>
      </div>
      <div class="completed-reader">
        <div class="completed-kicker">${escapeHtml(primary.subtitle || "已完成正文")}</div>
        <h3>${escapeHtml(primary.title || "未命名正文")}</h3>
        <div class="completed-meta">
          ${renderBadges(primary.badges || [])}
          <span>${escapeHtml(shortPath(primary.path || ""))}</span>
        </div>
        <div class="completed-preview">${renderBodyPreview(primary.body || primary.excerpt || "")}</div>
        <button type="button" class="open-library-drafts">查看全部正文</button>
      </div>
    </article>
    ${others.length ? `
      <div class="completed-strip">
        ${others.map((item) => `
          <button type="button" class="completed-mini" data-prose-id="${escapeHtml(item.id)}">
            <span>${escapeHtml(item.subtitle || "正文")}</span>
            <b>${escapeHtml(item.title || item.id)}</b>
            <small>${escapeHtml((item.metrics || {}).chinese_content_chars || 0)} 字</small>
          </button>
        `).join("")}
      </div>
    ` : ""}
  `;
}

function renderDashboardEvidence(result, { dashboard, summary, actions, routes, events }) {
  const routeState = dashboard.route_state?.summary || {};
  const taskStatus = dashboard.agent_task_status?.summary || {};
  const paths = result.paths || {};
  const frontend = dashboard.frontend || {};
  const rules = Array.isArray(result.rules) ? result.rules : Array.isArray(dashboard.rules) ? dashboard.rules : [];
  const blockedRoutes = routes.filter((route) => Number(route.blocking_count || 0) > 0);
  const warningRoutes = routes.filter((route) => Number(route.warning_count || 0) > 0);
  const pendingTasks =
    Number(taskStatus.pending_count || 0) +
    Number(taskStatus.partial_count || 0) +
    Number(taskStatus.unknown_count || 0);

  const routeSummary = blockedRoutes.length
    ? blockedRoutes.slice(0, 3).map((route) => `${routeName(route.route)}：${route.blocking_count} 个硬阻塞`).join("；")
    : warningRoutes.length
      ? warningRoutes.slice(0, 3).map((route) => `${routeName(route.route)}：${route.warning_count} 个提醒`).join("；")
      : "全部路线暂未发现硬阻塞。";

  const outputItems = [
    ["人读总控报告", paths.markdown],
    ["机器索引", paths.json || frontend.json],
    ["网页快照", paths.html || frontend.html],
    ["状态机摘要", dashboard.route_state?.path],
    ["平台任务摘要", dashboard.agent_task_status?.path],
  ].filter(([, value]) => value);

  $("#dashboardEvidence").innerHTML = [
    evidenceCard(
      "状态机读数",
      `${Number(routeState.ready_count || summary.ready_count || 0)} 条路线就绪`,
      evidenceText(`状态机另发现 ${Number(routeState.blocked_count || summary.state_blocked_count || 0)} 处阻塞，下一步动作 ${actions.length} 条。`),
      ["来自 workflow-state", formatTime(dashboard.generated_at || "")]
    ),
    evidenceCard(
      "平台任务读数",
      pendingTasks ? `${pendingTasks} 个任务待处理` : "平台任务已清爽",
      evidenceText(`共扫描 ${Number(taskStatus.task_count || summary.sidecar_task_count || 0)} 个 sidecar；缺失预期产物 ${Number(taskStatus.missing_expected_count || summary.missing_expected_count || 0)} 个。`),
      ["来自 agent-task-status"]
    ),
    evidenceCard(
      "路线审计读数",
      `${Number(summary.blocking_count || 0)} 个硬门禁`,
      evidenceText(routeSummary),
      [`覆盖 ${routes.length} 条正式路线`]
    ),
    evidenceCard(
      "输出与索引",
      "报告、网页和机器索引都保留",
      evidenceList(outputItems.map(([label, value]) => `${label}：${shortPath(value)}`)),
      ["可追溯", "不裸露 JSON"]
    ),
    evidenceCard(
      "使用边界",
      "这里只读，不替代执行",
      evidenceList(rules.length ? rules.map(friendlyRule).slice(0, 3) : ["正式推进仍由平台 Agent 通过 CLI 状态机完成。"]),
      ["防跳步", "防误操作"]
    ),
    evidenceCard(
      "最近活动",
      events.length ? `${events.length} 条事件已纳入观察` : "还没有事件记录",
      evidenceText(events.length ? "事件已整理在左侧“最近推进记录”，用于判断平台 Agent 是否真的完成了提交与验收。" : "项目还没有可展示的 task event；开始正式路线后这里会自动出现。"),
      ["来自 task events"]
    ),
  ].join("");
}

function evidenceCard(title, value, detailHtml, tags = []) {
  return `
    <article class="evidence-card">
      <span class="evidence-title">${escapeHtml(title)}</span>
      <strong>${escapeHtml(value)}</strong>
      <div class="evidence-detail">${detailHtml}</div>
      <footer>${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</footer>
    </article>
  `;
}

function evidenceText(value) {
  return `<p>${escapeHtml(value)}</p>`;
}

function evidenceList(items) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function dashboardNarrative({ blocking, stateBlocked, pending, missing, actions }) {
  if (pending) return `还有 ${pending} 个平台 Agent 任务没有处理完。先打开“下一步建议”，按顺序完成任务，再刷新这里。`;
  if (blocking) return `有 ${blocking} 个正式门禁没有通过。它们通常涉及审查、文风、字数预算、角色资产或导出准备。`;
  if (stateBlocked) return `状态机发现 ${stateBlocked} 处流程还没走完。建议从第一条下一步建议开始补齐。`;
  if (missing) return `有 ${missing} 个预期产物缺失。先生成缺失的报告、候选稿、审查或发布文件。`;
  if (actions.length) return "项目没有明显硬阻塞，但仍有一些建议动作可以提升完整度。";
  return "当前没有阻塞信号。可以继续写作、审查下一章，或准备导出发布。";
}

function renderRouteCard(route) {
  const blocking = Number(route.blocking_count || 0);
  const warnings = Number(route.warning_count || 0);
  const pending = Number(route.pending_task_count || 0);
  const status = blocking ? "需处理" : warnings || pending ? "需留意" : "正常";
  const top = Array.isArray(route.top_blocking_gates) ? route.top_blocking_gates[0] : null;
  return `
    <article class="route-card ${blocking ? "blocked" : warnings || pending ? "warn" : "pass"}">
      <div>
        <b>${escapeHtml(routeName(route.route))}</b>
        <span>${escapeHtml(status)}</span>
      </div>
      <p>${escapeHtml(top ? friendlyMessage(top.message) : routeReadyText(route.route))}</p>
      <footer>
        <span>阻塞 ${blocking}</span>
        <span>提醒 ${warnings}</span>
        <span>待办 ${pending}</span>
      </footer>
    </article>
  `;
}

function renderActionCard(action, index) {
  return `
    <article class="action-item">
      <div class="action-index">${String(index + 1).padStart(2, "0")}</div>
      <div>
        <b>${escapeHtml(routeName(action.route))}</b>
        <span>${escapeHtml(action.target ? friendlyTarget(action.target) : "项目整体")}</span>
        <p>${escapeHtml(friendlyMessage(action.next_action || ""))}</p>
      </div>
    </article>
  `;
}

function renderEvent(event) {
  return `
    <article class="event-item">
      <b>${escapeHtml(eventLabel(event.event_type || event.type || "event"))}</b>
      <span>${escapeHtml(formatTime(event.created_at || event.timestamp || ""))}</span>
      <p>${escapeHtml(friendlyTarget(event.task_id || event.route || "项目事件"))}</p>
    </article>
  `;
}

async function loadLibrary() {
  const form = $("#libraryForm");
  const root = form.project_root.value || $("#dashboardForm").project_root.value || $("#configForm").project_root.value || $("#styleForm").project_root.value;
  if (!root) throw new Error("请先填写当前项目目录。");
  setSharedProjectRoot(root);
  $("#libraryStatus").textContent = "正在整理作品档案";
  const result = await api(`/project/library?project_root=${encodeURIComponent(root)}`);
  librarySnapshot = result;
  activeLibraryKind = form.section.value || activeLibraryKind;
  renderLibrary(result);
  await loadChoices(root);
  $("#libraryStatus").textContent = result.generated_at ? `已整理 ${formatTime(result.generated_at)}` : "已整理";
  return result;
}

function renderLibrary(result) {
  const project = result.project || {};
  const counts = result.counts || {};
  const sections = result.sections || {};
  const projectBadges = Array.isArray(project.badges) ? project.badges.filter(Boolean) : [];
  $("#librarySummary").innerHTML = `
    <article class="library-cover">
      <div class="cover-stamp">作品</div>
      <div>
        <span class="eyebrow light">当前项目</span>
        <h3>${escapeHtml(project.title || "未命名作品")}</h3>
        <p>${escapeHtml(project.excerpt || "还没有项目简介。")}</p>
        <footer>${projectBadges.map((badge) => `<span>${escapeHtml(badge)}</span>`).join("")}</footer>
      </div>
    </article>
    <article class="library-stat"><b>${escapeHtml(counts.drafts || 0)}</b><span>正文与候选</span></article>
    <article class="library-stat"><b>${escapeHtml(counts.characters || 0)}</b><span>人物档案</span></article>
    <article class="library-stat"><b>${escapeHtml(counts.scenes || 0)}</b><span>场景设定</span></article>
    <article class="library-stat"><b>${escapeHtml(counts.branches || 0)}</b><span>分支推演</span></article>
  `;

  $("#libraryTabs").innerHTML = Object.entries(sectionNames).map(([key, label]) => {
    const count = counts[key] || 0;
    return `<button type="button" data-kind="${key}" class="${key === activeLibraryKind ? "active" : ""}">${escapeHtml(label)}<span>${escapeHtml(count)}</span></button>`;
  }).join("");
  const items = Array.isArray(sections[activeLibraryKind]) ? sections[activeLibraryKind] : [];
  renderLibraryList(items);
  if (items.length) selectLibraryItem(items[0]);
  else renderLibraryEmpty();
}

function renderLibraryList(items) {
  $("#libraryList").classList.toggle("empty", !items.length);
  $("#libraryList").innerHTML = items.length ? items.map((item, index) => `
    <button type="button" class="library-item ${selectedLibraryItem?.id === item.id ? "active" : ""}" data-index="${index}">
      <span>${escapeHtml(item.subtitle || sectionNames[item.kind] || "档案")}</span>
      <b>${escapeHtml(item.title || item.id)}</b>
      <p>${escapeHtml(item.excerpt || "暂无摘要。")}</p>
      <footer>${renderBadges(item.badges)}</footer>
    </button>
  `).join("") : "这个分类下还没有可展示内容。";
}

function renderLibraryEmpty() {
  selectedLibraryItem = null;
  $("#libraryDetail").className = "library-detail empty";
  $("#libraryDetail").innerHTML = "这个分类暂时没有内容。";
}

function selectLibraryItem(item) {
  selectedLibraryItem = item;
  const items = librarySnapshot?.sections?.[activeLibraryKind] || [];
  renderLibraryList(items);
  const body = item.body ? renderBody(item.body) : `<p>${escapeHtml(item.excerpt || "暂无正文或详情。")}</p>`;
  const facts = Array.isArray(item.facts) ? item.facts : [];
  const metrics = item.metrics || {};
  const options = Array.isArray(item.options) && item.options.length ? `
    <div class="branch-options">
      ${item.options.map((option) => `
        <article class="${option.selected ? "selected" : ""}">
          <b>${escapeHtml(option.label || option.id)}</b>
          <p>${escapeHtml(option.summary || "暂无说明。")}</p>
          ${option.risk ? `<small>${escapeHtml(option.risk)}</small>` : ""}
        </article>
      `).join("")}
    </div>
  ` : "";
  $("#libraryDetail").className = "library-detail";
  $("#libraryDetail").innerHTML = `
    <article class="detail-head">
      <span>${escapeHtml(item.subtitle || sectionNames[item.kind] || "档案")}</span>
      <h3>${escapeHtml(item.title || item.id)}</h3>
      <footer>${renderBadges(item.badges)}</footer>
    </article>
    ${item.user_note ? `<aside class="user-note">你的备注：${escapeHtml(item.user_note)}</aside>` : ""}
    ${Object.keys(metrics).length ? renderMetricStrip(metrics) : ""}
    ${facts.length ? `<div class="fact-grid">${facts.map(renderFact).join("")}</div>` : ""}
    ${options}
    <div class="reader-body">${body}</div>
  `;
  const editForm = $("#editForm");
  editForm.target_type.value = item.kind || "";
  editForm.target_id.value = item.id || "";
  editForm.querySelector("[name=value]").value = "";
  $("#editStatus").textContent = `正在标注：${item.title || item.id}`;
}

function renderBadges(badges = []) {
  return (Array.isArray(badges) ? badges : []).filter(Boolean).slice(0, 5).map((badge) => `<span>${escapeHtml(badge)}</span>`).join("");
}

function renderFact(fact) {
  return `
    <article class="fact-card">
      <span>${escapeHtml(fact.label || "信息")}</span>
      <b>${escapeHtml(fact.value ?? "未填写")}</b>
    </article>
  `;
}

function renderMetricStrip(metrics) {
  const items = [
    ["中文内容字数", metrics.chinese_content_chars],
    ["机器字符", metrics.machine_nonspace_chars],
    ["目标字数", metrics.target_chinese_content_chars],
  ].filter(([, value]) => value !== undefined && value !== "");
  return `<div class="mini-metrics">${items.map(([label, value]) => `<span><b>${escapeHtml(value)}</b>${escapeHtml(label)}</span>`).join("")}</div>`;
}

function renderBody(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .filter((part) => part.trim())
    .slice(0, 30)
    .map((part) => `<p>${escapeHtml(part.trim()).replace(/\n/g, "<br />")}</p>`)
    .join("");
}

function renderBodyPreview(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .filter((part) => part.trim())
    .slice(0, 5)
    .map((part) => `<p>${escapeHtml(part.trim()).replace(/\n/g, "<br />")}</p>`)
    .join("") || "<p>正文为空或只有工程说明。</p>";
}

async function loadChoices(root = "") {
  const projectRoot = root || sharedProjectRoot();
  if (!projectRoot) return;
  const result = await api(`/workflow/current-choice?project_root=${encodeURIComponent(projectRoot)}`);
  currentChoices = result.choices || [];
  renderChoices(currentChoices, result.recent_choices || []);
}

function renderChoices(choices, recent = []) {
  const list = $("#choiceList");
  list.classList.toggle("empty", !choices.length && !recent.length);
  if (!choices.length && !recent.length) {
    list.innerHTML = "暂无等待用户选择的节点。正式流程需要你决定时，这里会出现分支卡、审批卡或扩纲方向卡。";
    return;
  }
  const choiceCards = choices.map((choice, index) => `
    <article class="choice-card" data-choice-index="${index}">
      <span>${escapeHtml(routeName(choice.route))}</span>
      <h3>${escapeHtml(choice.title || "等待选择")}</h3>
      <p>${escapeHtml(choice.summary || choice.next_action || "请选择一个方向。")}</p>
      ${choice.recommended ? `<div class="choice-recommended">建议关注：${escapeHtml(choice.recommended)}</div>` : ""}
      <div class="choice-options">
        ${(choice.options || []).map((option) => `
          <button type="button" class="choice-option" data-selected="${escapeHtml(option.id)}">
            <b>${escapeHtml(option.label || option.id)}</b>
            <small>${escapeHtml(option.summary || "")}</small>
          </button>
        `).join("")}
      </div>
      <textarea class="choice-rationale" rows="3" placeholder="可选：写下你为什么这样选，平台 Agent 后续会读取这条理由。"></textarea>
    </article>
  `).join("");
  const recentCards = recent.length ? `
    <div class="recent-choice">
      <b>最近记录</b>
      ${recent.slice(-4).reverse().map((item) => `<p>${escapeHtml(item.decision_type || "选择")}：${escapeHtml(item.selected || item.decision || "")}</p>`).join("")}
    </div>
  ` : "";
  list.innerHTML = choiceCards + recentCards;
}

async function submitHumanChoice(choice, selected, rationale) {
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const payload = {
    project_root: root,
    choice_id: choice.choice_id,
    route: choice.route,
    task_id: choice.task_id || "",
    decision_type: choice.decision_type,
    target: choice.target || {},
    options: choice.options || [],
    selected,
    rationale,
    actor: "user-ui",
    materialize: true,
  };
  const result = await api("/workflow/human-choice", { method: "POST", body: JSON.stringify(payload) });
  $("#libraryStatus").textContent = result.materialized ? `已记录选择，并写入 ${shortPath(result.materialized)}` : "已记录选择。";
  await loadLibrary();
}

async function saveDisplayField(event) {
  event.preventDefault();
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const data = formData($("#editForm"));
  const payload = {
    project_root: root,
    target_type: data.target_type,
    target_id: data.target_id,
    field: data.field,
    value: data.value,
    actor: "user-ui",
  };
  await api("/project/display-field", { method: "PATCH", body: JSON.stringify(payload) });
  $("#editStatus").textContent = "标注已保存。正式剧情改动仍需候选、审查和审批。";
  await loadLibrary();
}

async function saveUiNote(event) {
  event.preventDefault();
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const data = formData($("#editForm"));
  const payload = {
    project_root: root,
    target_type: data.target_type,
    target_id: data.target_id,
    note: data.value,
    actor: "user-ui",
  };
  await api("/project/ui-note", { method: "POST", body: JSON.stringify(payload) });
  $("#editStatus").textContent = "备注已追加。平台 Agent 可把它作为后续创作意图读取。";
  $("#editForm").querySelector("[name=value]").value = "";
  await loadLibrary();
}

function toggleLibraryPoll() {
  const button = $("#toggleLibraryPoll");
  if (libraryTimer) {
    clearInterval(libraryTimer);
    libraryTimer = null;
    button.textContent = "开始流式观察";
    $("#libraryStatus").textContent = "已停止观察";
    return;
  }
  guarded(loadLibrary);
  libraryTimer = setInterval(() => guarded(loadLibrary), 6000);
  button.textContent = "停止流式观察";
}

async function loadStyleStatus() {
  const data = formData($("#styleForm"));
  const root = data.project_root || $("#configForm").project_root.value || $("#dashboardForm").project_root.value;
  if (!root) throw new Error("请先填写当前项目目录。");
  setSharedProjectRoot(root);
  $("#styleStatusText").textContent = "正在检查";
  const result = await api(`/style-lab/mounts?project_root=${encodeURIComponent(root)}`);
  renderStyleStatus(result);
  await loadStyleLibrary(data.style_library_root || $("#configForm").style_library_root.value || "");
}

function renderStyleStatus(result) {
  const active = result.active_style_skill || {};
  const ready = active.readiness?.ready;
  $("#styleStatusText").textContent = "已检查";
  if (!active.style_id) {
    $("#styleStatus").className = "style-status empty";
    $("#styleStatus").innerHTML = "这个项目还没有挂载文风。正式长篇创作前，建议先完成文风学习并挂载 Style Skill。";
    return;
  }
  $("#styleStatus").className = `style-status ${ready ? "pass" : "warn"}`;
  $("#styleStatus").innerHTML = `
    <div class="style-name">${escapeHtml(active.style_id)}</div>
    <div class="key-state ${ready ? "pass" : "warn"}">${ready ? "可用于正式生成" : "还需要补齐评测或提示词质量"}</div>
    <p>文风会作为表达层最高优先级约束进入场景生成、修订和审查。</p>
  `;
}

async function loadStyleLibrary(styleRoot = "") {
  const query = styleRoot ? `?style_library_root=${encodeURIComponent(styleRoot)}` : "";
  const result = await api(`/style-lab/library${query}`);
  renderStyleLibrary(result.style_skills || {});
}

function renderStyleLibrary(styleSkills) {
  const items = styleSkills.items || [];
  const list = $("#styleLibrary");
  list.classList.toggle("empty", !items.length);
  if (!items.length) {
    list.innerHTML = "暂未发现可挂载文风。可以先通过文风学习流程生成 Style Skill。";
    return;
  }
  list.innerHTML = items.map((item) => `
    <article class="style-skill-card">
      <div>
        <span>${escapeHtml(item.author || item.author_id || "未知作家")}</span>
        <b>${escapeHtml(item.style_id)}</b>
        <p>${escapeHtml(item.mode || "文风技能")}</p>
      </div>
      <button type="button" class="mount-style" data-style-id="${escapeHtml(item.style_id)}">挂载</button>
    </article>
  `).join("");
}

async function mountStyle(styleId) {
  const data = formData($("#styleForm"));
  const root = data.project_root || sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const styleLibraryRoot = data.style_library_root || $("#configForm").style_library_root.value || "";
  await api("/workflow/human-choice", {
    method: "POST",
    body: JSON.stringify({
      project_root: root,
      route: "style-engineering",
      decision_type: "style_mount",
      target: { style_id: styleId },
      selected: styleId,
      rationale: "用户在前端文风库中选择挂载此文风。",
      actor: "user-ui",
      materialize: false,
    }),
  });
  const mounted = await api("/style-lab/mount", {
    method: "POST",
    body: JSON.stringify({
      project_root: root,
      style_library_root: styleLibraryRoot,
      style_id: styleId,
      allow_unreviewed: false,
    }),
  });
  renderStyleStatus(mounted);
  $("#styleStatusText").textContent = `已挂载 ${styleId}`;
  if ($("#libraryForm").project_root.value) guarded(loadLibrary);
}

function toggleDashboardPoll() {
  const button = $("#toggleDashboardPoll");
  if (dashboardTimer) {
    clearInterval(dashboardTimer);
    dashboardTimer = null;
    button.textContent = "开始实时观察";
    $("#dashboardStatus").textContent = "已停止观察";
    return;
  }
  const seconds = Math.max(3, Math.min(60, Number($("#dashboardForm").refresh_seconds.value) || 8));
  guarded(loadDashboard);
  dashboardTimer = setInterval(() => guarded(loadDashboard), seconds * 1000);
  button.textContent = "停止实时观察";
}

function routeName(route) {
  return routeNames[route] || route || "项目流程";
}

function friendlyTarget(value) {
  return String(value)
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\bscene\b/gi, "场景")
    .replace(/\bchapter\b/gi, "章节")
    .replace(/\blongform\b/gi, "长篇规划")
    .trim();
}

function friendlyMessage(value) {
  let text = String(value || "需要继续处理。");
  text = text.replace(/\.agent_tasks\.md/g, "平台 Agent 任务");
  text = text.replace(/\.agent_completion\.json/g, "任务完成标记");
  text = text.replace(/\.json/g, "记录");
  text = text.replace(/\.md/g, "报告");
  text = text.replace(/_/g, " ");
  text = text.replace(/route-audit/gi, "路线审计");
  text = text.replace(/sidecar/gi, "平台任务");
  text = text.replace(/workflow/g, "工作流");
  text = text.replace(/candidate/g, "候选稿");
  text = text.replace(/promotion/g, "晋升");
  text = text.replace(/review/g, "审查");
  return text;
}

function friendlyRule(value) {
  const text = String(value || "");
  if (text.includes("read-only")) return "总控面板只读，不能绕过任务领取、提交和完成确认。";
  if (text.includes("platform agent")) return "创作与审查判断仍由平台 Agent 执行，本页只聚合正式证据。";
  if (text.includes("blocking message")) return "出现阻塞时，阻塞说明就是下一条修复任务。";
  return friendlyMessage(text);
}

function routeReadyText(route) {
  const copy = {
    "scene-development": "场景开发证据完整，可以继续推进下一场。",
    "longform-planning": "长篇规划没有发现硬阻塞。",
    "source-ingest": "旧文导入链路暂时正常。",
    "style-engineering": "文风工程没有发现硬阻塞。",
    "character-and-world-assets": "人物与世界资产链路暂时正常。",
    "review-and-audit": "审查与审计链路暂时正常。",
    "export-and-release": "导出与发布链路暂时正常。",
  };
  return copy[route] || "这条流程暂时没有硬阻塞。";
}

function eventLabel(value) {
  const labels = {
    issued: "已派发任务",
    opened: "已打开任务",
    submitted: "已提交产物",
    completed: "已完成任务",
    invalid: "记录异常",
  };
  return labels[value] || "项目事件";
}

function shortPath(value) {
  const text = String(value || "");
  if (text.length <= 54) return text;
  return `...${text.slice(-51)}`;
}

function formatTime(value) {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function toast(message) {
  $("#dashboardStatus").textContent = message;
}

function activateView(view) {
  $$(".nav button").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((item) => item.classList.toggle("active", item.id === `view-${view}`));
}

async function openLibraryDrafts() {
  activeLibraryKind = "drafts";
  if ($("#libraryForm")) $("#libraryForm").section.value = "drafts";
  activateView("library");
  await loadLibrary();
}

function bind() {
  $$(".nav button").forEach((button) => {
    button.addEventListener("click", () => {
      activateView(button.dataset.view);
      if (button.dataset.view === "dashboard" && sharedProjectRoot()) guarded(loadDashboard);
      if (button.dataset.view === "library" && sharedProjectRoot()) guarded(loadLibrary);
      if (button.dataset.view === "style" && sharedProjectRoot()) guarded(loadStyleStatus);
    });
  });
  $("#refreshDashboard").addEventListener("click", () => guarded(loadDashboard));
  $("#toggleDashboardPoll").addEventListener("click", () => toggleDashboardPoll());
  $("#dashboardProse").addEventListener("click", (event) => {
    if (event.target.closest(".open-library-drafts") || event.target.closest(".completed-mini")) {
      guarded(openLibraryDrafts);
    }
  });
  $("#refreshLibrary").addEventListener("click", () => guarded(loadLibrary));
  $("#toggleLibraryPoll").addEventListener("click", () => toggleLibraryPoll());
  $("#libraryForm").section.addEventListener("change", (event) => {
    activeLibraryKind = event.target.value;
    if (librarySnapshot) renderLibrary(librarySnapshot);
  });
  $("#libraryTabs").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-kind]");
    if (!button) return;
    activeLibraryKind = button.dataset.kind;
    $("#libraryForm").section.value = activeLibraryKind;
    if (librarySnapshot) renderLibrary(librarySnapshot);
  });
  $("#libraryList").addEventListener("click", (event) => {
    const button = event.target.closest(".library-item");
    if (!button || !librarySnapshot) return;
    const items = librarySnapshot.sections?.[activeLibraryKind] || [];
    const item = items[Number(button.dataset.index)];
    if (item) selectLibraryItem(item);
  });
  $("#choiceList").addEventListener("click", (event) => {
    const button = event.target.closest(".choice-option");
    if (!button) return;
    const card = button.closest(".choice-card");
    const choice = currentChoices[Number(card.dataset.choiceIndex)];
    if (!choice) return;
    const rationale = card.querySelector(".choice-rationale")?.value || "";
    guarded(() => submitHumanChoice(choice, button.dataset.selected, rationale));
  });
  $("#saveDisplayField").addEventListener("click", (event) => guarded(() => saveDisplayField(event)));
  $("#saveUiNote").addEventListener("click", (event) => guarded(() => saveUiNote(event)));
  $("#loadStyleStatus").addEventListener("click", () => guarded(loadStyleStatus));
  $("#styleLibrary").addEventListener("click", (event) => {
    const button = event.target.closest(".mount-style");
    if (!button) return;
    guarded(() => mountStyle(button.dataset.styleId));
  });
  $("#loadConfig").addEventListener("click", () => guarded(loadConfig));
  $("#saveConfig").addEventListener("click", () => guarded(saveConfig));
  $("#apiToken").value = localStorage.getItem("lewApiToken") || "";
  $("#apiToken").addEventListener("input", (event) => {
    localStorage.setItem("lewApiToken", event.target.value.trim());
  });
}

async function guarded(fn) {
  try {
    await fn();
  } catch (error) {
    $("#dashboardStatus").textContent = error.message || String(error);
  }
}

bind();
loadHealth();
guarded(loadConfig);
