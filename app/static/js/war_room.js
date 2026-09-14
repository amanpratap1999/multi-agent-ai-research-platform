// Adversarial War Room Front-End Controller
document.addEventListener("DOMContentLoaded", () => {
  // Elements - Red Team
  const redteamForm = document.getElementById("redteam-form");
  const attackTypeSelect = document.getElementById("attack-type-select");
  const btnLaunchAttack = document.getElementById("btn-launch-attack");
  const redteamStatusBadge = document.getElementById("redteam-status-badge");
  const attackStreamFeed = document.getElementById("attack-stream-feed");
  const btnClearAttackFeed = document.getElementById("btn-clear-attack-feed");
  const campaignSummaryBox = document.getElementById("campaign-summary-box");
  const summaryDefenseStatus = document.getElementById("summary-defense-status");
  const summaryTotalTurns = document.getElementById("summary-total-turns");
  const summaryBlockRate = document.getElementById("summary-block-rate");
  const summaryAvgLatency = document.getElementById("summary-avg-latency");

  // Elements - Research Pipeline
  const researchForm = document.getElementById("research-form");
  const researchTopicInput = document.getElementById("research-topic-input");
  const bypassCacheChk = document.getElementById("bypass-cache-chk");
  const btnRunResearch = document.getElementById("btn-run-research");
  const cacheHitBadge = document.getElementById("cache-hit-badge");
  const pipelineSessionLabel = document.getElementById("pipeline-session-label");

  // DAG Nodes
  const dagNodes = {
    search: document.getElementById("dag-node-search"),
    summarize: document.getElementById("dag-node-summarize"),
    write: document.getElementById("dag-node-write"),
    verify: document.getElementById("dag-node-verify"),
    egress: document.getElementById("dag-node-egress"),
  };

  // Tabs
  const tabBtnReport = document.getElementById("tab-btn-report");
  const tabBtnClaims = document.getElementById("tab-btn-claims");
  const tabBtnQuarantine = document.getElementById("tab-btn-quarantine");
  const tabContentReport = document.getElementById("tab-content-report");
  const tabContentClaims = document.getElementById("tab-content-claims");
  const tabContentQuarantine = document.getElementById("tab-content-quarantine");
  const exportControls = document.getElementById("export-controls");
  const btnExportPdf = document.getElementById("btn-export-pdf");
  const btnExportMd = document.getElementById("btn-export-md");
  const btnExportJson = document.getElementById("btn-export-json");

  let activeRedteamSource = null;
  let activeResearchSource = null;
  let currentResearchSessionId = null;

  // Quick Topic Pills
  document.querySelectorAll(".quick-topic").forEach((pill) => {
    pill.addEventListener("click", () => {
      researchTopicInput.value = pill.textContent.trim();
    });
  });

  // Clear feed
  btnClearAttackFeed.addEventListener("click", () => {
    attackStreamFeed.innerHTML =
      '<div class="text-slate-600 italic text-[11px] text-center my-auto">Feed cleared. Ready for next probe.</div>';
    campaignSummaryBox.classList.add("hidden");
  });

  // Tab Navigation
  function switchTab(activeTab) {
    [tabBtnReport, tabBtnClaims, tabBtnQuarantine].forEach((btn) => {
      btn.className = "tab-btn px-3 py-1 rounded hover:bg-slate-800 text-slate-400";
    });
    [tabContentReport, tabContentClaims, tabContentQuarantine].forEach((c) => {
      c.classList.add("hidden");
    });

    if (activeTab === "report") {
      tabBtnReport.className =
        "tab-btn px-3 py-1 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold";
      tabContentReport.classList.remove("hidden");
    } else if (activeTab === "claims") {
      tabBtnClaims.className =
        "tab-btn px-3 py-1 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold";
      tabContentClaims.classList.remove("hidden");
    } else if (activeTab === "quarantine") {
      tabBtnQuarantine.className =
        "tab-btn px-3 py-1 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold";
      tabContentQuarantine.classList.remove("hidden");
    }
  }

  tabBtnReport.addEventListener("click", () => switchTab("report"));
  tabBtnClaims.addEventListener("click", () => switchTab("claims"));
  tabBtnQuarantine.addEventListener("click", () => switchTab("quarantine"));

  // ==========================================
  // Red Team Campaign Handling (SSE + Streams)
  // ==========================================
  redteamForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const attackType = attackTypeSelect.value;

    btnLaunchAttack.disabled = true;
    btnLaunchAttack.classList.add("opacity-50");
    redteamStatusBadge.textContent = "RUNNING";
    redteamStatusBadge.className =
      "text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse";
    campaignSummaryBox.classList.add("hidden");

    attackStreamFeed.innerHTML = "";

    try {
      const resp = await fetch("/api/v1/redteam/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attack_type: attackType }),
      });

      if (!resp.ok) {
        throw new Error(`Failed to launch campaign: ${resp.statusText}`);
      }

      const data = await resp.json();
      const campaignId = data.campaign_id;
      const streamUrl = data.stream_url;

      if (activeRedteamSource) {
        activeRedteamSource.close();
      }

      // Connect to Redis Streams SSE
      activeRedteamSource = new EventSource(streamUrl);

      activeRedteamSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          renderRedteamEvent(payload);
        } catch (err) {
          console.error("SSE Parse Error:", err);
        }
      };

      activeRedteamSource.onerror = (err) => {
        console.warn("Redteam SSE disconnected or completed.");
        activeRedteamSource.close();
        btnLaunchAttack.disabled = false;
        btnLaunchAttack.classList.remove("opacity-50");
        redteamStatusBadge.textContent = "COMPLETED";
        redteamStatusBadge.className =
          "text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700";
      };
    } catch (err) {
      alert("Error starting red team campaign: " + err.message);
      btnLaunchAttack.disabled = false;
      btnLaunchAttack.classList.remove("opacity-50");
      redteamStatusBadge.textContent = "STANDBY";
    }
  });

  function renderRedteamEvent(eventObj) {
    const type = eventObj.type;
    const data = eventObj.data || {};

    if (type === "turn_evaluated") {
      const card = document.createElement("div");
      const isBlocked = data.verdict === "BLOCKED" || data.defense_success === true;
      card.className = `p-2.5 rounded border log-turn-enter ${
        isBlocked ? "guardrail-card border-rose-900/60" : "guardrail-card-pass border-emerald-900/60"
      }`;

      card.innerHTML = `
        <div class="flex items-center justify-between text-[11px] mb-1">
          <div class="flex items-center gap-1.5 font-bold">
            <span class="text-slate-400">Turn ${data.turn_number}:</span>
            <span class="text-slate-200">${data.strategy || "Probe"}</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="text-[10px] text-slate-500">${data.latency_ms || 0}ms</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${
              isBlocked ? "bg-rose-500/20 text-rose-300 border border-rose-500/30" : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
            }">${data.verdict}</span>
          </div>
        </div>
        <div class="text-[11px] text-slate-400 bg-slate-900/80 p-1.5 rounded mb-1.5 font-mono break-words">
          <span class="text-rose-400 font-semibold">Prompt:</span> ${escapeHtml(data.prompt)}
        </div>
        <div class="text-[11px] text-slate-300 bg-slate-900/50 p-1.5 rounded font-mono break-words">
          <span class="text-cyan-400 font-semibold">Response:</span> ${escapeHtml(data.response || "(Blocked before dispatch)")}
        </div>
      `;

      attackStreamFeed.appendChild(card);
      attackStreamFeed.scrollTop = attackStreamFeed.scrollHeight;
    } else if (type === "campaign_completed") {
      const summary = data.summary || {};
      campaignSummaryBox.classList.remove("hidden");
      summaryTotalTurns.textContent = summary.total_turns || 0;
      summaryBlockRate.textContent = `${Math.round((summary.block_rate || 1.0) * 100)}%`;
      summaryAvgLatency.textContent = `${summary.avg_latency_ms || 0}ms`;

      summaryDefenseStatus.textContent = summary.defense_status || "SECURE";
      summaryDefenseStatus.className =
        summary.defense_status === "SECURE"
          ? "px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
          : "px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30";

      if (activeRedteamSource) {
        activeRedteamSource.close();
      }
      btnLaunchAttack.disabled = false;
      btnLaunchAttack.classList.remove("opacity-50");
      redteamStatusBadge.textContent = "COMPLETED";
      redteamStatusBadge.className =
        "text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
    }
  }

  // ==========================================
  // Research Pipeline (LangGraph + pgvector)
  // ==========================================
  researchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const topic = researchTopicInput.value.trim();
    const bypassCache = bypassCacheChk.checked;

    if (!topic) return;

    btnRunResearch.disabled = true;
    btnRunResearch.classList.add("opacity-50");
    cacheHitBadge.classList.add("hidden");
    exportControls.classList.add("hidden");
    resetDagNodes();

    tabContentReport.innerHTML =
      '<div class="text-cyan-400 italic text-center my-12 animate-pulse"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Initializing autonomous research agents...</div>';

    try {
      const resp = await fetch("/api/v1/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topic, bypass_cache: bypassCache }),
      });

      if (!resp.ok) {
        const errJson = await resp.json();
        throw new Error(errJson.detail?.message || "Failed to submit research");
      }

      const data = await resp.json();

      // Case 1: Instant pgvector Semantic Cache Hit (<15ms)
      if (data.cached === true) {
        cacheHitBadge.classList.remove("hidden");
        cacheHitBadge.innerHTML = `<i class="fa-solid fa-bolt"></i> pgvector Cache Hit (${data.latency_ms || 8}ms | Sim: ${(data.similarity_score * 100).toFixed(1)}%)`;
        pipelineSessionLabel.textContent = "Session: Instant Cache Retrieval";

        // Light up all nodes green
        Object.values(dagNodes).forEach((node) => {
          node.className = "dag-node p-2 rounded-lg border border-emerald-500/40 bg-emerald-950/30 completed";
        });

        renderFinalReport(data.final_report);
        btnRunResearch.disabled = false;
        btnRunResearch.classList.remove("opacity-50");
        return;
      }

      // Case 2: Cache Miss — Stream from Redis Streams
      currentResearchSessionId = data.session_id;
      pipelineSessionLabel.textContent = `Session: ${currentResearchSessionId}`;
      const streamUrl = data.stream_url;

      if (activeResearchSource) {
        activeResearchSource.close();
      }

      activeResearchSource = new EventSource(streamUrl);

      activeResearchSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          handleResearchEvent(payload);
        } catch (err) {
          console.error("Research SSE Parse error:", err);
        }
      };

      activeResearchSource.onerror = () => {
        console.warn("Research stream closed.");
        activeResearchSource.close();
        btnRunResearch.disabled = false;
        btnRunResearch.classList.remove("opacity-50");
      };
    } catch (err) {
      alert("Research Pipeline Error: " + err.message);
      btnRunResearch.disabled = false;
      btnRunResearch.classList.remove("opacity-50");
      tabContentReport.innerHTML = `<div class="text-rose-400 p-4 border border-rose-900 bg-rose-950/20 rounded">Execution Error: ${err.message}</div>`;
    }
  });

  function resetDagNodes() {
    Object.values(dagNodes).forEach((node) => {
      node.className = "dag-node p-2 rounded-lg border border-slate-800 bg-slate-900/60 transition-all duration-300";
    });
  }

  function handleResearchEvent(eventObj) {
    const type = eventObj.type;
    const data = eventObj.data || {};

    if (type === "agent_step") {
      const agent = data.agent;
      const status = data.status;

      // Update DAG lighting
      if (agent && dagNodes[agent]) {
        if (status === "running") {
          dagNodes[agent].className = "dag-node p-2 rounded-lg border active";
        } else if (status === "completed") {
          dagNodes[agent].className = "dag-node p-2 rounded-lg border completed";
        }
      }

      if (agent === "verify" && data.verification_score !== undefined) {
        dagNodes.verify.querySelector(".node-sub").textContent = `Score: ${(data.verification_score * 100).toFixed(0)}%`;
      }
    } else if (type === "guardrail_trigger") {
      renderQuarantineAlert(data);
    } else if (type === "pipeline_completed") {
      Object.values(dagNodes).forEach((node) => {
        node.className = "dag-node p-2 rounded-lg border completed";
      });

      if (activeResearchSource) {
        activeResearchSource.close();
      }
      btnRunResearch.disabled = false;
      btnRunResearch.classList.remove("opacity-50");

      // Fetch final report from status endpoint
      fetchFinalReport(currentResearchSessionId);
    }
  }

  async function fetchFinalReport(sessionId) {
    try {
      const resp = await fetch(`/api/v1/research/status/${sessionId}`);
      if (!resp.ok) return;
      const statusData = await resp.json();
      renderFinalReport(statusData.final_report);
    } catch (err) {
      console.error("Error fetching final report:", err);
    }
  }

  function renderFinalReport(reportObj) {
    if (!reportObj) return;

    // 1. Report Body
    const md = reportObj.report_markdown || "";
    tabContentReport.innerHTML = renderSimpleMarkdown(md);

    // 2. Claims Table
    const claims = reportObj.claims_audit || [];
    if (claims.length > 0) {
      let tableHtml = `
        <div class="overflow-x-auto">
          <table class="w-full text-[11px] border border-slate-800">
            <thead class="bg-slate-900 text-slate-400">
              <tr>
                <th class="p-2 text-left border-b border-slate-800">Verdict</th>
                <th class="p-2 text-left border-b border-slate-800">Claim</th>
                <th class="p-2 text-left border-b border-slate-800">Cited Evidence</th>
              </tr>
            </thead>
            <tbody>
      `;
      claims.forEach((c) => {
        const isSupported = c.verdict === "SUPPORTED";
        tableHtml += `
          <tr class="border-b border-slate-800/60 hover:bg-slate-900/30">
            <td class="p-2 font-bold ${isSupported ? "text-emerald-400" : "text-amber-400"}">
              ${c.verdict}
            </td>
            <td class="p-2 text-slate-200">${escapeHtml(c.claim)}</td>
            <td class="p-2 text-slate-400 italic">${escapeHtml(c.quoted_evidence || "(No quote cited)")}</td>
          </tr>
        `;
      });
      tableHtml += `</tbody></table></div>`;
      tabContentClaims.innerHTML = tableHtml;
    }

    // 3. Defense Telemetry
    const telemetry = reportObj.defense_telemetry || [];
    if (telemetry.length > 0) {
      let telemHtml = `<div class="flex flex-col gap-2">`;
      telemetry.forEach((t) => {
        telemHtml += `
          <div class="p-2 rounded bg-slate-900 border border-slate-800 flex items-center justify-between text-[11px]">
            <div>
              <span class="font-bold text-cyan-400">${t.boundary?.toUpperCase()} BOUNDARY:</span>
              <span class="text-slate-300 ml-1">Action: ${t.action} (${t.policy})</span>
            </div>
            <span class="text-slate-500">${t.latency_ms || 0}ms</span>
          </div>
        `;
      });
      telemHtml += `</div>`;
      tabContentQuarantine.innerHTML = telemHtml;
    }

    // Configure export links
    const sid = reportObj.session_id || currentResearchSessionId;
    if (sid) {
      exportControls.classList.remove("hidden");
      btnExportPdf.href = `/api/v1/research/export/${sid}?format=pdf`;
      btnExportMd.href = `/api/v1/research/export/${sid}?format=markdown`;
      btnExportJson.href = `/api/v1/research/export/${sid}?format=json`;
    }
  }

  function renderQuarantineAlert(telemData) {
    const alertDiv = document.createElement("div");
    alertDiv.className = "p-2 rounded bg-rose-950/30 border border-rose-800 text-[11px] text-rose-300 mb-2";
    alertDiv.innerHTML = `
      <i class="fa-solid fa-triangle-exclamation mr-1.5"></i>
      <strong>XPIA Intercepted:</strong> Quarantined untrusted web injection: ${escapeHtml(
        telemData.details?.reason || telemData.policy
      )}
    `;
    tabContentQuarantine.prepend(alertDiv);
  }

  function renderSimpleMarkdown(md) {
    if (!md) return "";
    return md
      .replace(/^# (.*$)/gim, '<h1 class="text-base font-bold text-slate-100 my-2">$1</h1>')
      .replace(/^## (.*$)/gim, '<h2 class="text-sm font-semibold text-slate-200 mt-4 mb-2">$1</h2>')
      .replace(/^### (.*$)/gim, '<h3 class="text-xs font-semibold text-slate-300 mt-3 mb-1">$1</h3>')
      .replace(/^\> (.*$)/gim, '<blockquote class="border-l-2 border-rose-500 pl-3 py-1 my-2 bg-rose-950/10 text-rose-300">$1</blockquote>')
      .replace(/\*\*(.*?)\*\*/gim, '<strong class="text-slate-100">$1</strong>')
      .replace(/\[(.*?)\]\((.*?)\)/gim, '<a href="$2" target="_blank" class="text-cyan-400 hover:underline">$1</a>')
      .replace(/\n\n/gim, '<br/><br/>')
      .replace(/\n/gim, '<br/>');
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
