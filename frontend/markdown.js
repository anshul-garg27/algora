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

// Tokenize the RAW (un-escaped) source, then HTML-escape each segment as we emit it.
// Escaping *after* tokenizing is essential: if we escaped first, a `'` would become
// `&#39;` and the string regex (which looks for real quote chars) would never match,
// so docstrings/strings wouldn't be detected AND the number rule would catch the `39`
// inside `&#39;`, splitting the entity and printing a literal `&#39;` on screen.
function highlightPy(code) {
  let out = "";
  let last = 0;
  code.replace(PY_TOKENS, (m, com, str, kw, num, offset) => {
    out += escapeHtml(code.slice(last, offset));
    if (com) out += `<span class="tok-com">${escapeHtml(com)}</span>`;
    else if (str) out += `<span class="tok-str">${escapeHtml(str)}</span>`;
    else if (kw) out += `<span class="tok-kw">${escapeHtml(kw)}</span>`;
    else if (num) out += `<span class="tok-num">${escapeHtml(num)}</span>`;
    else out += escapeHtml(m);
    last = offset + m.length;
    return m;
  });
  out += escapeHtml(code.slice(last));
  return out;
}

// C-family keyword tint (Java / C++ / TS / Go / Kotlin / Rust / Swift). Operates on
// already-HTML-escaped code, so — like the Python pass — it tints keywords, // and
// /* */ comments, and numbers (string literals stay plain, matching highlightPy).
// LLD explicitly supports non-Python languages, so this stops Java rendering as a
// flat monochrome wall.
const C_TOKENS =
  /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|\b(abstract|class|interface|enum|extends|implements|public|private|protected|final|static|synchronized|volatile|transient|void|new|return|if|else|for|while|do|switch|case|default|break|continue|throw|throws|try|catch|finally|this|super|null|true|false|import|package|const|let|var|function|func|fun|type|struct|namespace|using|val|override|int|long|double|float|boolean|bool|char|byte|short|String|string|auto|nil)\b|\b(\d+\.?\d*[fFlLdD]?)\b/g;

// Same raw-first, escape-per-segment strategy as highlightPy (see note there) so an
// apostrophe in a Java/C string can never render as a literal `&#39;`.
function highlightC(code) {
  let out = "";
  let last = 0;
  code.replace(C_TOKENS, (m, com, kw, num, offset) => {
    out += escapeHtml(code.slice(last, offset));
    if (com) out += `<span class="tok-com">${escapeHtml(com)}</span>`;
    else if (kw) out += `<span class="tok-kw">${escapeHtml(kw)}</span>`;
    else if (num) out += `<span class="tok-num">${escapeHtml(num)}</span>`;
    else out += escapeHtml(m);
    last = offset + m.length;
    return m;
  });
  out += escapeHtml(code.slice(last));
  return out;
}
const C_LANGS = /^(java|c|cpp|c\+\+|cs|csharp|js|javascript|ts|typescript|go|golang|kotlin|kt|rust|rs|swift|scala)$/;

let _mermaidSeq = 0;

function renderCodeBlock(lang, code, opts) {
  // `opts.gutter` adds a left line-number column. It's opt-in (full-code viewer + modal
  // only) so inline answer snippets and tool-card bodies stay clean and unchanged.
  opts = opts || {};
  // Strip the " copy" suffix that Next.js-style docs use (```py copy) — we
  // handle copying ourselves; the word is meaningless as a language tag.
  const language = (lang || "").toLowerCase().replace(/\s+copy\s*$/, "").trim();
  // Mermaid -> a placeholder rendered into SVG after the text settles.
  if (language === "mermaid") {
    const raw = btoa(unescape(encodeURIComponent(code.replace(/\n$/, ""))));
    return `<div class="mermaid-block" data-code="${raw}" data-id="mmd-${_mermaidSeq++}"><pre class="mermaid-src">${escapeHtml(code.replace(/\n$/, ""))}</pre></div>`;
  }
  // The highlighters tokenize raw source and escape each segment themselves; the
  // plain (untinted) path escapes here. Only tint blocks the model explicitly tagged
  // python/C-family — so a bare ```...``` ASCII trace isn't sprayed with random colors.
  const clean = code.replace(/\n$/, "");
  const isPy = /^(py|python)$/.test(language);
  const body = isPy ? highlightPy(clean) : (C_LANGS.test(language) ? highlightC(clean) : escapeHtml(clean));
  // Suppress the language chip for plain/untagged/copy-only blocks.
  const label = /^(copy|text|plain|txt)$/.test(language) ? "" : language;
  const raw = btoa(unescape(encodeURIComponent(code.replace(/\n$/, ""))));
  let inner = `<pre><code>${body}</code></pre>`;
  if (opts.gutter) {
    const n = clean.split("\n").length;
    let nums = "";
    for (let i = 1; i <= n; i++) nums += i + "\n";
    inner = `<div class="code-rows"><span class="code-gutter" aria-hidden="true">${nums}</span>${inner}</div>`;
  }
  return (
    `<div class="code-block${opts.gutter ? " has-gutter" : ""}"><div class="code-bar">` +
    `<span class="code-lang">${escapeHtml(label)}</span>` +
    `<button class="copy-btn" data-raw="${raw}" type="button">copy</button></div>` +
    inner + `</div>`
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

// Lead-emoji -> blockquote modifier class. Covers all emojis used in HLD/LLD prompts.
// Uses startsWith so multi-codepoint variants (e.g. ↔️ = ↔ + U+FE0F) match naturally.
function markerClass(s) {
  const t = s.trimStart();
  if (t.startsWith("💬")) return "talk";
  if (t.startsWith("🎙")) return "script";
  if (t.startsWith("🤝")) return "check";
  if (t.startsWith("🆘")) return "sos";
  if (t.startsWith("🧠")) return "ask";
  if (t.startsWith("⚠"))  return "trap";
  if (t.startsWith("🗣"))  return "voice";
  if (t.startsWith("⚡"))  return "hard";
  if (t.startsWith("💥"))  return "warn";
  if (t.startsWith("↔"))  return "fork";
  if (t.startsWith("↩"))  return "prev";
  if (t.startsWith("🔢")) return "math";
  if (t.startsWith("✅")) return "ok";
  if (t.startsWith("🔁")) return "upgrade";
  if (t.startsWith("🔀")) return "tradeoff";
  return "";
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
  const work = src.replace(/```([\w]+(?:\s+copy)?)?\s*\n?([\s\S]*?)```/g, (m, lang, code) => {
    blocks.push(renderCodeBlock(lang, code));
    return `  BLOCK${blocks.length - 1}  `;
  });

  // Pre-unwrap bold-wrapped headings (**#### Bad: ...**) BEFORE dehyphenated runs,
  // so the dehyphenated step doesn't split the ** from the #### and leave orphan ** paragraphs.
  const preUnwrapped = work.replace(/^\*\*(#{1,4}\s[\s\S]*?)\*\*\s*$/mg, "$1");

  // split headers glued onto the end of a line (e.g. "…numbers)### Key numbers").
  // The preceding char must be non-space AND non-'#' so real line-start headers
  // (## / ### / ####) are never split.
  const dehyphenated = preUnwrapped.replace(/([^\s#])(#{2,4}\s)/g, "$1\n$2");
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

    // Strip orphan leading "** " (two stars + space) — not valid Markdown bold.
    // The model emits this for "spoken" text: ** "I'd start with..."
    line = line.replace(/^\*\*\s+/, "");

    // Horizontal rule: --- or *** or ___ alone on a line.
    if (/^(\*{3,}|-{3,}|_{3,})\s*$/.test(line.trim())) {
      flushPara(); closeList(); closeTier();
      html += "<hr>";
      continue;
    }

    // Skip lone language/copy tokens the model places before a code fence
    // (e.g. "py" then "```python ...") — only when the next non-blank line
    // is a code block placeholder so we never eat real single-word paragraphs.
    if (/^(copy|py|js|ts|python|java|go|rust|c|cpp|cs|text|plain|txt|bash|shell|sh)$/.test(line.trim())) {
      let j = i + 1;
      while (j < lines.length && lines[j].trim() === "") j++;
      if (j < lines.length && /^ \x00BLOCK\d+\x00 $/.test(lines[j])) { i = j - 1; continue; }
    }

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
      const bqContent = bq[1];

      // "> | header |" followed by "> |---|" — a table embedded in a blockquote context.
      // Strip the leading "> " from each row and render as a normal table.
      if (bqContent.includes("|") && i + 1 < lines.length) {
        const nextBq = lines[i + 1].match(/^>\s?(.*)$/);
        if (nextBq && isTableSep(nextBq[1])) {
          const tableLines = [bqContent];
          let j = i + 1;
          while (j < lines.length) {
            const nb = lines[j].match(/^>\s?(.*)$/);
            if (nb && nb[1].trim().startsWith("|")) { tableLines.push(nb[1]); j++; }
            else break;
          }
          html += renderTable(tableLines);
          i = j - 1;
          continue;
        }
      }

      // "> - item" inside a blockquote: render as a styled list item, not plain "- text".
      const bqLi = bqContent.match(/^[-*]\s+(.*)$/);
      if (bqLi) {
        html += `<li class="bq-li">${inlineMd(escapeHtml(bqLi[1]))}</li>`;
      } else {
        html += `<blockquote class="${markerClass(bqContent)}">${inlineMd(escapeHtml(bqContent))}</blockquote>`;
      }
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
        // Strip orphan leading ** the model emits for emphasis in spoken text.
        parts.push(nx.trim().replace(/^\*\*\s*/, ""));
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
    // read first is visible) rather than centering it half-off-screen, and offer a
    // "fit" toggle that scales the whole diagram down to the column width.
    requestAnimationFrame(() => {
      if (el.scrollWidth > el.clientWidth + 4) {
        el.classList.add("mmd-wide");
        if (!el.querySelector(".mmd-fit-btn")) {
          const btn = document.createElement("button");
          btn.className = "mmd-fit-btn";
          btn.type = "button";
          btn.textContent = "⤢ fit";
          btn.title = "Toggle fit-to-width";
          btn.addEventListener("click", (e) => {
            e.stopPropagation(); // don't trigger the click-to-zoom on the block
            const fit = el.classList.toggle("mmd-fit");
            btn.textContent = fit ? "↔ actual size" : "⤢ fit";
          });
          el.appendChild(btn);
        }
      }
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
    // cloneNode(true) copies inline styles set by _onMermaidRendered (maxWidth:"none").
    // Clear that so CSS max-width:calc(100vw - 48px) can scale the SVG to fit the viewport.
    clone.removeAttribute("width");
    clone.style.maxWidth = "";
    // Always start the zoom view from the left edge (the start of the diagram),
    // not the center — wide diagrams were opening with the beginning off-screen.
    clone.style.alignSelf = "flex-start";
    overlay.appendChild(clone);
    const hint = document.createElement("div");
    hint.className = "mermaid-zoom-hint";
    hint.textContent = "drag to pan · tap to close · Esc to close";
    overlay.appendChild(hint);

    const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (ev) => { if (ev.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);

    // Drag-to-pan: track mouse movement; only fire close() on a genuine tap (< 6px travel).
    let dragStartX = 0, dragStartY = 0, scrollStartX = 0, scrollStartY = 0, didDrag = false;
    overlay.addEventListener("mousedown", (ev) => {
      dragStartX = ev.clientX; dragStartY = ev.clientY;
      scrollStartX = overlay.scrollLeft; scrollStartY = overlay.scrollTop;
      didDrag = false;
      overlay.classList.add("is-dragging");
      ev.preventDefault();
    });
    overlay.addEventListener("mousemove", (ev) => {
      if (!overlay.classList.contains("is-dragging")) return;
      const dx = ev.clientX - dragStartX;
      const dy = ev.clientY - dragStartY;
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) didDrag = true;
      overlay.scrollLeft = scrollStartX - dx;
      overlay.scrollTop  = scrollStartY - dy;
    });
    overlay.addEventListener("mouseup", () => {
      overlay.classList.remove("is-dragging");
      if (!didDrag) close();
    });
    overlay.addEventListener("mouseleave", () => overlay.classList.remove("is-dragging"));

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
