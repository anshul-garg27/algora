/* ============================================================
   Algora client — two independent tabs (Assessment / Interview),
   each its own conversation. Streams /api/chat over fetch (SSE),
   renders thinking, tool calls, execution output, markdown answers,
   tables and Mermaid diagrams. Voice dictation via audio.js.
   ============================================================ */

"use strict";

// One source of truth for id generation (UUID, with a tiny fallback for old engines).
function rawId() {
  return (crypto.randomUUID && crypto.randomUUID()) ||
    "s-" + Math.abs(Date.now() ^ ((performance.now() * 1000) | 0)).toString(36);
}
function newSessionId(mode) {
  return rawId() + ":" + mode;
}
const TOUCH = window.matchMedia("(pointer: coarse)").matches;

// Optional access token (only used if the server sets ALGORA_TOKEN).
let authToken = localStorage.getItem("algora_token") || "";
function authHeaders() {
  return authToken ? { "X-Algora-Token": authToken } : {};
}
function promptToken() {
  const t = window.prompt("This server requires an access token (ALGORA_TOKEN):", "");
  if (t) { authToken = t.trim(); localStorage.setItem("algora_token", authToken); }
  return authToken;
}

// Collapse absolute workspace paths in tool output to just the filename, so a
// traceback reads `File "sol.py"` instead of leaking /Users/<me>/.../workspace/<id>/sol.py.
function stripWorkspacePaths(s) {
  return String(s).replace(/\/(?:[^\s"'\n]+\/)?workspace\/[^/\s"'\n]+\//g, "");
}

const $ = (id) => document.getElementById(id);
const panels = document.querySelector(".panels");
const input = $("input");
const form = $("composer");
const sendBtn = $("send-btn");
const fileInput = $("file-input");
const attachBtn = $("attach-btn");
const micBtn = $("mic-btn");
const attachmentsEl = $("attachments");
const statusDot = $("status-dot");
const modelSelect = $("model-select");
const thinkingToggle = $("thinking-toggle");
const resetBtn = $("reset-btn");
const dropOverlay = $("drop-overlay");

const PLACEHOLDERS = {
  assessment: "Describe the problem, or paste a screenshot…",
  interview: "Paste or dictate the problem — get a full interview walkthrough…",
  lld: "Name an OOD problem (e.g. design a parking lot) — or dictate it…",
  hld: "Name a system to design (e.g. design a URL shortener) — or dictate it…",
  behavioral: "Ask a behavioral question, or say 'tell me about yourself' — voice or text…",
};

// ---------- per-tab state ----------
function makeTab(mode) {
  const el = panels.querySelector(`.transcript[data-mode="${mode}"]`);
  return {
    mode,
    el,
    sessionId: newSessionId(mode),
    emptyHTML: el.innerHTML,
    attachments: [],
    streaming: false,
    turn: null,
  };
}
const tabs = {
  assessment: makeTab("assessment"),
  interview: makeTab("interview"),
  lld: makeTab("lld"),
  hld: makeTab("hld"),
  behavioral: makeTab("behavioral"),
};
let active = "assessment";
const cur = () => tabs[active];

// ============================================================
//  Tab switching
// ============================================================
// Reflect the active tab's session id in the URL (?s=…) so each session is easy to
// identify and a reload restores it. Uses replaceState — no page navigation.
function setUrlSession(id) {
  try {
    const u = new URL(window.location.href);
    if (id) u.searchParams.set("s", id); else u.searchParams.delete("s");
    history.replaceState(null, "", u);
  } catch (_) { /* non-fatal */ }
}

// ── LP Coach embed ──────────────────────────────────────────────
// The LP Coach tab is a special case: it embeds an iframe to the
// skills-study-guide-ui project running on localhost:5173.
// It bypasses the session/streaming system entirely.
const lpPanel = $("lp-panel");
const lpIframe = $("lp-iframe");
const lpOffline = $("lp-offline");
const lpTab = $("lp-tab");
let lpActive = false;

function lpCoachUrl() {
  // Use the same host that served Algora so the URL works on MacBook (0.0.0.0
  // or localhost) and on phone/tablet (LAN IP like 192.168.1.x) automatically.
  const host = window.location.hostname || "localhost";
  return `https://${host}:5173/google-interview-prep/chat`;
}

function tryLoadLpIframe() {
  // Skip the fetch probe — it fails on self-signed certs even when the server
  // is up. Just set the src directly; if the server is down or the cert hasn't
  // been accepted yet, the browser shows its own "can't connect" page in the
  // iframe which is clear enough.
  const url = lpCoachUrl();
  if (lpIframe.src !== url) lpIframe.src = url;
  lpIframe.hidden = false;
  lpOffline.hidden = true;
}

$("lp-reload").addEventListener("click", tryLoadLpIframe);

function enterLpTab() {
  if (lpActive) return;
  lpActive = true;
  // Deactivate all regular tabs and hide their panels + composer
  for (const m in tabs) {
    tabs[m].el.hidden = true;
    tabs[m].el.classList.remove("is-active");
  }
  panels.hidden = true;
  form.hidden = true;
  lpPanel.hidden = false;
  document.querySelectorAll(".tab").forEach((b) => {
    b.classList.toggle("is-active", b === lpTab);
    b.setAttribute("aria-selected", b === lpTab ? "true" : "false");
  });
  tryLoadLpIframe();
}

function exitLpTab() {
  if (!lpActive) return;
  lpActive = false;
  panels.hidden = false;
  form.hidden = false;
  lpPanel.hidden = true;
}

lpTab.addEventListener("click", enterLpTab);

function switchTab(mode) {
  if (!tabs[mode] || (mode === active && !lpActive)) return;
  exitLpTab();
  active = mode;
  setUrlSession(tabs[mode].sessionId);
  for (const m in tabs) {
    tabs[m].el.classList.toggle("is-active", m === mode);
    tabs[m].el.hidden = m !== mode;
  }
  document.querySelectorAll(".tab").forEach((b) => {
    const on = b.dataset.mode === mode;
    b.classList.toggle("is-active", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
  });
  input.placeholder = PLACEHOLDERS[mode];
  renderAttachments();
  syncComposer();
}
document.querySelectorAll(".tab[data-mode]").forEach((b) =>
  b.addEventListener("click", () => switchTab(b.dataset.mode))
);

function syncComposer() {
  const t = cur();
  sendBtn.disabled = t.streaming;
  if (t.streaming) {
    statusDot.className = "status-dot busy";
    statusDot.title = "working…";
  } else if (t.lastError) {
    statusDot.className = "status-dot err";
    statusDot.title = "last turn failed";
  } else {
    statusDot.className = "status-dot ok";
    statusDot.title = "ready";
  }
}

// ============================================================
//  Transcript helpers (operate on an explicit tab)
// ============================================================
function clearEmpty(tab) {
  const es = tab.el.querySelector(".empty-state");
  if (es) es.remove();
}
function atBottom(tab) {
  return tab.el.scrollHeight - tab.el.scrollTop - tab.el.clientHeight < 140;
}
function scrollDown(tab, force) {
  if (force || atBottom(tab)) tab.el.scrollTop = tab.el.scrollHeight;
}

function addUserMessage(tab, text, imgs) {
  clearEmpty(tab);
  const el = document.createElement("div");
  el.className = "msg user";
  let html = "";
  if (imgs && imgs.length) {
    html += `<div class="user-images">` +
      imgs.map((a) => `<img src="${a.dataUrl}" alt="attached image" />`).join("") + `</div>`;
  }
  if (text) html += `<div class="user-text"></div>`;
  el.innerHTML = html;
  if (text) el.querySelector(".user-text").textContent = text;
  tab.el.appendChild(el);
  scrollDown(tab, true);
}

function startAssistantTurn(tab) {
  clearEmpty(tab);
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML =
    `<div class="assistant-label"><span class="al-name">Algora</span>` +
    `<button class="full-code-btn" type="button" title="View the complete code, file by file" hidden>📂 full code</button>` +
    `</div><div class="assistant-body"></div><div class="quick-actions" hidden></div>`;
  tab.el.appendChild(el);
  tab.turn = {
    msgEl: el,
    body: el.querySelector(".assistant-body"),
    thinkEl: null, thinkRaw: "",
    textEl: null, textRaw: "",
    toolCards: {},
    files: [],   // {path, content} from write_file calls — powers the "full code" modal
    raf: 0,
  };
  scrollDown(tab, true);
}

function ensureThink(tab) {
  const turn = tab.turn;
  if (turn.thinkEl) return;
  const block = document.createElement("div");
  block.className = "think-block";
  block.innerHTML =
    `<div class="think-head"><span>🧠 Reasoning</span><span class="caret">▾</span></div>` +
    `<div class="think-body"></div>`;
  turn.body.appendChild(block);
  turn.thinkEl = block.querySelector(".think-body");
  turn.thinkRaw = "";
}

function ensureText(tab) {
  const turn = tab.turn;
  if (turn.textEl) return;
  const p = document.createElement("div");
  p.className = "prose cursor";
  turn.body.appendChild(p);
  turn.textEl = p;
  turn.textRaw = "";
}

function scheduleRender(tab) {
  const turn = tab.turn;
  if (turn.raf) return;
  turn.raf = requestAnimationFrame(() => {
    turn.raf = 0;
    if (turn.textEl) turn.textEl.innerHTML = renderMarkdown(turn.textRaw);
    scrollDown(tab);
  });
}

// Flush the current streaming text block to its FINAL rendered state, then close it.
// Critical: a pending requestAnimationFrame render is guarded by `turn.textEl`, so if we
// null textEl (to start a tool card / next step) without flushing first, that pending
// frame fires, sees textEl === null, and silently DROPS the last streamed chunk — e.g.
// Sections 3-5 of the opener vanishing the moment the first tool card appears. Reload looks
// fine because the saved transcript renders in one pass. Always finalize before moving on.
function finalizeText(turn) {
  if (!turn) return;
  if (turn.raf) { cancelAnimationFrame(turn.raf); turn.raf = 0; }
  if (turn.textEl) {
    turn.textEl.innerHTML = renderMarkdown(turn.textRaw);
    turn.textEl.classList.remove("cursor");
    if (typeof renderMermaidIn === "function") renderMermaidIn(turn.textEl);
  }
  turn.textEl = null;
  turn.thinkEl = null;
}

// ============================================================
//  Quick-action buttons — mode-specific follow-up prompts shown
//  below each completed assistant turn so one click fires the
//  most common next question without any typing.
// ============================================================
const QUICK_ACTIONS = {
  interview: [
    { label: "🔍 Brute Force",          prompt: "Walk me through the brute force approach step by step — narrate it exactly as I'd explain it out loud to an interviewer. Show the code too." },
    { label: "⚡ Optimal Deep Dive",    prompt: "Go line by line through the optimal solution. For each key step, tell me exactly what to say to the interviewer." },
    { label: "📖 Explain the Code",     prompt: "Explain the optimal code to me properly so I actually understand it, in simple Hinglish. Break it into a few logical parts; for each part show that piece of the code, then explain in plain words WHAT it does and WHY — like teaching a friend. Use small concrete examples and tiny diagrams where they help. This is for my own learning, not for narrating to an interviewer. At the end, give the whole thing in one Hinglish line, and invite me to ask about any single line or loop I'm stuck on." },
    { label: "💡 Core Intuition",       prompt: "What is the single key insight that makes the optimal solution work? Explain the 'aha' moment I should be able to articulate clearly." },
    { label: "🧪 Dry Run",              prompt: "Trace through the optimal solution on the problem's example — show exactly what's in each variable/data-structure at every step, like I'd draw on a whiteboard." },
    { label: "❓ Interviewer Follow-ups", prompt: "What are the 3 most likely follow-up questions an interviewer would ask after I present this solution? Give me each question and an ideal concise answer." },
    { label: "🎯 Quiz Me",              prompt: "Don't explain anything — quiz me instead. Ask me one targeted question to test my understanding of this solution, and wait for my answer before revealing anything." },
    { label: "📐 Edge Cases",           prompt: "What are the critical edge cases I must identify and handle? For each one, show what the solution does and what I should say to the interviewer." },
  ],
  assessment: [
    { label: "🧪 More Tests",           prompt: "Run 5 more adversarial test cases — especially edge cases the sample didn't cover. Verify the solution handles them all." },
    { label: "⚡ Optimize Further",     prompt: "Is there a way to optimize this solution further in time or space? If so, implement and verify the optimized version." },
    { label: "🔄 Alternative Approach", prompt: "Show me a completely different algorithmic approach to this problem. Compare both on time, space, and code simplicity." },
    { label: "🔍 Explain Logic",        prompt: "Explain the logic of this solution in plain English — what is the algorithm actually doing conceptually, step by step?" },
  ],
  lld: [
    { label: "🧩 Design Patterns",      prompt: "Which design patterns best strengthen this design and why? Show how to refactor one key class to apply one of them." },
    { label: "📊 Sequence Diagram",     prompt: "Generate a more detailed sequence diagram showing a complete end-to-end interaction flow through all layers." },
    { label: "🔒 Error Handling",       prompt: "Add comprehensive error handling and input validation to the existing code — show exactly what changes and why each matters." },
    { label: "🧪 Unit Tests",           prompt: "Write a thorough unit test suite for the core classes in this design." },
  ],
  hld: [
    { label: "📈 Scale 10x",            prompt: "Walk through what happens when this system gets 10x the expected load. What is the first bottleneck and exactly how would you fix it?" },
    { label: "🔒 Security",             prompt: "What are the top 3 security threats to this design and how would you mitigate each one concretely?" },
    { label: "💾 DB Deep Dive",         prompt: "Go deeper on the database layer — design the schema, key indexes, and explain the partitioning or sharding strategy with tradeoffs." },
    { label: "🔄 Failure Modes",        prompt: "Walk through the 3 most likely failure scenarios. What fails, what is the user impact, and how does the system detect and recover?" },
  ],
  behavioral: [
    { label: "💪 Strengthen It",        prompt: "Make this answer stronger — sharper numbers, clearer impact statement, tighter STAR structure. Show me the improved version." },
    { label: "🎯 LP Mapping",           prompt: "Which Amazon Leadership Principle is the strongest fit for this story? Rewrite the answer to make that connection explicit and compelling." },
    { label: "❓ Hard Follow-ups",      prompt: "What are the 3 hardest follow-up questions an interviewer could ask about this story? Give me an ideal response for each." },
    { label: "🔄 Different Angle",      prompt: "Reframe this same story to answer a different behavioral question type — pick the best alternative question it could answer and give the full answer." },
  ],
};

function showQuickActions(tab) {
  const turn = tab.turn;
  if (!turn || !turn.msgEl) return;
  const qa = turn.msgEl.querySelector(".quick-actions");
  if (!qa) return;
  const actions = QUICK_ACTIONS[tab.mode] || [];
  if (!actions.length) return;
  qa.innerHTML = actions
    .map((a) => `<button class="quick-action-btn" data-prompt="${a.prompt.replace(/"/g, "&quot;")}">${a.label}</button>`)
    .join("");
  qa.hidden = false;
}

const TOOL_META = {
  write_file: { cls: "write", icon: "✎", title: "write_file" },
  read_file: { cls: "read", icon: "▤", title: "read_file" },
  list_files: { cls: "read", icon: "≡", title: "list_files" },
  run_python: { cls: "run", icon: "▶", title: "run_python" },
  run_command: { cls: "run", icon: "$", title: "run_command" },
};
function targetForTool(name, inp) {
  if (!inp) return "";
  if (name === "write_file" || name === "read_file" || name === "run_python") return inp.path || "";
  if (name === "run_command") return inp.command || "";
  return "";
}

function addToolCall(tab, ev) {
  const turn = tab.turn;
  finalizeText(turn);

  const meta = TOOL_META[ev.name] || { cls: "read", icon: "•", title: ev.name };
  const card = document.createElement("div");
  card.className = "tool-card";
  const target = targetForTool(ev.name, ev.input);

  let detail = "";
  if (ev.name === "write_file" && ev.input && ev.input.content != null) {
    const lang = (target.split(".").pop() || "").toLowerCase();
    detail = `<div class="tool-body">${renderCodeBlock(lang, String(ev.input.content))}</div>`;
    // Capture this file for the "full code" modal (dedup by path, last write wins — a
    // rewrite after a failed run is the corrected version).
    if (target) {
      const files = turn.files || (turn.files = []);
      const existing = files.find((f) => f.path === target);
      if (existing) existing.content = String(ev.input.content);
      else files.push({ path: target, content: String(ev.input.content) });
    }
  } else if (ev.name === "run_command") {
    detail = `<div class="tool-body"><pre>$ ${escapeHtml(target)}</pre></div>`;
  } else if (ev.name === "run_python" && ev.input && ev.input.stdin) {
    detail = `<div class="tool-body"><div class="io-label">stdin</div><pre>${escapeHtml(String(ev.input.stdin))}</pre></div>`;
  }

  card.innerHTML =
    `<div class="tool-head">` +
    `<span class="tool-icon ${meta.cls}">${meta.icon}</span>` +
    `<span class="tool-title">${escapeHtml(meta.title)}</span>` +
    `<span class="tool-target">${escapeHtml(target)}</span>` +
    `<span class="tool-badge pending">running…</span>` +
    `</div>${detail}`;
  turn.body.appendChild(card);
  turn.toolCards[ev.id] = card;
  scrollDown(tab);
}

function addWebSearch(tab, query) {
  const turn = tab.turn;
  finalizeText(turn);
  const el = document.createElement("div");
  el.className = "web-search-card";
  el.innerHTML = `<span class="ws-icon">🔎</span><span class="ws-text"></span>`;
  el.querySelector(".ws-text").textContent = query
    ? "Searched the web: " + query
    : "Searched the web…";
  turn.body.appendChild(el);
  scrollDown(tab);
}

function addToolResult(tab, ev) {
  const card = tab.turn.toolCards[ev.id];
  if (!card) return;
  const badge = card.querySelector(".tool-badge");
  badge.classList.remove("pending");
  badge.classList.add(ev.is_error ? "err" : "ok");
  badge.textContent = ev.is_error ? "error" : "done";

  const isRun = ev.name === "run_python" || ev.name === "run_command";
  const showOutput = isRun || ev.is_error || ev.name === "read_file" || ev.name === "list_files";
  if (showOutput) {
    let body = card.querySelector(".tool-body");
    if (!body) { body = document.createElement("div"); body.className = "tool-body"; card.appendChild(body); }
    const pre = document.createElement("pre");
    if (ev.is_error || /stderr ---\n(?!\(empty\))/.test(ev.output)) pre.className = "stderr";
    pre.textContent = stripWorkspacePaths(ev.output);
    body.appendChild(pre);
    // Only auto-expand FAILURES. A successful run shows its green "done" badge as proof;
    // its raw stdout is not what the candidate reads aloud, so keep it collapsed (one tap
    // to open). This removes the wall-of-output between the problem and the talking points.
    if (ev.is_error) card.classList.add("open");
  }
  scrollDown(tab);
}

function showNotice(tab, msg) {
  if (!tab.turn) startAssistantTurn(tab);
  const turn = tab.turn;
  finalizeText(turn);
  const el = document.createElement("div");
  el.className = "notice-line";
  el.textContent = "ⓘ " + msg;
  turn.body.appendChild(el);
  scrollDown(tab);
}

function showError(tab, msg) {
  tab.lastError = true;
  if (!tab.turn) startAssistantTurn(tab);
  const turn = tab.turn;
  finalizeText(turn);
  const el = document.createElement("div");
  el.className = "tool-card open error-card";
  el.innerHTML =
    `<div class="tool-head"><span class="tool-icon err-icon">!</span>` +
    `<span class="tool-title err-title">error</span></div>` +
    `<div class="tool-body"><pre class="stderr"></pre></div>`;
  el.querySelector("pre").textContent = msg;
  turn.body.appendChild(el);
  scrollDown(tab, true);
}

function showUsage(tab, u) {
  if (!u || u.input_tokens == null) return;
  const parts = [`${u.input_tokens} in`, `${u.output_tokens} out`];
  if (u.cache_read_input_tokens) parts.push(`${u.cache_read_input_tokens} cached`);
  const tag = document.createElement("div");
  tag.className = "usage-line";
  tag.textContent = "↳ " + parts.join(" · ");
  tab.turn.body.appendChild(tag);
}

function handleEvent(tab, ev) {
  switch (ev.type) {
    case "step_start":
      finalizeText(tab.turn);
      break;
    case "thinking_delta":
      ensureThink(tab);
      tab.turn.thinkRaw += ev.text;
      tab.turn.thinkEl.textContent = tab.turn.thinkRaw;
      scrollDown(tab);
      break;
    case "text_delta":
      ensureText(tab);
      tab.turn.textRaw += ev.text;
      scheduleRender(tab);
      break;
    case "web_search":
      addWebSearch(tab, ev.query);
      break;
    case "tool_call":
      addToolCall(tab, ev);
      break;
    case "tool_result":
      addToolResult(tab, ev);
      break;
    case "turn_done":
      // finalizeText owns the one true "flush streaming text" path (cancel pending rAF,
      // final render, drop cursor, draw mermaid) — reuse it instead of a second copy that
      // could drift out of sync. The body-level mermaid pass catches diagrams in earlier
      // text blocks too.
      finalizeText(tab.turn);
      renderMermaidIn(tab.turn.body);
      attachFullCode(tab.turn, tab.mode);
      if (ev.usage) showUsage(tab, ev.usage);
      showQuickActions(tab);
      break;
    case "notice":
      showNotice(tab, ev.message);
      break;
    case "error":
      showError(tab, ev.message);
      break;
    case "done":
      break;
  }
}

// ============================================================
//  Sending
// ============================================================
async function send() {
  const tab = cur();
  const text = input.value.trim();
  if ((!text && tab.attachments.length === 0) || tab.streaming) return;

  tab.lastError = false;
  tab.passiveSession = null;  // this device is now the AUTHOR — stop live-sync polling/appending
  setUrlSession(tab.sessionId);  // this session is now running — show its id in the URL
  const imgs = tab.attachments.slice();
  addUserMessage(tab, text, imgs);

  input.value = "";
  autosize();
  if (mic) mic.stop();  // Stop dictation so old text doesn't reappear on next dictation
  const payloadImages = imgs.map((a) => ({ media_type: a.media_type, data: a.data }));
  tab.attachments = [];
  renderAttachments();

  setStreaming(tab, true);
  startAssistantTurn(tab);

  const payload = {
    session_id: tab.sessionId,
    message: text,
    images: payloadImages,
    model: modelSelect.value,
    mode: tab.mode,
    thinking: thinkingToggle.classList.contains("is-on") ? undefined : 0,
  };

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (resp.status === 401) {
      authToken = ""; localStorage.removeItem("algora_token"); promptToken();
      throw new Error("Unauthorized — enter the access token and try again.");
    }
    if (!resp.ok || !resp.body) {
      const t = await resp.text().catch(() => "");
      throw new Error(`HTTP ${resp.status} ${t}`);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const m = chunk.match(/^data:\s?([\s\S]*)$/);
        if (!m) continue;
        try { handleEvent(tab, JSON.parse(m[1])); }
        catch (err) { console.error("bad event", m[1], err); }
      }
    }
  } catch (err) {
    tab.pendingRecovery = true;  // attempt server-side recovery on next foreground
    // Show a soft "resuming" notice instead of a hard error — the server keeps
    // generating even after iOS suspends the browser; we'll auto-load on return.
    if (!tab.turn) startAssistantTurn(tab);
    finalizeText(tab.turn);
    const notice = document.createElement("div");
    notice.className = "notice-line bg-resume-notice";
    notice.textContent = "⏳ Generating in background — come back to see your answer.";
    tab.turn.body.appendChild(notice);
    scrollDown(tab);
  } finally {
    setStreaming(tab, false); // syncComposer reflects the error state for the active tab
  }
}

function setStreaming(tab, on) {
  tab.streaming = on;
  if (on) {
    // Hide all quick-action bars in this tab — a new user message is being processed.
    tab.el.querySelectorAll(".quick-actions").forEach((el) => { el.hidden = true; });
  }
  if (tab === cur()) syncComposer();
}

// ============================================================
//  Attachments
// ============================================================
function fileToAttachment(file) {
  return new Promise((resolve) => {
    if (!file.type.startsWith("image/")) return resolve(null);
    const r = new FileReader();
    r.onload = () => {
      const dataUrl = r.result;
      resolve({ media_type: file.type, data: dataUrl.slice(dataUrl.indexOf(",") + 1), dataUrl });
    };
    r.onerror = () => resolve(null);
    r.readAsDataURL(file);
  });
}
async function addFiles(files) {
  const tab = cur();

  // Direct approach: use File objects straight from file picker (works on Chrome iOS)
  for (const file of files) {
    if (!file.type.startsWith("image/")) continue;
    const a = await fileToAttachment(file);
    if (a) tab.attachments.push(a);
  }

  if (tab === cur()) renderAttachments();
}
function renderAttachments() {
  const list = cur().attachments;
  if (!list.length) { attachmentsEl.hidden = true; attachmentsEl.innerHTML = ""; return; }
  attachmentsEl.hidden = false;
  attachmentsEl.innerHTML = list
    .map((a, i) => `<div class="attachment"><img src="${a.dataUrl}" alt=""/><button data-i="${i}" type="button" aria-label="remove">✕</button></div>`)
    .join("");
}
attachmentsEl.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-i]");
  if (!b) return;
  cur().attachments.splice(+b.dataset.i, 1);
  renderAttachments();
});
attachBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => { 
  addFiles(Array.from(fileInput.files)).finally(() => {
    fileInput.value = ""; 
  });
});

document.addEventListener("paste", (e) => {
  const items = e.clipboardData && e.clipboardData.items;
  if (!items) return;
  const files = [];
  for (const it of items) if (it.kind === "file" && it.type.startsWith("image/")) files.push(it.getAsFile());
  if (files.length) { e.preventDefault(); addFiles(files); }
});

let dragDepth = 0;
window.addEventListener("dragenter", (e) => { e.preventDefault(); dragDepth++; dropOverlay.hidden = false; });
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("dragleave", (e) => { e.preventDefault(); if (--dragDepth <= 0) { dragDepth = 0; dropOverlay.hidden = true; } });
window.addEventListener("drop", (e) => {
  e.preventDefault(); dragDepth = 0; dropOverlay.hidden = true;
  if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
});

// ============================================================
//  Delegated clicks (copy / collapse / example chips) across both panels
// ============================================================
// Copy a renderCodeBlock copy-button's base64 payload to the clipboard, with feedback.
function copyRawBtn(btn) {
  let text = "";
  try { text = decodeURIComponent(escape(atob(btn.dataset.raw))); } catch { text = ""; }
  navigator.clipboard.writeText(text).then(() => {
    const prev = btn.textContent;
    btn.textContent = "copied!"; btn.classList.add("copied");
    setTimeout(() => { btn.textContent = prev || "copy"; btn.classList.remove("copied"); }, 1400);
  });
}

panels.addEventListener("click", (e) => {
  const copy = e.target.closest(".copy-btn");
  if (copy) { copyRawBtn(copy); return; }
  const fc = e.target.closest(".full-code-btn");
  if (fc) {
    const msg = fc.closest(".msg.assistant");
    if (msg && msg._files) openCodeModal(msg._files);
    return;
  }
  const th = e.target.closest(".think-head");
  if (th) { th.parentElement.classList.toggle("collapsed"); return; }
  const tc = e.target.closest(".tool-head");
  if (tc) { tc.parentElement.classList.toggle("open"); return; }
  const chip = e.target.closest(".example-chip");
  if (chip) { input.value = chip.dataset.example; autosize(); input.focus(); return; }
  const qa = e.target.closest(".quick-action-btn");
  if (qa && !cur().streaming) {
    input.value = qa.dataset.prompt;
    autosize();
    send();
  }
});

// Attach the captured write_file files to the message. In LLD mode we render a
// hellointerview-style "Complete Code Implementation" section INLINE at the end of the
// answer — collapsible per file, no modal. In every other mode the existing "📂 full
// code" button reveals the modal. The data source is the same `turn.files` either way.
function attachFullCode(turn, mode) {
  if (!turn || !turn.msgEl) return;
  turn.msgEl._files = turn.files || [];
  const btn = turn.msgEl.querySelector(".full-code-btn");
  const hasFiles = !!(turn.files && turn.files.length);
  if (mode === "lld") {
    if (btn) btn.hidden = true;     // LLD prefers the inline section
    renderInlineFullCode(turn);
    return;
  }
  if (btn) btn.hidden = !hasFiles;
}

// LLD-only: render an inline "Complete Code Implementation" section after the answer.
// A TABBED viewer (hellointerview style): file names as tabs along the top, a single
// fixed-height code pane below that scrolls internally. Switching tabs swaps the pane —
// the page stays compact instead of stacking every file vertically.
function renderInlineFullCode(turn) {
  if (!turn || !turn.body) return;
  // Idempotent: replace any existing section if attachFullCode runs twice (e.g. restore
  // after a live render).
  const existing = turn.body.querySelector(".inline-fullcode");
  if (existing) existing.remove();
  const files = turn.files || [];
  if (!files.length) return;

  const section = document.createElement("section");
  section.className = "inline-fullcode";
  section.innerHTML =
    `<div class="ifc-head">` +
    `<h2 class="ifc-title">Complete Code Implementation</h2>` +
    `<button class="ifc-copyall" type="button" title="Copy every file as one block">copy all</button>` +
    `</div>` +
    `<p class="ifc-blurb">While most companies only require pseudocode during interviews, ` +
    `some ask for full implementations. Below is the complete working implementation, ` +
    `file by file.</p>` +
    `<div class="ifc-viewer">` +
    `<div class="ifc-tabs" role="tablist"></div>` +
    `<div class="ifc-pane"></div>` +
    `</div>`;

  const tabsEl = section.querySelector(".ifc-tabs");
  const paneEl = section.querySelector(".ifc-pane");

  files.forEach((f, idx) => {
    const tab = document.createElement("button");
    tab.className = "ifc-tab" + (idx === 0 ? " active" : "");
    tab.type = "button";
    tab.dataset.i = String(idx);
    tab.innerHTML =
      `<span class="ifc-tab-name">${escapeHtml(f.path)}</span>` +
      `<span class="ifc-tab-meta">${f.content.split("\n").length}</span>`;
    tabsEl.appendChild(tab);
  });

  const show = (idx) => {
    paneEl.innerHTML = renderCodeBlock(langFromPath(files[idx].path), files[idx].content);
    tabsEl.querySelectorAll(".ifc-tab").forEach((t, k) => t.classList.toggle("active", k === idx));
    paneEl.scrollTop = 0;
  };
  show(0);

  tabsEl.addEventListener("click", (e) => {
    const b = e.target.closest(".ifc-tab");
    if (b) show(+b.dataset.i);
  });

  // The "copy all" button; per-file copy uses the existing panels-level `.copy-btn`
  // handler since the rendered code-block already includes its own copy button.
  const copyAll = section.querySelector(".ifc-copyall");
  copyAll.addEventListener("click", () => {
    const all = files.map((f) => `# ===== ${f.path} =====\n${f.content}`).join("\n\n\n");
    navigator.clipboard.writeText(all).then(() => {
      copyAll.textContent = "copied!";
      copyAll.classList.add("copied");
      setTimeout(() => {
        copyAll.textContent = "copy all";
        copyAll.classList.remove("copied");
      }, 1400);
    });
  });

  turn.body.appendChild(section);
}

// ============================================================
//  Full-code modal — the complete program, file by file (reuses the mermaid-zoom
//  overlay pattern: fixed overlay, Esc / click-scrim to close, no library).
// ============================================================
function langFromPath(p) { return (String(p).split(".").pop() || "").toLowerCase(); }

function openCodeModal(files) {
  if (!files || !files.length) return;
  const overlay = document.createElement("div");
  overlay.className = "code-modal";
  overlay.innerHTML =
    `<div class="cm-panel" role="dialog" aria-label="Full code" aria-modal="true">` +
    `<div class="cm-head">` +
    `<span class="cm-title">📂 Full code · ${files.length} file${files.length > 1 ? "s" : ""}</span>` +
    `<button class="cm-copyall" type="button">copy all</button>` +
    `<button class="cm-close" type="button" aria-label="Close">✕</button>` +
    `</div>` +
    `<div class="cm-body"><nav class="cm-files"></nav><div class="cm-code"></div></div>` +
    `</div>`;
  const filesEl = overlay.querySelector(".cm-files");
  const codeEl = overlay.querySelector(".cm-code");
  files.forEach((f, idx) => {
    const t = document.createElement("button");
    t.className = "cm-file" + (idx === 0 ? " active" : "");
    t.type = "button";
    t.textContent = f.path;
    t.dataset.i = String(idx);
    filesEl.appendChild(t);
  });
  const show = (idx) => {
    codeEl.innerHTML = renderCodeBlock(langFromPath(files[idx].path), files[idx].content);
    filesEl.querySelectorAll(".cm-file").forEach((t, k) => t.classList.toggle("active", k === idx));
    codeEl.scrollTop = 0;
  };
  show(0);
  filesEl.addEventListener("click", (e) => {
    const b = e.target.closest(".cm-file"); if (b) show(+b.dataset.i);
  });
  codeEl.addEventListener("click", (e) => {
    const c = e.target.closest(".copy-btn"); if (c) copyRawBtn(c);
  });
  overlay.querySelector(".cm-copyall").addEventListener("click", (e) => {
    const all = files.map((f) => `# ===== ${f.path} =====\n${f.content}`).join("\n\n\n");
    navigator.clipboard.writeText(all).then(() => {
      e.target.textContent = "copied!";
      setTimeout(() => { e.target.textContent = "copy all"; }, 1400);
    });
  });
  const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay || e.target.closest(".cm-close")) close();
  });
  document.addEventListener("keydown", onKey);
  document.body.appendChild(overlay);
}

// ============================================================
//  Composer behaviour
// ============================================================
function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
}
input.addEventListener("input", autosize);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !TOUCH) { e.preventDefault(); send(); }
});
form.addEventListener("submit", (e) => { e.preventDefault(); send(); });

thinkingToggle.addEventListener("click", () => thinkingToggle.classList.toggle("is-on"));

resetBtn.addEventListener("click", async () => {
  const tab = cur();
  if (tab.streaming) return;
  try {
    await fetch("/api/reset", {
      method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ session_id: tab.sessionId }),
    });
  } catch {}
  tab.el.innerHTML = tab.emptyHTML;
  tab.turn = null;
  tab.attachments = [];
  tab.lastError = false;
  tab.passiveSession = null;  // fresh conversation — nothing to live-sync
  // fresh session id -> a brand-new isolated workspace for the next problem
  tab.sessionId = newSessionId(tab.mode);
  setUrlSession(tab.sessionId);
  renderAttachments();
  syncComposer();
});

// ============================================================
//  Conversation history (server-persisted, per tab/mode)
// ============================================================
const historyDrawer = $("history-drawer");
const historyBackdrop = $("history-backdrop");
const historyList = $("history-list");

function relTime(epoch) {
  if (!epoch) return "";
  const s = Math.max(0, Date.now() / 1000 - epoch);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
}

// History lives on the server (this laptop), so it's identical on every device. We keep
// the open drawer fresh by polling + a change-signature so a conversation finished on the
// laptop shows up on the phone without a manual reload.
let _historyTimer = null;
let _historySig = "";
function historySignature(items) {
  return items.map((c) => `${c.session_id}:${c.updated_at}:${c.turns}`).join("|");
}
async function refreshHistory() {
  try {
    const r = await fetch(`/api/conversations?mode=${encodeURIComponent(active)}`, { headers: authHeaders() });
    const { conversations } = await r.json();
    const items = conversations || [];
    const sig = historySignature(items);
    if (sig !== _historySig) { _historySig = sig; renderHistory(items); }  // only repaint on change
  } catch {
    if (/Loading/.test(historyList.textContent)) {
      historyList.innerHTML = '<div class="history-empty">Could not load history.</div>';
    }
  }
}
async function openHistory() {
  historyList.innerHTML = '<div class="history-empty">Loading…</div>';
  historyDrawer.hidden = false;
  historyBackdrop.hidden = false;
  $("history-title").textContent = "History · " + (document.querySelector(`.tab[data-mode="${active}"]`)?.textContent.trim() || "");
  _historySig = "";
  await refreshHistory();
  clearInterval(_historyTimer);
  _historyTimer = setInterval(() => {
    if (!historyDrawer.hidden && !document.hidden) refreshHistory();
  }, 4000);
}
function closeHistory() {
  historyDrawer.hidden = true; historyBackdrop.hidden = true;
  clearInterval(_historyTimer); _historyTimer = null;
}

function renderHistory(items) {
  if (!items.length) {
    historyList.innerHTML = '<div class="history-empty">No saved chats in this tab yet.</div>';
    return;
  }
  historyList.innerHTML = "";
  for (const c of items) {
    const el = document.createElement("div");
    el.className = "history-item";
    el.innerHTML =
      `<div class="hi-main"><div class="hi-title"></div>` +
      `<div class="hi-meta">${relTime(c.updated_at)} · ${c.turns} msg${c.turns === 1 ? "" : "s"}</div></div>` +
      `<button class="hi-del" title="Delete" aria-label="Delete">🗑</button>`;
    el.querySelector(".hi-title").textContent = c.title || "Untitled";
    el.querySelector(".hi-main").addEventListener("click", () => restoreConversation(c.session_id, c.mode));
    el.querySelector(".hi-del").addEventListener("click", (e) => { e.stopPropagation(); deleteConv(c.session_id); });
    historyList.appendChild(el);
  }
}

async function deleteConv(id) {
  try { await fetch(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE", headers: authHeaders() }); } catch {}
  _historySig = ""; refreshHistory();
}

// Replay a saved assistant turn into the DOM, reusing the live renderers.
function renderSavedAssistant(tab, item) {
  startAssistantTurn(tab);
  const turn = tab.turn;
  if (item.thinking) {
    ensureThink(tab);
    turn.thinkEl.textContent = item.thinking;
    turn.thinkEl.parentElement.classList.add("collapsed"); // collapsed by default on restore
    turn.thinkEl = null;
  }
  for (const b of item.blocks || []) {
    turn.textEl = null; turn.thinkEl = null;
    if (b.k === "text") {
      const p = document.createElement("div");
      p.className = "prose";
      p.innerHTML = renderMarkdown(b.md || "");
      turn.body.appendChild(p);
    } else if (b.k === "tool") {
      const id = b.id || "t" + Math.random().toString(36).slice(2);
      addToolCall(tab, { id, name: b.name, input: b.input || {} });
      addToolResult(tab, { id, name: b.name, output: b.output || "", is_error: !!b.is_error });
    } else if (b.k === "web") {
      addWebSearch(tab, b.query);
    }
  }
  renderMermaidIn(turn.body);
  attachFullCode(turn, tab.mode);
  if (item.usage) showUsage(tab, item.usage);
}

async function restoreConversation(id, mode) {
  let data;
  try {
    const r = await fetch(`/api/conversations/${encodeURIComponent(id)}`, { headers: authHeaders() });
    if (!r.ok) throw new Error("not found");
    data = await r.json();
  } catch { return; }
  mode = mode || data.mode || active;
  if (mode !== active) switchTab(mode);
  const t = tabs[mode];
  if (t.streaming) { closeHistory(); return; }
  t.el.innerHTML = "";
  t.turn = null; t.lastError = false; t.attachments = [];
  t.sessionId = id; // follow-ups continue THIS conversation
  setUrlSession(id);
  const tr = data.transcript || [];
  let lastRole = null;
  for (const it of tr) {
    if (it.role === "user") {
      const txt = (it.images ? `📎 ${it.images} image(s)\n` : "") + (it.text || "");
      addUserMessage(t, txt, []);
    } else {
      renderSavedAssistant(t, it);
    }
    lastRole = it.role;
  }
  // Show quick-action buttons on the last assistant turn so follow-ups are one click away.
  if (lastRole === "assistant") showQuickActions(t);
  // This device is now PASSIVELY viewing a server-stored conversation: live-sync picks up
  // turns added from another device. Cleared the moment this device authors a turn (send()).
  t.passiveSession = id;
  t.renderedCount = tr.length;
  renderAttachments();
  syncComposer();
  closeHistory();
  t.el.scrollTop = t.el.scrollHeight;
}

$("history-btn").addEventListener("click", openHistory);
$("history-close").addEventListener("click", closeHistory);
historyBackdrop.addEventListener("click", closeHistory);

// ============================================================
//  Cross-device: "open on another device" + live conversation sync
// ============================================================
function deviceUrls() {
  // Build "open here" URLs from the server's LAN IP(s) + this page's own scheme & port,
  // so a phone/iPad on the same Wi-Fi can reach this laptop. Falls back to this origin.
  const port = location.port ? ":" + location.port : "";
  const urls = (lanHosts || []).map((ip) => `${location.protocol}//${ip}${port}`);
  if (!urls.length) urls.push(location.origin);
  return urls;
}
function openDeviceModal() {
  const urls = deviceUrls();
  const overlay = document.createElement("div");
  overlay.className = "code-modal device-modal";
  overlay.innerHTML =
    `<div class="cm-panel dm-panel" role="dialog" aria-modal="true">` +
    `<div class="cm-head"><span class="cm-title">📱 Open on another device</span>` +
    `<button class="cm-close" type="button" aria-label="Close">✕</button></div>` +
    `<div class="dm-body">` +
    `<p class="dm-note">On your phone or iPad — on the <strong>same Wi-Fi</strong> — open this address. Everything, including all your history, is served from this laptop, so every device stays in sync.</p>` +
    urls.map((u) => `<div class="dm-url"><code></code><button class="dm-copy" type="button">copy</button></div>`).join("") +
    `<p class="dm-hint">Over HTTPS you'll accept the self-signed certificate once. No internet needed — it's your laptop.</p>` +
    `</div></div>`;
  // set URL text via textContent (avoids any escaping concerns) + wire copy
  overlay.querySelectorAll(".dm-url").forEach((row, i) => {
    row.querySelector("code").textContent = urls[i];
    row.querySelector(".dm-copy").addEventListener("click", (e) => {
      navigator.clipboard.writeText(urls[i]).then(() => {
        e.target.textContent = "copied!"; setTimeout(() => { e.target.textContent = "copy"; }, 1400);
      });
    });
  });
  const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  overlay.addEventListener("click", (e) => { if (e.target === overlay || e.target.closest(".cm-close")) close(); });
  document.addEventListener("keydown", onKey);
  document.body.appendChild(overlay);
}
$("devices-btn").addEventListener("click", openDeviceModal);

// Live-sync a conversation this device is PASSIVELY viewing (restored from history): if
// another device adds a turn, the server transcript grows and we append the new turns here.
async function liveSyncTick() {
  const t = cur();
  if (!t || t.streaming || !t.passiveSession || document.hidden) return;
  const id = t.passiveSession;
  try {
    const r = await fetch(`/api/conversations/${encodeURIComponent(id)}`, { headers: authHeaders() });
    if (!r.ok) return;
    const data = await r.json();
    // bail if anything changed while we awaited (tab switch / send / restore)
    if (t !== cur() || t.passiveSession !== id || t.streaming) return;
    const tr = data.transcript || [];
    if (tr.length <= (t.renderedCount || 0)) return;
    const wasBottom = atBottom(t);
    let syncLastRole = null;
    for (let k = t.renderedCount || 0; k < tr.length; k++) {
      const it = tr[k];
      if (it.role === "user") {
        addUserMessage(t, (it.images ? `📎 ${it.images} image(s)\n` : "") + (it.text || ""), []);
      } else {
        renderSavedAssistant(t, it);
      }
      syncLastRole = it.role;
    }
    t.renderedCount = tr.length;
    if (syncLastRole === "assistant") showQuickActions(t);
    if (wasBottom) t.el.scrollTop = t.el.scrollHeight;
  } catch { /* transient — try again next tick */ }
}
setInterval(liveSyncTick, 5000);
// When a stream fails because iOS backgrounded the app (fetch connection drops while
// suspended), the server's agent keeps running and saves the completed response via
// _persist_turn(). On foreground, we poll until the assistant turn appears, then
// silently re-render the full conversation — no error card, seamless resume.
async function tryRecoverInterruptedStream() {
  const t = cur();
  if (!t || !t.pendingRecovery || t.streaming) return;
  t.pendingRecovery = false;
  const id = t.sessionId;
  if (!id) return;

  // Poll up to ~60s (12 × 5s) — covers long behavioral / code answers.
  for (let attempt = 0; attempt < 12; attempt++) {
    await new Promise(r => setTimeout(r, attempt === 0 ? 1500 : 5000));
    if (t !== cur() || t.streaming || !id) return;  // user navigated away or sent a new msg
    try {
      const r = await fetch(`/api/conversations/${encodeURIComponent(id)}`, { headers: authHeaders() });
      if (!r.ok) continue;
      const data = await r.json();
      const tr = data.transcript || [];
      if (!tr.length || tr[tr.length - 1].role !== "assistant") continue;
      // Got the completed assistant turn — clear partial content and re-render cleanly.
      t.el.innerHTML = "";
      t.turn = null; t.lastError = false;
      for (const it of tr) {
        if (it.role === "user") {
          addUserMessage(t, (it.images ? `📎 ${it.images} image(s)\n` : "") + (it.text || ""), []);
        } else {
          renderSavedAssistant(t, it);
        }
      }
      showQuickActions(t);
      t.el.scrollTop = t.el.scrollHeight;
      return;  // done
    } catch { /* transient — retry */ }
  }
  // All retries exhausted — show a real error so user knows to re-send.
  if (!t.turn) startAssistantTurn(t);
  const notice = t.el.querySelector(".bg-resume-notice");
  if (notice) {
    notice.className = "tool-card open error-card";
    notice.innerHTML =
      `<div class="tool-head"><span class="tool-icon err-icon">!</span>` +
      `<span class="tool-title err-title">error</span></div>` +
      `<div class="tool-body"><pre class="stderr">Response lost — please re-send your message.</pre></div>`;
  }
}

// Coming back to a device (unlock phone / refocus tab): refresh immediately rather than
// waiting for the next interval, so it feels in-sync the moment you look at it.
document.addEventListener("visibilitychange", () => {
  if (document.hidden) return;
  if (!historyDrawer.hidden) refreshHistory();
  liveSyncTick();
  tryRecoverInterruptedStream();
});
window.addEventListener("focus", () => { if (!historyDrawer.hidden) refreshHistory(); liveSyncTick(); });

// voice dictation (mic button shows only if supported)
const mic = setupMic({ input, button: micBtn, onText: autosize });

// ============================================================
//  Health check
// ============================================================
let lanHosts = [];  // this server's LAN IP(s) — for the "open on another device" helper
(async function init() {
  try {
    const r = await fetch("/api/health");
    const h = await r.json();
    if (h.auth_required && !authToken) promptToken();
    if (h.default_model && [...modelSelect.options].some((o) => o.value === h.default_model)) {
      modelSelect.value = h.default_model;
    }
    lanHosts = h.lan_hosts || [];
    statusDot.className = "status-dot ok";
    statusDot.title = "ready · workspace: " + h.workspace;
  } catch {
    statusDot.className = "status-dot err";
    statusDot.title = "backend unreachable";
  }
  // Restore a session from ?s=<id> in the URL (id encodes the tab as "<uuid>:<mode>").
  // If it was a saved conversation, its transcript loads; otherwise the tab just adopts
  // the id so a reload keeps the same session. With no ?s=, show the default session id.
  const urlSession = new URL(window.location.href).searchParams.get("s");
  if (urlSession && urlSession.includes(":")) {
    const mode = urlSession.split(":").pop();
    if (tabs[mode]) {
      if (mode !== active) switchTab(mode);
      tabs[mode].sessionId = urlSession;       // adopt id (covers the never-saved case)
      restoreConversation(urlSession, mode);   // load transcript if it exists (no-op if not)
    }
  } else {
    setUrlSession(cur().sessionId);
  }
})();



