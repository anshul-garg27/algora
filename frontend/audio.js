/* ============================================================
   Voice dictation (speech-to-text) using the browser's free
   Web Speech API. Works on Chrome (desktop) and Safari (iOS 14.5+).
   Gracefully no-ops where unsupported (the mic button stays hidden).
   Exposes global: setupMic({ input, button, onText }).
   ============================================================ */

"use strict";

function setupMic({ input, button, onText }) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return; // unsupported -> leave the mic button hidden

  button.hidden = false;

  const recog = new SR();
  recog.continuous = true;
  recog.interimResults = true;
  recog.lang = "en-US";

  let listening = false;
  let baseText = "";      // input value when dictation started
  let finalText = "";     // accumulated finalized transcript this session

  function setText(extra) {
    const joined = [baseText.trim(), (finalText + extra).trim()].filter(Boolean).join(" ");
    input.value = joined;
    if (onText) onText();
  }

  recog.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i];
      if (res.isFinal) finalText += res[0].transcript + " ";
      else interim += res[0].transcript;
    }
    setText(interim);
  };

  recog.onerror = (e) => {
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      stop();
      button.title = "Microphone permission denied";
    }
  };

  // iOS Safari often ends recognition after a pause; restart while the user
  // still has dictation toggled on.
  recog.onend = () => {
    if (listening) {
      try { recog.start(); } catch { /* starting too soon; ignore */ }
    } else {
      button.classList.remove("is-recording");
    }
  };

  function start() {
    baseText = input.value;
    finalText = "";
    listening = true;
    button.classList.add("is-recording");
    button.title = "Stop dictation";
    try { recog.start(); } catch { /* already started */ }
  }

  function stop() {
    listening = false;
    button.classList.remove("is-recording");
    button.title = "Dictate by voice";
    try { recog.stop(); } catch { /* already stopped */ }
  }

  button.addEventListener("click", () => (listening ? stop() : start()));

  // Stop dictation when the user submits or the page is hidden.
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
  return { stop, isListening: () => listening };
}

/* ============================================================
   Text-to-speech (read aloud). Uses the browser's free
   speechSynthesis with the most NATURAL local voice available
   (not a robotic default). For practising what to say out loud.
   Exposes globals: ttsSupported, setupVoicePicker, speakElement, stopSpeaking.
   ============================================================ */

const ttsSupported = typeof window !== "undefined" && "speechSynthesis" in window;
let _voices = [];
let _chosenVoice = null;

// Prefer high-quality, natural English voices; avoid novelty/robotic ones.
const _GOOD = [
  "Ava", "Samantha", "Allison", "Serena", "Zoe", "Evan", "Nathan", "Tom",
  "Google US English", "Google UK English", "Microsoft Aria", "Microsoft Guy",
  "Microsoft Jenny", "Daniel", "Karen", "Moira",
];
const _BAD = /(eloquence|novelty|bells|bad news|bubbles|wobble|whisper|albert|zarvox|trinoids|cellos|organ|jester|superstar|boing|junior|ralph|fred|grandma|grandpa|rocko|shelley|sandy|flo|reed|eddy|rishi)/i;

function _rankVoice(v) {
  let score = 0;
  if (/^en[-_]US/i.test(v.lang)) score += 5;
  else if (/^en/i.test(v.lang)) score += 3;
  if (v.localService) score += 2; // local = lower latency, often higher quality
  if (/(enhanced|premium|natural|neural|siri)/i.test(v.name)) score += 6;
  if (_GOOD.some((g) => v.name.includes(g))) score += 4;
  if (_BAD.test(v.name)) score -= 10;
  return score;
}

function _loadVoices() {
  if (!ttsSupported) return [];
  _voices = (window.speechSynthesis.getVoices() || []).filter((v) => /^en/i.test(v.lang));
  _voices.sort((a, b) => _rankVoice(b) - _rankVoice(a));
  if (!_chosenVoice && _voices.length) _chosenVoice = _voices[0];
  return _voices;
}

function setupVoicePicker(wrap, select) {
  if (!ttsSupported) return;
  wrap.hidden = false;
  const fill = () => {
    _loadVoices();
    if (!_voices.length) return;
    select.innerHTML = _voices
      .map((v, i) => `<option value="${i}">${v.name.replace(/\s*\(.*?\)\s*/g, " ").trim()}</option>`)
      .join("");
    // keep the dropdown in sync with the voice that will actually be spoken
    const idx = _chosenVoice ? _voices.indexOf(_chosenVoice) : 0;
    select.value = String(idx >= 0 ? idx : 0);
  };
  fill();
  // voices often load asynchronously
  window.speechSynthesis.onvoiceschanged = fill;
  select.addEventListener("change", () => {
    const v = _voices[+select.value];
    if (v) _chosenVoice = v;
  });
}

let _activeBtn = null;
function _resetBtn(b) {
  if (b) { b.classList.remove("speaking"); b.textContent = "🔊 read aloud"; }
}

function stopSpeaking() {
  if (ttsSupported) window.speechSynthesis.cancel();
  _resetBtn(_activeBtn);
  _activeBtn = null;
}

// Collect natural, speakable text from a rendered assistant body (skips code,
// diagrams, tool output). Prefers the 💬 talking points — that's exactly what the
// candidate says out loud to the interviewer — and falls back to the full prose
// only when an answer has no talk blocks.
function _speakableText(bodyEl) {
  // 1st choice: the 🎙️ Script teleprompter blocks — the connected narration the candidate
  // actually speaks, top to bottom (the design modes' whole promise).
  const scripts = bodyEl.querySelectorAll(".prose .script-block .script-body");
  if (scripts.length) {
    const parts = [];
    scripts.forEach((s) => {
      const t = s.textContent.replace(/\s+/g, " ").trim();
      if (t) parts.push(t);
    });
    if (parts.length) return parts.join(". ");
  }
  // 2nd: the 💬 say-lines (coding/interview modes).
  const talk = bodyEl.querySelectorAll(".prose blockquote.talk");
  if (talk.length) {
    const parts = [];
    talk.forEach((q) => {
      const t = q.textContent.replace(/💬/g, " ").replace(/\s+/g, " ").trim();
      if (t) parts.push(t);
    });
    if (parts.length) return parts.join(". ");
  }
  const parts = [];
  bodyEl.querySelectorAll(".prose").forEach((prose) => {
    prose.querySelectorAll(":scope > p, :scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope li, :scope > blockquote").forEach((node) => {
      if (node.closest(".code-block, .mermaid-block")) return;
      const t = node.textContent.replace(/\s+/g, " ").trim();
      if (t) parts.push(t);
    });
  });
  return parts.join(". ");
}

// Toggle reading a message body aloud; updates the button label. Handles the
// case where another message is already being read (resets that button too).
function speakElement(bodyEl, button) {
  if (!ttsSupported) return;
  const wasSpeaking = window.speechSynthesis.speaking;
  const sameButton = _activeBtn === button;
  if (wasSpeaking) {
    window.speechSynthesis.cancel(); // resets _activeBtn via its onend, but be explicit:
    _resetBtn(_activeBtn);
    _activeBtn = null;
    if (sameButton) return; // clicking the playing button again = just stop
  }
  const text = _speakableText(bodyEl);
  if (!text) return;
  _loadVoices();
  const u = new SpeechSynthesisUtterance(text);
  if (_chosenVoice) u.voice = _chosenVoice;
  u.rate = 1.02;
  u.pitch = 1.0;
  u.onend = u.onerror = () => {
    _resetBtn(button);
    if (_activeBtn === button) _activeBtn = null;
  };
  _activeBtn = button;
  if (button) { button.classList.add("speaking"); button.textContent = "⏹ stop"; }
  window.speechSynthesis.speak(u);
}
