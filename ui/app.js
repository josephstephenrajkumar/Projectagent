/**
 * OpenClaw Chat UI – App Logic
 * Talks to the Node.js Gateway at the same origin (or localhost:3000)
 */

const GATEWAY = ""; // empty = same origin; change to "http://localhost:3000" for dev

// ─── DOM Refs ──────────────────────────────────────────────────────────────
const messagesEl = document.getElementById("messages");
const userInput = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
const btnClear = document.getElementById("btn-clear");
const btnMenu = document.getElementById("btn-menu");
const btnIngest = document.getElementById("btn-ingest");
const sidebar = document.getElementById("sidebar");
const statusDot = document.getElementById("status-dot");
const statusLabel = document.getElementById("status-label");
const drawer = document.getElementById("thinking-drawer");
const thinkingPre = document.getElementById("thinking-content");
const btnCloseDrawer = document.getElementById("btn-close-drawer");
const overlay = document.getElementById("overlay");

// ─── Status helpers ────────────────────────────────────────────────────────
function setStatus(state, label) {
    statusDot.className = `status-dot ${state}`;
    statusLabel.textContent = label;
}

async function checkHealth() {
    try {
        const r = await fetch(`${GATEWAY}/health`);
        if (r.ok) setStatus("online", "Online");
        else setStatus("offline", "Error");
    } catch {
        setStatus("offline", "Unreachable");
    }
}
checkHealth();
setInterval(checkHealth, 15_000);

// ─── RAID Alerts Polling ───────────────────────────────────────────────────
async function fetchRaidAlerts() {
    try {
        const res = await fetch(`http://localhost:8000/raid/alerts`);
        const data = await res.json();
        const alertsContainer = document.getElementById("raid-alerts-container");
        const alertsList = document.getElementById("raid-alerts-list");

        if (data.alerts && data.alerts.length > 0) {
            alertsList.innerHTML = "";
            let html = "";
            data.alerts.forEach(a => {
                let ownerStr = a.owner && a.owner.toLowerCase() !== "unassigned" ? ` (Owner: ${a.owner})` : "";
                let descFixed = typeof a.Description === 'string' ? a.Description.replace(/<\/?[^>]+(>|$)/g, "") : a.Description;
                let shortDesc = descFixed && descFixed.length > 60 ? descFixed.substring(0, 57) + "..." : descFixed || "No Description";
                html += `<li><strong>[${a.ProjectNumber}]</strong> ${a.raidID}: ${shortDesc} <strong style="color: #991b1b;">(Due: ${a.DueDate})</strong>${ownerStr}</li>`;
            });
            alertsList.innerHTML = html;
            alertsContainer.style.display = "block";
        } else {
            alertsContainer.style.display = "none";
        }
    } catch (e) {
        // fail silently to avoid logging spam
    }
}
// Initial fetch and poll every 30 seconds
fetchRaidAlerts();
setInterval(fetchRaidAlerts, 30_000);

// ─── Agent badge config ────────────────────────────────────────────────────
const AGENT_META = {
    "plan-forecast_agent": { label: "📊 Plan-Forecast Agent", css: "badge-forecast" },
    "contract_agent": { label: "📜 Contract Agent", css: "badge-contract" },
    "general_agent": { label: "💬 General Agent", css: "badge-general" },
    "pricing_agent": { label: "💰 Pricing Agent", css: "badge-both" },
    "risk_agent": { label: "⚠️ Risk Agent", css: "badge-contract" },
    "raid_update_agent": { label: "⚡ RAID Update", css: "badge-both" },
    "both": { label: "⚖️  Synthesizer", css: "badge-both" },
};

function getAgentMeta(agent) {
    return AGENT_META[agent] || { label: agent, css: "badge-general" };
}

// ─── Message rendering ─────────────────────────────────────────────────────
function appendMessage(role, text, { agent = null, debugLog = null } = {}) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "👤" : "🤖";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    if (agent && role === "assistant") {
        const meta = getAgentMeta(agent);
        const badge = document.createElement("span");
        badge.className = `agent-badge ${meta.css}`;
        badge.textContent = meta.label;
        bubble.appendChild(badge);

        // Highlight sidebar chip
        document.querySelectorAll(".agent-chip").forEach(c => c.classList.remove("active"));
        const chip = document.querySelector(`[data-agent="${agent}"]`);
        if (chip) chip.classList.add("active");
    }

    // Render markdown-ish text (bold only, for brevity)
    const content = document.createElement("div");
    content.innerHTML = formatText(text);
    bubble.appendChild(content);

    if (debugLog) {
        const link = document.createElement("a");
        link.className = "thinking-link";
        link.textContent = "🧠 View thinking process →";
        link.onclick = () => showDrawer(debugLog);
        bubble.appendChild(link);
    }

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return wrapper;
}

function formatText(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, `<code style="background:#21262d;padding:1px 5px;border-radius:4px;font-family:var(--mono)">$1</code>`)
        .replace(/\n/g, "<br>");
}

function appendLoading() {
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant";
    wrapper.id = "loading-msg";
    wrapper.innerHTML = `
    <div class="avatar">🤖</div>
    <div class="bubble loading-bubble">
      <div class="dots">
        <span></span><span></span><span></span>
      </div>
    </div>`;
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function removeLoading() {
    document.getElementById("loading-msg")?.remove();
}

// ─── Send message ──────────────────────────────────────────────────────────
async function sendMessage(query) {
    if (!query.trim()) return;

    appendMessage("user", query);
    userInput.value = "";
    userInput.style.height = "auto";
    btnSend.disabled = true;
    setStatus("thinking", "Thinking…");
    appendLoading();

    try {
        const res = await fetch(`${GATEWAY}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });

        removeLoading();

        if (!res.ok) {
            const err = await res.json();
            appendMessage("assistant", `❌ Error: ${err.error || res.statusText}`);
            setStatus("offline", "Error");
            return;
        }

        const data = await res.json();
        appendMessage("assistant", data.response, {
            agent: data.agent,
            debugLog: data.debug_log,
        });
        setStatus("online", "Online");

    } catch (err) {
        removeLoading();
        appendMessage("assistant",
            "❌ Cannot reach the OpenClaw Gateway.\n\nMake sure the Node.js server is running:\n`cd runtime && node gateway/server.js`"
        );
        setStatus("offline", "Unreachable");
    } finally {
        btnSend.disabled = false;
        userInput.focus();
    }
}

// ─── Thinking drawer ───────────────────────────────────────────────────────
function showDrawer(log) {
    thinkingPre.textContent = log || "No log available.";
    drawer.classList.remove("hidden");
    overlay.classList.add("visible");
}
function hideDrawer() {
    drawer.classList.add("hidden");
    overlay.classList.remove("visible");
}
btnCloseDrawer.addEventListener("click", hideDrawer);
overlay.addEventListener("click", hideDrawer);

// ─── Event listeners ───────────────────────────────────────────────────────
btnSend.addEventListener("click", () => sendMessage(userInput.value));

userInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(userInput.value);
    }
});

// Auto-grow textarea
userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 200) + "px";
});

btnClear.addEventListener("click", () => {
    messagesEl.innerHTML = "";
    document.querySelectorAll(".agent-chip").forEach(c => c.classList.remove("active"));
});

btnMenu.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    overlay.classList.toggle("visible");
});

// Example chips
document.addEventListener("click", e => {
    if (e.target.matches(".chip[data-q]")) {
        sendMessage(e.target.dataset.q);
    }
});

// Re-ingest
btnIngest.addEventListener("click", async () => {
    btnIngest.textContent = "⏳ Ingesting…";
    btnIngest.disabled = true;
    try {
        const r = await fetch(`${GATEWAY}/ingest`, { method: "POST" });
        const d = await r.json();
        const count = Object.keys(d.indexed || {}).length;
        appendMessage("assistant", `✅ Re-ingestion complete! Indexed **${count}** document collection(s).`);
    } catch {
        appendMessage("assistant", "❌ Ingestion failed. Check server logs.");
    } finally {
        btnIngest.textContent = "🗄️ Re-Ingest Docs";
        btnIngest.disabled = false;
    }
});

// ─── Tab Navigation (Chat ↔ Create Project) ─────────────────────────────────
const navChat = document.getElementById("nav-chat");
const navCreate = document.getElementById("nav-create");
const mainEl = document.getElementById("main");
const createPanel = document.getElementById("create-panel");

function switchTab(tab) {
    if (tab === "chat") {
        mainEl.style.display = "flex";
        createPanel.classList.add("hidden-panel");
        navChat.classList.add("nav-active");
        navCreate.classList.remove("nav-active");
    } else {
        mainEl.style.display = "none";
        createPanel.classList.remove("hidden-panel");
        createPanel.style.display = "flex";
        navCreate.classList.add("nav-active");
        navChat.classList.remove("nav-active");
    }
}

navChat.addEventListener("click", () => switchTab("chat"));
navCreate.addEventListener("click", () => switchTab("create"));

// Mobile sidebar toggle for create panel
document.getElementById("btn-menu-create")?.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    overlay.classList.toggle("visible");
});

// ─── Project Creation Flow ──────────────────────────────────────────────────
const projectForm = document.getElementById("project-form");
const createStatus = document.getElementById("create-status");
const confirmSection = document.getElementById("confirmation-section");
const tableWrapper = document.getElementById("extracted-table-wrapper");
const confirmStatus = document.getElementById("confirm-status");

let pendingProjectData = null; // stores { project_name, project_code, opportunity_id, extracted_data }

// ─── File Upload Validation ─────────────────────────────────────────────────
const VALID_CONTRACT_EXT = [".docx", ".doc", ".pdf"];
const VALID_EXCEL_EXT = [".xlsx", ".xls"];

function getFileExt(filename) {
    return (filename || "").substring(filename.lastIndexOf(".")).toLowerCase();
}

function validateFileUpload(inputId, statusId, validExtensions, structureHint) {
    const input = document.getElementById(inputId);
    const status = document.getElementById(statusId);
    if (!input || !status) return;

    input.addEventListener("change", () => {
        const file = input.files[0];
        if (!file) { status.textContent = ""; status.className = "file-status"; return; }

        const ext = getFileExt(file.name);
        if (!validExtensions.includes(ext)) {
            status.textContent = `❌ Invalid file type "${ext}". Expected: ${validExtensions.join(", ")}`;
            status.className = "file-status invalid";
            return;
        }

        // Additional structure hints based on filename
        if (structureHint === "contract") {
            status.textContent = `✅ ${file.name} — will be ingested into Contract collection`;
            status.className = "file-status valid";
        } else if (structureHint === "estimation") {
            const nameLower = file.name.toLowerCase();
            if (nameLower.includes("estimat") || nameLower.includes("milestone") || nameLower.includes("resource")) {
                status.textContent = `✅ ${file.name} — will be ingested into Estimation-Milestone collection`;
                status.className = "file-status valid";
            } else {
                status.textContent = `⚠️ ${file.name} — filename doesn't contain "estimation" or "milestone". Please verify this is the correct file.`;
                status.className = "file-status invalid";
            }
        } else if (structureHint === "project") {
            const nameLower = file.name.toLowerCase();
            if (nameLower.includes("project") || nameLower.includes("erp") || nameLower.includes("data")) {
                status.textContent = `✅ ${file.name} — will be ingested into Project collection`;
                status.className = "file-status valid";
            } else {
                status.textContent = `⚠️ ${file.name} — filename doesn't contain "project" or "ERP". Please verify this is the correct file.`;
                status.className = "file-status invalid";
            }
        }
    });
}

validateFileUpload("inp-contract-file", "contract-file-status", VALID_CONTRACT_EXT, "contract");
validateFileUpload("inp-estimation-file", "estimation-file-status", VALID_EXCEL_EXT, "estimation");
validateFileUpload("inp-erp-file", "erp-file-status", VALID_EXCEL_EXT, "project");


projectForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const projectName = document.getElementById("inp-project-name").value.trim();
    const projectCode = document.getElementById("inp-project-code").value.trim();
    const opportunityId = document.getElementById("inp-opportunity-id").value.trim();
    const contractFile = document.getElementById("inp-contract-file").files[0];
    const estimationFile = document.getElementById("inp-estimation-file").files[0];
    const erpFile = document.getElementById("inp-erp-file")?.files[0];

    if (!projectName || !projectCode || !contractFile || !estimationFile) {
        createStatus.innerHTML = "❌ Please fill in Project Name, Project Code, and upload the required files.";
        return;
    }

    const formData = new FormData();
    formData.append("project_name", projectName);
    formData.append("project_code", projectCode);
    formData.append("opportunity_id", opportunityId);
    formData.append("contract_file", contractFile);
    formData.append("estimation_file", estimationFile);
    if (erpFile) {
        formData.append("erp_file", erpFile);
    }

    const btn = document.getElementById("btn-create-project");
    btn.disabled = true;
    btn.textContent = "⏳ Extracting project data…";
    createStatus.innerHTML = "📥 Uploading and ingesting documents… this may take a minute.";

    try {
        const res = await fetch(`${GATEWAY}/project/create`, {
            method: "POST",
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            createStatus.innerHTML = `❌ Error: ${err.detail || res.statusText}`;
            return;
        }

        const data = await res.json();
        pendingProjectData = {
            project_name: data.project_name,
            project_code: data.project_code,
            opportunity_id: data.opportunity_id,
            extracted_data: data.extracted_data,
        };

        createStatus.innerHTML = "✅ Data extracted! Please review below.";
        renderConfirmationTable(data.extracted_data);
        confirmSection.classList.remove("hidden-panel");
        confirmSection.style.display = "block";

    } catch (err) {
        createStatus.innerHTML = `❌ Connection error: ${err.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = "🚀 Create Project";
    }
});


// JSON fields require expandable textarea editors
const JSON_FIELDS = new Set([
    "sow_json", "resources_json", "invoice_json",
    "revenue_json", "total_hours_json", "work_packages"
]);

function renderConfirmationTable(data) {
    const friendlyLabels = {
        ProjectNumber: "Project Number",
        OpportunityID: "Opportunity ID",
        customer: "Customer",
        end_customer: "End Customer",
        PMName: "Project Manager",
        DMName: "Delivery Manager",
        country: "Country",
        startdateContract: "Contract Start Date",
        endDateContract: "Contract End Date",
        startdateBaseline: "Baseline Start Date",
        endDateBaseline: "Baseline End Date",
        exchangerate: "Exchange Rate",
        MBRReporting_currency: "Reporting Currency",
        Proj_Stage: "Project Stage",
        Contr_Type: "Contract Type",
        Rev_Type: "Revenue Type",
        Baseline_Rev: "Baseline Revenue",
        Baseline_Cost: "Baseline Cost",
        Prod_Grp: "Product Group",
        Portfolio: "Portfolio",
        Region: "Region",
        Project_Owner: "Project Owner",
        invoice_json: "Invoice Data",
        revenue_json: "Revenue Data",
    };

    let html = '<table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>';
    for (const [key, value] of Object.entries(data)) {
        const label = friendlyLabels[key] || key;
        const val = value ?? "";

        if (JSON_FIELDS.has(key) && val) {
            // Format JSON nicely for display
            let formatted = val;
            try {
                const parsed = typeof val === "string" ? JSON.parse(val) : val;
                formatted = JSON.stringify(parsed, null, 2);
            } catch { formatted = String(val); }

            const uid = `json-toggle-${key}`;
            html += `<tr>
                <th>
                    ${label}
                    <button type="button" class="btn-json-toggle" onclick="
                        const el = document.getElementById('${uid}');
                        const btn = this;
                        if (el.style.display === 'none') {
                            el.style.display = 'block';
                            btn.textContent = '▼ Collapse';
                        } else {
                            el.style.display = 'none';
                            btn.textContent = '▶ Expand';
                        }
                    ">▶ Expand</button>
                </th>
                <td>
                    <div class="json-preview">${String(val).substring(0, 80)}…</div>
                    <textarea id="${uid}" data-field="${key}" class="json-textarea" style="display:none">${formatted.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</textarea>
                </td>
            </tr>`;
        } else {
            html += `<tr>
                <th>${label}</th>
                <td><input type="text" data-field="${key}" value="${String(val).replace(/"/g, '&quot;')}" /></td>
            </tr>`;
        }
    }
    html += '</tbody></table>';
    tableWrapper.innerHTML = html;
}

// Confirm & Save
document.getElementById("btn-confirm-save")?.addEventListener("click", async () => {
    if (!pendingProjectData) {
        confirmStatus.innerHTML = "❌ No project data to confirm.";
        return;
    }

    // Read edited values from the table (inputs for flat fields, textareas for JSON)
    const inputs = tableWrapper.querySelectorAll("input[data-field], textarea[data-field]");
    const editedData = {};
    inputs.forEach(inp => {
        let val = inp.value.trim();
        if (val && inp.tagName === "TEXTAREA" && JSON_FIELDS.has(inp.dataset.field)) {
            try {
                // Parse it back to object/array so it isn't sent as a raw string
                // Especially for work_packages which the DB agent needs as a list
                val = JSON.parse(val);
            } catch (e) {
                console.warn("Failed to parse JSON for", inp.dataset.field, e);
            }
        }
        editedData[inp.dataset.field] = val || null;
    });

    // Try to parse numeric fields
    for (const numField of ["Baseline_Rev", "Baseline_Cost"]) {
        if (editedData[numField] && !isNaN(editedData[numField])) {
            editedData[numField] = Number(editedData[numField]);
        }
    }

    const btn = document.getElementById("btn-confirm-save");
    btn.disabled = true;
    btn.textContent = "⏳ Saving…";
    confirmStatus.innerHTML = "💾 Persisting to database…";

    try {
        const res = await fetch(`${GATEWAY}/project/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project_name: pendingProjectData.project_name,
                project_code: pendingProjectData.project_code,
                opportunity_id: pendingProjectData.opportunity_id,
                extracted_data: editedData,
            }),
        });

        const data = await res.json();
        if (data.status === "created") {
            confirmStatus.innerHTML = `✅ ${data.response.replace(/\n/g, "<br>")}`;
            projectForm.reset();
            pendingProjectData = null;
        } else {
            confirmStatus.innerHTML = `⚠️ ${data.response.replace(/\n/g, "<br>")}`;
        }
    } catch (err) {
        confirmStatus.innerHTML = `❌ Error: ${err.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = "✅ Confirm & Save";
    }
});

// Cancel
document.getElementById("btn-cancel-create")?.addEventListener("click", () => {
    confirmSection.classList.add("hidden-panel");
    pendingProjectData = null;
    confirmStatus.innerHTML = "";
    createStatus.innerHTML = "";
});
