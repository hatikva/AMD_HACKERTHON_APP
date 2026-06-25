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

function renderState() {
  $("status").textContent = `Ollama Cloud: ${state.preflight.ollama_cloud_configured ? "configured" : "missing key"} | Fireworks: ${state.preflight.fireworks_configured ? "configured" : "missing key"}`;

  $("scenario").innerHTML = state.scenarios.map((scenario) => `<option value="${scenario.id}">${scenario.id}</option>`).join("");
  $("profile").innerHTML = Object.keys(state.profiles).map((profile) => `<option value="${profile}">${profile}</option>`).join("");
  renderProfile();

  $("bench-scenarios").innerHTML = state.scenarios
    .map((scenario, index) => `<label><input type="checkbox" name="bench-scenario" value="${scenario.id}" ${index === 0 ? "checked" : ""}> ${scenario.id}</label>`)
    .join("");
  $("bench-profiles").innerHTML = Object.keys(state.profiles)
    .map((profile, index) => `<label><input type="checkbox" name="bench-profile" value="${profile}" ${index === 0 ? "checked" : ""}> ${profile}</label>`)
    .join("");
  renderRuns(state.runs);
}

function renderProfile() {
  const profileId = $("profile").value;
  $("profile-json").value = JSON.stringify(state.profiles[profileId], null, 2);
}

function renderRuns(runs) {
  $("runs").innerHTML = runs.map((run) => `
    <tr>
      <td>${run.id}</td>
      <td>${run.suite_id || ""}</td>
      <td>${run.scenario_id}</td>
      <td>${run.profile_id}</td>
      <td>${run.provider}</td>
      <td>${run.model}</td>
      <td>${run.validation_passed ? "yes" : "no"}</td>
      <td>${run.total_tokens}</td>
      <td>${run.latency_ms} ms</td>
    </tr>
  `).join("");
}

async function refresh() {
  state = await api("/api/state");
  renderState();
}

async function runTask() {
  $("result").textContent = "Running...";
  try {
    const payload = {
      scenario_id: $("scenario").value,
      profile_id: $("profile").value,
      provider: $("provider").value || null,
      model: $("model").value || null,
    };
    const result = await api("/api/run", { method: "POST", body: JSON.stringify(payload) });
    $("result").textContent = JSON.stringify(result, null, 2);
    await refresh();
  } catch (error) {
    $("result").textContent = String(error.message || error);
  }
}

async function saveProfile() {
  const profile = JSON.parse($("profile-json").value);
  await api("/api/profiles", {
    method: "POST",
    body: JSON.stringify({ profile_id: profile.profile_id || $("profile").value, profile }),
  });
  await refresh();
}

async function runBenchmark() {
  $("result").textContent = "Running benchmark matrix...";
  try {
    const result = await api("/api/benchmark", {
      method: "POST",
      body: JSON.stringify({
        scenario_ids: selectedChecks("bench-scenario"),
        profile_ids: selectedChecks("bench-profile"),
        providers: selectedChecks("bench-provider"),
        models: selectedChecks("bench-model"),
      }),
    });
    $("result").textContent = JSON.stringify(result, null, 2);
    await refresh();
  } catch (error) {
    $("result").textContent = String(error.message || error);
  }
}

$("refresh").addEventListener("click", refresh);
$("run").addEventListener("click", runTask);
$("profile").addEventListener("change", renderProfile);
$("save-profile").addEventListener("click", saveProfile);
$("run-benchmark").addEventListener("click", runBenchmark);

refresh().catch((error) => {
  $("status").textContent = String(error.message || error);
});
