# Interview Questions & Answers - Fake Follower Detection ML System

> **Comprehensive Q&A bank covering ML/NLP, AWS/Serverless, Python engineering, and system design.**
> Each answer is structured for concise delivery in 60-90 seconds.

---

## SECTION 1: Machine Learning & NLP

### Q1: "Explain the ML pipeline for fake follower detection."

> "The pipeline has three phases. **Phase 1 is text normalization** - we convert 13 Unicode symbol variants to ASCII, detect non-Indic scripts like Greek and Chinese, and transliterate 10 Indic scripts to English using HMM-based ML models. **Phase 2 is feature extraction** - we compute 5 independent features: language detection, digit count, special character correlation, weighted fuzzy similarity, and Indian name database matching. **Phase 3 is ensemble scoring** - the features are combined into a final confidence score of 0.0 (real), 0.33 (suspicious), or 1.0 (fake). Each feature catches a different bot pattern, and because they're independent, the system is modular and debuggable."

### Q2: "How does the HMM-based transliteration work?"

> "The indictrans library uses Hidden Markov Models trained on thousands of transliteration pairs for each language. Each model has 5 pre-trained numpy arrays - coefficient matrices, output character classes, and intercept matrices for initial, transition, and final states. At inference time, the input text is converted to WX notation, which is a standard romanization. Character n-grams are extracted as features. The Viterbi algorithm then finds the most likely output sequence through the HMM state space. For example, Bengali 'রাহুল' gets decoded character-by-character through the ben-eng model to produce 'Rahul'."

### Q3: "Why did you build a custom Hindi transliteration instead of using the ML model?"

> "Hindi was our dominant language, and the generic HMM model sometimes produced unexpected results for complex Devanagari features - specifically nukta diacritics, halant consonant clusters, and matra vowel signs. I built a deterministic lookup table with 24 vowel mappings and 42 consonant mappings. The `process_word()` function handles three key cases: nukta characters (two-codepoint combinations), consonant clusters (halant sequences where the inherent 'a' vowel is suppressed), and standard consonant-vowel combinations. This gives us predictable, debuggable output for the most common language."

### Q4: "Explain the RapidFuzz weighted similarity scoring."

> "We use three RapidFuzz metrics combined with a weighted formula: `(2 * partial_ratio + token_sort_ratio + token_set_ratio) / 4`. Partial ratio gets double weight because Instagram handles are often abbreviations of real names - 'rahul' is a partial match of 'Rahul Kumar Sharma'. Token sort ratio is order-invariant, catching 'kumar_rahul' matching 'Rahul Kumar'. Token set ratio handles deduplication and subsets. We also generate all permutations of name words (up to 4! = 24) and take the maximum score, because someone might register as 'rahul_kumar' but their display name is 'Kumar Rahul'."

### Q5: "How does the 35,183 Indian name database work?"

> "We loaded a CSV of 35,183 Indian baby names into a pandas Series at module import time. For each follower, we split their cleaned name into first and last parts, then fuzzy-match each part against the entire database using the same weighted formula as our similarity scoring. The maximum score across all database names becomes the `indian_name_score`. If this exceeds 80, we flag it as a real Indian name. The linear scan takes 10-50ms per name - acceptable for batch processing but would need optimization for real-time use."

### Q6: "What makes a follower 'fake' in your model?"

> "Strong fake indicators that produce a 1.0 score include: non-Indic script characters (Greek, Armenian, Chinese, Korean - real Indian users don't use these), more than 4 random digits in the handle (like 'user_123456'), and handles with special characters that don't match the display name. A weak fake signal at 0.33 is a handle-name similarity between 0-40% - the handle bears almost no resemblance to the display name. Real indicators include high fuzzy similarity (>90%), multi-word names with separators, and high match against the Indian name database."

### Q7: "How do you handle Unicode normalization?"

> "There are two normalization stages. First, `symbol_name_convert()` handles 13 different Unicode mathematical/decorative alphabets - things like bold, italic, script, fraktur, double-struck, monospace, and full-width characters. Fake accounts love using these to appear distinctive. We build a character-to-ASCII mapping dictionary from all 13 variant sets and replace each fancy character. Second, `uni_decode()` uses the unidecode library for any remaining non-ASCII characters - accented Latin characters, diacritical marks, etc. Together, these convert any Unicode name into a clean ASCII string for comparison."

---

## SECTION 2: AWS & Serverless Architecture

### Q8: "Walk me through the AWS architecture."

> "It's a 4-stage serverless pipeline. **Stage 1:** push.py extracts follower data from ClickHouse using complex CTE queries, exports to S3 as JSONEachRow, then downloads locally. **Stage 2:** The data is divided into 10K-line batches, split across 8 workers using multiprocessing.Pool, and sent to SQS (creator_follower_in). **Stage 3:** SQS triggers AWS Lambda, which runs fake.py in an ECR container. Each invocation processes one follower through the ML pipeline and sends results to Kinesis. **Stage 4:** pull.py reads from Kinesis using multi-shard parallel processing and aggregates results into a final JSON file."

### Q9: "Why SQS for input and Kinesis for output?"

> "They solve different problems. SQS for input gives us reliable delivery with automatic retries - if Lambda fails to process a message, SQS re-queues it after the 30-second visibility timeout. Dead-letter queues catch persistent failures. For output, Kinesis provides ordered streaming with multi-consumer support. The results need to be aggregated in sequence, and multiple downstream services may need to read them. Kinesis also provides 24-hour retention as a buffer. Using the same service for both would be a compromise - SQS doesn't do ordered streaming, and Kinesis doesn't do reliable retry-based delivery."

### Q10: "How does the 8-worker multiprocessing work?"

> "In push.py, we read 10,000 lines at a time from the downloaded JSON file. Each batch is divided into 8 buckets using round-robin distribution - `index % 8` assigns each message to a bucket. Then `multiprocessing.Pool(processes=8)` maps the `final()` function across all 8 buckets in parallel. Each worker sends its bucket of messages to SQS using `send_messages()` which supports batches of up to 10 messages per API call. This parallelizes the network I/O of SQS messaging, which is the bottleneck in the push phase."

### Q11: "How does the ECR container work with Lambda?"

> "The Dockerfile starts from AWS's official Lambda Python 3.10 base image. During build, we install gcc-c++ for compiling the Cython-based Viterbi decoder in indictrans. We install indictrans from source, then copy the pre-trained HMM model numpy arrays and character mapping files into the Python site-packages path. The svar.csv and vyanjan.csv Hindi mappings are copied to the working directory. Finally, the baby names database is copied and renamed. The CMD directive points to `fake.handler` - Lambda calls this function for each SQS event. The container is pushed to ECR and Lambda pulls it on cold start."

### Q12: "Explain the ClickHouse CTE query."

> "The query uses 5 CTEs chained together. CTE 1 (`handles`) loads creator handles from a CSV file stored in S3. CTE 2 (`profile_ids`) maps those handles to Instagram profile IDs using the `mart_instagram_account` table. CTE 3 (`follower_data`) extracts follower handles and full names from the historical staging table using `JSONExtractString` on the `source_dimensions` JSON column. CTE 4 (`follower_events_data`) does the same from the real-time events table. CTE 5 (`data`) UNION ALLs the historical and real-time data. The final SELECT joins back to get the creator handle and deduplicates with GROUP BY. The result is written directly to S3 in JSONEachRow format."

### Q13: "How did you achieve the 50% processing speed improvement?"

> "The improvement came from four areas. First, Lambda auto-scaling processes multiple followers concurrently instead of sequentially. Second, the 8-worker multiprocessing in push.py parallelizes SQS message delivery. Third, ON_DEMAND Kinesis auto-scales shards based on throughput. Fourth, batch processing in 10K chunks with round-robin distribution ensures even load across workers. The previous approach was a single-threaded sequential process - the combination of serverless concurrency and parallel I/O delivered the 50% improvement."

---

## SECTION 3: Python Engineering

### Q14: "How do you handle the character detection for 10 Indic scripts?"

> "I built a reverse lookup dictionary. The source code defines 10 arrays of characters - one per Indic script. Hindi has 77 characters, Gujarati has 82, Bengali has 65, and so on. At module load time, we iterate through all arrays and build a `char_to_lang` dictionary mapping every character to its language code. When `detect_language()` is called, it checks each character against this dictionary. The first hit determines the language. This is O(n) for the word length with O(1) dictionary lookups, which is very fast."

### Q15: "Explain the handle cleaning pipeline."

> "The `clean_handle()` function applies 4 regex substitutions in sequence. First, `[_\\-.]` becomes spaces - these are common handle separators. Second, `[^\\w\\s]` removes non-word, non-space characters - emojis, special symbols. Third, `\\d` removes all digits. Fourth, `[^a-zA-Z\\s]` removes anything that's not a Latin letter or space. Finally, lowercase and strip. The same function is applied to both the handle and the display name, so they're in the same normalized format for comparison. The progressive cleaning ensures we don't accidentally remove valid characters before they're normalized."

### Q16: "What's the `process_word()` function doing for Hindi?"

> "It's a character-by-character Devanagari-to-Latin converter. It iterates through the word checking three cases. First, if the next character is a nukta (a dot diacritic), it combines two characters into one - for example, 'ज' + '़' becomes 'ज़' (za). Second, if the current character is a consonant followed by another consonant, it checks whether to add the inherent 'a' vowel or suppress it - this handles consonant clusters correctly. Third, for vowels, it does a direct lookup. The OrderedDict in createDict.py ensures that longer sequences (like 'क्ष' for 'ksh') are checked before shorter ones."

### Q17: "How is the baby names database loaded and used?"

> "It's loaded once at module import time with `pd.read_csv('baby_names.csv')['Baby Names'].str.lower()`, which gives us a pandas Series of 35,183 lowercase names. This happens during Lambda container initialization, so it's loaded once per container lifecycle - not per invocation. The `check_indian_names()` function splits the input name, then iterates through the entire database computing fuzzy scores. This O(n) scan is the most expensive operation per record at 10-50ms, but since the database fits in memory and the fuzzy functions are C++-optimized via RapidFuzz, it's fast enough for batch processing."

---

## SECTION 4: System Design & Scale

### Q18: "How would you scale this to 10 million followers?"

> "Three optimizations. First, replace the linear name database scan with approximate nearest neighbor search - a BK-tree or trigram index reduces O(35K) to O(log n). Second, increase Lambda concurrency and SQS batch size. Lambda can scale to thousands of concurrent executions. Third, use Kinesis enhanced fan-out for dedicated read throughput per consumer. The architecture is already designed for horizontal scaling - Lambda handles compute scaling, SQS handles input queuing, and Kinesis handles output streaming. The bottleneck at 10M would be the name database scan, not the infrastructure."

### Q19: "What would a v2 of this system look like?"

> "I'd make three changes. First, now that we have scored output from v1, I'd use it to create a labeled training dataset and train a gradient boosting classifier (XGBoost) using the 5 features as inputs. This would learn optimal thresholds and feature interactions automatically. Second, I'd add a caching layer - many followers appear across multiple creators, so we'd cache results by follower_handle to avoid reprocessing. Third, I'd add monitoring: CloudWatch metrics for Lambda invocations, SQS queue depth, Kinesis shard utilization, and a dashboard showing fake follower percentages per creator."

### Q20: "What are the security concerns in this system?"

> "There are several that I'd address in production. The code has hardcoded AWS credentials - these should use IAM roles for Lambda and environment variables or Secrets Manager for push.py and pull.py. The ClickHouse password is in plaintext - should use Secrets Manager. There's no input validation on the SQS event data - malformed JSON could crash the Lambda. There's no encryption at rest or in transit for SQS and Kinesis (though AWS provides these as configurable options). And the S3 bucket with creator data should have bucket policies restricting access."

### Q21: "How would you add real-time processing?"

> "Replace the batch push.py with an API Gateway endpoint that accepts webhook events when a new follower is detected. API Gateway triggers Lambda directly (no SQS intermediary needed for single-record processing). Keep the same fake.py ML pipeline inside Lambda. Replace Kinesis output with DynamoDB for real-time lookup - when the analytics dashboard requests a creator's follower quality, it reads the latest scores from DynamoDB. Add Lambda provisioned concurrency to eliminate cold starts. The ML pipeline itself (50-100ms per record) is fast enough for real-time."

### Q22: "Compare your approach to how social platforms detect fake accounts."

> "Major platforms like Instagram use much more sophisticated signals - account age, posting frequency, login patterns, IP addresses, device fingerprints, follower/following ratios. We only have two data points per follower: their handle and display name. Within that constraint, our 5-feature ensemble extracts maximum signal. Platforms also use deep learning at scale with billions of labeled examples. Our approach is closer to what third-party analytics tools do - working with limited public data. The key insight is that Indian market-specific features (Indic script support, Indian name database) give us an edge that generic international tools lack."

---

## Quick-Fire Round (30-Second Answers)

### Q: "What's the time complexity of your similarity scoring?"
> "O(p * s) where p is permutations (max 24 for 4-word names) and s is string comparison. The C++ backend of RapidFuzz makes the constant factor very small."

### Q: "Why Python and not Java/Go?"
> "Python has the best ML/NLP ecosystem - pandas, numpy, rapidfuzz, indictrans. Lambda supports Python natively. The compute-intensive parts (fuzzy matching, HMM inference) run in C++/Cython under the hood."

### Q: "How many Indic scripts can you actually handle?"
> "10 directly (Hindi, Bengali, Gujarati, Kannada, Malayalam, Odia, Punjabi, Tamil, Telugu, Urdu) plus 4 derivative scripts that share a base model (Marathi/Nepali/Konkani share Hindi, Assamese shares Bengali)."

### Q: "What happens if the name is in a script you don't support?"
> "If it's in a non-Indic script like Greek or Chinese, we flag it as fake (1.0). If it's in an unsupported Indic script, `detect_language()` returns the word unchanged, and `uni_decode()` tries its best ASCII conversion. The system degrades gracefully."

### Q: "What's the false positive rate?"
> "We don't have a formal FPR because there's no labeled test set. Spot-checking showed the 1.0 bucket (foreign scripts, >4 digits) has very low false positives. The 0.33 bucket (low similarity) has more - some real users have handles unrelated to their names. That's why 0.33 routes to review, not automatic filtering."

### Q: "Explain the Viterbi algorithm in one sentence."
> "It's a dynamic programming algorithm that finds the most likely sequence of hidden states in an HMM by computing the maximum probability path through a trellis of states, in O(T * N^2) time where T is sequence length and N is the number of states."

---

*Last Updated: February 2026*
