const taskInput = document.querySelector("#taskInput");
const runButton = document.querySelector("#runButton");
const formatButton = document.querySelector("#formatButton");
const resultsBody = document.querySelector("#resultsBody");
const analyticsGrid = document.querySelector("#analyticsGrid");
const runState = document.querySelector("#runState");
const statusStrip = document.querySelector("#statusStrip");
const analyticsState = document.querySelector("#analyticsState");
const version5Analytics = document.querySelector("#version5Analytics");
const toolingAnalysis = document.querySelector("#toolingAnalysis");
const tabButtons = [...document.querySelectorAll(".tab-button")];

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
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[char]));
}

function rawText(value) {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function percent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function statusClass(value) {
  const text = rawText(value);
  if (text.includes("blocked") || text.includes("DENIED")) return "bad";
  if (text.includes("PENDING") || text.includes("CONDITIONAL") || text.includes("review")) return "warn";
  if (text.includes("promotable") || text.includes("CERTIFIED")) return "ok";
  return "";
}

function tokenText(record) {
  const usage = record.token_usage || {};
  const total = usage.total_tokens || 0;
  const prompt = usage.prompt_tokens || 0;
  const completion = usage.completion_tokens || 0;
  return `${total} (${prompt}/${completion})`;
}

function switchView(viewId) {
  for (const button of tabButtons) {
    button.classList.toggle("active", button.dataset.view === viewId);
  }
  for (const view of document.querySelectorAll(".view")) {
    view.classList.toggle("active", view.id === viewId);
  }
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

function resultModelColumns(data) {
  return data.per_model_overall_metrics || [];
}

function renderEvidenceRows(data) {
  const rows = resultModelColumns(data);
  return `
    <h3>Results Per Model</h3>
    <div class="table-scroll">
      <table class="review-table">
        <thead>
          <tr>
            <th>Model / Provider</th>
            <th>Candidate Path</th>
            <th>Result File</th>
            <th>Suite</th>
            <th>Passed</th>
            <th>Accuracy</th>
            <th>Fireworks Tokens</th>
            <th>Runtime Failures</th>
            <th>Validation Failures</th>
            <th>Status</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${safeText(row.display_name)}</td>
              <td>${safeText(row.provider)} -> ${safeText(row.effective_provider)}</td>
              <td>${safeText(row.result_file_name)}</td>
              <td>${safeText(row.benchmark_suite)}<br><span class="muted">${safeText(row.benchmark_hash)}</span></td>
              <td>${safeText(row.overall_passed)} / ${safeText(row.overall_tasks)}</td>
              <td>${percent(row.overall_accuracy)}</td>
              <td>${safeText(row.judged_fireworks_tokens)}</td>
              <td>${safeText(row.runtime_failures)}</td>
              <td>${safeText(row.validation_failures)}</td>
              <td><span class="${statusClass(row.qualification_status)}">${safeText(row.qualification_status)}</span></td>
              <td>${row.qualification_only ? '<span class="warn">qualification-only</span>' : '<span class="ok">final-provider evidence</span>'}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderCategoryComparison(data) {
  const models = resultModelColumns(data);
  const rankings = data.per_category_ranking || {};
  return `
    <h3>Model Vs Category Comparison</h3>
    <div class="table-scroll">
      <table class="review-table category-table">
        <thead>
          <tr>
            <th>Task Category</th>
            ${models.map((model) => `<th>${safeText(model.display_name)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${Object.entries(rankings).map(([category, rows]) => `
            <tr>
              <td>${safeText(category)}</td>
              ${models.map((model) => {
                const row = (rows || []).find((item) => item.id === model.id) || {};
                const cls = Number(row.passed || 0) === 5 ? "ok" : Number(row.passed || 0) === 0 ? "bad" : "warn";
                return `<td>
                  <strong class="${cls}">${safeText(row.passed || 0)} / ${safeText(row.tasks || 0)}</strong><br>
                  ${percent(row.accuracy || 0)} · ${safeText(row.judged_fireworks_tokens || 0)} FW tokens<br>
                  ${safeText(row.validation_failures || 0)} validation · ${safeText(row.evaluator_failures || 0)} evaluator failures
                </td>`;
              }).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderRecommendations(data) {
  const recommendations = data.recommended_model_provider_per_category || {};
  const avoid = data.avoid_list_per_category || {};
  return `
    <h3>Deduced Analytics</h3>
    <div class="table-scroll">
      <table class="review-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Best Current Evidence</th>
            <th>Runner-Up</th>
            <th>Avoid</th>
            <th>Reason</th>
            <th>Confidence</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${Object.entries(recommendations).map(([category, row]) => `
            <tr>
              <td>${safeText(category)}</td>
              <td>${safeText(row.recommended)}</td>
              <td>${safeText(row.runner_up)}</td>
              <td>${(avoid[category] || []).map((item) => safeText(item.model)).join("<br>") || "-"}</td>
              <td>${safeText(row.reason)}</td>
              <td>${safeText(row.confidence)}</td>
              <td><span class="${statusClass(row.recommendation_status)}">${safeText(row.recommendation_status)}</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderWorkScopes(data) {
  const rows = data.work_scope_matrix || [];
  return `
    <h3>Work-Scope Per Model Table</h3>
    <div class="table-scroll">
      <table class="review-table">
        <thead>
          <tr>
            <th>Work Scope</th>
            <th>Benchmark Category</th>
            <th>Evidence Status</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((scope) => `
            <tr>
              <td>${safeText(scope.work_scope)}</td>
              <td>${safeText(scope.benchmark_category)}</td>
              <td>${(scope.models || []).map((item) => `
                <div class="scope-line">
                  <strong>${safeText(item.model)}</strong>
                  <span class="${statusClass(item.status)}">${safeText(item.status)}</span>
                  <span>${safeText(item.evidence_source)}</span>
                  <span>${safeText(item.reason)}</span>
                </div>
              `).join("")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderCategorization(data) {
  const report = data.categorization_evaluation || {};
  const matrix = report.confusion_matrix || {};
  const categories = Object.keys(matrix);
  return `
    <h3>Categorization Function Evaluation</h3>
    <div class="summary-strip">
      <span>Total ${safeText(report.total_tasks)}</span>
      <span>Accuracy ${percent(report.accuracy || 0)}</span>
      <span>Official shape ${report.official_shape_valid ? "valid" : "invalid"}</span>
      <span>Metadata withheld ${report.benchmark_metadata_withheld ? "yes" : "no"}</span>
    </div>
    <div class="table-scroll">
      <table class="review-table matrix-table">
        <thead>
          <tr>
            <th>Expected \\ Predicted</th>
            ${categories.map((category) => `<th>${safeText(category)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${categories.map((expected) => `
            <tr>
              <td>${safeText(expected)}</td>
              ${categories.map((predicted) => `<td>${safeText((matrix[expected] || {})[predicted] || 0)}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
    <div class="table-scroll">
      <table class="review-table">
        <thead><tr><th>Task</th><th>Expected</th><th>Predicted</th><th>Risk</th></tr></thead>
        <tbody>
          ${(report.miscategorized_task_ids || []).map((row) => `
            <tr>
              <td>${safeText(row.task_id)}</td>
              <td>${safeText(row.expected_category)}</td>
              <td>${safeText(row.predicted_category)}</td>
              <td>${safeText(row.downstream_risk)}</td>
            </tr>
          `).join("") || '<tr><td colspan="4" class="empty">No categorization misses</td></tr>'}
        </tbody>
      </table>
    </div>
    <p class="risk-note">${safeText(report.risk_note)}</p>
  `;
}

function renderVersion5Analytics(data) {
  version5Analytics.innerHTML = [
    renderEvidenceRows(data),
    renderCategoryComparison(data),
    renderRecommendations(data),
  ].join("");
  toolingAnalysis.innerHTML = [
    renderWorkScopes(data),
    renderCategorization(data),
  ].join("");
  analyticsState.textContent = "Loaded";
}

async function refreshVersion5Analytics() {
  const response = await fetch("/api/version5-analytics");
  if (!response.ok) throw new Error("analytics unavailable");
  renderVersion5Analytics(await response.json());
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
for (const button of tabButtons) {
  button.addEventListener("click", () => switchView(button.dataset.view));
}
refreshPreflight().catch(() => {
  statusStrip.innerHTML = `<span>Preflight unavailable</span>`;
});
refreshVersion5Analytics().catch((error) => {
  analyticsState.textContent = safeText(error.message);
  version5Analytics.innerHTML = `<p class="empty">${safeText(error.message)}</p>`;
  toolingAnalysis.innerHTML = `<p class="empty">${safeText(error.message)}</p>`;
});
