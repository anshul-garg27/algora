import json, os
BASE = "/Users/anshullkgarg/Desktop/projects/claude-gpt/uber-interviews"
data = json.load(open(os.path.join(BASE, "data.json")))
data_js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Uber Interview Question Bank — EngineBogie</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<style>
:root{
  --ink:#0c0c0d; --ink-2:#3a3a3e; --ink-3:#6b6b72;
  --paper:#f4f3ef; --surface:#ffffff; --line:#e4e2db; --line-2:#d6d4cc;
  --accent:#0a0a0a; --signal:#1769ff;
  --easy-bg:#e7f4ec; --easy-fg:#1f7a4d;
  --med-bg:#fbf0db; --med-fg:#9a6700;
  --hard-bg:#fbe6e4; --hard-fg:#b42318;
  --shadow:0 1px 2px rgba(12,12,13,.05),0 8px 24px -16px rgba(12,12,13,.25);
  --radius:14px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:Inter,system-ui,-apple-system,sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
a{color:inherit}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}

/* ---------- Masthead ---------- */
.mast{background:var(--ink);color:#fff;padding:40px 0 34px;border-bottom:3px solid #000}
.mast .wrap{display:flex;flex-direction:column;gap:18px}
.brandrow{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.logo{font-family:"Space Grotesk",sans-serif;font-weight:700;font-size:13px;letter-spacing:.18em;
  text-transform:uppercase;border:1px solid rgba(255,255,255,.35);padding:5px 11px;border-radius:6px}
.src{font-size:12.5px;color:rgba(255,255,255,.6);letter-spacing:.02em}
h1{font-family:"Space Grotesk",sans-serif;font-weight:700;letter-spacing:-.02em;
  font-size:clamp(2.1rem,1.2rem+3.4vw,3.6rem);line-height:1.02;margin:0}
h1 .u{color:#fff}
h1 .q{color:#8b8b93}
.subtitle{color:rgba(255,255,255,.66);max-width:60ch;font-size:15.5px;margin:0}
.statstrip{display:flex;gap:30px;flex-wrap:wrap;margin-top:6px}
.stat{display:flex;flex-direction:column;gap:1px}
.stat b{font-family:"Space Grotesk",sans-serif;font-size:28px;font-weight:700;line-height:1}
.stat span{font-size:11.5px;text-transform:uppercase;letter-spacing:.13em;color:rgba(255,255,255,.55)}

/* ---------- Controls ---------- */
.controls{position:sticky;top:0;z-index:30;background:rgba(244,243,239,.86);
  backdrop-filter:saturate(140%) blur(10px);border-bottom:1px solid var(--line-2);padding:14px 0}
.ctrl-grid{display:flex;flex-wrap:wrap;gap:14px 22px;align-items:flex-end}
.field{display:flex;flex-direction:column;gap:6px}
.field>label{font-size:10.5px;text-transform:uppercase;letter-spacing:.13em;color:var(--ink-3);font-weight:600}
.search{flex:1 1 240px;min-width:200px}
.search input{width:100%;border:1px solid var(--line-2);background:var(--surface);border-radius:10px;
  padding:10px 12px;font:inherit;font-size:14px;color:var(--ink)}
.search input:focus{outline:none;border-color:var(--ink);box-shadow:0 0 0 3px rgba(12,12,13,.08)}
.segwrap{display:flex;gap:0;border:1px solid var(--line-2);border-radius:10px;overflow:hidden;background:var(--surface)}
.seg{appearance:none;border:0;background:transparent;font:inherit;font-size:13px;font-weight:500;
  padding:9px 13px;cursor:pointer;color:var(--ink-2);border-right:1px solid var(--line)}
.seg:last-child{border-right:0}
.seg.active{background:var(--ink);color:#fff;font-weight:600}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{appearance:none;border:1px solid var(--line-2);background:var(--surface);border-radius:999px;
  padding:6px 12px;font:inherit;font-size:12.5px;cursor:pointer;color:var(--ink-2);display:inline-flex;gap:6px;align-items:center}
.chip:hover{border-color:var(--ink-3)}
.chip.active{background:var(--ink);color:#fff;border-color:var(--ink)}
.chip .c{opacity:.6;font-variant-numeric:tabular-nums}
.chip.df-EASY.active{background:var(--easy-fg);border-color:var(--easy-fg)}
.chip.df-MEDIUM.active{background:var(--med-fg);border-color:var(--med-fg)}
.chip.df-HARD.active{background:var(--hard-fg);border-color:var(--hard-fg)}
.ctrl-actions{display:flex;gap:10px;align-items:center;margin-left:auto}
.txtbtn{appearance:none;background:none;border:0;font:inherit;font-size:12.5px;color:var(--signal);cursor:pointer;font-weight:600}
.txtbtn:hover{text-decoration:underline}
.filterbtn{appearance:none;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;
  border:1px solid var(--line-2);background:var(--surface);color:var(--ink-2);
  border-radius:10px;padding:8px 14px;transition:all .12s ease}
.filterbtn:hover{border-color:var(--ink);color:var(--ink)}
.filterbtn.has-active{background:var(--ink);color:#fff;border-color:var(--ink)}
.filterpanel{display:none}
.controls.filters-open .filterpanel{display:block}
.resultline{font-size:12.5px;color:var(--ink-3);padding:10px 0 0}
.jumpnav{display:flex;align-items:center;gap:8px;overflow-x:auto;padding:11px 0 3px;margin-top:8px;
  border-top:1px dashed var(--line-2);scrollbar-width:thin}
.jumpnav .jl{flex:none;font-size:10.5px;text-transform:uppercase;letter-spacing:.13em;color:var(--ink-3);
  font-weight:700;margin-right:2px}
.jumpnav button{flex:none;appearance:none;cursor:pointer;font:inherit;font-size:12.5px;font-weight:600;
  color:var(--ink-2);border:1px solid var(--line-2);background:var(--surface);border-radius:999px;
  padding:6px 13px;white-space:nowrap;transition:all .12s ease}
.jumpnav button:hover{border-color:var(--ink);color:var(--ink);transform:translateY(-1px)}
.jumpnav button.cur{background:var(--ink);color:#fff;border-color:var(--ink)}
.jumpnav button .c{opacity:.55;font-weight:500;margin-left:5px;font-variant-numeric:tabular-nums}
.jumpnav button.cur .c{opacity:.7}
.group{scroll-margin-top:20px}

/* ---------- Groups ---------- */
main{padding:26px 0 90px}
.group{margin-bottom:40px}
.group-head{display:flex;align-items:baseline;gap:14px;margin:0 0 16px;padding-bottom:10px;
  border-bottom:2px solid var(--ink)}
.group-num{font-family:"Space Grotesk",sans-serif;font-weight:700;font-size:13px;letter-spacing:.1em;
  text-transform:uppercase;background:var(--ink);color:#fff;padding:4px 10px;border-radius:6px;white-space:nowrap}
.group-title{font-family:"Space Grotesk",sans-serif;font-weight:600;font-size:20px;letter-spacing:-.01em;margin:0}
.group-count{font-size:13px;color:var(--ink-3);margin-left:auto;font-variant-numeric:tabular-nums}

/* ---------- Cards ---------- */
.cards{display:grid;grid-template-columns:1fr;gap:13px}
.card{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--line-2);
  border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;transition:transform .12s ease,box-shadow .12s ease}
.card:hover{transform:translateY(-2px);box-shadow:0 2px 4px rgba(12,12,13,.06),0 18px 40px -22px rgba(12,12,13,.4)}
.card.d-EASY{border-left-color:var(--easy-fg)}
.card.d-MEDIUM{border-left-color:var(--med-fg)}
.card.d-HARD{border-left-color:var(--hard-fg)}
.card-main{padding:15px 17px}
.card-top{display:flex;align-items:flex-start;gap:12px}
.qtitle{font-family:"Space Grotesk",sans-serif;font-weight:600;font-size:16.5px;letter-spacing:-.01em;
  margin:0;flex:1;line-height:1.28}
.qtitle a{text-decoration:none}
.qtitle a:hover{text-decoration:underline;text-decoration-color:var(--line-2)}
.badge{font-size:10.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 9px;border-radius:999px;white-space:nowrap;flex-shrink:0}
.badge.EASY{background:var(--easy-bg);color:var(--easy-fg)}
.badge.MEDIUM{background:var(--med-bg);color:var(--med-fg)}
.badge.HARD{background:var(--hard-bg);color:var(--hard-fg)}
.badge.NA{background:#eee;color:#777}
.meta{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px;align-items:center}
.tag{font-size:11.5px;padding:3px 9px;border-radius:6px;border:1px solid var(--line-2);
  color:var(--ink-2);background:#fafafa;display:inline-flex;gap:5px;align-items:center;white-space:nowrap}
.tag.role{background:var(--ink);color:#fff;border-color:var(--ink);font-weight:600}
.tag.roundnum{background:var(--signal);color:#fff;border-color:var(--signal);font-weight:700;letter-spacing:.02em}
.tag.round{background:#eef3ff;border-color:#cdddff;color:#1c4ec2;font-weight:600}
.tag.cat{background:#f3eefe;border-color:#ddd0fb;color:#6b3fcf}
.tag.filt{cursor:pointer;transition:background .12s,color .12s}
.tag.cat.filt:hover{background:#e9dffb}
.tag.round.filt:hover{background:#e3ecff}
.tag.cat.on{background:#6b3fcf;color:#fff;border-color:#6b3fcf}
.tag.round.on{background:#1c4ec2;color:#fff;border-color:#1c4ec2}
.tag.src{background:#fff;border-style:dashed}
.tag.src.lc{background:#fff7ec;border-color:#f3cf9a;color:#9a5b00;border-style:solid;font-weight:600}
.card.lc{border-left-color:#ffa116}
.card.lc .badge{background:#fff3e0;color:#b26a00}
.lc-comment{background:#fbfaf7;border-color:var(--line-2);margin-bottom:10px;color:var(--ink)}
.lc-comment .statement{font-size:13.5px}
.lc-comment-by{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:var(--ink-3);margin-bottom:6px}
.markbtns{display:flex;gap:6px;flex-shrink:0}
.markbtn{appearance:none;border:1px solid var(--line-2);background:var(--surface);border-radius:7px;
  padding:4px 9px;font:inherit;font-size:11.5px;font-weight:700;color:var(--ink-3);cursor:pointer;
  transition:all .12s ease}
.markbtn:hover{border-color:var(--ink);color:var(--ink)}
.markbtn.on-done{background:var(--easy-fg);border-color:var(--easy-fg);color:#fff}
.markbtn.on-rev{background:var(--med-fg);border-color:var(--med-fg);color:#fff}
.card.p-done{opacity:.5}
.card.p-done .qtitle{text-decoration:line-through;text-decoration-color:var(--ink-3);text-decoration-thickness:1.5px}
.card.p-revisit{border-left-color:var(--med-fg)!important}
.tag .k{color:var(--ink-3);font-weight:500}
.tag.role .k{color:rgba(255,255,255,.6)}
.topics{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.topic{font-size:11px;color:var(--ink-3);background:transparent;border:1px solid var(--line);
  padding:2px 8px;border-radius:999px}
.offer{font-size:11px;font-weight:600}
.offer.yes{color:var(--easy-fg)} .offer.no{color:var(--ink-3)}

.expandbtn{appearance:none;border:0;border-top:1px solid var(--line);width:100%;text-align:left;
  background:#fbfbfa;font:inherit;font-size:12.5px;font-weight:600;color:var(--ink-2);
  padding:9px 17px;cursor:pointer;display:flex;align-items:center;gap:8px}
.expandbtn:hover{background:#f5f5f3;color:var(--ink)}
.expandbtn .chev{transition:transform .15s ease;display:inline-block}
.card.open .expandbtn .chev{transform:rotate(90deg)}
.detail{display:none;padding:4px 18px 20px;border-top:1px solid var(--line);background:#fcfcfb}
.card.open .detail{display:block}
.detail h6{font-size:10.5px;text-transform:uppercase;letter-spacing:.13em;color:var(--ink-3);
  margin:18px 0 8px;font-weight:700}
.statement{font-size:14px;line-height:1.62;color:var(--ink)}
.statement p{margin:.5em 0}
.statement pre{background:#0c0c0d;color:#f4f3ef;padding:13px 15px;border-radius:10px;overflow:auto;
  font-family:"JetBrains Mono",monospace;font-size:12.5px;line-height:1.5}
.statement code{font-family:"JetBrains Mono",monospace;font-size:12.5px;background:#efeee9;
  padding:1px 5px;border-radius:5px}
.statement pre code{background:none;padding:0}
.statement h1,.statement h2,.statement h3,.statement h4,.statement h5,.statement h6{
  font-family:"Space Grotesk",sans-serif;font-size:13px;margin:16px 0 6px;font-weight:600}
.statement ul,.statement ol{margin:.4em 0;padding-left:1.3em}
.statement table{border-collapse:collapse;margin:.6em 0}
.statement th,.statement td{border:1px solid var(--line-2);padding:5px 10px;font-size:13px}
.ansbox{background:#f0f6f1;border:1px solid #d2e7d8;border-radius:10px;padding:12px 14px;
  font-size:13.5px;line-height:1.55;color:#23402c}
.detaillinks{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;font-size:12.5px}
.detaillinks a{color:var(--signal);font-weight:600;text-decoration:none}
.detaillinks a:hover{text-decoration:underline}

.empty{text-align:center;padding:70px 20px;color:var(--ink-3)}
.empty b{font-family:"Space Grotesk",sans-serif;color:var(--ink);font-size:18px;display:block;margin-bottom:6px}

footer{border-top:1px solid var(--line-2);padding:26px 0 50px;color:var(--ink-3);font-size:12.5px}
footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
.kbd{font-family:"JetBrains Mono",monospace;font-size:11px;background:#fff;border:1px solid var(--line-2);
  border-bottom-width:2px;border-radius:5px;padding:1px 6px}
@media (max-width:640px){
  .wrap{padding:0 16px}
  .ctrl-actions{margin-left:0;width:100%}
  .statstrip{gap:22px}
}
</style>
</head>
<body>
<header class="mast">
  <div class="wrap">
    <div class="brandrow">
      <span class="logo">Uber</span>
      <span class="src">Interview intelligence · enginebogie.com + leetcode.com/discuss · generated __GEN__</span>
    </div>
    <h1><span class="u">Uber</span> <span class="q">Interview Question Bank</span></h1>
    <p class="subtitle">Every coding, design, and behavioral question pulled from real Uber interview
      experiences on EngineBogie and LeetCode Discuss — organised by round, tagged by role,
      difficulty, and topic, with top community answers inline.</p>
    <div class="statstrip" id="statstrip"></div>
  </div>
</header>

<div class="controls">
  <div class="wrap">
    <div class="ctrl-grid">
      <div class="field search">
        <label for="q">Search</label>
        <input id="q" type="search" placeholder="Search title, statement, topic, role…" autocomplete="off"/>
      </div>
      <div class="field">
        <label>Group by</label>
        <div class="segwrap" id="groupseg"></div>
      </div>
      <div class="field">
        <label>Sort</label>
        <div class="segwrap" id="sortseg"></div>
      </div>
      <div class="ctrl-actions">
        <button class="filterbtn" id="filterToggle">Filters ▾</button>
        <button class="txtbtn" id="expandAll">Expand all</button>
        <button class="txtbtn" id="collapseAll">Collapse all</button>
      </div>
    </div>
    <div id="filterpanel" class="filterpanel">
      <div class="ctrl-grid" style="margin-top:12px">
        <div class="field">
          <label>Difficulty</label>
          <div class="chips" id="diffchips"></div>
        </div>
        <div class="field">
          <label>Source</label>
          <div class="chips" id="srcchips"></div>
        </div>
        <div class="field">
          <label>Progress</label>
          <div class="chips" id="progchips"></div>
        </div>
      </div>
      <div class="ctrl-grid" style="margin-top:12px">
        <div class="field" style="flex:1 1 100%">
          <label>Round type</label>
          <div class="chips" id="catchips"></div>
        </div>
      </div>
      <div class="ctrl-grid" style="margin-top:12px">
        <div class="field" style="flex:1 1 100%">
          <label>Role</label>
          <div class="chips" id="rolechips"></div>
        </div>
      </div>
    </div>
    <div class="resultline" id="resultline"></div>
    <nav class="jumpnav" id="jumpnav"></nav>
  </div>
</div>

<main><div class="wrap" id="content"></div></main>

<footer><div class="wrap">
  <span>Uber interview dossier · <b id="fcount"></b> questions across <b id="ecount"></b> experiences</span>
  <span>Tip: click a card footer to expand · press <span class="kbd">/</span> to search</span>
</div></footer>

<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<script>
const DATA = __DATA__;
const Q = DATA.questions;
const DIFF_ORDER = {HARD:0, MEDIUM:1, EASY:2, NA:3};
const state = { group:"category", sort:"diff", search:"", diffs:new Set(), roles:new Set(), cats:new Set(), rnames:new Set(), sources:new Set(), progress:new Set(), onlyGroup:null };

/* ---- progress tracking (localStorage) ---- */
const PROG_KEY = 'uberbank-progress';
let progress = {};
try{ progress = JSON.parse(localStorage.getItem(PROG_KEY) || '{}'); }catch(e){ progress = {}; }
function saveProgress(){ try{ localStorage.setItem(PROG_KEY, JSON.stringify(progress)); }catch(e){} }
function doneCount(){ return Q.filter(q=>progress[q.qid]==='done').length; }
const SRC_LABEL = {enginebogie:"EngineBogie", leetcode:"LeetCode Discuss"};

/* ---- stat strip ---- */
(function(){
  const s = DATA.stats;
  const roles = new Set(Q.map(q=>q.role)).size;
  const el = document.getElementById('statstrip');
  const items = [[s.experiences,'Experiences'],[s.questions,'Questions'],
    [s.rounds,'Rounds'],[s.leetcodePosts||0,'LeetCode posts'],[roles,'Distinct roles']];
  el.innerHTML = items.map(([n,l])=>`<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('')
    + `<div class="stat"><b id="donestat">${doneCount()}</b><span>Done</span></div>`;
  document.getElementById('fcount').textContent = s.questions;
  document.getElementById('ecount').textContent = s.experiences;
})();

/* ---- build controls ---- */
const GROUPS = [["round","Round"],["category","Round type"],["role","Role"],["difficulty","Difficulty"]];
document.getElementById('groupseg').innerHTML = GROUPS.map(([k,l])=>
  `<button class="seg ${k===state.group?'active':''}" data-g="${k}">${l}</button>`).join('');
document.querySelectorAll('#groupseg .seg').forEach(b=>b.onclick=()=>{
  state.group=b.dataset.g; state.onlyGroup=null;
  document.querySelectorAll('#groupseg .seg').forEach(x=>x.classList.toggle('active',x===b));
  render();
});

const SORTS = [["diff","Difficulty"],["new","Newest"],["votes","Most voted"]];
document.getElementById('sortseg').innerHTML = SORTS.map(([k,l])=>
  `<button class="seg ${k===state.sort?'active':''}" data-s="${k}">${l}</button>`).join('');
document.querySelectorAll('#sortseg .seg').forEach(b=>b.onclick=()=>{
  state.sort=b.dataset.s;
  document.querySelectorAll('#sortseg .seg').forEach(x=>x.classList.toggle('active',x===b));
  render();
});

function sortQs(qs){
  if(state.sort==='new') return qs.sort((a,b)=>(b.interviewDate||0)-(a.interviewDate||0));
  if(state.sort==='votes') return qs.sort((a,b)=>((b.votes||0)-(a.votes||0)) || ((b.views||0)-(a.views||0)));
  return qs.sort((a,b)=>(DIFF_ORDER[a.difficulty]-DIFF_ORDER[b.difficulty])
    || ((b.votes||0)-(a.votes||0)) || ((b.interviewDate||0)-(a.interviewDate||0)));
}

function counts(key){ const m={}; Q.forEach(q=>{m[q[key]]=(m[q[key]]||0)+1}); return m; }
const dc = counts('difficulty');
document.getElementById('diffchips').innerHTML = ['HARD','MEDIUM','EASY'].filter(d=>dc[d]).map(d=>
  `<button class="chip df-${d}" data-d="${d}">${d[0]+d.slice(1).toLowerCase()} <span class="c">${dc[d]||0}</span></button>`).join('');
document.querySelectorAll('#diffchips .chip').forEach(b=>b.onclick=()=>{
  const d=b.dataset.d; state.diffs.has(d)?state.diffs.delete(d):state.diffs.add(d);
  b.classList.toggle('active'); render();
});

function renderProgChips(){
  const pc = {done:0, revisit:0, none:0};
  Q.forEach(q=>pc[progress[q.qid]||'none']++);
  document.getElementById('progchips').innerHTML = [['done','✓ Done'],['revisit','★ Revisit'],['none','Untouched']]
    .map(([k,l])=>`<button class="chip${state.progress.has(k)?' active':''}" data-p="${k}">${l} <span class="c">${pc[k]}</span></button>`).join('');
  document.querySelectorAll('#progchips .chip').forEach(b=>b.onclick=()=>{
    const p=b.dataset.p; state.progress.has(p)?state.progress.delete(p):state.progress.add(p);
    renderProgChips(); render();
  });
}
renderProgChips();

const sc = counts('source');
document.getElementById('srcchips').innerHTML = Object.keys(sc).map(s=>
  `<button class="chip" data-s="${s}">${SRC_LABEL[s]||s} <span class="c">${sc[s]}</span></button>`).join('');
document.querySelectorAll('#srcchips .chip').forEach(b=>b.onclick=()=>{
  const s=b.dataset.s; state.sources.has(s)?state.sources.delete(s):state.sources.add(s);
  b.classList.toggle('active'); render();
});

const rc = counts('role');
const roleSorted = Object.keys(rc).sort((a,b)=>rc[b]-rc[a]);
document.getElementById('rolechips').innerHTML = roleSorted.map(r=>
  `<button class="chip" data-r="${encodeURIComponent(r)}">${r} <span class="c">${rc[r]}</span></button>`).join('');
document.querySelectorAll('#rolechips .chip').forEach(b=>b.onclick=()=>{
  const r=decodeURIComponent(b.dataset.r); state.roles.has(r)?state.roles.delete(r):state.roles.add(r);
  b.classList.toggle('active'); render();
});

/* Round-type (category) chips, e.g. "DSA / Coding", "Machine Coding - LLD", "System Design (HLD)" */
const cc = counts('roundCategory');
const catSorted = Object.keys(cc).filter(Boolean).sort((a,b)=>cc[b]-cc[a]);
function renderCatChips(){
  document.getElementById('catchips').innerHTML = catSorted.map(c=>
    `<button class="chip${state.cats.has(c)?' active':''}" data-c="${encodeURIComponent(c)}">${c} <span class="c">${cc[c]}</span></button>`).join('');
  document.querySelectorAll('#catchips .chip').forEach(b=>b.onclick=()=>{
    const c=decodeURIComponent(b.dataset.c); state.cats.has(c)?state.cats.delete(c):state.cats.add(c);
    b.classList.toggle('active'); render();
  });
}
renderCatChips();

/* Click a round-type / round-name tag ON A CARD to toggle that filter directly. */
document.getElementById('content').addEventListener('click', (e)=>{
  const mb = e.target.closest('[data-mark]');
  if(mb){
    const qid = mb.dataset.qid, mark = mb.dataset.mark;
    if(progress[qid] === mark) delete progress[qid]; else progress[qid] = mark;
    saveProgress();
    const ds = document.getElementById('donestat');
    if(ds) ds.textContent = doneCount();
    if(state.progress.size){ renderProgChips(); render(); return; }
    // update in place (avoid collapsing open cards)
    document.querySelectorAll(`.card[data-q='${qid}']`).forEach(card=>{
      card.classList.toggle('p-done', progress[qid]==='done');
      card.classList.toggle('p-revisit', progress[qid]==='revisit');
      card.querySelectorAll('[data-mark]').forEach(b=>{
        b.classList.toggle('on-done', b.dataset.mark==='done' && progress[qid]==='done');
        b.classList.toggle('on-rev', b.dataset.mark==='revisit' && progress[qid]==='revisit');
      });
    });
    renderProgChips();
    return;
  }
  const fc = e.target.closest('[data-fc]');
  if(fc){ e.preventDefault();
    const c=decodeURIComponent(fc.dataset.fc); state.cats.has(c)?state.cats.delete(c):state.cats.add(c);
    renderCatChips(); render(); return; }
  const fr = e.target.closest('[data-fr]');
  if(fr){ e.preventDefault();
    const r=decodeURIComponent(fr.dataset.fr); state.rnames.has(r)?state.rnames.delete(r):state.rnames.add(r);
    render(); return; }
});

const filterBtn = document.getElementById('filterToggle');
const controlsEl = document.querySelector('.controls');
filterBtn.onclick = ()=>{ controlsEl.classList.toggle('filters-open'); updateFilterBtn(); };
function activeFilterCount(){
  return state.diffs.size + state.roles.size + state.cats.size + state.rnames.size + state.sources.size + state.progress.size;
}
function updateFilterBtn(){
  const n = activeFilterCount();
  const open = controlsEl.classList.contains('filters-open');
  filterBtn.textContent = `Filters${n?` · ${n}`:''} ${open?'▴':'▾'}`;
  filterBtn.classList.toggle('has-active', n>0);
}

const qinput = document.getElementById('q');
qinput.addEventListener('input', ()=>{ state.search=qinput.value.toLowerCase().trim(); render(); });
document.addEventListener('keydown', e=>{
  if(e.key==='/' && document.activeElement!==qinput){ e.preventDefault(); qinput.focus(); }
});
document.getElementById('expandAll').onclick=()=>document.querySelectorAll('.card').forEach(openCard);
document.getElementById('collapseAll').onclick=()=>document.querySelectorAll('.card.open').forEach(c=>c.classList.remove('open'));

/* ---- filtering ---- */
function passes(q){
  if(state.progress.size && !state.progress.has(progress[q.qid]||'none')) return false;
  if(state.sources.size && !state.sources.has(q.source)) return false;
  if(state.diffs.size && !state.diffs.has(q.difficulty)) return false;
  if(state.roles.size && !state.roles.has(q.role)) return false;
  if(state.cats.size && !state.cats.has(q.roundCategory)) return false;
  if(state.rnames.size && !state.rnames.has(q.roundName)) return false;
  if(state.search){
    const hay=(q.title+' '+q.statement+' '+q.topics.join(' ')+' '+q.role+' '+(q.roleRaw||'')+' '+(q.roundName||'')).toLowerCase();
    if(!hay.includes(state.search)) return false;
  }
  return true;
}

/* ---- grouping ---- */
function groupKey(q){
  if(state.group==='round') return 'Round '+(q.roundNumber ?? '—');
  if(state.group==='category') return q.roundCategory;
  if(state.group==='role') return q.role;
  if(state.group==='difficulty') return q.difficulty;
}
function groupOrder(keys){
  if(state.group==='round') return keys.sort((a,b)=>(parseInt(a.split(' ')[1])||99)-(parseInt(b.split(' ')[1])||99));
  if(state.group==='difficulty') return keys.sort((a,b)=>DIFF_ORDER[a]-DIFF_ORDER[b]);
  return keys.sort((a,b)=>byCount[b]-byCount[a]);
}
let byCount={};

/* ---- render helpers ---- */
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
const fmtDate = ts => ts ? new Date(ts).toLocaleDateString('en-IN',{month:'short',year:'numeric'}) : null;

function cardHTML(q){
  const dd = fmtDate(q.interviewDate);
  const isLC = q.source==='leetcode';
  const topics = q.topics.slice(0,8).map(t=>`<span class="topic">${esc(t)}</span>`).join('');
  const offer = q.receivedOffer===true ? '<span class="offer yes">● offer</span>'
              : q.receivedOffer===false ? '<span class="offer no">○ no offer</span>' : '';
  const rnum = q.roundNumber!=null ? `<span class="tag roundnum">Round ${q.roundNumber}</span>` : '';
  const rnLabel = q.roundName||q.roundCategory;
  const rn = (rnLabel && !isLC) ? `<span class="tag round filt${state.rnames.has(rnLabel)?' on':''}" data-fr="${encodeURIComponent(rnLabel)}" title="Filter by this round">${esc(rnLabel)}</span>` : '';
  const srcTag = isLC
    ? `<span class="tag src lc"><span class="k">LeetCode</span>${dd?' '+dd:''}</span>
       <span class="tag"><span class="k">▲</span> ${q.votes||0} <span class="k">·</span> ${q.views||0} <span class="k">views</span>${q.commentCount?` <span class="k">·</span> ${q.commentCount} <span class="k">cmts</span>`:''}</span>`
    : `<span class="tag src"><span class="k">exp</span> #${q.expId}${dd?' · '+dd:''}</span>`;
  const nComments = (q.comments||[]).length;
  const expandLabel = isLC
    ? `View post${nComments?` & ${nComments} top answer${nComments>1?'s':''}`:''}`
    : `View problem statement${q.answerSummary?' & approach':''}`;
  const pmark = progress[q.qid] || '';
  return `<article class="card d-${q.difficulty}${isLC?' lc':''}${pmark?' p-'+pmark:''}" data-q='${q.qid}'>
    <div class="card-main">
      <div class="card-top">
        <h3 class="qtitle">${q.qurl?`<a href="${q.qurl}" target="_blank" rel="noopener">${esc(q.title)}</a>`:esc(q.title)}</h3>
        <div class="markbtns">
          <button class="markbtn${pmark==='done'?' on-done':''}" data-mark="done" data-qid="${q.qid}" title="Mark as done">✓</button>
          <button class="markbtn${pmark==='revisit'?' on-rev':''}" data-mark="revisit" data-qid="${q.qid}" title="Mark to revisit">★</button>
        </div>
        <span class="badge ${q.difficulty}">${isLC?'LC':q.difficulty}</span>
      </div>
      <div class="meta">
        <span class="tag role"><span class="k">role</span> ${esc(q.role)}</span>
        ${rnum}
        ${rn}
        <span class="tag cat filt${state.cats.has(q.roundCategory)?' on':''}" data-fc="${encodeURIComponent(q.roundCategory)}" title="Filter by this round type">${esc(q.roundCategory)}</span>
        ${srcTag}
        ${offer}
      </div>
      ${topics?`<div class="topics">${topics}</div>`:''}
    </div>
    <button class="expandbtn"><span class="chev">▸</span> ${expandLabel}</button>
    <div class="detail" data-raw="0"></div>
  </article>`;
}

function render(){
  updateFilterBtn();
  const filtered = Q.filter(passes);
  byCount={}; filtered.forEach(q=>{const k=groupKey(q);byCount[k]=(byCount[k]||0)+1;});
  const groups={}; filtered.forEach(q=>{(groups[groupKey(q)] ||= []).push(q);});
  const allKeys = groupOrder(Object.keys(groups));
  // if the isolated group no longer exists after other filters, drop it
  if(state.onlyGroup && !groups[state.onlyGroup]) state.onlyGroup=null;
  const keys = state.onlyGroup ? [state.onlyGroup] : allKeys;
  const cont = document.getElementById('content');

  const shown = state.onlyGroup ? groups[state.onlyGroup].length : filtered.length;
  const hasFilter = state.diffs.size||state.roles.size||state.cats.size||state.rnames.size||state.search||state.onlyGroup;
  document.getElementById('resultline').innerHTML =
    `Showing <b>${shown}</b> of ${Q.length} questions`
    + (state.onlyGroup? ` · <b>${esc(groupLabel(state.onlyGroup).title)}</b> only`:'')
    + (hasFilter? ` · <span style="color:var(--signal);cursor:pointer" id="clearf">clear filters</span>`:'');

  if(!filtered.length){
    cont.innerHTML = `<div class="empty"><b>No questions match.</b>Try clearing a filter or searching something broader.</div>`;
    document.getElementById('jumpnav').innerHTML=''; wireClear(); return;
  }
  cont.innerHTML = keys.map((k,i)=>{
    const qs = sortQs(groups[k]);
    const label = groupLabel(k);
    return `<section class="group" id="grp${i}">
      <div class="group-head">
        <span class="group-num">${label.num}</span>
        <h2 class="group-title">${esc(label.title)}</h2>
        <span class="group-count">${qs.length} question${qs.length>1?'s':''}</span>
      </div>
      <div class="cards">${qs.map(cardHTML).join('')}</div>
    </section>`;
  }).join('');
  buildNav(allKeys, groups, filtered.length);
  wireCards(); wireClear();
}

/* round nav now FILTERS to a single group (others removed); "All" restores everything */
function buildNav(keys, groups, totalShown){
  const nav = document.getElementById('jumpnav');
  if(keys.length<2 && !state.onlyGroup){ nav.innerHTML=''; return; }
  const lbl = state.group==='round' ? 'Show round' : 'Show only';
  let html = `<span class="jl">${lbl}</span>`;
  html += `<button data-k="" class="${!state.onlyGroup?'cur':''}">All<span class="c">${totalShown}</span></button>`;
  html += keys.map(k=>{
    const t = groupLabel(k).title;
    return `<button data-k="${encodeURIComponent(k)}" class="${state.onlyGroup===k?'cur':''}">${esc(t)}<span class="c">${groups[k].length}</span></button>`;
  }).join('');
  nav.innerHTML = html;
  nav.querySelectorAll('button').forEach(b=>b.onclick=()=>{
    const k = decodeURIComponent(b.dataset.k||'');
    state.onlyGroup = (!k || state.onlyGroup===k) ? null : k;  // click active round again -> back to All
    render();
    scrollToContentTop();
  });
}
function scrollToContentTop(){
  const c=document.getElementById('content');
  const off=document.querySelector('.controls').offsetHeight + 8;
  const y=c.getBoundingClientRect().top + window.scrollY - off;
  if(window.scrollY > y) window.scrollTo({top:Math.max(0,y), behavior:'auto'});
}

function groupLabel(k){
  if(state.group==='round'){ const n=k.split(' ')[1]; return {num:'Round', title:'Round '+n}; }
  if(state.group==='difficulty') return {num:'Level', title:k[0]+k.slice(1).toLowerCase()};
  if(state.group==='role') return {num:'Role', title:k};
  return {num:'Type', title:k};
}

function wireClear(){
  const c=document.getElementById('clearf');
  if(c) c.onclick=()=>{
    state.diffs.clear(); state.roles.clear(); state.cats.clear(); state.rnames.clear(); state.sources.clear(); state.progress.clear(); state.search=''; state.onlyGroup=null; qinputReset();
    document.querySelectorAll('.chip.active').forEach(x=>x.classList.remove('active')); renderCatChips(); renderProgChips(); render();
  };
}
function qinputReset(){ qinput && (document.getElementById('q').value=''); }

function wireCards(){
  document.querySelectorAll('.card').forEach(card=>{
    card.querySelector('.expandbtn').onclick=()=>{
      card.classList.toggle('open');
      if(card.classList.contains('open')) fillDetail(card);
    };
  });
}
function openCard(card){ card.classList.add('open'); fillDetail(card); }

function fillDetail(card){
  const box=card.querySelector('.detail');
  if(box.dataset.raw==='1') return;
  const qid=card.getAttribute('data-q');
  const q=Q.find(x=>String(x.qid)===String(qid));
  let html='';
  if(q.statement){
    let md=q.statement;
    try{ md = marked.parse(esc(q.statement)); }catch(e){ md='<pre>'+esc(q.statement)+'</pre>'; }
    html+=`<h6>${q.source==='leetcode'?'Post':'Problem statement'}</h6><div class="statement">${md}</div>`;
  }
  if(q.answerSummary){
    let a=q.answerSummary;
    try{ a=marked.parse(esc(q.answerSummary)); }catch(e){ a=esc(q.answerSummary); }
    html+=`<h6>Candidate's approach</h6><div class="ansbox">${a}</div>`;
  }
  if(q.comments && q.comments.length){
    html+=`<h6>Top community answers</h6>`;
    html+=q.comments.map(c=>{
      let body=c.content;
      try{ body=marked.parse(esc(c.content)); }catch(e){ body='<pre>'+esc(c.content)+'</pre>'; }
      return `<div class="ansbox lc-comment">
        <div class="lc-comment-by">▲ ${c.votes} · ${esc(c.author||'anonymous')}</div>
        <div class="statement">${body}</div>
      </div>`;
    }).join('');
  }
  const isLC = q.source==='leetcode';
  html+=`<div class="detaillinks">
    ${q.qurl?`<a href="${q.qurl}" target="_blank" rel="noopener">↗ ${isLC?'Post on LeetCode Discuss':'Question on EngineBogie'}</a>`:''}
    ${q.expUrl?`<a href="${q.expUrl}" target="_blank" rel="noopener">↗ Full experience #${q.expId}</a>`:''}
  </div>`;
  box.innerHTML=html; box.dataset.raw='1';
  if(window.renderMathInElement){
    try{ renderMathInElement(box,{delimiters:[
      {left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},
      {left:'\\(',right:'\\)',display:false},{left:'\\[',right:'\\]',display:true}],throwOnError:false});
    }catch(e){}
  }
}

render();
</script>
</body>
</html>
"""

html = TEMPLATE.replace("__DATA__", data_js).replace("__GEN__", data["generatedAt"])
out = os.path.join(BASE, "index.html")
with open(out, "w") as f:
    f.write(html)
print("wrote", out, "(", len(html), "bytes )")
