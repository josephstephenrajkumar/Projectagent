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

// ─── Agent badge config ────────────────────────────────────────────────────
const AGENT_META = {
    "plan-forecast_agent": { label: "📊 Plan-Forecast Agent", css: "badge-forecast" },
    "contract_agent": { label: "📜 Contract Agent", css: "badge-contract" },
    "general_agent": { label: "💬 General Agent", css: "badge-general" },
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
