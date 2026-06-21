# How To Speak About Fake Follower ML System In Interview

> **Ye file sikhata hai fake follower detection project ke baare mein KAISE bolna hai - word by word.**
> Interview se pehle ye OUT LOUD practice karo.

---

## YOUR 90-SECOND PITCH (Ye Yaad Karo)

Jab interviewer bole "Tell me about your ML experience" ya "Tell me about NLP work":

> "At Good Creator Co, I built an ML-powered system to detect fake followers on Instagram. The core challenge was uniquely Indian - users write their names in 10 different scripts: Hindi in Devanagari, Bengali, Tamil, Urdu, and more. You can't just string-match a handle like 'rahul_27' against a name written as 'राहुल'.
>
> I built a multi-stage pipeline. First, I normalize 13 different Unicode symbol variants that bots use to evade detection. Then I transliterate Indic scripts to English using HMM-based ML models for 9 languages, plus a custom Hindi converter I built with 66 vowel and consonant mappings.
>
> The detection uses a 5-feature ensemble: non-Indic language detection, digit count analysis, handle-name character correlation, weighted RapidFuzz similarity scoring, and fuzzy matching against a 35,000-name Indian name database. The output is a 3-level confidence score.
>
> The whole thing runs on a serverless AWS pipeline - SQS for input queuing, Lambda in ECR containers for processing, Kinesis for output streaming - which improved processing speed by 50% compared to the previous sequential approach."

**Practice until it flows naturally. Time yourself - should be ~90 seconds.**

---

## 30-SECOND PITCH (Jab time kam ho)

> "I built a fake follower detection system that uses 5-feature ensemble scoring with multi-language NLP. The hardest part was transliterating 10 Indian scripts to English using HMM-based ML models so we could compare Instagram handles against display names. It runs on a serverless AWS Lambda pipeline processing followers 50% faster than the previous approach."

---

## 15-SECOND PITCH (Jab sirf mention karna ho)

> "I built an ML pipeline for fake follower detection that uses NLP to handle 10 Indian languages, fuzzy string matching against a 35,000-name database, and runs on serverless AWS Lambda."

---

## PYRAMID METHOD - Architecture Question

**Q: "Walk me through the architecture"**

### Level 1 - Headline (Isse shuru karo HAMESHA):
> "It's a serverless ML pipeline that detects fake Instagram followers using a 5-feature ensemble model with multi-language NLP support."

### Level 2 - Structure (Agar unhone aur jaanna chaha):
> "Data flows through 4 stages. Push.py extracts follower data from ClickHouse using complex CTE queries, exports to S3, and distributes across SQS using 8 parallel workers.
>
> AWS Lambda picks up each record, runs the ML pipeline - Unicode normalization, Indic script transliteration, 5-feature extraction, ensemble scoring - and writes results to Kinesis.
>
> Pull.py reads from Kinesis shards in parallel and aggregates into the final analysis file."

### Level 3 - Go deep on ONE part (Jo sabse interesting lage):
> "The most technically interesting part is the NLP pipeline. Indian users write names in 10 scripts. For Hindi, I built a custom transliterator with 24 vowel and 42 consonant mappings that handles nukta diacritics and consonant clusters correctly. For the other 9 languages, I used pre-trained HMM models that do Viterbi decoding - each model has coefficient matrices and transition probabilities stored as numpy arrays. After transliteration, weighted RapidFuzz scoring compares the handle against all name permutations."

### Level 4 - OFFER (Ye zaroor bolo):
> "I can go deeper into the HMM-based transliteration, the RapidFuzz weighted scoring algorithm, or the AWS Lambda serverless architecture - which interests you?"

**YE LINE INTERVIEW KA GAME CHANGER HAI - TU DECIDE KAR RAHA HAI CONVERSATION KAHAN JAAYE.**

---

## KEY DECISION STORIES - "Why did you choose X?"

### Story 1: "Why 5 heuristics instead of training a neural network?"

> "Three reasons. First, we had no labeled training data - no dataset of confirmed fake vs real followers to train a supervised model. Building one would take weeks of manual labeling.
>
> Second, interpretability mattered. When a brand pays for influencer analytics and we flag 30% of followers as fake, they want to know WHY. Our system can say 'this account uses Chinese characters, which is a bot indicator for an Indian creator' or 'the handle has 6 random digits'.
>
> Third, modularity. Each of the 5 features catches a different bot pattern independently. I can add a 6th feature without retraining the entire model.
>
> Now that we've processed thousands of records, I could use the scored outputs as training data for a supervised model - that's the natural v2."

### Story 2: "Why HMM models for transliteration?"

> "Rule-based transliteration fails for ambiguous characters. In Bengali, the same character can map to different English letters depending on context. HMM models capture these statistical patterns from thousands of real transliteration pairs. The Viterbi algorithm finds the most probable English character sequence given the input script.
>
> For Hindi specifically, I DID use rule-based because Hindi was our dominant language and I needed deterministic, debuggable output. I wrote 66 character mappings covering vowels, consonants, nukta variants, and complex conjuncts."

### Story 3: "How did you handle the 10 Indic scripts?"

> "I built a character-to-language mapping dictionary. The code defines arrays of characters for each script - 77 for Hindi, 82 for Gujarati, 65 for Bengali, and so on. At load time, every character maps to its language code. When we encounter a follower name, we scan character by character, and the first Indic character tells us the language.
>
> Then we route: Hindi goes to my custom process_word() function, all others go to the HMM-based Transliterator from the indictrans library. The output is always English text, ready for fuzzy comparison with the handle."

### Story 4: "Why serverless Lambda instead of EC2?"

> "Follower analysis is a bursty batch workload. We run it daily - 100K records in 10-20 minutes, then nothing until the next day. EC2 would charge us for 24 hours of uptime when we only need 20 minutes of compute. Lambda auto-scales to the batch size and we pay only for the 100ms per-record processing time. The ECR container approach handles our large ML model dependencies that exceed Lambda's normal 250MB limit."

---

## IMPACT STORY - "Tell me about the impact"

> "Before this system, content filtering was manual - someone had to look at follower lists and guess which ones were fake. This was slow and inconsistent.
>
> The automated system processes followers at 50% faster speed with consistent, explainable scoring across three confidence levels. The 1.0 score catches definite bots - foreign script names, handles with 6+ random digits. The 0.33 score flags suspicious accounts for human review. And 0.0 validates likely real followers.
>
> This directly maps to the resume bullet - 'automated content filtering and elevated data processing speed by 50%'. The automation means creators get reliable follower quality metrics, and brands can make informed decisions about influencer partnerships."

---

## TECHNICAL DEPTH PIVOT - Jab interviewer specific area mein jaana chahe

### If they ask about ML:
> "The ensemble model combines 5 independent heuristics. Each captures a different signal - foreign script detection uses Unicode regex for Greek, Armenian, Chinese, Korean ranges. Digit counting uses a simple threshold. The fuzzy scoring uses a weighted average of 3 RapidFuzz metrics across all name permutations. The name database does a linear scan of 35,183 names with the same fuzzy formula. These feed into a priority-based scoring function that outputs 0.0, 0.33, or 1.0."

### If they ask about NLP:
> "The biggest NLP challenge is handling 10 Indic scripts plus 13 Unicode symbol variants. Each script has its own character set, diacritics system, and romanization rules. Hindi Devanagari has matras (vowel marks) that modify the inherent 'a' vowel of consonants, nukta dots that change pronunciation, and halant marks that create consonant clusters. The indictrans HMM models handle this for 9 languages; I built a custom 66-mapping lookup for Hindi."

### If they ask about AWS:
> "The pipeline uses 5 AWS services orchestrated together. S3 for intermediate storage between ClickHouse and SQS. SQS for reliable message queuing with 256KB max, 4-day retention, 30-second visibility timeout. Lambda in ECR containers for ML processing. Kinesis ON_DEMAND for auto-scaling output streaming. ECR for hosting the Docker image with ML models. The 8-worker multiprocessing in push.py and multi-shard parallel reading in pull.py handle the I/O parallelism."

### If they ask about data engineering:
> "The ClickHouse query is a 5-level CTE chain. It loads creator handles from S3 CSV, maps to Instagram profile IDs, extracts follower data from both historical and real-time tables using JSONExtractString on nested JSON columns, unions the results, joins back to get creator handles, and deduplicates with GROUP BY. The output goes directly to S3 in JSONEachRow format via ClickHouse's S3 function."

---

## COMMON FOLLOW-UP PATTERNS

### Pattern: "What would you improve?"
> "Three things. First, optimize the O(35K) name database scan with approximate nearest neighbor search. Second, add caching for repeat followers across creators. Third, use the scored outputs as training data for a supervised model that could learn optimal thresholds automatically."

### Pattern: "What was the hardest part?"
> "Getting the Hindi transliteration right. Devanagari has this concept of 'inherent vowel' - every consonant has an implicit 'a' sound unless explicitly suppressed by a halant mark. So 'क' is 'ka', not 'k'. But 'क्' with halant is just 'k'. Getting the process_word() function to handle this correctly for all combinations of consonant clusters, matras, and nukta diacritics took multiple iterations of testing with real Hindi names."

### Pattern: "How did you test it?"
> "We did spot-checking across the three confidence buckets. Sampled accounts scored as 1.0 (fake) and manually verified they showed bot patterns. Sampled 0.0 (real) accounts and verified they had genuine Indian names matching their handles. The 0.33 bucket required the most human review - some were real users with creative handles, others were genuine fakes."

### Pattern: "Tell me about a bug you found."
> "The Unicode nukta handling in Hindi. Some Unicode libraries represent 'ज़' (za) as a single precomposed character, while others use 'ज' + '़' (two separate codepoints - the letter plus a combining nukta). If process_word() only checks for one representation, it misses the other. The fix was checking for the nukta combining character at position i+1 and merging them before dictionary lookup. The createDict.py file actually has a comment: 'these two are very different, see them in unicode'."

---

## RESUME BULLET ALIGNMENT

**Bullet 7: "Automated content filtering and elevated data processing speed by 50%"**

When they ask "Tell me more about this bullet":

> "This refers to the fake follower detection system. Previously, identifying fake followers was a manual process - someone would scan follower lists and make subjective judgments. I automated this with an ML pipeline that processes every follower through 5 detection features, multi-language transliteration, and fuzzy matching.
>
> The 50% speed improvement came from the serverless architecture. Instead of a single-threaded sequential process, I built a pipeline with 8 parallel SQS workers for input distribution, auto-scaling Lambda for compute, and ON_DEMAND Kinesis for output aggregation. The batch processing in 10K chunks with round-robin distribution ensures even load.
>
> The content filtering automation means every follower gets a consistent, explainable score. No more manual guesswork. Creators get quantitative follower quality metrics, and brands can trust the influencer analytics."

---

## NUMBERS TO DROP NATURALLY IN CONVERSATION

- "...transliterates across **10 Indic scripts**..."
- "...matched against a database of **35,000 Indian names**..."
- "...normalizes **13 different Unicode variants**..."
- "...the HMM model uses **Viterbi decoding**..."
- "...**5 independent features** combined in an ensemble..."
- "...three confidence levels: **0, 0.33, and 1**..."
- "...runs on **serverless Lambda** with ECR containers..."
- "...**8 parallel workers** for SQS distribution..."
- "...**50% faster** than the previous approach..."
- "...**66 hand-crafted Hindi mappings** - 24 vowels and 42 consonants..."

---

*Last Updated: February 2026*
