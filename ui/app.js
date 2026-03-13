/**
 * OpenClaw Chat UI – App Logic
 */

const GATEWAY = "http://localhost:8000";
const ORCHESTRATOR_URL = "http://localhost:8000";

// ─── DOM Refs ──────────────────────────────────────────────────────────────
const get = (id) => document.getElementById(id);

const refs = {
    messagesEl: get("messages"),
    userInput: get("user-input"),
    btnSend: get("btn-send"),
    btnClear: get("btn-clear"),
    btnMenu: get("btn-menu"),
    btnIngest: get("btn-ingest"),
    sidebar: get("sidebar"),
    statusDot: get("status-dot"),
    statusLabel: get("status-label"),
    drawer: get("thinking-drawer"),
    thinkingPre: get("thinking-content"),
    btnCloseDrawer: get("btn-close-drawer"),
    overlay: get("overlay"),

    navChat: get("nav-chat"),
    navCreate: get("nav-create"),
    navData: get("nav-data"),
    mainEl: get("main"),
    createPanel: get("create-panel"),
    dataPanel: get("data-panel"),

    projectForm: get("project-form"),
    createStatus: get("create-status"),
    confirmSection: get("confirmation-section"),
    tableWrapper: get("extracted-table-wrapper"),
    confirmStatus: get("confirm-status"),

    // Data Manager
    selTable: get("sel-table"),
    btnRefreshData: get("btn-refresh-data"),
    inpDataSearch: get("inp-data-search"),
    dataTableWrapper: get("data-table-wrapper"),
};

// ─── Status helpers ────────────────────────────────────────────────────────
function setStatus(state, label) {
    if (refs.statusDot) refs.statusDot.className = `status-dot ${state}`;
    if (refs.statusLabel) refs.statusLabel.textContent = label;
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

// ─── RAID Alerts Polling ───────────────────────────────────────────────────
async function fetchRaidAlerts() {
    try {
        const res = await fetch(`${ORCHESTRATOR_URL}/raid/alerts`);
        const data = await res.json();
        const container = get("raid-alerts-container");
        const list = get("raid-alerts-list");

        if (container && list && data.alerts && data.alerts.length > 0) {
            list.innerHTML = "";
            let html = "";
            data.alerts.forEach(a => {
                let ownerStr = a.owner && a.owner.toLowerCase() !== "unassigned" ? ` (Owner: ${a.owner})` : "";
                let descFixed = typeof a.Description === 'string' ? a.Description.replace(/<\/?[^>]+(>|$)/g, "") : a.Description;
                let shortDesc = descFixed && descFixed.length > 60 ? descFixed.substring(0, 57) + "..." : descFixed || "No Description";
                html += `<li><strong>[${a.ProjectNumber}]</strong> ${a.raidID}: ${shortDesc} <strong style="color: #991b1b;">(Due: ${a.DueDate})</strong>${ownerStr}</li>`;
            });
            list.innerHTML = html;
            container.style.display = "block";
        } else if (container) {
            container.style.display = "none";
        }
    } catch (e) {
        // fail silently
    }
}

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

function formatText(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, `<code style="background:#21262d;padding:1px 5px;border-radius:4px;font-family:var(--mono)">$1</code>`)
        .replace(/\n/g, "<br>");
}

function appendMessage(role, text, { agent = null, debugLog = null } = {}) {
    if (!refs.messagesEl) return;
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role}`;
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "👤" : "🤖";
    const bubble = document.createElement("div");
    bubble.className = "bubble";

    if (agent && role === "assistant") {
        const meta = AGENT_META[agent] || { label: agent, css: "badge-general" };
        const badge = document.createElement("span");
        badge.className = `agent-badge ${meta.css}`;
        badge.textContent = meta.label;
        bubble.appendChild(badge);
    }

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
    refs.messagesEl.appendChild(wrapper);
    refs.messagesEl.scrollTop = refs.messagesEl.scrollHeight;
    return wrapper;
}

function appendLoading() {
    if (!refs.messagesEl) return;
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant";
    wrapper.id = "loading-msg";
    wrapper.innerHTML = `
    <div class="avatar">🤖</div>
    <div class="bubble loading-bubble"><div class="dots"><span></span><span></span><span></span></div></div>`;
    refs.messagesEl.appendChild(wrapper);
    refs.messagesEl.scrollTop = refs.messagesEl.scrollHeight;
}

function removeLoading() {
    document.getElementById("loading-msg")?.remove();
}

async function sendMessage(query) {
    if (!query.trim()) return;
    appendMessage("user", query);
    if (refs.userInput) {
        refs.userInput.value = "";
        refs.userInput.style.height = "auto";
    }
    if (refs.btnSend) refs.btnSend.disabled = true;
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
        appendMessage("assistant", data.response, { agent: data.agent, debugLog: data.debug_log });
        setStatus("online", "Online");
    } catch (err) {
        removeLoading();
        appendMessage("assistant", "❌ Cannot reach the Gateway. Is the server running?");
        setStatus("offline", "Unreachable");
    } finally {
        if (refs.btnSend) refs.btnSend.disabled = false;
        if (refs.userInput) refs.userInput.focus();
    }
}

// ─── Navigation ────────────────────────────────────────────────────────────
function switchTab(tab) {
    if (!refs.mainEl || !refs.createPanel || !refs.dataPanel) return;
    
    // Reset all
    refs.mainEl.style.display = "none";
    refs.createPanel.classList.add("hidden-panel");
    refs.createPanel.style.display = "none";
    refs.dataPanel.classList.add("hidden-panel");
    refs.dataPanel.style.display = "none";
    
    refs.navChat?.classList.remove("nav-active");
    refs.navCreate?.classList.remove("nav-active");
    refs.navData?.classList.remove("nav-active");

    if (tab === "chat") {
        refs.mainEl.style.display = "flex";
        refs.navChat?.classList.add("nav-active");
    } else if (tab === "create") {
        refs.createPanel.classList.remove("hidden-panel");
        refs.createPanel.style.display = "flex";
        refs.navCreate?.classList.add("nav-active");
    } else if (tab === "data") {
        refs.dataPanel.classList.remove("hidden-panel");
        refs.dataPanel.style.display = "flex";
        refs.navData?.classList.add("nav-active");
        loadTablesList();
    }
}

// ─── Data Manager ──────────────────────────────────────────────────────────
let currentTableData = { columns: [], rows: [] };

async function loadTablesList() {
    if (!refs.selTable) return;
    try {
        const res = await fetch(`${ORCHESTRATOR_URL}/db/tables`);
        const data = await res.json();
        refs.selTable.innerHTML = '<option value="">Select Table...</option>';
        data.tables.forEach(table => {
            const opt = document.createElement('option');
            opt.value = table;
            opt.innerText = table;
            refs.selTable.appendChild(opt);
        });
    } catch {}
}

async function loadTableData(tableName) {
    if (!refs.dataTableWrapper) return;
    refs.dataTableWrapper.innerHTML = '<p class="data-placeholder">Loading...</p>';
    try {
        const res = await fetch(`${ORCHESTRATOR_URL}/db/table/${tableName}`);
        currentTableData = await res.json();
        renderDataTable(currentTableData.columns, currentTableData.rows, tableName);
    } catch (err) {
        refs.dataTableWrapper.innerHTML = `<p class="data-placeholder" style="color:var(--red)">Error: ${err.message}</p>`;
    }
}

function renderDataTable(columns, rows, tableName) {
    if (!refs.dataTableWrapper) return;
    if (!rows.length && !columns.length) {
        refs.dataTableWrapper.innerHTML = '<p class="data-placeholder">Table is empty.</p>';
        return;
    }
    
    // Determine the Primary Key (assume 'id' or first column)
    const pk = columns.includes('id') ? 'id' : 
               columns.includes('raidID') ? 'raidID' :
               columns.includes('project_id') ? 'project_id' : 
               columns.includes('wp_id') ? 'wp_id' : 
               columns.includes('keyword') ? 'keyword' : columns[0];

    let html = `
        <div style="padding: 12px; background: rgba(88, 166, 255, 0.1); border-bottom: 1px solid var(--border); font-size: 12px; color: var(--accent);">
            <strong>💡 Dynamic Inference Tip:</strong> Edit <code>SemanticMap</code> keywords to help the AI map natural language to DB entities. 
            Edit <code>RAIDitems</code> to refine risk status.
        </div>
        <table class="sql-table"><thead><tr>`;
    columns.forEach(col => html += `<th>${col}</th>`);
    html += '</tr></thead><tbody>';
    
    rows.forEach(row => {
        const pkValue = row[pk];
        html += '<tr>';
        columns.forEach(col => {
            const val = row[col] === null ? '' : row[col];
            const isPK = (col === pk);
            const editableClass = !isPK ? 'editable-field' : '';
            html += `<td class="${editableClass}" 
                        data-table="${tableName}" 
                        data-col="${col}" 
                        data-pk-col="${pk}" 
                        data-pk-val="${pkValue}"
                        onclick="makeEditable(this)"
                        title="${isPK ? 'Primary Key (Locked)' : 'Click to edit'}">${val}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    refs.dataTableWrapper.innerHTML = html;
}

window.makeEditable = function(td) {
    if (td.querySelector('input') || !td.classList.contains('editable-field')) return;
    const originalVal = td.innerText;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = originalVal;
    input.style.width = '100%';
    input.style.background = 'var(--bg-input)';
    input.style.color = 'var(--text)';
    input.style.border = '1px solid var(--accent)';
    input.style.borderRadius = '4px';
    input.style.padding = '4px';
    
    td.innerHTML = '';
    td.appendChild(input);
    input.focus();
    
    const save = async () => {
        const newVal = input.value.trim();
        if (newVal === originalVal) {
            td.innerText = originalVal;
            return;
        }
        
        const { table, col, pkCol, pkVal } = td.dataset;
        td.innerText = '⏳...';
        
        try {
            const res = await fetch(`${ORCHESTRATOR_URL}/db/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    table_name: table,
                    pk_column: pkCol,
                    pk_value: pkVal,
                    updates: { [col]: newVal }
                })
            });
            if (res.ok) {
                td.innerText = newVal;
                // Highlight success
                td.style.backgroundColor = 'rgba(63, 185, 80, 0.2)';
                setTimeout(() => td.style.backgroundColor = '', 1000);
            } else {
                throw new Error('Update failed');
            }
        } catch (err) {
            alert('Failed to save: ' + err.message);
            td.innerText = originalVal;
        }
    };
    
    input.onblur = save;
    input.onkeydown = (e) => {
        if (e.key === 'Enter') save();
        if (e.key === 'Escape') td.innerText = originalVal;
    };
};

// ─── Drawer ────────────────────────────────────────────────────────────────
function showDrawer(log) {
    if (refs.thinkingPre) refs.thinkingPre.textContent = log || "No log available.";
    refs.drawer?.classList.remove("hidden");
    refs.overlay?.classList.add("visible");
}
function hideDrawer() {
    refs.drawer?.classList.add("hidden");
    refs.overlay?.classList.remove("visible");
    refs.sidebar?.classList.remove("open");
}

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
        status.textContent = `✅ ${file.name} — validated for ${structureHint}`;
        status.className = "file-status valid";
    });
}

// ─── Project Creation ──────────────────────────────────────────────────────
const JSON_FIELDS = new Set(["sow_json", "resources_json", "invoice_json", "revenue_json", "total_hours_json", "work_packages"]);
let pendingProjectData = null;

function renderConfirmationTable(data) {
    if (!refs.tableWrapper) return;
    let html = '<table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>';
    for (const [key, value] of Object.entries(data)) {
        const val = value ?? "";
        if (JSON_FIELDS.has(key) && val) {
            let formatted = val;
            try { formatted = JSON.stringify(typeof val === "string" ? JSON.parse(val) : val, null, 2); } catch {}
            const uid = `json-toggle-${key}`;
            html += `<tr><th>${key} <button type="button" class="btn-json-toggle" onclick="const el=document.getElementById('${uid}'); el.style.display=el.style.display==='none'?'block':'none'">▶ Toggle</button></th>
                     <td><textarea id="${uid}" data-field="${key}" class="json-textarea" style="display:none">${formatted.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</textarea></td></tr>`;
        } else {
            html += `<tr><th>${key}</th><td><input type="text" data-field="${key}" value="${String(val).replace(/"/g, '&quot;')}" /></td></tr>`;
        }
    }
    html += '</tbody></table>';
    refs.tableWrapper.innerHTML = html;
}

// ─── Init ──────────────────────────────────────────────────────────────────
function init() {
    if (refs.btnSend) refs.btnSend.onclick = () => sendMessage(refs.userInput?.value);
    
    validateFileUpload("inp-contract-file", "contract-file-status", VALID_CONTRACT_EXT, "contract");
    validateFileUpload("inp-estimation-file", "estimation-file-status", VALID_EXCEL_EXT, "estimation");
    validateFileUpload("inp-erp-file", "erp-file-status", VALID_EXCEL_EXT, "project");

    if (refs.projectForm) {
        refs.projectForm.onsubmit = async (e) => {
            e.preventDefault();
            const projectName = get("inp-project-name")?.value.trim();
            const projectCode = get("inp-project-code")?.value.trim();
            const opportunityId = get("inp-opportunity-id")?.value.trim();
            const contractFile = get("inp-contract-file")?.files[0];
            const estimationFile = get("inp-estimation-file")?.files[0];
            const erpFile = get("inp-erp-file")?.files[0];

            if (!projectName || !projectCode || !contractFile || !estimationFile) {
                if (refs.createStatus) refs.createStatus.innerHTML = "❌ Missing required fields.";
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

            const btn = get("btn-create-project");
            if (btn) { btn.disabled = true; btn.textContent = "⏳ Extracting..."; }
            if (refs.createStatus) refs.createStatus.innerHTML = "📥 Uploading documents...";

            const pollInterval = setInterval(async () => {
                try {
                    const statusRes = await fetch(`${GATEWAY}/project/status/${projectCode}`);
                    const statusData = await statusRes.json();
                    if (refs.createStatus && statusData.status) {
                        refs.createStatus.innerHTML = `⏳ ${statusData.status}`;
                    }
                } catch (e) {}
            }, 2000);

            try {
                const res = await fetch(`${GATEWAY}/project/create`, { method: "POST", body: formData });
                const data = await res.json();
                pendingProjectData = { project_name: data.project_name, project_code: data.project_code, opportunity_id: data.opportunity_id, extracted_data: data.extracted_data };
                if (refs.createStatus) refs.createStatus.innerHTML = "✅ Extraction complete!";
                renderConfirmationTable(data.extracted_data);
                refs.confirmSection?.classList.remove("hidden-panel");
                if (refs.confirmSection) refs.confirmSection.style.display = "block";
            } catch (err) {
                if (refs.createStatus) refs.createStatus.innerHTML = `❌ Error: ${err.message}`;
            } finally {
                clearInterval(pollInterval);
                if (btn) { btn.disabled = false; btn.textContent = "🚀 Create Project"; }
            }
        };
    }

    if (get("btn-confirm-save")) {
        get("btn-confirm-save").onclick = async () => {
            if (!pendingProjectData || !refs.tableWrapper) return;
            const inputs = refs.tableWrapper.querySelectorAll("input[data-field], textarea[data-field]");
            const editedData = {};
            inputs.forEach(inp => {
                let val = inp.value.trim();
                if (val && inp.tagName === "TEXTAREA" && JSON_FIELDS.has(inp.dataset.field)) {
                    try { val = JSON.parse(val); } catch {}
                }
                editedData[inp.dataset.field] = val || null;
            });

            const btn = get("btn-confirm-save");
            btn.disabled = true;
            btn.textContent = "⏳ Saving...";

            try {
                const res = await fetch(`${GATEWAY}/project/confirm`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ...pendingProjectData, extracted_data: editedData }),
                });
                const data = await res.json();
                if (refs.confirmStatus) refs.confirmStatus.innerHTML = `✅ ${data.response}`;
                refs.projectForm?.reset();
                pendingProjectData = null;
            } catch (err) {
                if (refs.confirmStatus) refs.confirmStatus.innerHTML = `❌ Error: ${err.message}`;
            } finally {
                btn.disabled = false;
                btn.textContent = "✅ Confirm & Save";
            }
        };
    }

    if (get("btn-cancel-create")) {
        get("btn-cancel-create").onclick = () => {
            refs.confirmSection?.classList.add("hidden-panel");
            if (refs.confirmSection) refs.confirmSection.style.display = "none";
            pendingProjectData = null;
        };
    }
    if (refs.userInput) {
        refs.userInput.onkeydown = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(refs.userInput.value);
            }
        };
        refs.userInput.oninput = () => {
            refs.userInput.style.height = "auto";
            refs.userInput.style.height = Math.min(refs.userInput.scrollHeight, 200) + "px";
        };
    }
    if (refs.btnClear) refs.btnClear.onclick = () => { if (refs.messagesEl) refs.messagesEl.innerHTML = ""; };
    if (refs.btnMenu) refs.btnMenu.onclick = () => {
        refs.sidebar?.classList.toggle("open");
        refs.overlay?.classList.toggle("visible");
    };
    if (refs.overlay) refs.overlay.onclick = hideDrawer;
    if (refs.btnCloseDrawer) refs.btnCloseDrawer.onclick = hideDrawer;

    if (refs.navChat) refs.navChat.onclick = () => switchTab("chat");
    if (refs.navCreate) refs.navCreate.onclick = () => switchTab("create");
    if (refs.navData) refs.navData.onclick = () => switchTab("data");

    if (refs.selTable) refs.selTable.onchange = () => loadTableData(refs.selTable.value);
    if (refs.btnRefreshData) refs.btnRefreshData.onclick = () => { if (refs.selTable?.value) loadTableData(refs.selTable.value); };
    if (refs.inpDataSearch) {
        refs.inpDataSearch.oninput = () => {
            const q = refs.inpDataSearch.value.toLowerCase();
            if (!q) { renderDataTable(currentTableData.columns, currentTableData.rows); return; }
            const filtered = currentTableData.rows.filter(row => Object.values(row).some(v => String(v).toLowerCase().includes(q)));
            renderDataTable(currentTableData.columns, filtered);
        };
    }

    if (refs.btnIngest) {
        refs.btnIngest.onclick = async () => {
            const originalText = refs.btnIngest.textContent;
            refs.btnIngest.disabled = true;
            refs.btnIngest.textContent = "⏳ Ingesting...";
            try {
                const res = await fetch(`${GATEWAY}/ingest`, { method: "POST" });
                const data = await res.json();
                alert(data.response || "Ingestion complete!");
            } catch (err) {
                alert("❌ Ingestion failed: " + err.message);
            } finally {
                refs.btnIngest.disabled = false;
                refs.btnIngest.textContent = originalText;
            }
        };
    }

    // example chips
    document.querySelectorAll(".chip").forEach(chip => {
        chip.onclick = () => {
            const q = chip.getAttribute("data-q");
            if (q) sendMessage(q);
        };
    });

    checkHealth();
    setInterval(checkHealth, 15000);
    fetchRaidAlerts();
    setInterval(fetchRaidAlerts, 30000);
}

// Wait for DOM
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
