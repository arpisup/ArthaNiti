// Helper: JSON Fetch
async function fetchJson(url, options = {}) {
  const token = localStorage.getItem("ecosim_token");
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  
  const response = await fetch(url, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) }
  });
  
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error || `Request failed: ${response.status}`);
  }
  return response.json();
}

function handleAuthUI() {
  const user = JSON.parse(localStorage.getItem("ecosim_user") || "null");
  const userInfoPanel = document.getElementById("user-info-panel");
  if (!userInfoPanel) return;

  if (user) {
    userInfoPanel.innerHTML = `
      <span>👤 ${user.username}</span>
      <button id="logout-btn" class="logout-btn">Logout</button>
    `;
  } else {
    userInfoPanel.innerHTML = `<button id="logout-btn" class="logout-btn">Login / Register</button>`;
  }
  
  document.getElementById("logout-btn").addEventListener("click", () => {
    localStorage.removeItem("ecosim_token");
    localStorage.removeItem("ecosim_user");
    window.location.href = "/login.html";
  });
}

// =========================================
// AUTH LOGIC (login.html)
// =========================================
export function initAuth() {
  const form = document.getElementById("auth-form");
  const errorMsg = document.getElementById("auth-error");
  const regFields = document.getElementById("register-fields");
  const tabBtns = document.querySelectorAll(".tab-btn");
  const skipBtn = document.getElementById("skip-login-btn");
  const submitBtn = document.getElementById("auth-submit-btn");
  if (!form) return;
  const btnText = submitBtn.querySelector(".btn-text");
  
  let mode = "login";

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      mode = btn.dataset.tab;
      
      if (mode === "register") {
        regFields.hidden = false;
        btnText.textContent = "Register & Continue";
      } else {
        regFields.hidden = true;
        btnText.textContent = "Login";
      }
      errorMsg.hidden = true;
    });
  });

  skipBtn.addEventListener("click", () => {
    localStorage.removeItem("ecosim_token");
    localStorage.removeItem("ecosim_user");
    window.location.href = "/";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorMsg.hidden = true;
    submitBtn.disabled = true;
    btnText.textContent = "Please wait...";
    
    const formData = new FormData(form);
    const payload = {
      username: formData.get("username"),
      password: formData.get("password")
    };
    
    if (mode === "register") {
      payload.profile = {
        age: Number(formData.get("age")),
        family_size: Number(formData.get("family_size")),
        annual_income: Number(formData.get("annual_income")),
        state: formData.get("state"),
        area: formData.get("area"),
        occupation: formData.get("occupation"),
        employment_status: formData.get("employment_status"),
        sector: formData.get("sector")
      };
    }
    
    try {
      const endpoint = mode === "login" ? "/api/login" : "/api/register";
      const data = await fetchJson(endpoint, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      
      if (data.error) throw new Error(data.error);
      
      localStorage.setItem("ecosim_token", data.token);
      localStorage.setItem("ecosim_user", JSON.stringify({username: data.username, profile: data.profile}));
      window.location.href = "/";
      
    } catch (err) {
      errorMsg.textContent = err.message;
      errorMsg.hidden = false;
      submitBtn.disabled = false;
      btnText.textContent = mode === "login" ? "Login" : "Register & Continue";
    }
  });
}

// =========================================
// LANDING PAGE LOGIC (index.html)
// =========================================
export function initLanding() {
  handleAuthUI();

  const form = document.getElementById("landing-form");
  const input = document.getElementById("landing-input");
  if (!form) return;

  // Auto-resize textarea
  input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event('submit'));
    }
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (text) {
      window.location.href = `/chat.html?q=${encodeURIComponent(text)}`;
    }
  });

  // Suggestion chips
  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      window.location.href = `/chat.html?q=${encodeURIComponent(chip.textContent)}`;
    });
  });
}

// =========================================
// CHAT & DASHBOARD LOGIC (chat.html)
// =========================================
export function initChat() {
  handleAuthUI();

  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatMessages = document.getElementById("chat-messages");
  const sendBtn = document.getElementById("send-btn");
  if (!chatForm) return;
  
  const dashboardPanel = document.getElementById("dashboard-panel");
  const dashContent = document.getElementById("dashboard-content");
  
  const charts = {};
  const compareButton = document.getElementById("compare-btn");
  const refreshButton = document.getElementById("dashboard-refresh");
  const copyBriefButton = document.getElementById("copy-brief-btn");
  const downloadReportButton = document.getElementById("download-report-btn");
  let policyLevers = [];
  let latestAssessment = null;
  let latestReply = "";
  let latestRequest = null;

  function destroyCharts() {
    Object.values(charts).forEach(chart => chart.destroy());
    Object.keys(charts).forEach(key => delete charts[key]);
  }

  function setDashboardState(status, horizon = "--") {
    dashboardPanel.hidden = false;
    dashContent.hidden = false;
    document.getElementById("dashboard-status").textContent = status;
    document.getElementById("dashboard-horizon").textContent = horizon;
  }

  function startTelemetry() {
    resetTelemetry();
    const steps = ["eco", "cit", "pol", "rsk", "evi"];
    const phases = [
      "Running macro simulation…",
      "Mapping household exposure…",
      "Matching policy schemes…",
      "Stress-testing risks…",
      "Retrieving supporting evidence…",
    ];
    let index = 0;
    document.getElementById(`trace-${steps[index]}`).classList.add("active");
    setDashboardState(phases[index], "working");
    const timer = setInterval(() => {
      const previous = document.getElementById(`trace-${steps[index]}`);
      previous.classList.remove("active");
      previous.classList.add("done");
      index = Math.min(index + 1, steps.length - 1);
      document.getElementById(`trace-${steps[index]}`).classList.add("active");
      document.getElementById("dashboard-status").textContent = phases[index];
    }, 500);
    return () => {
      clearInterval(timer);
      steps.forEach(step => document.getElementById(`trace-${step}`).classList.add("done"));
      document.querySelectorAll(".trace-step").forEach(el => el.classList.remove("active"));
    };
  }

  function numberOrZero(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : 0;
  }

  function formatLabel(value) {
    return String(value || "").replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
  }

  function formatUnit(unit) {
    return unit === "index" ? " index" : unit || "";
  }

  function renderMetricTiles(metrics) {
    const container = document.getElementById("dash-metrics");
    container.replaceChildren();
    metrics.slice(0, 6).forEach(metric => {
      const delta = numberOrZero(metric.delta);
      const scenarioValue = numberOrZero(metric.value);
      const unit = formatUnit(metric.unit);
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = `metric-tile ${delta >= 0 ? "positive" : "negative"}`;
      const label = document.createElement("span");
      label.className = "metric-tile-label";
      label.textContent = metric.label || formatLabel(metric.id);
      const currentValue = document.createElement("strong");
      currentValue.textContent = `${scenarioValue.toFixed(2)}${unit}`;
      const changeValue = document.createElement("small");
      changeValue.textContent = `Change from baseline: ${delta >= 0 ? "+" : ""}${delta.toFixed(2)}${unit}`;
      tile.append(label, currentValue, changeValue);
      tile.addEventListener("click", () => {
        const index = metrics.indexOf(metric);
        if (charts.macro && index >= 0) {
          charts.macro.setActiveElements([{ datasetIndex: 0, index }]);
          charts.macro.tooltip.setActiveElements([{ datasetIndex: 0, index }], { x: 0, y: 0 });
          charts.macro.update();
          document.getElementById("macroChart").scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
      container.appendChild(tile);
    });
  }

  function renderAgentRoom(masData) {
    const container = document.getElementById("agent-detail-list");
    container.replaceChildren();
    const metadata = masData._metadata || {};
    const failed = new Map((metadata.agents_failed || []).map(item => [item.agent_id, item.error]));
    const skipped = new Set((metadata.agents_skipped || []).map(item => item.agent_id));
    const executed = new Set((metadata.agents_executed || []).map(item => item.agent_id));
    const labels = { economic: "Economic impact", citizen: "Citizen impact", policy: "Policy matching", risk: "Risk analysis", evidence: "Evidence retrieval" };
    ["economic", "citizen", "policy", "risk", "evidence"].forEach(key => {
      const agentId = `${key}_agent`;
      const status = failed.has(agentId) ? "Failed" : skipped.has(agentId) ? "Skipped" : executed.has(agentId) ? "Complete" : "Not run";
      const result = masData[key] || {};
      const item = document.createElement("details");
      item.className = `agent-detail ${status.toLowerCase()}`;
      item.innerHTML = `<summary><span class="agent-status-dot"></span><span>${labels[key]}</span><b>${status}</b></summary><div class="agent-detail-body"></div>`;
      const body = item.querySelector(".agent-detail-body");
      if (status === "Failed") body.textContent = failed.get(agentId);
      else if (status === "Skipped") body.textContent = "This lens needs a user profile for a personalized assessment.";
      else if (status === "Not run") body.textContent = "This lens was not run for the current baseline view.";
      else {
        const summary = key === "economic" ? result.headline : key === "citizen" ? result.headline : key === "policy" ? `${result.matched_scheme_count || 0} eligible schemes found.` : key === "risk" ? `${result.flagged_risks?.length || 0} risks flagged at ${result.risk_level || "low"} level.` : `${result.citations?.length || 0} supporting sources retrieved.`;
        body.textContent = summary || "Analysis completed.";
      }
      container.appendChild(item);
    });
  }

  function renderEvidence(masData) {
    const evidence = masData.evidence || {};
    document.getElementById("dash-evidence-query").textContent = evidence.query || "No evidence query generated.";
    const citations = document.getElementById("dash-citations");
    citations.replaceChildren();
    const liveCount = (evidence.live_citations || []).length;
    const liveStatus = document.createElement("p");
    liveStatus.className = "text-sm text-muted";
    liveStatus.textContent = liveCount ? `${liveCount} live web source${liveCount > 1 ? "s" : ""} retrieved by Tavily.` : "No live web sources returned; showing local evidence.";
    citations.appendChild(liveStatus);
    (evidence.citations || []).forEach((citation, index) => {
      const item = document.createElement("article");
      item.className = "citation-item";
      const number = document.createElement("span");
      number.className = "citation-index";
      number.textContent = String(index + 1).padStart(2, "0");
      const content = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = citation.title || citation.source || "Knowledge base source";
      const snippet = document.createElement("p");
      snippet.textContent = citation.snippet || citation.text || "Supporting context retrieved for this scenario.";
      content.append(title, snippet);
      if (citation.provider === "tavily" && citation.url) {
        const link = document.createElement("a");
        link.href = citation.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Live source";
        content.append(link);
      }
      item.append(number, content);
      citations.appendChild(item);
    });
    if (!citations.children.length) citations.innerHTML = `<p class="text-sm text-muted">No matching citations were returned.</p>`;

    const tradeoffs = document.getElementById("dash-tradeoffs");
    tradeoffs.replaceChildren();
    (masData.risk?.trade_offs || []).forEach(tradeoff => {
      const item = document.createElement("li");
      item.textContent = tradeoff;
      tradeoffs.appendChild(item);
    });
    if (!tradeoffs.children.length) tradeoffs.innerHTML = "<li>No explicit trade-offs detected.</li>";
  }

  function buildBriefText() {
    const economic = latestAssessment?.economic || {};
    const risk = latestAssessment?.risk || {};
    const citizen = latestAssessment?.citizen || {};
    const evidence = latestAssessment?.evidence || {};
    const lines = [
      "ARTHANITI ASSESSMENT BRIEF",
      "===========================",
      `Headline: ${economic.headline || "Not available"}`,
      `Outlook: ${economic.overall_macro_status || "Not available"}`,
      `Horizon: ${economic.horizon?.requested_years || "Not available"} years`,
      `Confidence: ${economic.confidence?.score ?? "Not available"}%`,
      "",
      "KEY MOVEMENTS",
      ...(economic.macro_metrics || []).slice(0, 6).map(metric => `- ${metric.label}: ${numberOrZero(metric.delta) >= 0 ? "+" : ""}${numberOrZero(metric.delta).toFixed(2)}${metric.unit || ""}`),
      "",
      "PERSONAL IMPACT",
      citizen.headline || "No personalized profile was attached.",
      citizen.dominant_persona ? `Dominant persona: ${citizen.dominant_persona}` : "",
      "",
      "RISK AND TRADE-OFFS",
      `Risk level: ${risk.risk_level || "Not assessed"}`,
      ...(risk.flagged_risks || []).map(item => `- ${item}`),
      ...(risk.trade_offs || []).map(item => `- Trade-off: ${item}`),
      "",
      `Evidence query: ${evidence.query || "Not available"}`,
      latestReply ? `\nASSISTANT BRIEF\n\n${latestReply}` : "",
    ];
    return lines.filter((line, index) => line !== "" || lines[index - 1] !== "").join("\n");
  }

  async function copyBrief() {
    if (!latestAssessment) return;
    const originalText = copyBriefButton.textContent;
    try {
      await navigator.clipboard.writeText(buildBriefText());
      copyBriefButton.textContent = "Copied";
    } catch (error) {
      copyBriefButton.textContent = "Copy failed";
    } finally {
      window.setTimeout(() => { copyBriefButton.textContent = originalText; }, 1400);
    }
  }

  function downloadReport() {
    if (!latestAssessment) return;
    const report = {
      generated_at: new Date().toISOString(),
      assistant_brief: latestReply,
      assessment: latestAssessment,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "arthaniti-assessment-report.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  function setupDashboardTabs() {
    document.querySelectorAll(".dashboard-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        const target = tab.dataset.dashboardTab;
        document.querySelectorAll(".dashboard-tab").forEach(item => item.classList.toggle("active", item === tab));
        document.querySelectorAll(".dashboard-view").forEach(view => view.classList.toggle("active", view.dataset.dashboardView === target));
      });
    });
  }

  function renderScenarioInputs(eco) {
    const container = document.getElementById("scenario-inputs");
    container.replaceChildren();
    const inputs = eco.policy_inputs || {};
    Object.entries(inputs).forEach(([key, value]) => {
      const item = document.createElement("span");
      item.className = "scenario-input";
      item.textContent = `${key.replaceAll("_", " ")} ${value}`;
      container.appendChild(item);
    });
    if (!Object.keys(inputs).length) {
      const item = document.createElement("span");
      item.className = "text-muted text-sm";
      item.textContent = "Baseline policy stance";
      container.appendChild(item);
    }
  }

  function renderComparisonControls(prefix, initialInputs = {}) {
    const container = document.getElementById(`scenario-${prefix}-controls`);
    container.replaceChildren();
    const initialKeys = Object.keys(initialInputs).filter(key => Number(initialInputs[key]) !== 100);
    const updateLeverOptions = () => {
      const selects = [...container.querySelectorAll("select")];
      const selectedValues = selects.map(select => select.value);
      selects.forEach(select => {
        [...select.options].forEach(option => {
          option.disabled = selectedValues.includes(option.value) && option.value !== select.value;
        });
      });
    };
    for (let index = 0; index < 3; index += 1) {
      const row = document.createElement("div");
      row.className = "slider-row";
      const select = document.createElement("select");
      select.id = `${prefix}-lever-${index}`;
      policyLevers.forEach(lever => {
        const option = document.createElement("option");
        option.value = lever.id;
        option.textContent = lever.label;
        select.appendChild(option);
      });
      const selectedId = initialKeys[index] || policyLevers[index]?.id;
      if (selectedId) select.value = selectedId;
      const slider = document.createElement("input");
      slider.type = "range";
      slider.id = `${prefix}-slider-${index}`;
      const value = document.createElement("output");
      value.id = `${prefix}-value-${index}`;
      value.className = "slider-value";
      row.append(select, slider, value);
      container.appendChild(row);

      const syncSlider = () => {
        const lever = policyLevers.find(item => item.id === select.value) || policyLevers[0];
        if (!lever) return;
        slider.min = lever.min;
        slider.max = lever.max;
        slider.step = lever.step;
        slider.value = initialInputs[lever.id] ?? lever.baseline;
        value.textContent = slider.value;
      };
      select.addEventListener("change", () => {
        syncSlider();
        updateLeverOptions();
      });
      slider.addEventListener("input", () => { value.textContent = slider.value; });
      syncSlider();
    }
    updateLeverOptions();
  }

  function buildAlternativePolicyInputs(baseInputs = {}) {
    const fallback = { ...baseInputs };
    const nudges = {
      capital_spending_index: 120,
      welfare_spending_index: 110,
      policy_rate: 5.5,
      gst_rate: 16,
      income_tax_rate: 18,
    };

    Object.entries(nudges).forEach(([key, value]) => {
      const lever = policyLevers.find(item => item.id === key);
      if (!lever) {
        fallback[key] = value;
        return;
      }
      const min = Number(lever.min);
      const max = Number(lever.max);
      fallback[key] = Math.min(max, Math.max(min, Number(value)));
    });

    return fallback;
  }

  function collectScenarioInputs(prefix) {
    const inputs = {};
    for (let index = 0; index < 3; index += 1) {
      const leverId = document.getElementById(`${prefix}-lever-${index}`).value;
      const value = Number(document.getElementById(`${prefix}-slider-${index}`).value);
      inputs[leverId] = value;
    }
    return inputs;
  }

  async function initializeComparisonControls() {
    try {
      const [config, baselineData] = await Promise.all([
        fetchJson("/api/config"),
        fetchJson("/api/baseline"),
      ]);
      policyLevers = config.policy_levers || [];
      const horizons = config.supported_horizons || [1, 5, 10];
      const baselineInputs = baselineData.default_policy_inputs || {};
      const alternativeInputs = buildAlternativePolicyInputs(baselineInputs);
      ["a", "b"].forEach(prefix => {
        const select = document.getElementById(`compare-horizon-${prefix}`);
        horizons.forEach(horizon => {
          const option = document.createElement("option");
          option.value = horizon;
          option.textContent = `${horizon} years`;
          select.appendChild(option);
        });
        select.value = config.default_horizon_years || 5;
        renderComparisonControls(prefix, prefix === "a" ? baselineInputs : alternativeInputs);
      });
    } catch (error) {
      document.getElementById("compare-status").textContent = `Controls unavailable: ${error.message}`;
    }
  }

  function buildBaselineAssessment(defaultSimulation) {
    const simpleSimulation = defaultSimulation || {};
    const metrics = Array.isArray(simpleSimulation.macro_metrics) ? simpleSimulation.macro_metrics : [];
    return {
      economic: {
        ...simpleSimulation,
        macro_metrics: metrics,
        headline: simpleSimulation.headline || "Baseline scenario", 
        overall_macro_status: simpleSimulation.overall_macro_status || "baseline",
        confidence: simpleSimulation.confidence || { score: 85, notes: "Baseline scenario" },
        horizon: {
          requested_years: simpleSimulation.horizon_years || 5,
          bucket: simpleSimulation.horizon_bucket || 5,
        },
      },
      citizen: {
        dominant_persona: "General public",
        blended_impact: {},
        macro_exposure: {},
      },
      policy: {
        matched_schemes: [],
        matched_scheme_count: 0,
      },
      risk: {
        risk_level: "baseline",
        flagged_risks: [],
        trade_offs: [],
      },
      evidence: {
        query: "Baseline scenario",
        citations: [],
      },
      _metadata: {
        agents_executed: [],
        agents_failed: [],
        agents_skipped: [],
      },
    };
  }

  async function loadDefaultAssessment() {
    try {
      const baseline = await fetchJson("/api/baseline");
      const defaultSimulation = baseline.default_simulation || {};
      const assessment = baseline.assessment || buildBaselineAssessment(defaultSimulation);
      renderDashboard(assessment);
      setDashboardState("Baseline loaded", `${defaultSimulation.horizon_years || 5} year view`);
    } catch (error) {
      setDashboardState(`Baseline unavailable: ${error.message}`, "--");
      document.getElementById("dash-headline").textContent = "Unable to load baseline scenario.";
      document.getElementById("dash-confidence").textContent = "The dashboard is not yet initialized.";
    }
  }

  function renderDashboard(masData) {
    latestAssessment = masData;
    const eco = masData.economic || {};
    const metrics = eco.macro_metrics || [];
    setDashboardState("Assessment complete", `${eco.horizon?.requested_years || "--"} year view`);
    destroyCharts();
    document.getElementById("comparisonChart").hidden = true;
    document.getElementById("compare-status").textContent = "Tune the controls, then compare.";
    document.getElementById("macroChart").closest(".chart-container").hidden = !metrics.some(metric => numberOrZero(metric.delta) !== 0);
    renderScenarioInputs(eco);
    renderComparisonControls("a", eco.policy_inputs || {});
    document.getElementById("dash-headline").textContent = eco.headline || "Scenario assessment ready.";
    const confidence = eco.confidence || {};
    const confidenceNotes = Array.isArray(confidence.notes) ? confidence.notes.join(" ") : confidence.notes;
    document.getElementById("dash-confidence").textContent = confidence.score !== undefined ? `Model confidence ${confidence.score}% · ${confidenceNotes || "Deterministic scenario engine"}` : "Deterministic scenario engine · confidence details unavailable";
    const status = eco.overall_macro_status || "mixed";
    const statusBadge = document.getElementById("dash-status-badge");
    statusBadge.textContent = `${status} outlook`;
    statusBadge.className = `status-badge ${status}`;
    const metadata = masData._metadata || {};
    const failedCount = metadata.agents_failed?.length || 0;
    const skippedCount = metadata.agents_skipped?.length || 0;
    const executedCount = metadata.agents_executed?.length || 0;
    document.getElementById("dash-agent-health").textContent = failedCount
      ? `${failedCount} agent issue${failedCount > 1 ? "s" : ""} · partial result`
      : !executedCount && !skippedCount ? "Baseline reference view" 
      : `${executedCount} complete${skippedCount ? ` · ${skippedCount} skipped` : ""}`;
    renderMetricTiles(metrics);
    const highlights = document.getElementById("dash-highlights");
    highlights.replaceChildren();
    (eco.highlights || []).forEach(highlight => {
      const item = document.createElement("div");
      item.className = "highlight-item";
      item.textContent = highlight;
      highlights.appendChild(item);
    });
    if (!highlights.children.length) highlights.innerHTML = '<p class="text-sm text-muted">No standout movements were identified.</p>';
    renderAgentRoom(masData);
    renderEvidence(masData);

    if (!metrics.length) {
      document.getElementById("macroChart").getContext("2d").clearRect(0, 0, 0, 0);
      document.getElementById("levelsChart").getContext("2d").clearRect(0, 0, 0, 0);
      return;
    }

    if (typeof window.Chart !== "function") {
      document.querySelectorAll(".chart-container").forEach(container => {
        container.hidden = true;
      });
    } else {
      // Macro delta chart
      const ctx = document.getElementById("macroChart").getContext("2d");
      charts.macro = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: metrics.map(metric => metric.label),
        datasets: [{
          label: 'Change',
          data: metrics.map(metric => numberOrZero(metric.delta)),
          backgroundColor: metrics.map(metric => numberOrZero(metric.delta) >= 0 ? '#34d399' : '#f87171'),
          borderWidth: 0,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: '#1E293B' }, ticks: { color: '#94a3b8' } },
          x: { grid: { display: false }, ticks: { color: '#94a3b8', maxRotation: 45, minRotation: 35 } }
        }
      }
      });

    // Baseline versus scenario chart
      charts.levels = new Chart(document.getElementById("levelsChart").getContext("2d"), {
      type: 'bar',
      data: {
        labels: metrics.map(metric => metric.label),
        datasets: [
          { label: 'Baseline', data: metrics.map(metric => numberOrZero(metric.baseline)), backgroundColor: '#475569' },
          { label: 'Scenario', data: metrics.map(metric => numberOrZero(metric.value)), backgroundColor: '#60a5fa' }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#cbd5e1' } } },
        scales: {
          y: { beginAtZero: true, grid: { color: '#1E293B' }, ticks: { color: '#94a3b8' } },
          x: { grid: { display: false }, ticks: { color: '#94a3b8', maxRotation: 45, minRotation: 35 } }
        }
      }
      });

    // Personal exposure chart
    const exposure = (masData.citizen || {}).macro_exposure || {};
    document.getElementById("exposure-container").hidden = !Object.keys(exposure).length;
      if (Object.keys(exposure).length) {
      charts.exposure = new Chart(document.getElementById("exposureChart").getContext("2d"), {
        type: 'radar',
        data: {
          labels: Object.keys(exposure).map(key => key.replaceAll("_", " ")),
          datasets: [{ label: 'Exposure', data: Object.values(exposure), borderColor: '#fbbf24', backgroundColor: 'rgba(251, 191, 36, 0.18)', pointBackgroundColor: '#fbbf24' }]
        },
        options: {
          responsive: true,
          scales: { r: { beginAtZero: true, max: 100, ticks: { color: '#94a3b8', backdropColor: 'transparent' }, grid: { color: '#334155' }, angleLines: { color: '#334155' }, pointLabels: { color: '#cbd5e1', font: { size: 10 } } } },
          plugins: { legend: { labels: { color: '#cbd5e1' } } }
        }
        });
      }
    }

    // 4. Render Citizen Data
    const cit = masData.citizen || {};
    document.getElementById("dash-persona").textContent = cit.dominant_persona || "General Public";
    
    const cit_impact = cit.blended_impact || {};
    if (cit_impact.disposable_income_delta_pct !== undefined) {
      document.getElementById("dash-persona-metrics").textContent = `Income Shift: ${cit_impact.disposable_income_delta_pct > 0 ? '+' : ''}${cit_impact.disposable_income_delta_pct.toFixed(2)}%`;
      document.getElementById("dash-persona-metrics").style.color = cit_impact.disposable_income_delta_pct >= 0 ? '#34d399' : '#f87171';
    } else {
      document.getElementById("dash-persona-metrics").textContent = "No personalized profile attached.";
    }

    // 5. Render Schemes
    const schemesDiv = document.getElementById("dash-schemes");
    schemesDiv.replaceChildren();
    const matched = (masData.policy || {}).matched_schemes || [];
    matched.slice(0, 3).forEach(scheme => {
      const item = document.createElement("div");
      item.className = "scheme-pill";
      item.title = scheme.name || "Scheme";
      item.textContent = scheme.name || "Unnamed scheme";
      schemesDiv.appendChild(item);
    });
    if (!matched.length) schemesDiv.textContent = "No specific schemes matched.";

    // 6. Render Risks
    const risksUl = document.getElementById("dash-risks");
    risksUl.replaceChildren();
    const risks = (masData.risk || {}).flagged_risks || [];
    risks.slice(0, 4).forEach(risk => {
      const item = document.createElement("li");
      item.textContent = risk;
      risksUl.appendChild(item);
    });
    if (!risks.length) risksUl.textContent = "No immediate risks detected.";
  }

  async function comparePolicies() {
    const status = document.getElementById("compare-status");
    try {
      const scenarioA = collectScenarioInputs("a");
      const scenarioB = collectScenarioInputs("b");
      status.textContent = "Comparing scenarios…";
      compareButton.disabled = true;
      const data = await fetchJson("/api/compare", {
        method: "POST",
        body: JSON.stringify({
          scenario_a: { label: document.getElementById("compare-label-a").value || "Scenario A", policy_inputs: scenarioA, horizon_years: Number(document.getElementById("compare-horizon-a").value) },
          scenario_b: { label: document.getElementById("compare-label-b").value || "Scenario B", policy_inputs: scenarioB, horizon_years: Number(document.getElementById("compare-horizon-b").value) }
        })
      });
      const canvas = document.getElementById("comparisonChart");
      canvas.hidden = false;
      if (charts.comparison) charts.comparison.destroy();
      charts.comparison = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: data.metrics.map(metric => metric.label),
          datasets: [
            { label: data.scenario_a.label, data: data.metrics.map(metric => metric.scenario_a), backgroundColor: "#60a5fa" },
            { label: data.scenario_b.label, data: data.metrics.map(metric => metric.scenario_b), backgroundColor: "#fbbf24" }
          ]
        },
        options: {
          responsive: true,
          plugins: { legend: { labels: { color: "#cbd5e1" } } },
          scales: { y: { beginAtZero: true, ticks: { color: "#94a3b8" }, grid: { color: "#1E293B" } }, x: { ticks: { color: "#94a3b8", maxRotation: 45, minRotation: 35 }, grid: { display: false } } }
        }
      });
      status.textContent = `Higher GDP: ${data.summary.higher_gdp_scenario}. Lower inflation: ${data.summary.lower_inflation_scenario}. GDP difference: ${data.summary.gdp_difference_b_minus_a >= 0 ? "+" : ""}${data.summary.gdp_difference_b_minus_a}.`;
    } catch (error) {
      status.textContent = `Comparison failed: ${error.message}`;
    } finally {
      compareButton.disabled = false;
    }
  }

  compareButton.addEventListener("click", comparePolicies);
  copyBriefButton.addEventListener("click", copyBrief);
  downloadReportButton.addEventListener("click", downloadReport);
  refreshButton.addEventListener("click", async () => {
    if (!latestAssessment) return;
    refreshButton.classList.add("spinning");
    try {
      if (latestRequest) {
        const data = await fetchJson("/api/chat", {
          method: "POST",
          body: JSON.stringify({ message: latestRequest })
        });
        latestReply = data.reply || latestReply;
        renderDashboard(data.mas_data);
      } else {
        await loadDefaultAssessment();
      }
    } catch (error) {
      setDashboardState(`Refresh failed: ${error.message}`, "error");
    } finally {
      refreshButton.classList.remove("spinning");
    }
  });

  const hasInitialQuery = Boolean(new URLSearchParams(window.location.search).get("q"));

  async function initializeDashboardShell() {
    await initializeComparisonControls();
    setupDashboardTabs();
    if (!hasInitialQuery) await loadDefaultAssessment();
  }

  const dashboardReady = initializeDashboardShell();

  function resetTelemetry() {
    document.querySelectorAll(".trace-step").forEach(el => {
      el.classList.remove("active", "done");
    });
  }

  function appendMessage(role, content) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}`;
    let icon = role === "user" ? "👤" : "AI";
    const safeContent = String(content || "").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    const htmlContent = window.marked ? window.marked.parse(safeContent) : `<p>${safeContent}</p>`;
    
    msgDiv.innerHTML = `
      <div class="message-icon">${icon}</div>
      <div class="message-content">${htmlContent}</div>
    `;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msgDiv;
  }

  function appendFollowUps(messageNode, masData) {
    const prompts = ["Who benefits most?", "What are the main risks?", "Show supporting evidence"];
    if (masData?.economic?.overall_macro_status === "mixed") prompts.push("Compare with an alternative policy");
    const actions = document.createElement("div");
    actions.className = "follow-up-actions";
    const label = document.createElement("span");
    label.className = "follow-up-label";
    label.textContent = "Continue exploring";
    actions.appendChild(label);
    prompts.forEach(prompt => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "follow-up-btn";
      button.textContent = prompt;
      button.addEventListener("click", () => {
        chatInput.value = prompt;
        chatInput.dispatchEvent(new Event("input"));
        chatForm.dispatchEvent(new Event("submit"));
      });
      actions.appendChild(button);
    });
    messageNode.querySelector(".message-content").appendChild(actions);
  }

  function appendTypingIndicator() {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message assistant typing`;
    msgDiv.innerHTML = `
      <div class="message-icon">AI</div>
      <div class="message-content">
        <div class="typing-indicator"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
      </div>
    `;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msgDiv;
  }

  chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
  });
  
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event('submit'));
    }
  });

  async function processQuery(text) {
    latestRequest = text;
    appendMessage("user", text);
    const typingNode = appendTypingIndicator();
    setDashboardState("Running assessment…", "working");
    const stopTelemetry = startTelemetry();
    
    try {
      const data = await fetchJson("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: text })
      });
      
      stopTelemetry();
      typingNode.remove();
      
      if (data.mas_data) {
        renderDashboard(data.mas_data);
      }
      
      latestReply = data.reply || "";
      const assistantMessage = appendMessage("assistant", data.reply);
      appendFollowUps(assistantMessage, data.mas_data);
    } catch (err) {
      stopTelemetry();
      setDashboardState("Assessment failed", "error");
      typingNode.remove();
      appendMessage("assistant", `**Error**: ${err.message}`);
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    
    chatInput.value = "";
    chatInput.style.height = 'auto';
    sendBtn.disabled = true;
    
    processQuery(text).finally(() => {
      sendBtn.disabled = false;
      chatInput.focus();
    });
  });

  // Check URL params for auto-query from landing page
  const urlParams = new URLSearchParams(window.location.search);
  const initialQuery = urlParams.get('q');
  if (initialQuery) {
    sendBtn.disabled = true;
    dashboardReady
      .then(() => processQuery(initialQuery))
      .finally(() => {
        sendBtn.disabled = false;
        chatInput.focus();
      });
    // Remove query from URL for clean copy-pasting
    window.history.replaceState({}, document.title, "/chat.html");
  }
}
