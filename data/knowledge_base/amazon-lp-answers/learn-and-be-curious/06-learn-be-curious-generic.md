# Q: Questions based on the 'Learn & Be Curious' leadership principle.

> **LP**: Learn and Be Curious
> **Primary story**: `G6 — Fake-Follower ML`
> **Backup story**: `G11 — Learn-Fast Onboarding`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2023 at Good Creator Co. A brand told our product lead they couldn't trust our influencer follower counts — some accounts had clear bot followers, others had what looked like real Indian users. The brand wanted us to flag fake followers before they paid for a campaign. The problem was nobody on the team had built ML before, and there was no labelled dataset to train on. The hardest twist — followers had names in 10 Indic scripts plus Unicode obfuscation tricks like `𝓐𝓵𝓲𝓬𝓮`.

### Task

I had zero ML background and zero NLP background. The product team gave me three weeks. I wanted the system to actually work, not just demo well.

### Action

I started by reading. Not Stack Overflow — I sat with two academic papers on Indian-script transliteration and one survey paper on fake-account detection. I learned about Hidden Markov Models and the Viterbi algorithm just enough to know what `indic-trans` was doing under the hood. I didn't try to retrain anything. I used the pre-trained models.

Then I had to learn Hindi script properly. The library handled 9 languages, but Hindi had edge cases — matras, halant marks for consonant clusters, nukta diacritics where `ज़` could be one codepoint or two. I sat with a colleague who reads Hindi and we went line by line through 24 vowel mappings and 42 consonant mappings. I learned what an inherent vowel was — that `क` is read as "ka", not "k", unless suppressed by halant.

For the detection signal, I had no training data. So I shifted to interpretable heuristics — five independent features. Non-Indic script detection. Digit count above 4. Handle-name character correlation. Weighted RapidFuzz similarity. And a 35,183-name Indian baby-name database for fuzzy matching. Each feature could be debugged on its own. The ensemble produced 0.0 / 0.33 / 1.0 — clear actions for the business team.

The deployment was new for me too — AWS Lambda, ECR containers, SQS, Kinesis. The HMM models with all 10 languages were 250MB+, way over Lambda's layer limit. I learned ECR Lambda containers so we could ship the whole thing.

### Result

The pipeline went live in about four weeks. Processed followers 50% faster than the previous manual approach. The brand started using the scores in pre-campaign vetting. Three things stayed with me from this project — read the academic source before the blog posts, sit with someone who speaks the domain, and build something interpretable when you have no data. I now reach for heuristic ensembles first when there's no labelled set.

---

## Technical depth — if they probe

- **HMM transliteration**: `indic-trans` library uses Hidden Markov Models with five `.npy` files per language pair — coefficient matrix, character classes, initial / transition / final state probabilities, and a sparse feature vocabulary. The Viterbi decoder is in Cython for speed.
- **Why ensemble**: no labelled data. I needed each signal to be interpretable so the product team could trust and tune it.
- **Lambda + ECR**: HMM models alone exceeded Lambda's 250MB layer limit. ECR containers gave us 10GB. The cold start hit ~5s — acceptable for a batch job.
- **Hindi-specific**: 24 vowels (`svar.csv`), 42 consonants (`vyanjan.csv`), plus nukta handling for two-codepoint forms like `ज़`. Inherent-vowel rule: `क` reads "ka" unless halant marks the consonant cluster.

---

## Likely follow-ups

**Q: How did you decide between supervised ML and heuristics?**
> No labelled data. A supervised model needed thousands of confirmed-fake examples. We had zero. Heuristics gave us a system the product team could ship and tune.

**Q: What would v2 look like?**
> The scored outputs from v1 are now my labelled training set. I'd train a gradient-boosted classifier on the same 5 features as inputs and keep the heuristic ensemble as the explainability fallback.

**Q: How would you scale to 10 million followers?**
> The bottleneck is the linear scan over 35,183 names — 10–50ms per follower. I'd replace it with a BK-tree or trigram index for sub-millisecond lookup. The rest scales horizontally on Lambda.

**Q: Most surprising thing you learned?**
> Two codepoints versus one for the same visible character. `ज़` looks identical but breaks string comparisons silently. Unicode is humbling.

---

## What NOT to say

- Don't claim I trained the HMM models. I used pre-trained models from `indic-trans`.
- Don't say "I learned ML in two weeks." I learned enough ML to use existing tools responsibly.
- Don't oversell the ensemble. It's a no-labelled-data v1, not a state-of-the-art detector.

---

## Backup story (if asked for another)

When I joined GCC, I had zero Go experience. The first project assigned was Event-gRPC — a high-throughput Go service handling 10K events per second. I learned Go's concurrency model in the first two weeks by reading the codebase and the Go docs, then writing the buffered sinker pattern myself — Go channels with a 1000-event batch or 5-second flush. Shipped my first production PR in 4 weeks. The trick was reading real code, not tutorials.
