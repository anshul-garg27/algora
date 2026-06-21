# Q: Tell me about a time when you had to learn new skillset beyond the scope of your day to day work.

> **LP**: Learn and Be Curious
> **Primary story**: `G6 — Fake-Follower ML`
> **Backup story**: `W11 — Unified Onboarding / IAM`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2023 at Good Creator Co. My day job was backend services in Go — Event-gRPC, Coffee, SaaS Gateway. One Tuesday our product lead came to standup with a brand complaint. They couldn't trust our follower counts because too many accounts looked like bots, and they'd seen Indian-script names that our existing scoring couldn't even read. The team had no ML engineer. He looked around the room and asked who wanted to take it.

### Task

Build a fake-follower detection system for Indian Instagram influencers — outside my normal backend remit. I had no ML background, no NLP background, and no labelled training data.

### Action

I started by being honest with myself about what I didn't know. Two academic papers — one on Indian-script transliteration, one survey on fake-account detection. I read them twice. I learned that Hidden Markov Models and the Viterbi algorithm were the standard way to handle script conversion, and that supervised ML for fake detection needs thousands of labelled examples. We had zero.

That framing changed the design. I wouldn't try to train a model. I'd build an interpretable heuristic ensemble — five features each capturing one bot signal — and use a pre-trained library for the language hard part.

For transliteration, I found `indic-trans`. It had pre-trained HMMs for 9 Indic languages. Hindi needed special handling — the inherent vowel rule (`क` reads "ka" not "k"), nukta marks like `ज़` that can be one codepoint or two. I sat with a Hindi-reading colleague and we built 24 vowel and 42 consonant mappings by hand. That took two afternoons.

The 5-feature ensemble — non-Indic script regex, digit count >4, handle-name character correlation, weighted RapidFuzz similarity, and fuzzy match against a 35,183-name Indian baby-name database. I picked RapidFuzz over FuzzyWuzzy because the C++ backend was 10–50x faster — important for Lambda cold-start budgets.

Deployment was new for me too. The HMM models for 10 languages plus the name database broke through Lambda's 250MB layer limit. I learned ECR Lambda containers — Docker image, 10GB allowed, `gcc-c++` to compile the Cython Viterbi decoder. SQS for input, Kinesis for output, 8-worker multiprocessing in the push script.

### Result

The pipeline shipped on AWS Lambda in about four weeks. 50% faster processing than the previous manual approach. Output was a 0.0 / 0.33 / 1.0 confidence score — clear actions for the business team. Two things stayed with me. First — when you don't have labelled data, build something interpretable. Second — read the academic source before the blog posts. Most "fake follower" content online was English-only and useless for our problem.

---

## Technical depth — if they probe

- **HMM + Viterbi**: `indic-trans` uses Hidden Markov Models with five `.npy` files per language pair. Viterbi decoder is in Cython for speed. We did not train these — they're pre-trained academic models.
- **Why no deep learning**: no labelled dataset. Supervised models need thousands of confirmed-fake examples. Heuristics work with zero.
- **Why RapidFuzz over FuzzyWuzzy**: C++ backend, 10–50x faster. We compare against 35K names per follower across up to 24 name permutations — speed matters.
- **Lambda ECR**: 250MB layer limit was way too small. ECR allows 10GB. Cold start ~5s but acceptable for batch.

---

## Likely follow-ups

**Q: How did you decide on 5 features and not 10?**
> Each feature had to be debuggable independently. We started with 3 (script, digits, fuzzy). Added handle-name correlation when we saw bot accounts using random underscores. Added name-DB match when a brand complained about Greek-script "followers." Five was where new features stopped adding signal.

**Q: Did you ever try a supervised model later?**
> The scored outputs from v1 became the labelled training set. v2 would be a gradient-boosted classifier on the same 5 features. I left GCC before doing it, but that was the obvious next step.

**Q: Hardest bug you hit?**
> Hindi nukta. `ज़` can be one Unicode codepoint or two (`ज` + combining `़`). My `process_word` function only handled one form for two weeks. Caught it when real Pepsi campaign data came back wrong.

**Q: How did this skill help your day job later?**
> The ECR Lambda pattern came back useful when I built the Coffee API caching layer. The interpretable-ensemble mindset shaped how I designed the SaaS Gateway middleware pipeline. Cross-domain learning shows up in unexpected places.

---

## What NOT to say

- Don't claim I trained HMMs from scratch. I used pre-trained `indic-trans` models.
- Don't say I "became an ML engineer." I learned enough ML to ship a heuristic system responsibly.
- Don't oversell — the system is interpretable v1, not state-of-the-art.

---

## Backup story (if asked for another)

W11 — Apollo Federation IAM platform at Walmart. My team needed a GraphQL BFF, but nobody had federation experience. I spent two weekends learning Apollo Federation, `@key` directives, subgraph composition, and NestJS. The interesting twist was cross-domain auth — our DevX session tokens weren't valid in the Scintilla domain where backend services lived. I learned the AppToApp token pattern and used it as the SubGraph's identity for downstream calls. That work also gave me a chance to mentor a junior through it — but I had to learn it first.
