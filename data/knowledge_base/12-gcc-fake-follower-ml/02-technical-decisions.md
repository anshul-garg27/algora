# Technical Decisions Deep Dive - "Why THIS and Not THAT?"

> **Every major decision in the Fake Follower Detection system with alternatives, trade-offs, and follow-up answers.**
> This is what separates "good" from "excellent" in a hiring manager interview.

---

## Decision 1: Why Ensemble of 5 Heuristics vs Single ML Model?

### What's In The Code
```python
# fake.py - 5 independent features combined in final()
def final(fake_real_based_on_lang, similarity_score,
          number_more_than_4_handle, chhitij_logic):
    if fake_real_based_on_lang: return 1
    if 0 < similarity_score <= 40: return 0.33
    if number_more_than_4_handle: return 1
    if chhitij_logic == 1: return 1
    elif chhitij_logic == 2: return 0
    return 0
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **5-Feature Ensemble** | Interpretable, debuggable, no training data needed | Thresholds are manually tuned | **YES** |
| **Random Forest / XGBoost** | Learns complex patterns, handles feature interactions | Needs labeled training data (thousands of examples) | No |
| **Neural Network (LSTM/BERT)** | Handles text sequences natively | Massive training data, slow inference for Lambda | No |
| **Single Rule (e.g., fuzzy only)** | Simplest possible | Misses bot patterns that fuzzy can't catch | No |

### Interview Answer
> "We had no labeled dataset of confirmed fake vs real followers - that's the biggest constraint. Building a supervised ML model would require manually labeling thousands of accounts first. Instead, I identified 5 independent signals that each capture a different bot pattern: foreign scripts, excessive digits, name-handle mismatch, fuzzy similarity, and Indian name validation. Each feature is independently interpretable - when a follower is flagged as fake, we can explain exactly WHY. A neural network would be a black box. The ensemble approach also lets us add new features incrementally without retraining an entire model."

### Follow-up: "Would you switch to a supervised model now?"
> "Yes, now that we've run this system and generated thousands of scored records, those outputs can be spot-checked to create a labeled dataset. I'd train a gradient boosting model using the 5 features as inputs, but keep the heuristic ensemble as a fallback and for explainability."

### Follow-up: "How do you evaluate accuracy without labels?"
> "We did spot-checking: manually reviewed samples from each confidence level (0.0, 0.33, 1.0) and validated the detection logic. The 1.0 bucket (foreign scripts, >4 digits) had near-perfect precision. The 0.33 bucket needed the most human review."

---

## Decision 2: Why RapidFuzz vs FuzzyWuzzy?

### What's In The Code
```python
from rapidfuzz import fuzz as fuzzz

partial_ratio = fuzzz.partial_ratio(cleaned_handle.lower(), cleaned_name.lower())
token_sort_ratio = fuzzz.token_sort_ratio(cleaned_handle.lower(), cleaned_name.lower())
token_set_ratio = fuzzz.token_set_ratio(cleaned_handle.lower(), cleaned_name.lower())
```

### The Options

| Library | Speed | Python Version | Dependencies | Our Choice |
|---------|-------|---------------|-------------|------------|
| **RapidFuzz 3.3.1** | 10-50x faster (C++ backend) | Pure C++ core | Minimal | **YES** |
| **FuzzyWuzzy** | Slow (pure Python fallback) | Requires python-Levenshtein | python-Levenshtein (C ext) | No |
| **Levenshtein (direct)** | Fast | Raw distance, no ratio | None | No - no partial/token matching |
| **difflib (stdlib)** | Slow | Built-in | None | No - no fuzzy matching modes |

### Interview Answer
> "RapidFuzz is a drop-in replacement for FuzzyWuzzy that's 10 to 50 times faster because the core algorithms are implemented in C++. Since we run similarity scoring for every name permutation - up to 24 permutations per record - AND scan 35,183 names in the Indian name database, performance is critical. In a Lambda function with cold start constraints, every millisecond matters. RapidFuzz also doesn't require python-Levenshtein as a separate dependency, which simplifies our Docker container build."

### Follow-up: "Why 3 different fuzzy metrics instead of 1?"
> "Each metric catches a different pattern. `partial_ratio` finds substring matches - critical when a handle is an abbreviation like 'rahul' from 'Rahul Kumar Sharma'. `token_sort_ratio` is order-invariant - catches 'kumar_rahul' matching 'Rahul Kumar'. `token_set_ratio` handles duplicates and subsets. The weighted average (2x partial + sort + set) / 4 gives partial extra weight because abbreviation is the most common pattern in Instagram handles."

---

## Decision 3: Why AWS Lambda vs EC2 for Processing?

### What's In The Code
```dockerfile
# Dockerfile
FROM public.ecr.aws/lambda/python:3.10
CMD [ "fake.handler" ]
```

### The Options

| Approach | Scaling | Cost Model | Cold Start | Our Choice |
|----------|---------|-----------|------------|------------|
| **AWS Lambda + ECR** | Auto-scales to demand | Pay per invocation | Yes (~5s for container) | **YES** |
| **EC2 Instance** | Manual/ASG scaling | Pay for uptime | No | No |
| **ECS Fargate** | Task-level scaling | Pay for vCPU/memory | Slower task launch | No |
| **Batch (AWS Batch)** | Job-level scaling | Pay for compute | Job scheduling delay | Considered |

### Interview Answer
> "Lambda was the right choice because follower analysis is a batch workload - we don't need a server running 24/7. With Lambda, we pay only for the ~100ms per record processing time. EC2 would cost us for idle time between batches. The auto-scaling is also critical - if we have 100K followers to process, Lambda spins up concurrent executions automatically. We use ECR containers instead of ZIP packages because the indictrans ML models are too large for Lambda's 250MB deployment limit."

### Follow-up: "What about cold start latency?"
> "Container-based Lambda cold starts are around 5 seconds. For a batch job that processes thousands of records, this is acceptable - the first record is slow, but subsequent invocations reuse warm containers. If this were a real-time API, I'd use provisioned concurrency."

### Follow-up: "Why not AWS Batch?"
> "AWS Batch is better for long-running jobs. Our per-record processing is 50-100ms. Lambda's 15-minute timeout is more than enough. Batch adds scheduling overhead and is designed for compute-intensive jobs that run for minutes to hours."

---

## Decision 4: Why SQS + Kinesis vs Just SQS?

### What's In The Code
```python
# push.py - Input via SQS
queue = sqs.create_queue(QueueName='creator_follower_in', ...)

# fake.py - Output via Kinesis (inside Lambda)
response = kinesis.put_record(
    StreamName='creator_out',
    Data=json.dumps(response_data),
    PartitionKey='follower_handle'
)

# pull.py - Read from Kinesis
response = client.get_records(ShardIterator=shard_iterator, Limit=10000)
```

### The Options

| Pattern | Input | Output | Trade-off | Our Choice |
|---------|-------|--------|-----------|------------|
| **SQS in + Kinesis out** | Reliable delivery, retries | Ordered streaming, multi-consumer | Different services for different needs | **YES** |
| **SQS in + SQS out** | Simple, same service | No ordering, single consumer | Simpler but less flexible | No |
| **Kinesis both** | Consistent | Retention issues for input | Input needs retries, not streaming | No |
| **SNS + SQS** | Fan-out capable | Standard pattern | Over-engineered for batch | No |

### Interview Answer
> "We chose different services for input vs output because they solve different problems. For INPUT, SQS provides reliable message delivery with built-in retries, visibility timeouts, and dead-letter queues. If Lambda fails to process a message, SQS automatically retries it. For OUTPUT, Kinesis provides ordered streaming with multi-shard parallel reads. The results need to be aggregated in order and read by multiple downstream consumers. Kinesis also retains data for 24 hours by default, giving us a buffer if the pull.py aggregator is temporarily down."

### Follow-up: "Why not just write results to S3?"
> "S3 would work for batch output but doesn't support real-time streaming. With Kinesis, we can have multiple consumers reading results as they're produced - analytics dashboards, alerting systems, etc. S3 would require polling and doesn't guarantee ordering."

---

## Decision 5: Why HMM-Based Transliteration vs Rule-Based?

### What's In The Code
```python
# For non-Hindi languages: HMM-based ML model
trn = Transliterator(source=lang, target='eng', build_lookup=True)
return trn.transform(word)

# For Hindi: Custom rule-based with svar/vyanjan CSVs
return process_word(word)
```

### The Options

| Approach | Accuracy | Speed | Maintenance | Our Choice |
|----------|----------|-------|-------------|------------|
| **HMM (indictrans)** | High - trained on real data | Moderate (ML inference) | Pre-trained, no updates needed | **YES (9 languages)** |
| **Rule-based mapping** | Moderate - misses edge cases | Fast (lookup table) | Manual rules per language | **YES (Hindi only)** |
| **Deep learning (seq2seq)** | Highest | Slow | Needs GPU for training | No |
| **Google Translate API** | Very high | Fast (API call) | Costly at scale, network dependency | No |

### Interview Answer
> "We use HMM-based ML models from the indictrans library for 9 Indic scripts because Hidden Markov Models capture the statistical patterns of how characters map across scripts - they handle ambiguous mappings that rule-based systems miss. For example, the same Bengali character can transliterate differently depending on context. The HMM models are pre-trained and ship as numpy arrays (coefficients, transition matrices), so inference is fast without needing a GPU. For Hindi specifically, we use a custom rule-based approach because we needed finer control over Devanagari diacritics and consonant clusters."

### Follow-up: "How do HMM models work for transliteration?"
> "Each model has 5 numpy arrays: coefficient matrix, output classes, and three intercept matrices for initial, transition, and final state probabilities. The input text is converted to WX notation, features are extracted as character n-grams, and the Viterbi algorithm finds the most likely output sequence. It's essentially sequence labeling - each input character gets mapped to an output character sequence."

---

## Decision 6: Why Custom Hindi Transliteration (svar/vyanjan) vs indictrans for All?

### What's In The Code
```python
def detect_language(word):
    for char in word:
        lang = char_to_lang.get(char)
        if lang is not None:
            if lang == 'hin':
                return process_word(word)  # Custom Hindi-specific
            else:
                trn = Transliterator(source=lang, target='eng', build_lookup=True)
                return trn.transform(word)
    return word
```

### Interview Answer
> "Hindi has the most complex diacritics system among Indic scripts - matras (vowel signs), halant (vowel suppression), nukta (dot below for borrowed sounds like 'z' and 'f'), and consonant clusters. The generic HMM model sometimes produced unexpected results for these edge cases. By writing custom mappings (24 vowels in svar.csv, 42 consonants in vyanjan.csv), we get deterministic, predictable output for Hindi. Since Hindi is the most common language among our Indian user base, accuracy there matters most. For the other 9 languages, the HMM models work well enough."

### Follow-up: "Why not custom rules for ALL 10 languages?"
> "Writing accurate transliteration rules requires deep linguistic knowledge of each script. For Tamil alone, you need to handle 12 vowels, 18 consonants, and 216 compound characters. The HMM models are trained on thousands of real transliteration pairs, capturing patterns I couldn't hand-code. Hindi was worth the manual effort because it's our dominant language."

---

## Decision 7: Why 35K Name Database vs NER Model?

### What's In The Code
```python
name_data = pd.read_csv('baby_names.csv')
namess = name_data['Baby Names'].str.lower()  # 35,183 names

def check_indian_names(name):
    for i in namess:
        similarity_score = max(similarity_score, score(i, first_name))
```

### The Options

| Approach | Accuracy | Speed | Coverage | Our Choice |
|----------|----------|-------|----------|------------|
| **35K name database + fuzzy match** | Good for Indian names | O(35K) per name | Indian names only | **YES** |
| **NER model (spaCy/BERT)** | High for any name | Fast after loading | All languages | No |
| **Census data** | High coverage | Depends on dataset size | Country-specific | Considered |
| **No name validation** | N/A | N/A | N/A | No - too many false positives |

### Interview Answer
> "An NER model like spaCy's would tell us IF something is a name, but not whether it's a plausible Indian name specifically. Our fake followers often use real-looking but non-Indian names. The 35,183-name database gives us a high-quality Indian name reference. Combined with fuzzy matching, it handles spelling variations and transliteration inconsistencies. The trade-off is O(35K) per name lookup - about 10-50ms - but this runs once per follower in a batch pipeline, so it's acceptable."

### Follow-up: "How would you optimize the O(35K) scan?"
> "Three approaches: (1) Build a BK-tree for edit-distance-based nearest neighbor search - O(log n) instead of O(n). (2) Pre-compute trigram indexes and filter candidates before fuzzy matching. (3) Use Annoy or Faiss for approximate nearest neighbor on character embeddings. The current linear scan works for our batch volumes, but I'd optimize if we moved to real-time processing."

---

## Decision 8: Why ON_DEMAND Kinesis vs Provisioned?

### What's In The Code
```python
# push.py
kinesis_client.create_stream(
    StreamName='creator_out',
    StreamModeDetails={'StreamMode': 'ON_DEMAND'}
)
```

### The Options

| Mode | Scaling | Cost | Management | Our Choice |
|------|---------|------|------------|------------|
| **ON_DEMAND** | Auto (up to 200MB/s write) | Higher per-shard cost | Zero management | **YES** |
| **Provisioned** | Manual shard splitting | Lower per-shard cost | Must predict traffic | No |

### Interview Answer
> "ON_DEMAND mode auto-scales Kinesis shards based on traffic. Since our workload is bursty - we push all records at once during batch processing, then have zero traffic until the next batch - provisioned shards would either be over-provisioned (wasting money) or under-provisioned (throttled). ON_DEMAND costs more per unit but we pay nothing during idle periods. For a batch pipeline that runs once daily, this is significantly cheaper than keeping provisioned shards running 24/7."

### Follow-up: "What are the limits of ON_DEMAND?"
> "ON_DEMAND auto-scales up to 200 MB/s write and 400 MB/s read. Each shard handles 1 MB/s write and 2 MB/s read. For our batch sizes (tens of thousands of records at ~1KB each), we're well within limits. If we scaled to millions of records per batch, we'd need to monitor shard count and potentially switch to provisioned with custom auto-scaling."

---

## Decision 9: Why ECR Container vs Lambda Layers?

### What's In The Code
```dockerfile
FROM public.ecr.aws/lambda/python:3.10
RUN yum install -y gcc-c++ pkgconfig poppler-cpp-devel
COPY indic-trans-master ./
RUN pip install .  # Compiles Cython extensions
RUN cp -r indictrans/models /var/lang/lib/python3.10/site-packages/indictrans/
```

### The Options

| Packaging | Size Limit | Build Complexity | Cold Start | Our Choice |
|-----------|-----------|-----------------|------------|------------|
| **ECR Container** | 10 GB | Dockerfile | ~5s | **YES** |
| **Lambda Layers** | 250 MB unzipped | Layer packaging | ~1s | No - too small |
| **ZIP Package** | 50 MB compressed | Simple | <1s | No - way too small |

### Interview Answer
> "The indictrans library alone with 10 pre-trained HMM models is several hundred MB. Add pandas, numpy, rapidfuzz, and the 35K name database, and we far exceed Lambda's 250MB layer limit. ECR containers support up to 10GB, giving us plenty of room. The container also needs gcc-c++ installed to compile the Cython-based Viterbi decoder during the build phase - that's a system dependency you can't install via Lambda layers. The trade-off is a longer cold start (~5s vs ~1s), but for a batch pipeline this is negligible."

### Follow-up: "How do you optimize the container size?"
> "Multi-stage builds would help - compile indictrans in a builder stage, then copy only the compiled .so files and model numpy arrays to the final stage. Also, we could prune unused model files if we only need specific language pairs. I'd also consider using Lambda SnapStart if it becomes available for Python to eliminate cold starts entirely."

---

## Decision 10: Why 0/0.33/1.0 Scoring vs Probability Output?

### What's In The Code
```python
def final(fake_real_based_on_lang, similarity_score,
          number_more_than_4_handle, chhitij_logic):
    if fake_real_based_on_lang: return 1       # 100% FAKE
    if 0 < similarity_score <= 40: return 0.33 # 33% confidence
    if number_more_than_4_handle: return 1     # 100% FAKE
    if chhitij_logic == 1: return 1            # 100% FAKE
    elif chhitij_logic == 2: return 0          # REAL
    return 0                                    # Default REAL
```

### The Options

| Output | Interpretability | Downstream Use | Calibration Needed | Our Choice |
|--------|-----------------|----------------|-------------------|------------|
| **3-level (0/0.33/1.0)** | Very clear | Easy threshold | No | **YES** |
| **Continuous probability (0-1)** | Requires interpretation | Flexible | Yes | Considered |
| **Binary (0/1)** | Simplest | No nuance | No | No - loses information |
| **Multi-class (fake/suspect/real)** | Clear labels | Categorical | No | Equivalent to our approach |

### Interview Answer
> "We output three discrete confidence levels instead of a continuous probability because each level maps to a clear action. 1.0 means definite fake - these accounts can be automatically filtered. 0.33 means suspicious - these go to a human review queue. 0.0 means no fake indicators detected. A continuous probability (like 0.67) would be harder for the business team to act on - what do you DO with a 67% fake score? The three levels give clear decision boundaries. If we had a supervised model producing calibrated probabilities, continuous output would make more sense."

### Follow-up: "Why 0.33 specifically?"
> "0.33 represents a single weak signal - the handle-name similarity is between 0 and 40, but no other strong indicators fired. It's intentionally low because low similarity alone isn't definitive - someone's handle might be a nickname or brand name. The value 0.33 was chosen to be clearly distinct from both 0.0 (real) and 1.0 (fake) while signaling 'worth investigating' to downstream consumers."

---

## Quick Reference Table

| # | Decision | Chose | Over | Key Reason |
|---|----------|-------|------|-----------|
| 1 | Ensemble heuristics | 5-feature rules | Neural network | No labeled training data |
| 2 | RapidFuzz | C++ backend | FuzzyWuzzy | 10-50x faster, critical for Lambda |
| 3 | AWS Lambda | Serverless | EC2 | Batch workload, pay-per-use |
| 4 | SQS + Kinesis | Different I/O services | SQS only | Input needs retries, output needs streaming |
| 5 | HMM transliteration | Pre-trained models | Rule-based | Handles ambiguous character mappings |
| 6 | Custom Hindi | svar/vyanjan CSVs | indictrans for Hindi | Better diacritics handling for dominant language |
| 7 | Name database | 35K fuzzy match | NER model | Validates Indian names specifically |
| 8 | ON_DEMAND Kinesis | Auto-scaling | Provisioned | Bursty batch workload |
| 9 | ECR container | 10GB limit | Lambda layers | ML models exceed 250MB limit |
| 10 | 3-level scoring | Discrete | Continuous probability | Clear action for each level |

---

*Last Updated: February 2026*
