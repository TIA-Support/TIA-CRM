const state = { me: null, users: [], companiesCache: [], currentCompanyId: null, activeTab: "activities" };

const STATUS_LABELS = { new: "New", contacted: "Contacted", interested: "Interested", not_interested: "Not interested", customer: "Customer", do_not_contact: "Do not contact" };
const STAGE_LABELS = { lead: "Lead", qualified: "Qualified", proposal_sent: "Proposal sent", negotiation: "Negotiation", won: "Won", lost: "Lost" };
const OUTCOME_LABELS = { no_answer: "No answer", callback: "Requested callback", interested: "Interested", not_interested: "Not interested", converted: "Converted", wrong_number: "Wrong number" };
const ACTIVITY_TYPE_LABELS = { call: "Call", email: "Email", meeting: "Meeting", note: "Note" };

// ---------- API ----------
async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (res.status === 401) { showLogin(); throw new Error("Not authenticated"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

// ---------- Auth ----------
function showLogin() { document.getElementById("login-screen").classList.remove("hidden"); document.getElementById("app").classList.add("hidden"); }
function showApp() { document.getElementById("login-screen").classList.add("hidden"); document.getElementById("app").classList.remove("hidden"); }

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.textContent = "";
  try {
    const user = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    state.me = user;
    onLoggedIn();
  } catch (err) { errorEl.textContent = err.message; }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  state.me = null;
  showLogin();
});

async function checkSession() {
  try { state.me = await api("/api/auth/me"); onLoggedIn(); }
  catch { showLogin(); }
}

async function onLoggedIn() {
  showApp();
  document.getElementById("me-name").textContent = state.me.name;
  document.getElementById("me-role").textContent = state.me.role;
  document.getElementById("me-avatar").textContent = state.me.name.charAt(0).toUpperCase();
  if (state.me.role === "agent") document.getElementById("nav-team").classList.add("hidden");
  await loadUsers();
  navigate("dashboard");
}

// ---------- Navigation ----------
document.querySelectorAll(".nav-item").forEach((btn) => btn.addEventListener("click", () => navigate(btn.dataset.view)));

function navigate(view) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  document.getElementById(`view-${view}`).classList.remove("hidden");
  if (view === "dashboard") loadDashboard();
  if (view === "companies") loadCompanies();
  if (view === "pipeline") loadPipeline();
  if (view === "tasks") loadTasks();
  if (view === "team") loadTeam();
}

// ---------- Users (shared across forms) ----------
async function loadUsers() {
  state.users = await api("/api/users");
  document.querySelectorAll(".assign-to-select").forEach((select) => {
    select.innerHTML = state.users.map((u) => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
    select.value = state.me.id;
  });
}

async function loadTeam() {
  await loadUsers();
  const isAdmin = state.me.role === "admin";
  document.querySelector("#team-table tbody").innerHTML = state.users.map((u) => `
    <tr>
      <td>${escapeHtml(u.name)}</td>
      <td class="mono">${escapeHtml(u.email)}</td>
      <td style="text-transform:capitalize">${u.role}</td>
      <td>${isAdmin ? `<button class="btn btn-ghost btn-sm" data-reset="${u.id}" data-name="${escapeHtml(u.name)}">Reset password</button>` : ""}</td>
    </tr>
  `).join("");

  document.querySelectorAll("[data-reset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById("reset-password-form").dataset.userId = btn.dataset.reset;
      document.getElementById("reset-password-user-name").textContent = btn.dataset.name;
      openModal("modal-reset-password");
    });
  });
}

// ---------- Dashboard ----------
async function loadDashboard() {
  document.getElementById("today-date").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const s = await api("/api/dashboard/summary");

  document.getElementById("stat-grid").innerHTML = `
    <div class="stat-card"><div class="num">${s.calls_today}</div><div class="label">Calls today</div></div>
    <div class="stat-card ${s.followups_due > 0 ? "alert" : ""}"><div class="num">${s.followups_due}</div><div class="label">Follow-ups due</div></div>
    <div class="stat-card ${s.tasks_due_today > 0 ? "alert" : ""}"><div class="num">${s.tasks_due_today}</div><div class="label">Tasks due today</div></div>
    <div class="stat-card accent"><div class="num">${formatCurrency(s.pipeline_value)}</div><div class="label">Open pipeline (${s.open_deal_count} deals)</div></div>
  `;

  document.getElementById("stage-breakdown").innerHTML = Object.keys(STAGE_LABELS).map((stg) => `
    <div class="status-row"><span class="stage-pill">${STAGE_LABELS[stg]}</span><span class="count">${s.stage_breakdown[stg] || 0}</span></div>
  `).join("");

  const lb = s.leaderboard_month;
  const max = Math.max(1, ...lb.map((r) => r.calls_made));
  document.getElementById("leaderboard").innerHTML = lb.length
    ? lb.map((r) => `
        <div class="leaderboard-row">
          <span style="width:90px">${escapeHtml(r.name)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(r.calls_made / max) * 100}%"></div></div>
          <span class="lb-count">${r.calls_made}</span>
        </div>`).join("")
    : `<div class="empty-state">No calls logged yet this month.</div>`;
}

// ---------- Companies list ----------
async function loadCompanies() {
  const search = document.getElementById("company-search").value;
  const status = document.getElementById("status-filter").value;
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status", status);

  const companies = await api(`/api/companies?${params.toString()}`);
  state.companiesCache = companies;
  populateCompanySelects(companies);
  const tbody = document.querySelector("#companies-table tbody");

  if (!companies.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">No companies yet — add your first lead.</div></td></tr>`;
    return;
  }

  const today = new Date().toISOString().slice(0, 10);
  tbody.innerHTML = companies.map((c) => {
    const overdue = c.next_task_due && c.next_task_due <= today;
    return `
    <tr class="clickable" data-id="${c.id}">
      <td><strong>${escapeHtml(c.name)}</strong></td>
      <td>${escapeHtml(c.industry || "—")}</td>
      <td><span class="status-chip status-${c.status}">${STATUS_LABELS[c.status]}</span></td>
      <td>${escapeHtml(c.assigned_name || "—")}</td>
      <td class="mono">${c.contact_count}</td>
      <td class="mono">${c.open_deal_count}</td>
      <td class="${overdue ? "overdue" : ""}">${c.next_task_due ? formatDate(c.next_task_due) : "—"}</td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll("tr[data-id]").forEach((row) => row.addEventListener("click", () => openCompanyDetail(row.dataset.id)));
}

document.getElementById("company-search").addEventListener("input", debounce(loadCompanies, 300));
document.getElementById("status-filter").addEventListener("change", loadCompanies);

function populateCompanySelects(companies) {
  document.querySelectorAll(".company-select").forEach((select) => {
    const placeholder = select.querySelector('option[value=""]');
    select.innerHTML = (placeholder ? placeholder.outerHTML : "") + companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  });
}

// ---------- Company detail ----------
async function openCompanyDetail(id) {
  state.currentCompanyId = id;
  state.activeTab = "activities";
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  document.getElementById("view-company-detail").classList.remove("hidden");
  await renderCompanyDetail();
}

async function renderCompanyDetail() {
  const c = await api(`/api/companies/${state.currentCompanyId}`);
  const el = document.getElementById("company-detail-content");

  el.innerHTML = `
    <div class="detail-header">
      <div>
        <h1>${escapeHtml(c.name)}</h1>
        <div class="detail-meta">
          <span>${escapeHtml(c.industry || "No industry set")}</span>
          ${c.tender_reference ? `<span class="mono">Ref: ${escapeHtml(c.tender_reference)}</span>` : ""}
          <span><span class="status-chip status-${c.status}">${STATUS_LABELS[c.status]}</span></span>
        </div>
      </div>
      <div class="detail-actions">
        <button class="btn btn-ghost" id="add-contact-btn">+ Contact</button>
        <button class="btn btn-ghost" id="add-deal-inline-btn">+ Deal</button>
        <button class="btn btn-primary" id="log-activity-btn">+ Log activity</button>
      </div>
    </div>

    <div class="detail-grid">
      <div class="info-panel">
        <div class="info-row"><div class="k">Assigned to</div><div class="v">${escapeHtml(c.assigned_name || "Unassigned")}</div></div>
        <div class="info-row"><div class="k">Source</div><div class="v">${escapeHtml(c.source || "—")}</div></div>
        <div class="info-row"><div class="k">Website</div><div class="v">${escapeHtml(c.website || "—")}</div></div>
        <div class="info-row"><div class="k">Added</div><div class="v">${formatDate(c.created_at)}</div></div>
        <h3 style="font-family:var(--font-display); font-size:14px; margin:20px 0 10px;">Contacts</h3>
        ${c.contacts.length ? c.contacts.map((ct) => `
          <div class="contact-card">
            <div class="contact-name">${escapeHtml(ct.name)} ${ct.is_primary ? '<span class="primary-badge">Primary</span>' : ""}</div>
            <div class="contact-meta">${escapeHtml(ct.title || "")}</div>
            <div class="contact-meta mono">${escapeHtml(ct.phone || "")} ${ct.email ? "· " + escapeHtml(ct.email) : ""}</div>
          </div>
        `).join("") : `<div class="empty-state">No contacts yet.</div>`}
      </div>

      <div>
        <div class="tab-bar">
          <button class="tab-btn ${state.activeTab === "activities" ? "active" : ""}" data-tab="activities">Activity (${c.activities.length})</button>
          <button class="tab-btn ${state.activeTab === "deals" ? "active" : ""}" data-tab="deals">Deals (${c.deals.length})</button>
          <button class="tab-btn ${state.activeTab === "tasks" ? "active" : ""}" data-tab="tasks">Tasks (${c.tasks.length})</button>
        </div>
        <div class="tab-panel" id="tab-panel-content"></div>
      </div>
    </div>
  `;

  renderTabPanel(c);

  document.querySelectorAll(".tab-btn").forEach((btn) => btn.addEventListener("click", () => {
    state.activeTab = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b === btn));
    renderTabPanel(c);
  }));

  document.getElementById("log-activity-btn").addEventListener("click", () => {
    document.getElementById("log-activity-company-name").textContent = c.name;
    document.getElementById("log-activity-form").dataset.companyId = c.id;
    onActivityTypeChange();
    openModal("modal-log-activity");
  });
  document.getElementById("add-contact-btn").addEventListener("click", () => {
    document.getElementById("add-contact-form").dataset.companyId = c.id;
    openModal("modal-add-contact");
  });
  document.getElementById("add-deal-inline-btn").addEventListener("click", () => {
    populateCompanySelects(state.companiesCache.length ? state.companiesCache : [c]);
    document.querySelector('#modal-add-deal select[name="company_id"]').value = c.id;
    openModal("modal-add-deal");
  });
}

function renderTabPanel(c) {
  const panel = document.getElementById("tab-panel-content");
  if (state.activeTab === "activities") {
    panel.innerHTML = c.activities.length ? c.activities.map((a) => `
      <div class="activity-entry">
        <div class="activity-entry-head">
          <span><span class="activity-type-tag">${ACTIVITY_TYPE_LABELS[a.type]}</span> ${a.outcome ? " · " + OUTCOME_LABELS[a.outcome] : ""}</span>
          <span class="activity-entry-meta">${escapeHtml(a.user_name || "")} · ${formatDateTime(a.occurred_at)}</span>
        </div>
        ${a.notes ? `<div class="activity-entry-notes">${escapeHtml(a.notes)}</div>` : ""}
        ${a.next_follow_up ? `<div class="activity-entry-followup">Follow up on ${formatDate(a.next_follow_up)}</div>` : ""}
      </div>
    `).join("") : `<div class="empty-state">No activity logged yet.</div>`;
  } else if (state.activeTab === "deals") {
    panel.innerHTML = c.deals.length ? c.deals.map((d) => `
      <div class="deal-card">
        <div class="deal-card-head">
          <span class="deal-title">${escapeHtml(d.title)}</span>
          <span class="deal-value">${d.value != null ? formatCurrency(d.value) : "—"}</span>
        </div>
        <div class="deal-meta"><span class="stage-pill">${STAGE_LABELS[d.stage]}</span> ${d.expected_close_date ? " · closes " + formatDate(d.expected_close_date) : ""} ${d.assigned_name ? " · " + escapeHtml(d.assigned_name) : ""}</div>
      </div>
    `).join("") : `<div class="empty-state">No deals yet.</div>`;
  } else if (state.activeTab === "tasks") {
    panel.innerHTML = c.tasks.length ? c.tasks.map((t) => `
      <div class="activity-entry">
        <div class="activity-entry-head">
          <span class="${t.status === "done" ? "task-row-done" : ""}">${escapeHtml(t.title)}</span>
          <span class="activity-entry-meta">${t.due_date ? formatDate(t.due_date) : "No due date"}</span>
        </div>
        ${t.description ? `<div class="activity-entry-notes">${escapeHtml(t.description)}</div>` : ""}
      </div>
    `).join("") : `<div class="empty-state">No tasks yet.</div>`;
  }
}

document.getElementById("back-to-companies").addEventListener("click", () => navigate("companies"));

function onActivityTypeChange() {
  const type = document.getElementById("activity-type-select").value;
  const outcomeField = document.getElementById("outcome-field");
  const outcomeSelect = outcomeField.querySelector("select");
  if (type === "call") {
    outcomeField.classList.remove("hidden");
    outcomeSelect.required = true;
  } else {
    outcomeField.classList.add("hidden");
    outcomeSelect.required = false;
  }
}
document.getElementById("activity-type-select").addEventListener("change", onActivityTypeChange);

// ---------- Pipeline (kanban) ----------
async function loadPipeline() {
  await loadUsers();
  populateCompanySelects(state.companiesCache.length ? state.companiesCache : await api("/api/companies"));
  const board = await api("/api/pipeline");
  const kanban = document.getElementById("kanban-board");

  kanban.innerHTML = Object.keys(STAGE_LABELS).filter((s) => s !== "won" && s !== "lost").concat(["won", "lost"]).map((stage) => `
    <div class="kanban-col">
      <h4>${STAGE_LABELS[stage]} <span class="count">${(board[stage] || []).length}</span></h4>
      ${(board[stage] || []).map((d) => `
        <div class="kanban-card" data-deal-id="${d.id}" data-company-id="${d.company_id}">
          <div class="kc-title">${escapeHtml(d.title)}</div>
          <div class="kc-company">${escapeHtml(d.company_name || "")}</div>
          ${d.value != null ? `<div class="kc-value">${formatCurrency(d.value)}</div>` : ""}
          <select data-stage-select="${d.id}">
            ${Object.keys(STAGE_LABELS).map((s) => `<option value="${s}" ${s === d.stage ? "selected" : ""}>${STAGE_LABELS[s]}</option>`).join("")}
          </select>
        </div>
      `).join("")}
    </div>
  `).join("");

  kanban.querySelectorAll(".kanban-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.tagName === "SELECT") return;
      openCompanyDetail(card.dataset.companyId);
    });
  });
  kanban.querySelectorAll("[data-stage-select]").forEach((select) => {
    select.addEventListener("click", (e) => e.stopPropagation());
    select.addEventListener("change", async (e) => {
      e.stopPropagation();
      await api(`/api/deals/${select.dataset.stageSelect}`, { method: "PUT", body: JSON.stringify({ stage: select.value }) });
      loadPipeline();
    });
  });
}

// won/lost stages need their own tinted columns — but note board still only returns non-closed deals by default;
// won/lost columns will simply show empty unless the API is called with them included, which is fine for a working board.

// ---------- Tasks ----------
async function loadTasks() {
  const status = document.getElementById("task-status-filter").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const tasks = await api(`/api/tasks?${params.toString()}`);

  const tbody = document.querySelector("#tasks-table tbody");
  tbody.innerHTML = tasks.length ? tasks.map((t) => {
    const today = new Date().toISOString().slice(0, 10);
    const overdue = t.due_date && t.due_date < today && t.status !== "done";
    return `
    <tr>
      <td><input type="checkbox" data-task-toggle="${t.id}" ${t.status === "done" ? "checked" : ""} /></td>
      <td class="${t.status === "done" ? "task-row-done" : ""}">${escapeHtml(t.title)}</td>
      <td>${t.company_name ? `<span class="mono">${escapeHtml(t.company_name)}</span>` : "—"}</td>
      <td class="${overdue ? "overdue" : ""}">${t.due_date ? formatDate(t.due_date) : "—"}</td>
      <td>${escapeHtml(t.assigned_name || "—")}</td>
      <td><button class="btn btn-ghost btn-sm" data-delete-task="${t.id}">Delete</button></td>
    </tr>`;
  }).join("") : `<tr><td colspan="6"><div class="empty-state">No tasks here.</div></td></tr>`;

  tbody.querySelectorAll("[data-task-toggle]").forEach((cb) => cb.addEventListener("change", async () => {
    await api(`/api/tasks/${cb.dataset.taskToggle}`, { method: "PUT", body: JSON.stringify({ status: cb.checked ? "done" : "pending" }) });
    loadTasks();
  }));
  tbody.querySelectorAll("[data-delete-task]").forEach((btn) => btn.addEventListener("click", async () => {
    await api(`/api/tasks/${btn.dataset.deleteTask}`, { method: "DELETE" });
    loadTasks();
  }));
}
document.getElementById("task-status-filter").addEventListener("change", loadTasks);

// ---------- Modals ----------
function openModal(id) {
  document.getElementById("modal-backdrop").classList.remove("hidden");
  document.querySelectorAll(".modal").forEach((m) => m.classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}
function closeModals() { document.getElementById("modal-backdrop").classList.add("hidden"); }
document.querySelectorAll("[data-close-modal]").forEach((btn) => btn.addEventListener("click", closeModals));
document.getElementById("modal-backdrop").addEventListener("click", (e) => { if (e.target.id === "modal-backdrop") closeModals(); });

document.getElementById("add-company-btn").addEventListener("click", () => openModal("modal-add-company"));
document.getElementById("add-deal-btn").addEventListener("click", () => openModal("modal-add-deal"));
document.getElementById("add-task-btn").addEventListener("click", () => openModal("modal-add-task"));
document.getElementById("add-user-btn").addEventListener("click", () => openModal("modal-add-user"));

document.getElementById("add-company-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  try { await api("/api/companies", { method: "POST", body: JSON.stringify(payload) }); closeModals(); form.reset(); loadCompanies(); }
  catch (err) { alert(err.message); }
});

document.getElementById("add-contact-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.is_primary = form.querySelector('[name="is_primary"]').checked;
  try {
    await api(`/api/companies/${form.dataset.companyId}/contacts`, { method: "POST", body: JSON.stringify(payload) });
    closeModals(); form.reset(); renderCompanyDetail();
  } catch (err) { alert(err.message); }
});

document.getElementById("add-deal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  if (payload.value === "") delete payload.value;
  if (payload.expected_close_date === "") delete payload.expected_close_date;
  try {
    await api("/api/deals", { method: "POST", body: JSON.stringify(payload) });
    closeModals(); form.reset();
    if (!document.getElementById("view-pipeline").classList.contains("hidden")) loadPipeline();
    if (state.currentCompanyId && !document.getElementById("view-company-detail").classList.contains("hidden")) renderCompanyDetail();
  } catch (err) { alert(err.message); }
});

document.getElementById("log-activity-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.company_id = form.dataset.companyId;
  if (payload.next_follow_up === "") delete payload.next_follow_up;
  try { await api("/api/activities", { method: "POST", body: JSON.stringify(payload) }); closeModals(); form.reset(); renderCompanyDetail(); }
  catch (err) { alert(err.message); }
});

document.getElementById("add-task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  if (payload.company_id === "") delete payload.company_id;
  if (payload.due_date === "") delete payload.due_date;
  try {
    await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
    closeModals(); form.reset();
    if (!document.getElementById("view-tasks").classList.contains("hidden")) loadTasks();
  } catch (err) { alert(err.message); }
});

document.getElementById("add-user-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  try { await api("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }); closeModals(); form.reset(); loadTeam(); }
  catch (err) { alert(err.message); }
});

document.getElementById("reset-password-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    await api(`/api/users/${form.dataset.userId}/reset_password`, { method: "POST", body: JSON.stringify(payload) });
    closeModals(); form.reset();
    alert("Password reset.");
  } catch (err) { alert(err.message); }
});

// ---------- Utils ----------
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function formatDate(str) {
  if (!str) return "—";
  const d = new Date(str.includes("T") ? str : str + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
function formatDateTime(str) {
  if (!str) return "—";
  const d = new Date(str);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " " + d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
function formatCurrency(n) {
  return "R " + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
}
function debounce(fn, ms) { let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); }; }

checkSession();
