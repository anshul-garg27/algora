# Q: Describe a creative solution under constraints.

> **LP**: Frugality
> **Primary story**: `G6 — Heuristic ensemble + transliteration instead of transformer`
> **Backup story**: `G1 — Buffered Sinker pattern under team-size constraint`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Good Creator Co., we were selling influencer analytics to brands. One pitch the sales team kept losing was "your follower counts include fake accounts" — brands were rejecting deals because some of the influencers we ranked had bot followers. They wanted a quality signal: which followers are real and which are bots.

The cleaner ML answer was a transformer-based classifier fine-tuned on labelled Instagram data. I had no GPU budget, no labelled dataset of any size, and no ML engineer. I was the platform engineer with a Python and applied-ML background. The product team wanted something useable in a few weeks.

### Task

Build a fake-follower detection system that ran on what we had — Lambda, SQS, Kinesis — and produced a signal brands trusted.

### Action

I started by looking at what bots actually look like on Indian Instagram. Three patterns kept showing up:

- Handle and name don't correlate (handle like `rahul_27`, name in a non-Indic script)
- Handle is mostly digits or special characters
- Name uses a non-Indic script that doesn't fit the audience (Greek, Armenian, Chinese on an Indian creator's followers)

The interesting twist was that Indian users write their names in 10 different scripts — Hindi in Devanagari, Bengali, Tamil, Urdu and more. A naive string match between handle `rahul_27` and name राहुल reads as "no match" — they're actually the same name.

So the system became a multi-stage pipeline, not a model:

Stage one — normalise. 13 different Unicode symbol variants that bots use to evade detection get collapsed. Then transliterate Indic scripts to Roman script using `indictrans` for 9 languages (HMM-based, public). For Hindi I built my own converter from 24 vowel + 42 consonant mappings I extracted from publicly available data — `indictrans` was weak on Hindi.

Stage two — features. Five independent heuristics: non-Indic language detection, digit count > 4, handle-name character correlation, RapidFuzz weighted similarity, fuzzy match against a 35,183-name Indian baby-name database.

Stage three — ensemble. Combine the features into a 3-level confidence score: 0 (real), 0.33 (weak fake), 1 (fake). No learned weights — hand-tuned thresholds I validated against a small manually-labelled set of about 2,000 accounts.

The whole thing ran on AWS Lambda containerised via ECR, fed by SQS, output to Kinesis. ClickHouse fed the input data via S3 export. Total cost: Lambda invocations.

### Result

Processing went 50% faster than the previous sequential approach. Brands trusted the signal enough that we used it in three product pitches. Total code: 955 lines of Python, 35K-name CSV, two transliteration mapping files. Zero GPU, no model training, no inference cluster.

The thing I'd flag honestly: a real transformer would have been more accurate. But "more accurate" wasn't the question. The question was "useable signal we can ship in weeks on the infra we have." A heuristic ensemble was the right answer to that question.

---

## Technical depth — if they probe

- **`indictrans` HMM models**: Hidden Markov Models with Viterbi decoder, Cython-implemented. Pre-trained for 9 Indic languages. Public, no training.
- **Hindi converter**: 24 vowel mappings + 42 consonant mappings extracted from public data. `indictrans` Hindi quality was bad, my converter was better for our specific input.
- **RapidFuzz over fuzzywuzzy**: RapidFuzz is ~10x faster, C++ backed. For Lambda cold starts that matters.
- **Lambda + SQS + Kinesis**: Lambda for compute, SQS for input queue (256KB max, 4-day retention), Kinesis for output streaming with shard auto-scaling. All serverless.
- **3-level output, not probabilistic**: Brands wanted bucketed answers. A 0.7 score is hard to act on; "weak fake" is easy.

---

## Likely follow-ups

**Q: Why not just train a model?**
> No GPU budget, no labelled dataset at scale, no ML engineer. Building a heuristic system was 3 weeks. Training pipeline + inference cluster + data labelling would have been months and $10K+ in cloud spend.

**Q: How accurate was it?**
> On the 2K-account hand-labelled set, ~85% precision and ~78% recall for the "fake" class. Not state-of-the-art, useable for filtering.

**Q: How did you validate it without a real test set?**
> Manual review of 2,000 accounts I labelled myself. Sampled across creators, included known bot networks. Imperfect ground truth.

**Q: What was the hardest feature?**
> Handle-name correlation across scripts. Took me a week to get the transliteration right for Hindi specifically. `indictrans` was OK for Bengali and Tamil; bad for Hindi.

**Q: Would you do this differently today?**
> Yes — I'd use a small open-source multilingual embedding model on CPU instead of heuristics. The model landscape now is much friendlier. In 2023 my heuristic was right.

---

## What NOT to say

- Don't oversell — "ML system" is the right framing only when you've already qualified it as heuristics, not learned models.
- Don't trash transformer approaches — they're the right answer when you have the data and budget.
- Don't skip the cultural piece — 10 Indic scripts is the actual problem; the constraint forced creative work.

---

## Backup story (if asked for another)

For the ClickHouse migration at GCC, the constraint was operational — 5-person team, no DevOps. The creative move was the buffered sinker pattern: a Go channel with dual-trigger flush (size limit or 1-minute ticker). Cut ingestion I/O from 10k INSERTs/sec to 10 batch INSERTs/sec. The trick wasn't ClickHouse, it was matching the batching pattern to a team that couldn't operate a heavyweight ingestion service.
