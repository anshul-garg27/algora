# Q: How, where, and why do you use GenAI tools in your workflow?

> **LP**: Learn and Be Curious
> **Primary story**: `G6 — Fake-Follower ML`
> **Backup story**: `W5 — Spring Boot 3 Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2023 at Good Creator Co. I was building a fake-follower detection system for Indian Instagram influencers. The hard part was language — followers have names in 10 Indic scripts: Hindi, Bengali, Tamil, Telugu, Gujarati, Kannada, Malayalam, Odia, Punjabi, Urdu. Plus English. Plus bots using Unicode tricks like math-script "𝓐𝓵𝓲𝓬𝓮" and full-width "ＲＡＨＵＬ". No labelled dataset. No off-the-shelf model.

### Task

Build a detection pipeline that handles 10 scripts and ships to AWS Lambda. Use AI tools wherever they help, but understand every line that goes into production.

### Action

I used GenAI for three things on this project.

First, Unicode regex hunting. Each Indic script lives in a different Unicode block — Devanagari is `ऀ-ॿ`, Bengali is `ঀ-৿`, Tamil is `஀-௿`, and so on. I had ChatGPT draft the regex ranges. Then I tested each against real follower data I'd already collected — Bengali names, Tamil handles, Devanagari display names. Twice the AI missed Urdu ligature characters. Once it included Burmese in the "Indic" set, which is wrong. So the workflow was: AI drafts, I verify against real data, I keep what works.

Second, the Hindi transliteration table. Hindi has 24 vowels (svar) and 42 consonants (vyanjan) plus complex conjuncts like क्ष → ksh, त्र → tr, ज्ञ → gy. I asked Claude to draft the mapping CSVs. Then I sat with a colleague who reads Hindi natively and we walked the file line by line. About 10 rows needed corrections — mostly nukta handling like ज़ being two codepoints in some inputs and one in others.

Third — and this is where I drew a line. The HMM transliteration models themselves I did not generate with AI. I used the `indic-trans` library, which has pre-trained Viterbi-decoded HMM models per language. AI was useful for explaining what the `.npy` files contained — coefficient matrices, transition probabilities — but the models were trained academically, not by Claude.

Where I refused to use AI: the 5-feature ensemble scoring logic. That was business judgement — when does a non-Indic script count as fake, when does ">4 digits in handle" count as a bot signal. Those thresholds came from looking at real follower samples and arguing with the product team. AI couldn't sit in that meeting.

### Result

The pipeline shipped on AWS Lambda with ECR containers. Processed followers 50% faster than the previous manual approach. Output was a 0.0 / 0.33 / 1.0 confidence score for each follower. The AI assists saved me about a week of regex and table work across 10 languages. What it could not do — pick thresholds, defend the design in review, debug a Hindi nukta edge case at 11pm — was still on me. That mix is how I use AI now: accelerator, not oracle.

---

## Technical depth — if they probe

- **Indic ranges**: Devanagari `ऀ-ॿ`, Bengali `ঀ-৿`, Tamil `஀-௿`, Telugu `ఀ-౿`, Kannada `ಀ-೿`, Gujarati `઀-૿`. Urdu uses Arabic block `؀-ۿ` — easy to miss if you only ask for "Indic scripts."
- **HMM transliteration**: `indictrans` library — Viterbi decoder in Cython. Five `.npy` files per language pair: coefficients, classes, initial / transition / final state probabilities, sparse feature vocab.
- **Why ensemble over deep learning**: no labelled data. A supervised model needed thousands of confirmed-fake examples. 5-feature heuristics are interpretable and ship today.
- **Where AI got it wrong**: Burmese included in "Indic set" (it's Brahmic-family but not Indic in our business sense). Nukta handling — `ज़` as one codepoint vs `ज` + `़`.

---

## Likely follow-ups

**Q: How did you validate the regex AI gave you?**
> Real data. I had a few hundred Bengali, Tamil, Devanagari follower names from our existing dataset. Any regex that didn't match those was wrong. Any that matched English was also wrong.

**Q: What about training your own ML model?**
> We had no labelled data. Now that the heuristic system has been running, we have thousands of scored records — those could be spot-checked into a training set. I'd build a gradient-boosted classifier on top of the same 5 features and keep the heuristic ensemble as the explainability fallback.

**Q: Did you ever try a pre-trained NER model for names?**
> Briefly. NER models tell you something is a name. They don't tell you if it's plausibly Indian. That's why I used a 35,183-name Indian baby-name database with fuzzy matching — it gave a real signal.

**Q: Hardest debugging moment?**
> Hindi nukta. `ज़` is one codepoint in some inputs and `ज` + combining `़` in others. My `process_word` function only handled one form for two weeks. I caught it by running real Pepsi-campaign data through the pipeline and seeing names come back wrong.

---

## What NOT to say

- Don't claim I trained the HMM models. I used a library — `indictrans` — with pre-trained academic models.
- Don't make the AI work sound bigger than it was. It was a productivity boost on regex and mapping tables, not the core ML.
- Don't pretend the 5-feature heuristic is state-of-the-art. It's a no-labelled-data first version. A supervised model is the obvious v2.

---

## Backup story (if asked for another)

Spring Boot 3 migration on cp-nrti-apis. I used Claude to script the javax → jakarta rename across 74 files, and to scaffold WebClient mocks for 42 test files. Saved me about a week of mechanical work. What I didn't use AI for was the `.block()` versus full-reactive decision — that needed a 1:1 with my team lead with my own analysis on the table. The pattern is the same in both stories: AI for mechanical scale, my own judgement for the decisions that ship.
