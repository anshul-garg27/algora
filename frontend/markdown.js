/* ============================================================
   Self-contained Markdown renderer (no external deps for text):
   - HTML-escaped output (XSS-safe for model/tool output)
   - fenced code blocks with copy button + light Python highlight
   - GFM tables (great for DP tables / array states)
   - Mermaid blocks -> rendered to SVG via the vendored mermaid lib,
     loaded lazily only when a diagram actually appears.
   Exposes globals: escapeHtml, renderMarkdown, renderMermaidIn.
   ============================================================ */

"use strict";

function escapeHtml(s) {
  // Escapes quotes too, so escaped text is safe inside quoted HTML attributes
  // (e.g. link href, data-* attrs) — not just in text nodes.
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const PY_TOKENS =
  /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|\b(def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|with|try|except|finally|raise|lambda|yield|global|nonlocal|pass|break|continue|None|True|False|is|assert|del|async|await|print|range|len|self)\b|\b(\d+\.?\d*)\b/g;

function highlightPy(escaped) {
  return escaped.replace(PY_TOKENS, (m, com, str, kw, num) => {
    if (com) return `<span class="tok-com">${com}</span>`;
    if (str) return `<span class="tok-str">${str}</span>`;
    if (kw) return `<span class="tok-kw">${kw}</span>`;
    if (num) return `<span class="tok-num">${num}</span>`;
    return m;
  });
}

// C-family keyword tint (Java / C++ / TS / Go / Kotlin / Rust / Swift). Operates on
// already-HTML-escaped code, so — like the Python pass — it tints keywords, // and
// /* */ comments, and numbers (string literals stay plain, matching highlightPy).
// LLD explicitly supports non-Python languages, so this stops Java rendering as a
// flat monochrome wall.
const C_TOKENS =
  /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|\b(abstract|class|interface|enum|extends|implements|public|private|protected|final|static|synchronized|volatile|transient|void|new|return|if|else|for|while|do|switch|case|default|break|continue|throw|throws|try|catch|finally|this|super|null|true|false|import|package|const|let|var|function|func|fun|type|struct|namespace|using|val|override|int|long|double|float|boolean|bool|char|byte|short|String|string|auto|nil)\b|\b(\d+\.?\d*[fFlLdD]?)\b/g;

function highlightC(escaped) {
  return escaped.replace(C_TOKENS, (m, com, kw, num) => {
    if (com) return `<span class="tok-com">${com}</span>`;
    if (kw) return `<span class="tok-kw">${kw}</span>`;
    if (num) return `<span class="tok-num">${num}</span>`;
    return m;
  });
}
const C_LANGS = /^(java|c|cpp|c\+\+|cs|csharp|js|javascript|ts|typescript|go|golang|kotlin|kt|rust|rs|swift|scala)$/;

let _mermaidSeq = 0;

function renderCodeBlock(lang, code) {
  const language = (lang || "").toLowerCase();
  // Mermaid -> a placeholder rendered into SVG after the text settles.
  if (language === "mermaid") {
    const raw = btoa(unescape(encodeURIComponent(code.replace(/\n$/, ""))));
    return `<div class="mermaid-block" data-code="${raw}" data-id="mmd-${_mermaidSeq++}"><pre class="mermaid-src">${escapeHtml(code.replace(/\n$/, ""))}</pre></div>`;
  }
  const escaped = escapeHtml(code.replace(/\n$/, ""));
  // Only tint blocks the model explicitly tagged python — so a bare ```...``` ASCII
  // trace / array diagram isn't sprayed with random keyword/number colors.
  const isPy = /^(py|python)$/.test(language);
  const body = isPy ? highlightPy(escaped) : (C_LANGS.test(language) ? highlightC(escaped) : escaped);
  // No language chip for plain/untagged blocks (the old "TEXT" stamp was pure noise).
  const label = /^(text|plain|txt)$/.test(language) ? "" : language;
  const raw = btoa(unescape(encodeURIComponent(code.replace(/\n$/, ""))));
  return (
    `<div class="code-block"><div class="code-bar">` +
    `<span class="code-lang">${escapeHtml(label)}</span>` +
    `<button class="copy-btn" data-raw="${raw}" type="button">copy</button></div>` +
    `<pre><code>${body}</code></pre></div>`
  );
}

function inlineMd(text) {
  // `text` is already HTML-escaped.
  let out = text;
  out = out.replace(/`([^`]+)`/g, (m, c) => `<code class="inline">${c}</code>`);
  // Lazy bold so inner single stars survive: **O(n*m)** -> one bold span, not garbage.
  out = out.replace(/\*\*([\s\S]+?)\*\*/g, "<strong>$1</strong>");
  // make Approach / Challenges / Trade-off labels stand out inside tiers
  out = out.replace(
    /<strong>(Approach|Challenges?|Trade-?offs?|Problem|Why it works)(:?)<\/strong>/gi,
    '<strong class="dd-label">$1</strong>'
  );
  // Boundary-safe *italics*: opening '*' sits at a word boundary (start, space, or '(')
  // and hugs its content; closing '*' is followed by space/punct/end. Keeps real emphasis
  // (*aggregates*, *composes*) while leaving multiplication (a*b, O(n*m), 10 * 5) untouched.
  out = out.replace(/(^|[\s(])\*(\S|\S[^*\n]*?\S)\*(?=[\s.,;:!?)]|$)/g, "$1<em>$2</em>");
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, url) => {
    // `url` is already HTML-escaped here (renderMarkdown escapes before inlineMd),
    // so quotes are &quot; and cannot break out of the attribute. Do NOT re-escape
    // (that would double-escape & in query strings).
    const u = url.trim();
    if (/^(https?:|mailto:)/i.test(u)) {
      return `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`;
    }
    return m;
  });
  return out;
}

function splitRow(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  // Honor GFM escaped pipes (\\|) so absolute-value cells like |d| or |c - n| stay in
  // ONE column instead of splitting the row. Protect, split, then restore the pipe.
  // (Sentinel + replace avoids a lookbehind regex for older-Safari compatibility.)
  return s
    .replace(/\\\|/g, "\u0001")
    .split("|")
    .map((c) => c.trim().replace(/\u0001/g, "|"));
}

function isTableSep(line) {
  return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(line);
}

function renderTable(rows) {
  const head = splitRow(rows[0]);
  const bodyRows = rows.slice(2);
  let html = '<div class="table-wrap"><table><thead><tr>';
  html += head.map((c) => `<th>${inlineMd(escapeHtml(c))}</th>`).join("");
  html += "</tr></thead><tbody>";
  for (const r of bodyRows) {
    const cells = splitRow(r);
    html += "<tr>" + cells.map((c) => `<td>${inlineMd(escapeHtml(c))}</td>`).join("") + "</tr>";
  }
  html += "</tbody></table></div>";
  return html;
}

// Some models emit an entire Markdown table glued onto ONE line:
//   "| a | b | |---|---| | 1 | 2 | | 3 | 4 |"
// Detect that and expand it back into proper per-row lines so it renders.
// Conservative: only fires for >=2 columns with a clean cell grid.
function maybeExpandGluedTable(line) {
  if (!/\|\s*:?-{2,}:?\s*\|/.test(line)) return null; // needs an embedded separator run
  const cells = line.split("|").map((c) => c.trim());
  while (cells.length && cells[0] === "") cells.shift();
  while (cells.length && cells[cells.length - 1] === "") cells.pop();
  const isSep = (c) => /^:?-{2,}:?$/.test(c);
  const cols = cells.filter(isSep).length;
  if (cols < 2) return null;
  // Drop separator cells AND the empty cells produced by "| |" row boundaries,
  // then regroup the real content into rows of `cols`.
  const content = cells.filter((c) => c !== "" && !isSep(c));
  if (content.length < 2 * cols || content.length % cols !== 0) return null; // not a clean grid
  const out = [];
  for (let i = 0; i < content.length; i += cols) {
    out.push("| " + content.slice(i, i + cols).join(" | ") + " |");
  }
  const sep = "|" + " --- |".repeat(cols);
  return [out[0], sep, ...out.slice(1)]; // header, separator, data rows
}

// A deep-dive solution tier (Bad / Good / Great) header -> the tier key, else null.
// Require a delimiter after the word (the prompts emit "#### Good: <technique>") so
// ordinary headings like "Good practices" or "Great, now..." don't become tier cards.
function tierOf(text) {
  // tolerate a stray leading ** the model sometimes wraps the heading in
  const m = text.replace(/^\*+\s*/, "").match(/^(bad|good|great)\s*[:\-—)]/i);
  return m ? m[1].toLowerCase() : null;
}

// Lead-emoji -> blockquote modifier class. Lets 💬 say-lines, 🎙 scripts, and the
// 🤝/🆘/🧠/⚠️ conversational beats each get a distinct, semantic treatment.
function markerClass(s) {
  const m = s.match(/^\s*(💬|🎙|🤝|🆘|🧠|⚠️|⚠)/u);
  if (!m) return "";
  return { "💬": "talk", "🎙": "script", "🤝": "check", "🆘": "sos", "🧠": "ask", "⚠️": "trap", "⚠": "trap" }[m[1]] || "";
}

function renderMarkdown(src) {
  if (!src) return "";
  // Strip stray tool-call grammar tags the model can leak into its text stream
  // (e.g. a lone </parameter> just before a code fence, which lands inside a
  // mermaid block and breaks the diagram). These are never part of the answer.
  src = src.replace(
    /<\/?(?:parameter|antml:[a-z_]+|function_calls|invoke|function_results|tool_use|tool_result)\b[^>]*>/gi,
    ""
  );
  // 1) extract fenced code (and mermaid) blocks
  const blocks = [];
  const work = src.replace(/```(\w+)?\n?([\s\S]*?)```/g, (m, lang, code) => {
    blocks.push(renderCodeBlock(lang, code));
    return `  BLOCK${blocks.length - 1}  `;
  });

  // split headers glued onto the end of a line (e.g. "…numbers)### Key numbers").
  // The preceding char must be non-space AND non-'#' so real line-start headers
  // (## / ### / ####) are never split.
  const dehyphenated = work.replace(/([^\s#])(#{2,4}\s)/g, "$1\n$2");
  const lines = [];
  for (const ln of dehyphenated.split("\n")) {
    const expanded = maybeExpandGluedTable(ln);
    if (expanded) lines.push(...expanded);
    else lines.push(ln);
  }
  let html = "";
  let listType = null;
  let para = [];
  let openTier = false;

  const flushPara = () => {
    if (para.length) { html += `<p>${inlineMd(escapeHtml(para.join("\n")))}</p>`; para = []; }
  };
  const closeList = () => { if (listType) { html += `</${listType}>`; listType = null; } };
  const closeTier = () => { if (openTier) { html += "</div>"; openTier = false; } };

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    // Unwrap a heading the model mistakenly bold-wrapped: **#### Bad: x** -> #### Bad: x
    line = line.replace(/^\*\*(#{1,4}\s[\s\S]*?)\*\*\s*$/, "$1");

    const placeholder = line.match(/^  BLOCK(\d+)  $/);
    if (placeholder) { flushPara(); closeList(); html += blocks[+placeholder[1]]; continue; }

    // GFM table: a row with pipes followed by a separator row
    if (line.includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      flushPara(); closeList();
      const tableLines = [line, lines[i + 1]];
      let j = i + 2;
      while (j < lines.length && lines[j].includes("|") && lines[j].trim() !== "") {
        tableLines.push(lines[j]); j++;
      }
      html += renderTable(tableLines);
      i = j - 1;
      continue;
    }

    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flushPara(); closeList();
      const lvl = h[1].length;
      const tier = lvl >= 3 ? tierOf(h[2]) : null;
      if (tier) {
        // Bad/Good/Great deep-dive tier -> a colour-coded card.
        closeTier();
        const title = h[2]
          .replace(/^\*+\s*/, "")                                    // drop leading orphan **
          .replace(/^(bad|good|great)(\s+solution)?\s*[:\-—)]*\s*/i, "")
          .replace(/\s*\*+$/, "");                                   // drop trailing orphan **
        html +=
          `<div class="tier tier-${tier}"><div class="tier-head">` +
          `<span class="tier-badge">${tier}</span>` +
          `<span class="tier-title">${inlineMd(escapeHtml(title))}</span></div>`;
        openTier = true;
      } else {
        if (lvl <= 3) closeTier(); // a new section/question closes the tier card
        html += `<h${lvl}>${inlineMd(escapeHtml(h[2]))}</h${lvl}>`;
      }
      continue;
    }

    const bq = line.match(/^>\s?(.*)$/);
    if (bq) {
      flushPara(); closeList();
      html += `<blockquote class="${markerClass(bq[1])}">${inlineMd(escapeHtml(bq[1]))}</blockquote>`;
      continue;
    }

    // 🎙️ Script — the connected, read-aloud narration the candidate SPEAKS. The single
    // most important HLD element: give it a distinct teleprompter block (and feed it to
    // read-aloud). Detect a plain line starting with the mic emoji and absorb the spoken
    // paragraph (continuation lines) until a blank line / new block.
    if (/^\s*🎙/u.test(line)) {
      flushPara(); closeList(); closeTier();
      const head = line.replace(/^\s*🎙️?\s*(?:\*\*)?\s*(?:Script|Say[- ]?it)?\s*(?:\*\*)?\s*[:：\-—]?\s*/iu, "");
      const parts = [];
      if (head.trim()) parts.push(head.trim());
      let j = i + 1;
      while (j < lines.length) {
        const nx = lines[j];
        if (nx.trim() === "") break;
        if (/^\s*(#{1,4}\s|>|[-*]\s|\d+\.\s|---|🎙|💬|🤝|🆘|🧠|⚠)/u.test(nx)) break;
        if (/^\s*\x00?\s*BLOCK\d+/.test(nx)) break;
        parts.push(nx.trim());
        j++;
      }
      i = j - 1;
      html +=
        `<aside class="script-block"><div class="script-head">🎙️ Script — say this</div>` +
        `<div class="script-body">${inlineMd(escapeHtml(parts.join(" ")))}</div></aside>`;
      continue;
    }

    // Trim leading indentation first so an indented sub-bullet still renders as a
    // (flat) list item instead of breaking into a paragraph. Nesting is intentionally
    // flattened — keeping the marker readable matters more than nested <ul> depth here.
    const lt = line.replace(/^\s+/, "");
    const ul = lt.match(/^[-*]\s+(.*)$/);
    const ol = lt.match(/^(\d+)\.\s+(.*)$/);
    if (ul || ol) {
      flushPara();
      const want = ul ? "ul" : "ol";
      if (listType !== want) {
        closeList();
        const start = ol && +ol[1] > 1 ? ` start="${+ol[1]}"` : "";  // honor resumed numbering
        html += `<${want}${start}>`;
        listType = want;
      }
      html += `<li>${inlineMd(escapeHtml(ul ? ul[1] : ol[2]))}</li>`;
      continue;
    }

    if (line.trim() === "") { flushPara(); closeList(); continue; }
    para.push(line);
  }
  flushPara(); closeList(); closeTier();
  return html;
}

/* ---------- Mermaid (lazy) ---------- */

let _mermaidPromise = null;
function ensureMermaid() {
  if (_mermaidPromise) return _mermaidPromise;
  _mermaidPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "/vendor/mermaid.min.js";
    s.onload = () => {
      try {
        window.mermaid.initialize({
          startOnLoad: false,
          theme: "base",
          securityLevel: "strict",
          fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
          themeVariables: {
            darkMode: true,
            background: "#0d1117",
            primaryColor: "#1f2937",
            primaryTextColor: "#e6edf3",
            primaryBorderColor: "#3b4757",
            lineColor: "#8b949e",
            secondaryColor: "#262d3a",
            tertiaryColor: "#161b22",
            textColor: "#e6edf3",
            clusterBkg: "#161b22",
            clusterBorder: "#30363d",
            edgeLabelBackground: "#0d1117",
            fontSize: "16px",
          },
          // useMaxWidth:false → SVG keeps its natural pixel size so the block can
          // scroll instead of shrinking the diagram to fit (the #1 readability bug).
          flowchart: { useMaxWidth: false, htmlLabels: true, nodeSpacing: 60, rankSpacing: 70, curve: "basis", padding: 12 },
          sequence: { useMaxWidth: false },
          class: { useMaxWidth: false },
          er: { useMaxWidth: false },
          state: { useMaxWidth: false },
        });
        resolve(window.mermaid);
      } catch (e) { reject(e); }
    };
    s.onerror = () => reject(new Error("failed to load mermaid"));
    document.head.appendChild(s);
  });
  return _mermaidPromise;
}

// After a diagram renders, let it keep its natural pixel width (so its block can
// scroll horizontally instead of squeezing the SVG down) and mark it done.
function _onMermaidRendered(el) {
  el.classList.add("rendered");
  const svg = el.querySelector("svg");
  if (svg) {
    svg.style.maxWidth = "none";
    svg.removeAttribute("width"); // keep viewBox + height so it scales cleanly
    // If the diagram is wider than its container, left-anchor it (so the part you
    // read first is visible) rather than centering it half-off-screen.
    requestAnimationFrame(() => {
      if (el.scrollWidth > el.clientWidth + 4) el.classList.add("mmd-wide");
    });
  }
}

// Tap/click a rendered diagram to open it full-screen (readable + scrollable) on
// laptop and iPhone. One delegated listener, no library needed.
let _mermaidZoomWired = false;
function wireMermaidZoom() {
  if (_mermaidZoomWired) return;
  _mermaidZoomWired = true;
  document.addEventListener("click", (e) => {
    const block = e.target.closest(".mermaid-block.rendered:not(.mermaid-error)");
    if (!block) return;
    const svg = block.querySelector("svg");
    if (!svg) return;
    const overlay = document.createElement("div");
    overlay.className = "mermaid-zoom";
    const clone = svg.cloneNode(true);
    clone.style.maxWidth = "none";
    clone.removeAttribute("width");
    overlay.appendChild(clone);
    const hint = document.createElement("div");
    hint.className = "mermaid-zoom-hint";
    hint.textContent = "tap anywhere or press Esc to close";
    overlay.appendChild(hint);
    const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (ev) => { if (ev.key === "Escape") close(); };
    overlay.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
  });
}

// Render any not-yet-rendered mermaid blocks inside `root`.
async function renderMermaidIn(root) {
  if (!root) return;
  wireMermaidZoom();
  const pending = root.querySelectorAll(".mermaid-block:not([data-done])");
  if (!pending.length) return;
  let mermaid;
  try { mermaid = await ensureMermaid(); }
  catch { return; } // leave the source <pre> as a readable fallback
  for (const el of pending) {
    el.setAttribute("data-done", "1");
    let code = "";
    try { code = decodeURIComponent(escape(atob(el.dataset.code))).trim(); } catch { continue; }
    try {
      const { svg } = await mermaid.render(el.dataset.id, code);
      el.innerHTML = svg;
      _onMermaidRendered(el);
    } catch (err) {
      // Salvage the common failure: breaking chars (| : ( ) < > /) inside quoted
      // labels (e.g. erDiagram `status "active|completed"`). Retry once cleaned.
      try {
        const safe = code.replace(/"([^"]*)"/g, (m, s) => '"' + s.replace(/[|:()<>/\[\]]/g, " ") + '"');
        const { svg } = await mermaid.render(el.dataset.id + "-s", safe);
        el.innerHTML = svg;
        _onMermaidRendered(el);
      } catch (e2) {
        el.classList.add("mermaid-error"); // keep the source visible as fallback
      }
    }
  }
}
