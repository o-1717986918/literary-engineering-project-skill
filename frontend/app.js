const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
let dashboardTimer = null;

function pretty(value) {
  return JSON.stringify(value, null, 2);
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
    throw new Error(typeof body === "object" ? body.detail || pretty(body) : body);
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
  return $("#dashboardForm")?.project_root.value || $("#chatForm")?.project_root.value || $("#configForm")?.project_root.value || "";
}

async function loadHealth() {
  try {
    const health = await api("/health");
    $("#healthDot").classList.add("ok");
    $("#healthText").textContent = `API ${health.version}`;
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
  $("#configPreview").textContent = pretty(cfg);
  $("#envPreview").textContent = pretty(await api("/config/env"));
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
  $("#configPreview").textContent = pretty(saved);
  setSharedProjectRoot(data.project_root);
  setSharedStyleLibraryRoot(data.style_library_root);
}

async function loadStyleLibrary() {
  const data = formData($("#styleForm"));
  const query = data.style_library_root ? `?style_library_root=${encodeURIComponent(data.style_library_root)}` : "";
  const result = await api(`/style-lab/library${query}`);
  $("#styleLibraryPreview").textContent = pretty(result);
  if (result.style_library_root) setSharedStyleLibraryRoot(result.style_library_root);
}

async function createAuthor() {
  const data = formData($("#styleForm"));
  const result = await api("/style-lab/author", {
    method: "POST",
    body: JSON.stringify({
      style_library_root: data.style_library_root,
      name: data.author_name,
      author_id: data.author_id,
      mode: data.mode,
      source_note: data.source_note,
    }),
  });
  $("#styleResult").textContent = pretty(result);
  $("#styleForm").author_id.value = result.author_id;
  await loadStyleLibrary();
}

async function createWork() {
  const data = formData($("#styleForm"));
  const result = await api("/style-lab/work", {
    method: "POST",
    body: JSON.stringify({
      style_library_root: data.style_library_root,
      author_id: data.author_id,
      title: data.work_title,
      work_id: data.work_id,
      year: data.year,
      notes: data.work_notes,
    }),
  });
  $("#styleResult").textContent = pretty(result);
  $("#styleForm").work_id.value = result.work_id;
  await loadStyleLibrary();
}

async function importSource() {
  const data = formData($("#styleForm"));
  const result = await api("/style-lab/import-source", {
    method: "POST",
    body: JSON.stringify({
      style_library_root: data.style_library_root,
      author_id: data.author_id,
      work_id: data.work_id,
      text: data.source_text,
      filename: data.filename,
    }),
  });
  $("#styleResult").textContent = pretty(result);
  await loadStyleLibrary();
}

async function compileStyle() {
  const data = formData($("#styleForm"));
  const result = await api("/style-lab/compile", {
    method: "POST",
    body: JSON.stringify({
      style_library_root: data.style_library_root,
      author_id: data.author_id,
      profile_id: data.profile_id || "default",
      provider: data.provider || "auto",
    }),
  });
  $("#styleResult").textContent = pretty(result);
}

async function buildStyleSkill() {
  const data = formData($("#styleForm"));
  const result = await api("/style-lab/build-skill", {
    method: "POST",
    body: JSON.stringify({
      style_library_root: data.style_library_root,
      author_id: data.author_id,
      profile_id: data.profile_id || "default",
      style_id: data.style_id,
    }),
  });
  $("#styleResult").textContent = pretty(result);
  $("#styleForm").style_id.value = result.style_id;
  await loadStyleLibrary();
}

async function evaluateStyle() {
  const data = formData($("#styleForm"));
  const result = await api("/style-lab/evaluate", {
    method: "POST",
    body: JSON.stringify({
      style_library_root: data.style_library_root,
      author_id: data.author_id,
      profile_id: data.profile_id || "default",
      reference_text: data.reference_text,
      task_input_text: data.task_input_text,
      mode: data.eval_mode,
      provider: data.provider || "auto",
    }),
  });
  $("#styleResult").textContent = pretty(result);
}

async function mountStyleSkill() {
  const data = formData($("#styleForm"));
  const result = await api("/style-lab/mount", {
    method: "POST",
    body: JSON.stringify({
      project_root: data.project_root,
      style_library_root: data.style_library_root,
      style_id: data.style_id,
      allow_unreviewed: Boolean(data.allow_unreviewed),
    }),
  });
  $("#styleResult").textContent = pretty(result);
  setSharedProjectRoot(result.project_root);
}

async function loadDashboard() {
  const form = $("#dashboardForm");
  const root = form.project_root.value || $("#configForm").project_root.value || $("#chatForm").project_root.value;
  if (!root) throw new Error("请先填写当前项目路径");
  setSharedProjectRoot(root);
  $("#dashboardStatus").textContent = "刷新中";
  const result = await api(`/workflow/dashboard?project_root=${encodeURIComponent(root)}`);
  renderDashboard(result);
  return result;
}

function renderDashboard(result) {
  const dashboard = result.dashboard || {};
  const summary = result.summary || dashboard.summary || {};
  const metrics = [
    ["Ready", summary.ready_count ?? 0],
    ["State blocked", summary.state_blocked_count ?? 0],
    ["Route blocking", summary.blocking_count ?? 0],
    ["Pending sidecars", summary.pending_task_count ?? 0],
    ["Missing expected", summary.missing_expected_count ?? 0],
    ["Next actions", summary.next_action_count ?? (result.next_actions || []).length],
  ];
  $("#dashboardSummary").innerHTML = metrics.map(([label, value]) => (
    `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
  )).join("");

  const routes = result.route_audits || [];
  $("#dashboardRoutes").innerHTML = routes.length ? routes.map((route) => (
    `<tr><td>${escapeHtml(route.route || "")}</td><td>${escapeHtml(route.blocking_count ?? 0)}</td><td>${escapeHtml(route.warning_count ?? 0)}</td><td>${escapeHtml(route.pending_task_count ?? 0)}</td></tr>`
  )).join("") : '<tr><td colspan="4">暂无阻塞数据</td></tr>';

  const actions = result.next_actions || [];
  $("#dashboardNextActions").classList.toggle("empty", !actions.length);
  $("#dashboardNextActions").innerHTML = actions.length ? actions.slice(0, 20).map((action) => (
    `<article class="action-item"><b>${escapeHtml(action.route || "")}</b><span>${escapeHtml(action.target || "")}</span><p>${escapeHtml(action.next_action || "")}</p></article>`
  )).join("") : "暂无下一步";

  const events = result.recent_events || [];
  $("#dashboardEvents").classList.toggle("empty", !events.length);
  $("#dashboardEvents").innerHTML = events.length ? events.slice(-12).reverse().map((event) => (
    `<article class="event-item"><b>${escapeHtml(event.event_type || event.type || "event")}</b><span>${escapeHtml(event.created_at || event.timestamp || "")}</span><p>${escapeHtml(event.task_id || event.route || "")}</p></article>`
  )).join("") : "暂无事件";

  $("#dashboardPreview").textContent = pretty(dashboard);
  const generatedAt = dashboard.generated_at || "";
  $("#dashboardStatus").textContent = generatedAt ? `已刷新 ${generatedAt}` : "已刷新";
}

function toggleDashboardPoll() {
  const button = $("#toggleDashboardPoll");
  if (dashboardTimer) {
    clearInterval(dashboardTimer);
    dashboardTimer = null;
    button.textContent = "开始轮询";
    $("#dashboardStatus").textContent = "已停止轮询";
    return;
  }
  const seconds = Math.max(3, Math.min(60, Number($("#dashboardForm").refresh_seconds.value) || 8));
  guarded(loadDashboard);
  dashboardTimer = setInterval(() => guarded(loadDashboard), seconds * 1000);
  button.textContent = "停止轮询";
}

function addMessage(who, text, options = {}) {
  const node = document.createElement("div");
  node.className = `msg ${options.kind || ""}`.trim();
  const title = document.createElement("b");
  title.textContent = who;
  const body = document.createElement("div");
  body.textContent = text;
  node.append(title, body);
  if (options.meta) node.appendChild(options.meta);
  $("#chatLog").appendChild(node);
  $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
  return node;
}

function addDirectorMessage(result) {
  const conversation = result.conversation || {};
  const data = result.data || {};
  const audit = conversation.audit || data;
  const message = conversation.message || result.reply || "我已经处理了这轮创作方向。";
  const node = document.createElement("div");
  node.className = "msg director-msg";

  const title = document.createElement("b");
  title.textContent = conversation.speaker || "创作总监";
  node.appendChild(title);

  if (conversation.headline) {
    const headline = document.createElement("div");
    headline.className = "director-headline";
    headline.textContent = conversation.headline;
    node.appendChild(headline);
  }

  const body = document.createElement("div");
  body.className = "director-body";
  body.textContent = message;
  node.appendChild(body);

  appendConversationList(node, "可选取舍", conversation.next_questions, true);
  appendConversationList(node, "我会在后台处理", conversation.will_handle, true);
  node.appendChild(auditDetails(audit));

  $("#chatLog").appendChild(node);
  $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
}

function appendConversationList(parent, title, items, collapsed = false) {
  if (!Array.isArray(items) || !items.length) return;
  const wrapper = collapsed ? document.createElement("details") : document.createElement("div");
  wrapper.className = collapsed ? "conversation-list collapsed" : "conversation-list";
  if (collapsed) {
    const summary = document.createElement("summary");
    summary.textContent = title;
    wrapper.appendChild(summary);
  } else {
    const heading = document.createElement("span");
    heading.className = "conversation-label";
    heading.textContent = title;
    wrapper.appendChild(heading);
  }
  const list = document.createElement("ul");
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
  wrapper.appendChild(list);
  parent.appendChild(wrapper);
}

function auditDetails(audit) {
  const details = document.createElement("details");
  details.className = "audit-details";
  const summary = document.createElement("summary");
  summary.textContent = "处理记录";
  details.appendChild(summary);
  const rows = [
    ["Run", audit.run_id],
    ["Status", audit.status],
    ["Workflow", audit.workflow],
    ["Provider", audit.provider],
    ["Report", audit.report],
    ["Validation", audit.validation],
    ["Tool Loop", audit.tool_loop],
    ["Workflow State", audit.workflow_state],
  ].filter((item) => item[1]);
  const list = document.createElement("dl");
  rows.forEach(([key, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    list.append(dt, dd);
  });
  details.appendChild(list);
  return details;
}

async function sendChat(event) {
  event?.preventDefault();
  const data = formData($("#chatForm"));
  if (!data.message) return;
  data.project_root = data.project_root || $("#configForm").project_root.value;
  data.provider = data.provider || "auto";
  data.auto_execute = Boolean(data.auto_execute);
  setSharedProjectRoot(data.project_root);
  addMessage("你", data.message, { kind: "user-msg" });
  const result = await api("/director/chat", { method: "POST", body: JSON.stringify(data) });
  if (result.data?.project_root) setSharedProjectRoot(result.data.project_root);
  addDirectorMessage(result);
  $("#chatForm").message.value = "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function bind() {
  $$(".nav button").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".nav button").forEach((item) => item.classList.remove("active"));
      $$(".view").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $(`#view-${button.dataset.view}`).classList.add("active");
      if (button.dataset.view === "dashboard" && sharedProjectRoot()) {
        guarded(loadDashboard);
      }
    });
  });
  $("#refreshDashboard").addEventListener("click", () => guarded(loadDashboard));
  $("#toggleDashboardPoll").addEventListener("click", () => toggleDashboardPoll());
  $("#loadConfig").addEventListener("click", () => guarded(loadConfig));
  $("#saveConfig").addEventListener("click", () => guarded(saveConfig));
  $("#loadStyleLibrary").addEventListener("click", () => guarded(loadStyleLibrary));
  $("#createAuthor").addEventListener("click", () => guarded(createAuthor));
  $("#createWork").addEventListener("click", () => guarded(createWork));
  $("#importSource").addEventListener("click", () => guarded(importSource));
  $("#compileStyle").addEventListener("click", () => guarded(compileStyle));
  $("#buildStyleSkill").addEventListener("click", () => guarded(buildStyleSkill));
  $("#evaluateStyle").addEventListener("click", () => guarded(evaluateStyle));
  $("#mountStyleSkill").addEventListener("click", () => guarded(mountStyleSkill));
  $("#sendChat").addEventListener("click", () => guarded(sendChat));
  $("#chatForm").addEventListener("submit", (event) => guarded(() => sendChat(event)));
  $("#apiToken").value = localStorage.getItem("lewApiToken") || "";
  $("#apiToken").addEventListener("input", (event) => {
    localStorage.setItem("lewApiToken", event.target.value.trim());
  });
}

async function guarded(fn) {
  try {
    await fn();
  } catch (error) {
    addMessage("错误", error.message || String(error));
  }
}

bind();
loadHealth();
guarded(loadConfig).then(() => guarded(loadStyleLibrary));
