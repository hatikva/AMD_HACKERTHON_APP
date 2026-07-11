const statusStrip = document.querySelector("#statusStrip");
const tabButtons = [...document.querySelectorAll(".tab-button")];
const views = [...document.querySelectorAll(".view")];

const nodes = {
  overview: document.querySelector("#overview"),
  results: document.querySelector("#results"),
  categories: document.querySelector("#categories"),
  routeFlow: document.querySelector("#routeFlow"),
  localEvidence: document.querySelector("#localEvidence"),
  readiness: document.querySelector("#readiness"),
  failures: document.querySelector("#failures"),
  compliance: document.querySelector("#compliance"),
  deduced: document.querySelector("#deduced"),
};

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

function percent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function statusClass(value) {
  const text = String(value || "");
  if (text.includes("blocked") || text.includes("DENIED") || text.includes("False")) return "bad";
  if (text.includes("PENDING") || text.includes("review") || text.includes("unavailable")) return "warn";
  if (text.includes("CERTIFIED") || text.includes("True") || text.includes("completed")) return "ok";
  return "";
}

function switchView(viewId) {
  for (const button of tabButtons) {
    const selected = button.dataset.view === viewId;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  }
  for (const view of views) {
    const selected = view.id === viewId;
    view.classList.toggle("active", selected);
    view.hidden = !selected;
  }
}

function table(headers, rows) {
  return `
    <div class="table-scroll">
      <table class="review-table">
        <thead><tr>${headers.map((header) => `<th>${safeText(header)}</th>`).join("")}</tr></thead>
        <tbody>${rows.length ? rows.join("") : `<tr><td colspan="${headers.length}" class="empty">No evidence</td></tr>`}</tbody>
      </table>
    </div>
  `;
}

function renderPreflight(data) {
  const items = [
    `Mode ${safeText(data.doctrine)}`,
    `Production ${safeText(data.version6_production_provider)}`,
    `Staging ${safeText(data.version6_staging_provider)}`,
    `Fireworks ${data.fireworks_base_url_configured ? "configured" : "not configured"}`,
    `Allowed models ${data.allowed_models_count || 0}`,
  ];
  statusStrip.innerHTML = items.map((item) => `<span>${item}</span>`).join("");
}

function renderOverview(data) {
  const overview = data.overview || {};
  nodes.overview.innerHTML = `
    <h3>Overview</h3>
    <div class="summary-strip">
      <span>${safeText(overview.active_version)}</span>
      <span>${safeText(overview.track)}</span>
      <span>${safeText(overview.team)}</span>
      <span>${safeText(overview.runtime)}</span>
    </div>
    <h3>Source Evidence</h3>
    ${table(["Result File"], (data.source_result_files || []).map((file) => `<tr><td>${safeText(file)}</td></tr>`))}
  `;
}

function renderResults(data) {
  nodes.results.innerHTML = `
    <h3>Results</h3>
    ${table(
      ["Provider", "Effective Provider", "Model", "Passed", "Accuracy", "Fireworks Tokens", "Failures", "Evidence"],
      (data.results || []).map((row) => `
        <tr>
          <td>${safeText(row.provider)}</td>
          <td>${safeText(row.effective_provider)}</td>
          <td>${safeText(row.display_name)}</td>
          <td>${safeText(row.overall_passed)} / ${safeText(row.overall_tasks)}</td>
          <td>${percent(row.overall_accuracy)}</td>
          <td>${safeText(row.judged_fireworks_tokens)}</td>
          <td>${safeText(row.runtime_failures + row.validation_failures + row.evaluator_failures)}</td>
          <td>${safeText(row.evidence_class)}</td>
        </tr>
      `)
    )}
  `;
}

function renderCategories(data) {
  const rankings = data.category_performance || {};
  const rows = Object.entries(rankings).flatMap(([category, items]) => (items || []).map((row) => `
    <tr>
      <td>${safeText(category)}</td>
      <td>${safeText(row.display_name)}</td>
      <td>${safeText(row.passed)} / ${safeText(row.tasks)}</td>
      <td>${percent(row.accuracy)}</td>
      <td>${safeText(row.judged_fireworks_tokens)}</td>
      <td>${safeText(row.validation_failures)}</td>
    </tr>
  `));
  nodes.categories.innerHTML = `<h3>Category Performance</h3>${table(["Category", "Provider", "Passed", "Accuracy", "Fireworks Tokens", "Validation"], rows)}`;
}

function renderRouteFlow(data) {
  const flow = data.route_and_token_flow || {};
  nodes.routeFlow.innerHTML = `
    <h3>Route And Token Flow</h3>
    ${table(
      ["Result", "Provider", "Effective Provider", "Judged Fireworks Tokens"],
      (flow.judged_fireworks_tokens_by_result || []).map((row) => `
        <tr>
          <td>${safeText(row.result_file)}</td>
          <td>${safeText(row.provider)}</td>
          <td>${safeText(row.effective_provider)}</td>
          <td>${safeText(row.judged_fireworks_tokens)}</td>
        </tr>
      `)
    )}
  `;
}

function renderLocal(data) {
  nodes.localEvidence.innerHTML = `
    <h3>Local Nemotron Evidence</h3>
    ${table(
      ["Provider", "Model", "Passed", "Accuracy", "Fireworks Tokens", "Evidence Class"],
      (data.local_nemotron_evidence || []).map((row) => `
        <tr>
          <td>${safeText(row.provider)}</td>
          <td>${safeText(row.model)}</td>
          <td>${safeText(row.overall_passed)} / ${safeText(row.overall_tasks)}</td>
          <td>${percent(row.overall_accuracy)}</td>
          <td>${safeText(row.judged_fireworks_tokens)}</td>
          <td>${safeText(row.evidence_class)}</td>
        </tr>
      `)
    )}
  `;
}

function renderReadiness(data) {
  const readiness = data.staging_vs_production_readiness || {};
  nodes.readiness.innerHTML = `
    <h3>Staging Vs Production Readiness</h3>
    ${table(["Check", "Value"], Object.entries(readiness).map(([key, value]) => `
      <tr><td>${safeText(key)}</td><td><span class="${statusClass(value)}">${safeText(value)}</span></td></tr>
    `))}
  `;
}

function renderFailures(data) {
  const failures = data.failures_and_validation || {};
  const categorization = failures.categorization || {};
  nodes.failures.innerHTML = `
    <h3>Failures And Validation</h3>
    <div class="summary-strip">
      <span>Total ${safeText(categorization.total_tasks)}</span>
      <span>Classifier Accuracy ${percent(categorization.accuracy)}</span>
      <span>Official Shape ${categorization.official_shape_valid ? "valid" : "invalid"}</span>
    </div>
    ${table(["Blocker"], (failures.blockers || []).map((item) => `<tr><td>${safeText(item)}</td></tr>`))}
  `;
}

function renderCompliance(data) {
  const compliance = data.submission_compliance || {};
  nodes.compliance.innerHTML = `
    <h3>Submission Compliance</h3>
    ${table(["Area", "Evidence"], Object.entries(compliance).map(([key, value]) => `
      <tr><td>${safeText(key)}</td><td><pre>${safeText(JSON.stringify(value, null, 2))}</pre></td></tr>
    `))}
  `;
}

function renderDeduced(data) {
  const deduced = data.deduced_analytics || {};
  nodes.deduced.innerHTML = `
    <h3>Deduced Analytics</h3>
    <div class="summary-strip">
      <span>${safeText(deduced.source)}</span>
      <span>Fireworks Called ${safeText(deduced.fireworks_called)}</span>
    </div>
    <p class="risk-note">${safeText(deduced.summary)}</p>
    <p class="risk-note">${safeText(deduced.recommendation)}</p>
  `;
}

async function refresh() {
  const [preflightResponse, analyticsResponse] = await Promise.all([
    fetch("/api/preflight"),
    fetch("/api/version6-analytics"),
  ]);
  renderPreflight(await preflightResponse.json());
  const data = await analyticsResponse.json();
  renderOverview(data);
  renderResults(data);
  renderCategories(data);
  renderRouteFlow(data);
  renderLocal(data);
  renderReadiness(data);
  renderFailures(data);
  renderCompliance(data);
  renderDeduced(data);
}

for (const button of tabButtons) button.addEventListener("click", () => switchView(button.dataset.view));

refresh().catch((error) => {
  statusStrip.innerHTML = `<span>${safeText(error.message)}</span>`;
  nodes.overview.innerHTML = `<p class="empty">${safeText(error.message)}</p>`;
});
