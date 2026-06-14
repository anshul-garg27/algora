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

