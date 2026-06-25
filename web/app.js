let state = null;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || response.statusText);
  return data;
}

function selectedChecks(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((node) => node.value);
}

function profilePair(profile) {
  return {
    localProvider: profile.local_provider || "local",
    localModel: profile.local_model,
    remoteProvider: profile.remote_provider || profile.api_provider || "fireworks",
    remoteModel: profile.remote_model || "env-configured remote",
  };
}

function optionList(values) {
  return values.map((value) => `<option value="${value}">${value}</option>`).join("");
}

function profileLabel(profileId) {
  const profile = state.profiles[profileId];
  const pair = profilePair(profile);
  return `${profile.display_name || profileId}: ${pair.localModel} -> ${pair.remoteProvider}/${pair.remoteModel}`;
}

function renderState() {
  $("status").textContent = [
    `Ollama Cloud: ${state.preflight.ollama_cloud_configured ? "configured" : "missing key"}`,
    `Fireworks: ${state.preflight.fireworks_configured ? "configured" : "missing key"}`,
    `Profile: ${state.preflight.routing_profile}`,
  ].join(" | ");

  const scenarios = state.scenarios.map((scenario) => scenario.id);
  const profiles = Object.keys(state.profiles);
  $("demo-scenario").innerHTML = optionList(scenarios);
  $("smoke-scenario").innerHTML = optionList(scenarios);
  $("smoke-profile").innerHTML = optionList(profiles);
  $("profile").innerHTML = optionList(profiles);
  $("smoke-model").innerHTML = optionList([
    "",
    "Phi-4-mini-instruct-GGUF",
    state.preflight.ollama_cloud_model,
    state.preflight.ollama_cloud_alt_model,
    state.preflight.fireworks_model,
  ]);

  $("demo-profiles").innerHTML = profiles
    .map((profile, index) => `<label><input type="checkbox" name="demo-profile" value="${profile}" ${index < 3 ? "checked" : ""}> ${profileLabel(profile)}</label>`)
    .join("");
  $("bench-scenarios").innerHTML = scenarios
    .map((scenario, index) => `<label><input type="checkbox" name="bench-scenario" value="${scenario}" ${index === 0 ? "checked" : ""}> ${scenario}</label>`)
    .join("");
  $("bench-profiles").innerHTML = profiles
    .map((profile, index) => `<label><input type="checkbox" name="bench-profile" value="${profile}" ${index < 3 ? "checked" : ""}> ${profileLabel(profile)}</label>`)
    .join("");
  renderProfile();
  renderRuns(state.runs);
}

function renderProfile() {
  const profileId = $("profile").value;
  $("profile-json").value = JSON.stringify(state.profiles[profileId], null, 2);
}

function renderResultCards(records, failures = []) {
  if (!records.length && !failures.length) return "<p>No results yet.</p>";
  const cards = records.map((record) => {
    const passed = record.validation_result && record.validation_result.passed;
    return `
      <article class="result-card ${passed ? "pass" : "fail"}">
        <h3>${record.profile_id}</h3>
        <dl>
          <dt>Validation</dt><dd>${passed ? "pass" : "fail"}</dd>
          <dt>Route</dt><dd>${record.selected_route_side}: ${record.fallback_or_escalation_reason}</dd>
          <dt>Local</dt><dd>${record.local_model}</dd>
          <dt>Remote</dt><dd>${record.remote_provider} / ${record.remote_model}</dd>
          <dt>Selected</dt><dd>${record.selected_provider} / ${record.selected_model}</dd>
          <dt>Tokens</dt><dd>${record.token_usage.total_tokens}</dd>
          <dt>Latency</dt><dd>${record.latency.milliseconds} ms</dd>
        </dl>
        <pre>${record.output}</pre>
      </article>
    `;
  });
  const failedCards = failures.map((failure) => `
    <article class="result-card fail">
      <h3>${failure.profile_id || failure.provider || "run failed"}</h3>
      <pre>${failure.error}</pre>
    </article>
  `);
  return [...cards, ...failedCards].join("");
}

function renderRuns(runs) {
  const text = $("filter-text").value.toLowerCase();
  const pass = $("filter-pass").value;
  const filtered = runs.filter((run) => {
    const haystack = JSON.stringify(run).toLowerCase();
    return (!text || haystack.includes(text)) && (!pass || String(run.validation_passed) === pass);
  });
  $("runs").innerHTML = filtered.map((run) => `
    <tr>
      <td>${run.id}</td>
      <td>${run.run_type || ""}</td>
      <td>${run.suite_id || ""}</td>
      <td>${run.scenario_id}</td>
      <td>${run.profile_id}</td>
      <td>${run.route_side || ""}</td>
      <td>${run.provider}</td>
      <td>${run.model}</td>
      <td>${run.validation_passed ? "yes" : "no"}</td>
      <td>${run.total_tokens}</td>
      <td>${run.latency_ms} ms</td>
    </tr>
  `).join("");
}

function setView(name) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.view === name));
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
}

async function refresh() {
  state = await api("/api/state");
  renderState();
}

async function runDemo() {
  $("demo-result").textContent = "Running demo...";
  try {
    const result = await api("/api/demo", {
      method: "POST",
      body: JSON.stringify({
        scenario_id: $("demo-scenario").value,
        profile_ids: selectedChecks("demo-profile"),
      }),
    });
    $("demo-result").innerHTML = renderResultCards(result.records, result.failures);
    await refresh();
  } catch (error) {
    $("demo-result").textContent = String(error.message || error);
  }
}

async function runSmoke() {
  $("smoke-result").textContent = "Running smoke test...";
  try {
    const result = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({
        scenario_id: $("smoke-scenario").value,
        profile_id: $("smoke-profile").value,
        provider: $("smoke-provider").value,
        model: $("smoke-model").value || null,
        run_type: "smoke_test",
      }),
    });
    $("smoke-result").textContent = JSON.stringify(result, null, 2);
    await refresh();
  } catch (error) {
    $("smoke-result").textContent = String(error.message || error);
  }
}

async function saveProfile() {
  const profile = JSON.parse($("profile-json").value);
  for (const field of ["profile_id", "local_model", "remote_provider", "remote_model", "task_thresholds", "mdr_budget", "validation_policy"]) {
    if (!profile[field]) throw new Error(`profile missing ${field}`);
  }
  await api("/api/profiles", {
    method: "POST",
    body: JSON.stringify({ profile_id: profile.profile_id || $("profile").value, profile }),
  });
  await refresh();
}

async function runBenchmark() {
  $("benchmark-result").textContent = "Running profile-pair benchmark...";
  try {
    const result = await api("/api/benchmark", {
      method: "POST",
      body: JSON.stringify({
        scenario_ids: selectedChecks("bench-scenario"),
        profile_ids: selectedChecks("bench-profile"),
      }),
    });
    $("benchmark-result").textContent = JSON.stringify(result, null, 2);
    await refresh();
  } catch (error) {
    $("benchmark-result").textContent = String(error.message || error);
  }
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => setView(tab.dataset.view)));
$("refresh").addEventListener("click", refresh);
$("run-demo").addEventListener("click", runDemo);
$("run-smoke").addEventListener("click", runSmoke);
$("profile").addEventListener("change", renderProfile);
$("save-profile").addEventListener("click", () => saveProfile().catch((error) => alert(error.message || error)));
$("run-benchmark").addEventListener("click", runBenchmark);
$("filter-text").addEventListener("input", () => renderRuns(state.runs));
$("filter-pass").addEventListener("change", () => renderRuns(state.runs));

refresh().catch((error) => {
  $("status").textContent = String(error.message || error);
});
