const taskInput = document.querySelector("#taskInput");
const runButton = document.querySelector("#runButton");
const formatButton = document.querySelector("#formatButton");
const resultsBody = document.querySelector("#resultsBody");
const analyticsGrid = document.querySelector("#analyticsGrid");
const runState = document.querySelector("#runState");
const statusStrip = document.querySelector("#statusStrip");

const versionNames = {
  version3: "Version 3",
  version4: "Version 4",
  version5: "Version 5",
};

function selectedVersions() {
  return [...document.querySelectorAll(".version-toggle input:checked")].map((node) => node.value);
}

function setBusy(isBusy) {
  runButton.disabled = isBusy;
  formatButton.disabled = isBusy;
  runState.textContent = isBusy ? "Running" : "Idle";
}

function safeText(value) {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function tokenText(record) {
  const usage = record.token_usage || {};
  const total = usage.total_tokens || 0;
  const prompt = usage.prompt_tokens || 0;
  const completion = usage.completion_tokens || 0;
  return `${total} (${prompt}/${completion})`;
}

function validationText(record) {
  const validation = record.validation_result || {};
  if (record.status === "blocked") return `<span class="warn">blocked</span>`;
  if (record.status === "failed") return `<span class="bad">failed</span>`;
  return validation.passed ? `<span class="ok">passed</span>` : `<span class="bad">${safeText(validation.reason)}</span>`;
}

function renderPreflight(data) {
  const items = [
    `Ollama model ${safeText(data.ollama_demo_model)}`,
    `Fireworks ${data.fireworks_base_url_configured ? "configured" : "not configured"}`,
    `Allowed models ${data.allowed_models_count || 0}`,
    `Lemonade active ${data.lemonade_active_runtime ? "yes" : "no"}`,
  ];
  statusStrip.innerHTML = items.map((item) => `<span>${item}</span>`).join("");
}

function renderAnalytics(analytics) {
  const entries = Object.entries(analytics || {});
  if (!entries.length) {
    analyticsGrid.innerHTML = "";
    return;
  }
  analyticsGrid.innerHTML = entries.map(([version, row]) => `
    <div class="metric">
      <span>${versionNames[version] || version}</span>
      <strong>${row.total_tokens || 0}</strong>
      <span>tokens · judged ${row.judged_fireworks_tokens || 0} · ${row.avg_latency_ms || 0} ms avg</span>
      <span>${row.completed || 0} complete · ${row.blocked || 0} blocked · ${row.validation_passed || 0} valid</span>
    </div>
  `).join("");
}

function flattenResults(payload) {
  const rows = [];
  for (const [version, records] of Object.entries(payload.results || {})) {
    for (const record of records) rows.push({ version, record });
  }
  return rows;
}

function renderResults(payload) {
  renderAnalytics(payload.analytics);
  const rows = flattenResults(payload);
  if (!rows.length) {
    resultsBody.innerHTML = `<tr><td colspan="8" class="empty">No run data</td></tr>`;
    return;
  }
  resultsBody.innerHTML = rows.map(({ version, record }) => `
    <tr>
      <td><span class="pill">${versionNames[version] || version}</span></td>
      <td>${safeText(record.task_id)}</td>
      <td>${safeText(record.selected_provider)}</td>
      <td>${safeText(record.selected_model)}</td>
      <td>${tokenText(record)}</td>
      <td>${safeText((record.latency || {}).milliseconds || 0)} ms</td>
      <td>${validationText(record)}</td>
      <td class="output-cell">${safeText(record.output || record.error)}</td>
    </tr>
  `).join("");
}

async function refreshPreflight() {
  const response = await fetch("/api/preflight");
  renderPreflight(await response.json());
}

async function runTasks() {
  setBusy(true);
  try {
    const payload = JSON.parse(taskInput.value);
    payload.versions = selectedVersions();
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "request failed");
    renderResults(data);
  } catch (error) {
    resultsBody.innerHTML = `<tr><td colspan="8" class="empty">${safeText(error.message)}</td></tr>`;
  } finally {
    setBusy(false);
  }
}

function formatInput() {
  const payload = JSON.parse(taskInput.value);
  taskInput.value = JSON.stringify(payload, null, 2);
}

runButton.addEventListener("click", runTasks);
formatButton.addEventListener("click", formatInput);
refreshPreflight().catch(() => {
  statusStrip.innerHTML = `<span>Preflight unavailable</span>`;
});
