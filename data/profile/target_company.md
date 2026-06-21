# Target Interview — Amazon (SDE-3)

> The specific round Anshul is preparing for right now. Tilt every practice answer toward this context.

## The round
- Company: **Amazon.** Target level: **SDE-3.**
- The recruiter named the two Leadership Principles this loop will probe: **Learn and Be Curious** and **Bias for Action.** Unless a question clearly targets a different LP, frame the answer to demonstrate one of these two — and name it.

## Bias for Action — lead with these
Amazon's bar: speed matters; many decisions are reversible and don't need extensive study; value calculated risk-taking.
- **PRIMARY: W5** (Spring Boot 3 `.block()` decision). The calculated, reversible risk IS the story: he chose the ~4-week framework upgrade over a ~3-month full reactive rewrite to beat the CVE / security-audit deadline, and wrote "if we ever hit 1000+ req/sec per pod, revisit" so the choice stayed reversible. Lead with the deadline pressure and the explicit reversibility.
- **BACKUP: P1** (partner API failure 4.6% → 0.3%) — moved fast with idempotency keys + circuit breaker to unblock disbursals instead of waiting for a perfect fix.
- Phrases to use: "this was reversible, so I didn't need a long study", "the cost of waiting was X", "I shipped the safe upgrade now and scoped the bigger change as a separate bet."

## Learn and Be Curious — lead with these
Amazon's bar: never done learning; curious about new possibilities and act to explore them.
- **PRIMARY: G6** (fake-follower detection, ML without labels). Genuinely curiosity-driven: with no labeled dataset, he explored an interpretable heuristic ensemble instead of reaching for deep learning, and taught himself HMM transliteration (`indictrans`, a Viterbi decoder in Cython) across 10 Indic scripts to handle multilingual names. Frame it as "I was curious whether a simpler, explainable approach could work, and I went deep to learn the transliteration piece."
- **BACKUP: G2 / G3** — learned the async-Python stack (asyncio/uvloop, `FOR UPDATE SKIP LOCKED`) and the Airflow/dbt data stack from scratch to build Beat and Stir.
- **BACKUP: P3** — as an intern, taught himself SonarQube + Flyway and drove test coverage 30% → 83%.
- **Honesty guardrail:** do NOT frame "self-taught the whole Go stack / owned services solo" as a personal hero story — Anshul's actual slice there was small. Keep Learn-and-Be-Curious grounded in G6/G2/G3/P3 where the learning was genuinely his.
- Phrases to use: "I hadn't worked with X before, so I…", "I was curious whether…", "I went further than I needed to because I wanted to understand the why."

## General
- Lead with "I" (not "we"); quantify; own the result. Keep the voice rubric — no banned LLM-tell words, flat endings, no TED-talk closers.
