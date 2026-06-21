# Q: Tell me about a time when you went above and beyond to serve a customer.

> **LP**: Customer Obsession
> **Primary story**: `G6 — Fake-Follower ML`
> **Backup story**: `W6 — Supplier Self-Service`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Good Creator Co. — an influencer analytics SaaS — brands like Nike and a few D2C startups paid us to vet creators before campaigns. The brand customer wanted one number: "how real is this creator's following?" The existing answer was an analyst manually scrolling follower lists. Slow, inconsistent, and missing the actual problem — Indian Instagram is full of bot accounts that use Devanagari, Bengali, Tamil scripts and fake-looking digits in handles.

### Task

I was a junior SE-I, not the assigned engineer for this. The analyst lead mentioned the manual review pain to me over coffee. I asked if I could prototype something on my own time. He said go.

### Action

The naive answer was a regex on the handle. That fails the moment a name is written in Hindi script. I had to build something for the Indian context — 10 different Indic scripts, plus all the Unicode tricks bots use to look real.

I built a 5-feature ensemble. None of the features alone is enough; together they have signal.

Feature one — non-Indic script detection. Real Indian users don't write their full name in Greek or Korean. A regex on those Unicode ranges flags it.

Feature two — handle digit count. Real handles sometimes have a birth year. Bots have random 6-8 digit suffixes. Threshold at 4.

Feature three — handle-to-name correlation. The display name and handle should match somehow. `rahul_27` matching "Rahul Kumar" is real. `xyzbot8821` matching "राहुल कुमार" isn't.

Feature four was the hard one. I needed to transliterate 10 Indic scripts to English before fuzzy-matching against the handle. I used the `indictrans` library — HMM-based ML models for 9 languages with Viterbi decoding. For Hindi I built my own transliterator with 24 vowel mappings and 42 consonant mappings, because Devanagari has nukta diacritics and inherent-a vowels that the generic HMM was getting wrong on common names.

Feature five — fuzzy-match the transliterated name against a 35,183-entry Indian baby-name database using RapidFuzz weighted scoring. `partial_ratio` gets 2x weight because handles are usually abbreviations.

Ensemble output is 0.0 (real), 0.33 (review), or 1.0 (fake). Three discrete levels because the analyst team needed action thresholds, not a continuous probability they'd have to bucket themselves.

The whole thing runs on AWS Lambda from SQS triggers, scaled out across the follower list. Output streams to Kinesis. I packaged the indictrans models in an ECR container because they don't fit in a Lambda layer.

### Result

The system processes followers 50% faster than the old sequential manual flow. More importantly — brands now see a fake-percentage on every creator profile before they sign. One D2C founder told the GCC sales lead that he'd been burned twice by inflated creators and our number was the first thing he checked now. The work was off my official sprint backlog. I picked it up because the analyst's problem was real.

---

## Technical depth — if they probe

- **HMM transliteration via `indictrans`**: Each language model is 5 numpy arrays — coefficient matrix, classes, initial/transition/final probabilities. Viterbi decodes the most likely English output for a given Indic input. Cython-compiled, fast at inference.
- **Custom Hindi transliterator**: `process_word()` walks Devanagari character by character. For each consonant, it adds an inherent 'a' unless the next character is a vowel matra or halant. Handles the nukta `़` as a two-character combination, not a precomposed glyph.
- **RapidFuzz weighted scoring**: `(2 * partial_ratio + token_sort_ratio + token_set_ratio) / 4`. Partial gets 2x because abbreviation is the dominant pattern. I tested all name permutations up to 4! = 24 and took the max — `kumar_rahul` should match "Rahul Kumar".
- **Lambda + SQS + Kinesis**: SQS for reliable input retry semantics. Kinesis for ordered output streaming with multi-shard parallel reads. ECR because the indictrans models are several hundred MB, well past Lambda's 250MB layer limit.
- **Why 0/0.33/1.0**: Each level maps to a clear analyst action — filter, queue for review, accept. A continuous 0.67 forces them to invent their own thresholds.

---

## Likely follow-ups

**Q: Why not a supervised ML model?**
> No labeled training set. We had zero confirmed-fake-vs-real ground truth. An ensemble of interpretable heuristics gave us a working v1 in two weeks. The plan was to use these scored outputs as labels for an XGBoost v2 later.

**Q: How did you validate it without labels?**
> Spot-checked against the analyst's existing manual reviews on a 500-account sample. The model agreed on roughly 85% of clear cases. The disagreements I walked through with the analyst — some were the model catching things she missed, some were the model over-firing on real users with year-of-birth handles. I tuned the digit feature based on that.

**Q: The Indic transliteration sounds complex. Did you really need 10 scripts?**
> Yes. Our top 50 creators were across Hindi, Bengali, Tamil, Telugu, Gujarati and Punjabi audiences. Each script has bot patterns. Skipping any of them would have left a blind spot for that creator's brand customer.

**Q: What did this cost in Lambda spend?**
> Lambda invocations were cheap — pay per record processed. ECR cold starts were ~5 seconds, fine for batch. The real cost was developer time. I did most of it on evenings and weekends.

---

## What NOT to say

- Don't claim it was a "production-grade ML pipeline." It was an ensemble of heuristics that worked.
- Don't oversell the 50% number — that's batch processing speed vs. sequential. Not a quality metric.
- Don't pretend I shipped it solo and silently. The analyst lead validated the approach early and the GCC platform team helped with the ECR setup.

---

## Backup story (if asked for another)

Pepsi's engineer spent two days debugging a failed `/iac/v1/inv` call before my audit-logging system shipped. After I added Parquet on GCS with BigQuery external tables and a row-level security policy on `consumer_id`, the same kind of failure is a 30-second SQL query against his own data. I went beyond the internal-logging spec because I'd seen the supplier support queue — that 2-day pattern was the norm.
