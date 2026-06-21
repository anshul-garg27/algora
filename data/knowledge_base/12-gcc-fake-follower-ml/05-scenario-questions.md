# Scenario-Based "What If?" Questions - Fake Follower Detection ML System

> **Hiring managers LOVE these.** They test if you truly understand your system under failure, scale, and edge cases.
> Use the framework: DETECT -> IMPACT -> MITIGATE -> RECOVER -> PREVENT

---

## Q1: "What if a real Indian user has a handle with 5+ digits?"

> **DETECT:** "The model flags them as fake (1.0) based on the digit count feature."
>
> **IMPACT:** "This is a false positive. A real user like 'rahul_20031' (birth year + day) would be incorrectly classified. The `number_more_than_4_handle` feature returns 1, and the `final()` function scores 1.0."
>
> **MITIGATE:** "Two factors reduce the damage. First, the output includes ALL 16 features, not just the final score. Downstream consumers can check `indian_name_score` - if it's above 80, the name matches the Indian database despite the digit issue. Second, the 0.33 bucket exists specifically for ambiguous cases - though digit count currently bypasses it and goes straight to 1.0."
>
> **RECOVER:** "For v2, I'd change the scoring logic so that >4 digits produces 0.33 (suspicious) instead of 1.0 (definite fake) when the `indian_name_score` is above 80. The ensemble should weigh conflicting signals, not let one feature dominate."
>
> **PREVENT:** "Add feature interaction logic. If digit count says fake but name database says real, output 0.33 instead of 1.0. This is exactly where a supervised ML model would outperform heuristics - it would learn these interactions from data."

---

## Q2: "What if someone uses a script you don't support - say, Thai or Japanese?"

> **DETECT:** "Thai/Japanese characters would NOT match any of the 10 Indic script arrays in `char_to_lang`. They would also NOT match the non-Indic detection regex (which only checks Greek, Armenian, Georgian, Chinese, Korean)."
>
> **IMPACT:** "The system has a blind spot. `detect_language()` would return the word unchanged. `uni_decode()` might partially convert it to ASCII, but the result would be garbled. The fuzzy score would be very low, likely triggering the 0.33 bucket, which is actually not a terrible outcome - the account IS suspicious."
>
> **MITIGATE:** "Add Thai (U+0E00-U+0E7F), Japanese Hiragana (U+3040-U+309F), Katakana (U+30A0-U+30FF), and other script ranges to the `check_lang_other_than_indic()` regex. Any non-Latin, non-Indic script on an Indian creator's followers should flag as fake."
>
> **FIX:** "Expand the regex pattern to:
> ```python
> r'[Α-Ωα-ωԱ-Ֆა-ჰ一-鿿가-힣\u0E00-\u0E7F\u3040-\u309F\u30A0-\u30FF]+'
> ```
> Or better: detect ANY script that is NOT Latin, NOT one of the 10 supported Indic scripts, and flag it."

---

## Q3: "What if Lambda cold starts cause SQS message timeouts?"

> **DETECT:** "SQS visibility timeout is 30 seconds. Lambda container cold start is ~5 seconds. If the ML processing (50-100ms) plus cold start exceeds 30 seconds, SQS re-queues the message."
>
> **IMPACT:** "The same follower gets processed multiple times. Results appear as duplicates in Kinesis. This wastes Lambda invocations (cost) and creates duplicate records in the output."
>
> **MITIGATE:** "Increase the SQS `VisibilityTimeout` from 30 seconds to at least 60 seconds to account for cold starts. Lambda's total execution time (cold start + processing) should always be less than the visibility timeout."
>
> **RECOVER:** "In pull.py, add deduplication on `follower_handle` when reading from Kinesis. The `dict(zip(column_name, response))` already overwrites duplicates if we store in a dictionary keyed by follower_handle."
>
> **PREVENT:** "Use Lambda provisioned concurrency to eliminate cold starts entirely. Keep 5-10 warm containers. Also add an SQS dead-letter queue with `maxReceiveCount=3` so messages don't loop infinitely."

---

## Q4: "What if the 35,183 name database is missing a common Indian name?"

> **DETECT:** "The `check_indian_names()` function returns a low `indian_name_score` for a legitimate name, but the handle-name fuzzy match (`similarity_score`) would still be high if handle matches the display name."
>
> **IMPACT:** "The `score_80` flag would be 0 (not matched), but the overall `final_` score would still be 0.0 (REAL) if other features don't flag it. The name database is one of 5 features, not the sole determinant. The ensemble design specifically handles this - no single feature failure breaks classification."
>
> **MITIGATE:** "The fuzzy matching against the database is forgiving. Even if 'Aadhira' isn't in the database, 'Aadhika' or 'Aadhya' would produce a partial match score above 60-70. RapidFuzz handles spelling variations gracefully."
>
> **PREVENT:** "Periodically update the baby names database from authoritative sources. Indian government census data, hospital records, and naming trends change yearly. Also consider adding a surname database as a complement - the current system only has first names."

---

## Q5: "What if someone intentionally crafts a handle to bypass all 5 features?"

> **DETECT:** "A sophisticated fake account with: (1) no foreign scripts, (2) fewer than 5 digits, (3) special characters matching name, (4) high handle-name similarity, and (5) a handle resembling an Indian name would score 0.0 (REAL)."
>
> **IMPACT:** "This is the fundamental limitation of our heuristic approach. A deliberately crafted account that passes all 5 checks IS a false negative. At the individual level, this is undetectable."
>
> **MITIGATE:** "Behavioral signals would catch this at scale. If a creator gains 10,000 followers in one hour, and ALL of them score 0.0, that's still suspicious. The fake follower analysis should be combined with temporal patterns (follow velocity), profile completeness (do these accounts have posts, profile pictures?), and network analysis (do fake followers follow each other?)."
>
> **PREVENT:** "v2 would add: (1) follow timing analysis - mass follows in short windows, (2) profile completeness scoring via API enrichment, (3) network graph analysis for follower-follower connections, (4) a supervised model trained on confirmed fakes that learns subtle patterns our heuristics miss."

---

## Q6: "What if the ClickHouse database is down during batch extraction?"

> **DETECT:** "The `client.query(query)` call in push.py would raise a connection exception. The script would crash at line 64."
>
> **IMPACT:** "The entire daily batch fails. No follower data is extracted, no SQS messages are sent, no Lambda processing happens. The pipeline has no data for the day."
>
> **MITIGATE:** "Add retry logic with exponential backoff around the ClickHouse query. Use `tenacity` library:
> ```python
> @retry(wait=wait_exponential(multiplier=1, max=300), stop=stop_after_attempt(5))
> def extract_data():
>     return client.query(query)
> ```
> Also add a notification (Slack, email) when extraction fails so the team knows."
>
> **RECOVER:** "Once ClickHouse is back, re-run push.py. The S3 output uses `s3_truncate_on_insert=1`, so re-runs overwrite the previous file cleanly."
>
> **PREVENT:** "Add health checks before the query. Keep a read replica of ClickHouse for failover. Schedule the batch during low-traffic hours. Add CloudWatch alarms for the entire pipeline status."

---

## Q7: "What if the SQS queue fills up with millions of messages?"

> **DETECT:** "SQS has no hard message count limit, but Lambda concurrency has a default limit of 1,000. If we push millions of messages and Lambda can't keep up, the queue depth grows."
>
> **IMPACT:** "Messages older than 4 days (our `MessageRetentionPeriod` of 345,600 seconds) are silently deleted. We'd lose follower records that weren't processed in time."
>
> **MITIGATE:** "Monitor SQS queue depth with CloudWatch. Set an alarm when `ApproximateNumberOfMessagesVisible` exceeds a threshold. Increase Lambda concurrency limit via AWS Support if needed."
>
> **RECOVER:** "Messages that expired are lost. Re-run push.py to re-queue them. Add a dead-letter queue to capture messages that failed processing after N retries."
>
> **PREVENT:** "Implement backpressure in push.py. Check queue depth before sending more batches. If queue has more than 100K messages pending, pause and wait for Lambda to catch up. Also consider Step Functions for orchestrating the entire pipeline with built-in error handling."

---

## Q8: "What if the indictrans HMM model produces garbage output for a new language variant?"

> **DETECT:** "The transliterated output would be nonsensical - like 'xqwz' for a Bengali name. The fuzzy similarity score against the handle would be very low, and the `indian_name_score` would also be low."
>
> **IMPACT:** "The follower might be classified as 0.33 (suspicious) or 1.0 (fake) due to low scores, even though they're real. This is a false positive caused by transliteration failure."
>
> **MITIGATE:** "The system already has a fallback: `uni_decode()` runs after transliteration and uses the unidecode library as a safety net. Even if indictrans fails, unidecode provides a best-effort ASCII conversion. Also, the `check_lang_other_than_indic()` check happens BEFORE transliteration, so language detection isn't affected."
>
> **RECOVER:** "Add logging for transliteration input/output pairs. If the output contains non-alphabetic characters or is significantly shorter/longer than the input, flag it as a transliteration failure and fall back to unidecode only."
>
> **PREVENT:** "Add a transliteration quality check: if the output length is less than 30% or more than 300% of the input length, discard the transliteration and use unidecode. Also consider updating the HMM models periodically with newer training data."

---

## Q9: "What if a creator has 1 million followers? How does the system handle it?"

> **DETECT:** "1 million records at 50-100ms each would take ~14-28 hours of sequential Lambda time. With concurrent Lambda executions, this could be much faster."
>
> **IMPACT:** "The bottleneck is the push.py SQS ingestion phase. 1M records at 10K per batch = 100 batches. With 8 workers and SQS batch limits, this takes several minutes. Lambda auto-scaling handles the compute, but 1M concurrent Lambdas would hit account limits."
>
> **MITIGATE:** "Lambda default concurrency is 1,000. At 100ms per record, 1,000 concurrent Lambdas process 10,000 records/second. 1M records would take ~100 seconds of Lambda time. The real bottleneck is SQS throughput - standard queues handle nearly unlimited transactions per second, so this is fine."
>
> **RECOVER:** "If some messages fail, SQS retries them automatically. Dead-letter queue catches persistent failures."
>
> **PREVENT:** "For very large creators, batch the SQS messages with higher efficiency - send 10 follower records per SQS message instead of 1. Modify Lambda to process batches of 10 records per invocation. This reduces Lambda invocations by 10x and SQS API calls by 10x."

---

## Q10: "What if the business wants to add a new detection feature - say, profile picture analysis?"

> **DETECT:** "Profile picture analysis would require image data, which we don't currently have - we only receive `follower_handle` and `follower_full_name` from the ClickHouse extraction."
>
> **IMPACT:** "Adding a new feature requires changes at multiple levels: the CTE query needs to extract additional data (profile_pic_url), the SQS message payload needs to include it, and fake.py needs a new feature function."
>
> **MITIGATE:** "The ensemble architecture makes adding features easy. The `model()` function is structured as a sequence of independent feature extractions. I'd add a `check_profile_picture()` function that: (1) downloads the image from the URL, (2) runs a pre-trained CNN to detect stock photos or AI-generated faces, (3) returns a score. Then add it to the `final()` scoring logic."
>
> **IMPLEMENTATION:**
> ```python
> # Add to model() function
> profile_pic_score = check_profile_picture(temp.get('profile_pic_url'))
>
> # Add to final() function
> if profile_pic_score > 0.8:  # AI-generated or stock photo
>     return 1.0  # FAKE
> ```
>
> **PREVENT:** "Design the ensemble as a plugin system. Each feature is a separate function with a standard interface: takes follower data, returns a score. New features are registered in a list and iterated during scoring. This makes the system extensible without modifying the core pipeline."

---

## Quick Reference: Detection Gaps & Improvements

| Gap | Current Behavior | Proposed Fix |
|-----|-----------------|-------------|
| Real user with >4 digits | False positive (1.0) | Weigh against name database score |
| Unsupported scripts (Thai, Japanese) | Falls through to unidecode | Expand regex detection |
| Lambda cold starts | Possible SQS re-queuing | Provisioned concurrency |
| Missing names in database | Low `indian_name_score` | Periodic database updates |
| Sophisticated fake accounts | Not detected | Add behavioral/temporal signals |
| ClickHouse downtime | Script crashes | Retry logic + alerting |
| Queue overflow | Messages expire after 4 days | Backpressure + monitoring |
| Transliteration errors | Garbage output | Quality checks + fallback |
| Massive creator (1M followers) | Slow processing | Batch multiple records per Lambda |
| New features needed | Manual code changes | Plugin-based feature system |

---

*Last Updated: February 2026*
