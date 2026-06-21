# Q: Describe a time you had to use intuition over data.

> **LP**: Are Right, A Lot
> **Primary story**: `G6 — Heuristic ML over deep learning`
> **Backup story**: `W7 — DSD Notifications (2 of 5 events from associate interviews)`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC the product team wanted to flag fake Instagram followers — bots, click-farms, accounts that inflate creator metrics. The obvious technical choice in 2023 was "throw deep learning at it" — a fine-tuned BERT or an LSTM on follower handles and bios. Two team members had used DL for similar text-classification tasks elsewhere and were pushing that route.

I had a problem with the data side. We had no labeled dataset of "this account is fake, this one is real." Building one would mean manually labeling thousands of accounts — weeks of work, and inconsistent labels because we couldn't even define "fake" precisely up front.

### Task

I owned the build. I had to pick an approach that would ship within a quarter and actually produce useful output, with no labeled training data and limited inference budget on Lambda.

### Action

I went with intuition over data. I picked a 5-feature heuristic ensemble instead of DL.

My reasoning was about what we actually knew. The "fake follower" problem in India has obvious signals — bots use non-Indic scripts (Greek, Armenian, Chinese), they pack handles with random digits, their display name doesn't match the handle, they don't match real Indian name patterns. I could enumerate those signals from talking to creators and looking at 30 accounts on a Friday afternoon. Each signal was independently interpretable.

So the design was: five features, each a heuristic, combined into a confidence score.

Feature 1: non-Indic script regex (Greek, Armenian, Georgian, Chinese, Korean) → fake.
Feature 2: digit count > 4 in the handle → fake.
Feature 3: handle-name special-character correlation with fuzzy similarity → signal of fake.
Feature 4: weighted RapidFuzz similarity (`(2*partial_ratio + token_sort + token_set) / 4`) across all name permutations → high score = real.
Feature 5: fuzzy match against a 35,183-name Indian name database → high score = real.

For the Indic script handling — 10 scripts including Hindi, Bengali, Tamil, Urdu — I used `indictrans` HMM models for 9 languages and built a custom Hindi transliterator with 24 vowel and 42 consonant mappings (the `svar.csv` and `vyanjan.csv` files). Hindi was the dominant language so I wanted deterministic, debuggable output for it.

Output: 0.0 (real), 0.33 (suspicious — flag for human review), 1.0 (fake — auto-filter).

I deliberately did NOT pick a continuous probability. Three buckets gave the business team clear actions. A continuous 0.67 would have triggered "what do we do with this" debates.

### Result

Shipped in a quarter on AWS Lambda + SQS + Kinesis. 50 percent faster than the previous manual review queue. Per-record processing: 50-100ms. Each feature was independently interpretable — when a follower was flagged, we could explain exactly why. That mattered for creator support tickets ("why was my follower flagged").

The intuition call was right but partly lucky. Heuristics worked because the bot patterns in our specific market were obvious. If the bots had been more sophisticated, DL would have been the better call. I'm honest about that — I picked the simpler approach because the data was simple. Six months later, with the scored outputs from this system, we DID have a labeled dataset, and a supervised XGBoost model became a reasonable v2.

---

## Technical depth — if they probe

- **5-feature ensemble scoring**: `process1()` returns 0/1/2; `final()` returns 0.0/0.33/1.0. Three clear decision buckets.
- **RapidFuzz weighted formula**: `(2 * partial_ratio + token_sort_ratio + token_set_ratio) / 4`. Partial gets 2x weight because handles are often abbreviations (kumar_rahul matches "Rahul Kumar").
- **Custom Hindi transliterator**: 24 vowel and 42 consonant mappings. Handles inherent 'a' vowel, nukta diacritics, halant marks. Deterministic; debuggable.
- **HMM via `indictrans`**: pre-trained models for 9 Indic languages, Viterbi-decoded. ML transliteration where rule-based would have been brittle.
- **Lambda + ECR**: indictrans library is several hundred MB — exceeds Lambda's 250MB layer limit. ECR container with `public.ecr.aws/lambda/python:3.10` base.
- **Why three buckets, not continuous**: each bucket maps to a clear business action — auto-filter, human review, no action. 0.67 forced debates we didn't want.

---

## Likely follow-ups

**Q: When would DL have been the right call?**
> If bots had been more sophisticated — coordinated, longer handles, plausible names. Heuristics work when adversaries are lazy. Once they adapt, heuristics break and DL with labeled data is the natural next step. We built a labeled dataset from v1's outputs, which means v2 with DL is now possible.

**Q: How did you know your heuristics would work without testing?**
> I tested informally. Pulled 30 accounts that creators had flagged as fake and 30 they'd said were real, ran my features mentally on each. Hit rate was about 80 percent — enough signal to be worth building. I treat that as "small-data validation," not "no testing."

**Q: What did you get wrong?**
> Initial weighting on Feature 3 (handle-name correlation) was too aggressive. Real users with underscores in their handles ("rahul_kumar") were getting flagged. Rebalanced so that feature only counts when combined with low Indian-name-DB score. False positives dropped meaningfully.

**Q: Why three buckets instead of two?**
> 0.0 (real, no action) and 1.0 (fake, auto-filter) are the obvious ones. 0.33 (suspicious, human review) is the bucket that prevented over-filtering. Without it, we'd have to choose between auto-filtering aggressively (false positives hurt creators) or never auto-filtering (defeating the point).

**Q: What's the second-order lesson?**
> Match the model to the data, not the data to the model. We didn't have labels, so a supervised model was wrong. We had domain signals, so a heuristic ensemble was right. The DL pull is real — but DL without labels is a research project, not a shipping feature.

---

## What NOT to say

- Don't oversell intuition — I had small-sample validation (30 + 30 accounts). Pure gut would be irresponsible.
- Don't disparage DL — for sophisticated adversaries it's the right call. I picked heuristics because the problem was tractable that way.
- Don't pretend the initial feature weighting was right — I had to rebalance Feature 3. Be honest.

---

## Backup story (if asked for another)

At Walmart on the DSD (Direct Store Delivery) notification system, I designed the event taxonomy with five event types. Three came from data — delivery confirmation, exception, schedule change (we had volume metrics for each). Two came from intuition after sitting with associates on a back-of-store ride-along — "associate accepts partial delivery" and "associate marks unit damaged at receipt" weren't in any system but the associates kept describing them as "the moment I want to be told something." Shipped all five. The two intuition-driven events drove 30 percent of the post-launch engagement.
