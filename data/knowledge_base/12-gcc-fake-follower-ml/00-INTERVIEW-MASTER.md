# Fake Follower Detection ML System -- Complete Interview Master Guide

> **Resume Bullet:** "Automated content filtering and elevated data processing speed by 50%"
> **Company:** Good Creator Co. (GCC) -- Influencer analytics platform
> **Repo:** `fake_follower_analysis` | **955+ lines Python**

---

## Pitches

### 30-Second Pitch

> "At GCC, I built an ML-powered fake follower detection system for Instagram analytics. The core challenge was that Indian users write names in 10 different scripts - Hindi, Bengali, Tamil, Urdu, and more - so you can't just string-match a handle against a name. I built a 5-feature ensemble model that transliterates Indic scripts to English using HMM-based ML models, does weighted fuzzy matching with RapidFuzz, validates against a 35,000-name Indian name database, and detects bot patterns like non-Indic scripts and excessive digits. The whole thing runs on a serverless AWS Lambda pipeline with SQS and Kinesis, processing followers 50% faster than the previous approach."

### 90-Second Pitch

> "At Good Creator Co, I built an ML-powered system to detect fake followers on Instagram. The core challenge was uniquely Indian - users write their names in 10 different scripts: Hindi in Devanagari, Bengali, Tamil, Urdu, and more. You can't just string-match a handle like 'rahul_27' against a name written as 'राहुल'.
>
> I built a multi-stage pipeline. First, I normalize 13 different Unicode symbol variants that bots use to evade detection. Then I transliterate Indic scripts to English using HMM-based ML models for 9 languages, plus a custom Hindi converter I built with 66 vowel and consonant mappings.
>
> The detection uses a 5-feature ensemble: non-Indic language detection, digit count analysis, handle-name character correlation, weighted RapidFuzz similarity scoring, and fuzzy matching against a 35,000-name Indian name database. The output is a 3-level confidence score.
>
> The whole thing runs on a serverless AWS pipeline - SQS for input queuing, Lambda in ECR containers for processing, Kinesis for output streaming - which improved processing speed by 50% compared to the previous sequential approach."

### 15-Second Pitch

> "I built an ML pipeline for fake follower detection that uses NLP to handle 10 Indian languages, fuzzy string matching against a 35,000-name database, and runs on serverless AWS Lambda."

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total Python code | **955+ lines** |
| Ensemble features | **5 independent heuristics** |
| Indic scripts supported | **10 (Hindi, Bengali, Tamil, Telugu, Gujarati, Kannada, Malayalam, Odia, Punjabi, Urdu)** |
| Indian name database | **35,183 names** |
| Unicode symbol variants | **13 normalization sets** |
| Confidence levels | **3 (0.0, 0.33, 1.0)** |
| AWS services | **5 (Lambda, SQS, Kinesis, S3, ECR)** |
| Processing speed improvement | **50%** |
| Hindi vowel mappings | **24 (svar.csv)** |
| Hindi consonant mappings | **42 (vyanjan.csv)** |
| Parallel workers | **8 (multiprocessing)** |
| Batch size | **10,000 lines** |
| Processing per record | **50-100ms** |

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Core Language | Python 3.10 |
| ML Models | HMM (Hidden Markov Models) via indictrans |
| Fuzzy Matching | RapidFuzz 3.3.1 |
| Data Processing | Pandas 2.1.1, NumPy 1.26.0 |
| Unicode | unidecode |
| Cloud | AWS Lambda, SQS, Kinesis, S3, ECR |
| Container | Docker (ECR Lambda Python 3.10) |
| Database | ClickHouse (source data) |
| Streaming JSON | ijson |

---

## Architecture

```
+-----------------------------------------------------------------------------+
|  STAGE 1: DATA EXTRACTION (push.py)                                         |
|  +-----------------+    +------------------+    +------------------+        |
|  |  ClickHouse DB  | -> |  S3 JSON Export  | -> |  Local Download  |        |
|  |  CTE Queries    |    |  JSONEachRow     |    |  10K line batches|        |
|  +-----------------+    +------------------+    +------------------+        |
+-----------------------------------------------------------------------------+
                                    |
                         8-worker multiprocessing
                                    |
                                    v
+-----------------------------------------------------------------------------+
|  STAGE 2: MESSAGE DISTRIBUTION (push.py)                                    |
|  +--------------------------------------------------------------+          |
|  |  SQS Queue: creator_follower_in                               |          |
|  |  256KB max | 4-day retention | 30s visibility timeout         |          |
|  +--------------------------------------------------------------+          |
+-----------------------------------------------------------------------------+
                                    |
                          SQS Event Trigger
                                    |
                                    v
+-----------------------------------------------------------------------------+
|  STAGE 3: ML PROCESSING (fake.py in AWS Lambda ECR Container)               |
|  +---------------+  +------------------+  +-----------------------+         |
|  | 13 Unicode    |->| 10 Indic Script  |->| 5-Feature Ensemble    |         |
|  | Symbol Norm   |  | Transliteration  |  | Model Scoring         |         |
|  +---------------+  +------------------+  +-----------------------+         |
|                                                                             |
|  Features: Language | Digits | Special Chars | Fuzzy Match | Name DB        |
|  Output: 0.0 (REAL) | 0.33 (WEAK FAKE) | 1.0 (FAKE)                       |
+-----------------------------------------------------------------------------+
                                    |
                          Kinesis put_record
                                    |
                                    v
+-----------------------------------------------------------------------------+
|  STAGE 4: RESULTS AGGREGATION (pull.py)                                     |
|  +--------------------------------------------------------------+          |
|  |  Kinesis Stream: creator_out (ON_DEMAND auto-scaling)         |          |
|  |  -> Multi-shard parallel read -> JSON output file             |          |
|  +--------------------------------------------------------------+          |
+-----------------------------------------------------------------------------+
```

### ML Pipeline Flow

```
INPUT: {follower_handle, follower_full_name}
                    |
     +--------------+--------------+
     |                             |
     v                             v
 HANDLE PATH                   NAME PATH
 clean_handle()                symbol_name_convert() [13 Unicode variants]
 - Remove _-. -> space               |
 - Remove digits                     v
 - Remove special chars         check_lang_other_than_indic()
 - Lowercase                    [Greek, Armenian, Chinese, Korean]
     |                               |
     |                               v
     |                          detect_language() -> process_word() [Hindi]
     |                                           -> Transliterator() [9 others]
     |                               |
     |                               v
     |                          uni_decode() -> ASCII normalization
     |                               |
     |                               v
     |                          clean_handle() [same normalization]
     |                               |
     +---------- MERGE -------------+
                    |
     +--------------+--------------+--------------+--------------+
     |              |              |              |              |
     v              v              v              v              v
  Feature 1     Feature 2     Feature 3     Feature 4     Feature 5
  Non-Indic     Digit Count   Special Char  RapidFuzz     Indian Name
  Language      >4 = FAKE     Correlation   Similarity    DB Match
  Detection                                 (Weighted)    (35,183)
     |              |              |              |              |
     +--------------+--------------+--------------+--------------+
                    |
                    v
            ENSEMBLE SCORING
         process1() -> Binary (0/1/2)
         final()    -> Weighted (0.0 / 0.33 / 1.0)
                    |
                    v
         OUTPUT: 16-field response
```

### Source File Structure

```
fake_follower_analysis/
  fake.py          # Core ML detection algorithm (385 lines)
  push.py          # Data pipeline: ClickHouse -> S3 -> SQS (154 lines)
  pull.py          # Kinesis stream data retrieval (131 lines)
  createDict.py    # Hindi vowel/consonant mapping generator (91 lines)
  Dockerfile       # Lambda Docker image definition (23 lines)
  requirement.txt  # Python dependencies
  baby_names_.csv  # 35,183 Indian baby names database
  svar.csv         # 24 Hindi vowel transliteration mappings
  vyanjan.csv      # 42 Hindi consonant transliteration mappings
  indic-trans-master/   # HMM-based transliteration library
      indictrans/
          models/       # 10 pre-trained HMM models (hin, ben, guj, kan, mal, ori, pan, tam, tel, urd)
          _decode/
              viterbi.pyx     # Viterbi algorithm (Cython)
              beamsearch.pyx  # Beamsearch decoder (Cython)
```

---

## Technical Implementation

### Lambda Handler Entry Point

```python
# fake.py - Lambda entry point
def handler(event, context):
    response = model(event)
    sqs = session.resource('sqs', region_name='eu-north-1')
    queue = sqs.get_queue_by_name(QueueName='output_queue')
    response = queue.send_message(MessageBody=json.dumps(response))
    return {"statusCode": 200, "body": {"message": response}}
```

### The model() Function -- Complete ML Pipeline

```python
# fake.py - model() function
def model(event):
    follower_data = [event]
    response = {}
    for index, temp in enumerate(follower_data, start=1):
        # PHASE 1: Text Normalization
        symbolic_name = symbol_name_convert(temp['follower_full_name'])
        fake_real_based_on_lang = check_lang_other_than_indic(symbolic_name)
        transliterated_follower_name = detect_language(symbolic_name)
        decoded_name = uni_decode(transliterated_follower_name)

        # PHASE 2: Feature Extraction
        cleaned_handle = clean_handle(temp['follower_handle'])
        cleaned_name = clean_handle(decoded_name)
        chhitij_logic = process(temp['follower_handle'], cleaned_handle, cleaned_name)
        number_handle = count_numerical_digits(temp['follower_handle'])
        number_more_than_4_handle = fake_real_more_than_4_digit(number_handle)
        similarity_score = generate_similarity_score(cleaned_handle, cleaned_name)
        fake_real_based_on_fuzzy_score_90 = based_on_partial_ratio(similarity_score)
        numeric_handle = only_numeric(temp['follower_handle'])

        # PHASE 3: Ensemble Scoring
        process1_ = process1(fake_real_based_on_lang, number_more_than_4_handle, chhitij_logic)
        final_ = final(fake_real_based_on_lang, similarity_score,
                       number_more_than_4_handle, chhitij_logic)

        # PHASE 4: Indian Name Validation
        indian_name_score = check_indian_names(cleaned_name)
        score_80 = 1 if indian_name_score > 80 else 0

        # 16-field response
        response = {
            "symbolic_name": symbolic_name,
            "fake_real_based_on_lang": fake_real_based_on_lang,
            "transliterated_follower_name": transliterated_follower_name,
            "decoded_name": decoded_name,
            "cleaned_handle": cleaned_handle,
            "cleaned_name": cleaned_name,
            "chhitij_logic": chhitij_logic,
            "number_handle": number_handle,
            "number_more_than_4_handle": number_more_than_4_handle,
            "similarity_score": similarity_score,
            "fake_real_based_on_fuzzy_score_90": fake_real_based_on_fuzzy_score_90,
            "process1_": process1_,
            "final_": final_,
            "numeric_handle": numeric_handle,
            "indian_name_score": indian_name_score,
            "score_80": score_80
        }
    return response
```

### Unicode Symbol Normalization (13 Variant Sets)

```python
# fake.py - symbol_name_convert()
def symbol_name_convert(name):
    original = [
        # 1. Circled Letters (negative)     2. Circled Letters (negative sq)
        # 3. Parenthesized/Squared          4. Circled Latin
        # 5. Mathematical Bold              6. Mathematical Sans-Serif Bold
        # 7. Mathematical Italic            8. Mathematical Bold Italic
        # 9. Mathematical Monospace        10. Mathematical Double-Struck
        # 11. Mathematical Bold Fraktur    12. Mathematical Bold Script
        # 13. Full-width
    ]
    replaceAlphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    originalMap = {}
    for alphabet in original:
        originalMap.update(dict(zip(alphabet, replaceAlphabet)))
    result = "".join(originalMap.get(char, char) for char in name)
    return result
```

Example: `"𝓐𝓵𝓲𝓬𝓮"` (Bold Script) -> `"Alice"`, `"ＲＡＨＵＬ"` (Full-width) -> `"RAHUL"`

### Language Detection and Transliteration (10 Indic Scripts)

```python
# fake.py - Character-to-language reverse lookup
data = {
    "hin": ["़","०","१","अ","आ","इ","ई","उ","ऊ","ऋ","ए","ऐ",...],  # 77 chars
    "pan": ["ਅ","ਆ","ਇ","ਈ","ਉ","ਊ","ਏ","ਐ",...],  # 61 chars
    "guj": ["અ","આ","ઇ","ઈ","ઉ","ઊ","એ","ઐ",...],  # 82 chars
    "ben": ["অ","আ","ই","ঈ","উ","ঊ","এ","ঐ",...],  # 65 chars
    "urd": ["ا","آ","ب","پ","ت","ٹ","ث","ج",...],  # 41 chars
    "tam": ["அ","ஆ","இ","ஈ","உ","ஊ","எ","ஏ",...],  # 62 chars
    "mal": ["അ","ആ","ഇ","ഈ","ഉ","ഊ","ഋ","എ",...],  # 43 chars
    "kan": ["ಅ","ಆ","ಇ","ಈ","ಉ","ಊ","ಎ","ಏ",...],  # 65 chars
    "ori": ["ଅ","ଆ","ଇ","ଈ","ଉ","ଊ","ଋ","ଏ",...],  # 63 chars
    "tel": ["అ","ఆ","ఇ","ఈ","ఉ","ఊ","ఋ","ఎ",...],  # 65 chars
}
char_to_lang = {}
for lang, chars in data.items():
    for char in chars:
        char_to_lang[char] = lang
```

```python
# fake.py - detect_language()
def detect_language(word):
    for char in word:
        lang = char_to_lang.get(char)
        if lang is not None:
            if lang == 'hin':
                return process_word(word)  # Custom Hindi transliteration
            else:
                trn = Transliterator(source=lang, target='eng', build_lookup=True)
                return trn.transform(word)  # HMM-based ML transliteration
    return word  # Already in English/Latin script
```

### Custom Hindi Transliteration (svar + vyanjan)

```python
# fake.py - Hindi Devanagari -> English
vowels = load_dict('svar.csv')       # 24 Hindi vowel mappings
consonants = load_dict('vyanjan.csv') # 42 Hindi consonant mappings

def process_word(word):
    """Example: "राहुल" -> "raahul" """
    str1 = ""
    i = 0
    while i < len(word):
        # Check for nukta diacritics - two-character combinations
        if (i+1 < len(word) and word[i+1].strip() == '़'.strip()):
            c = word[i] + word[i+1]
            i += 2
        else:
            c = word[i]
            i += 1
        if c in vowels:
            str1 += vowels[c]
        elif c in consonants:
            if i < len(word) and word[i] in consonants:
                if (c == 'झ' and i != 0) or \
                   (i != 0 and i+1 < len(word) and word[i+1] in vowels):
                    str1 += consonants[c]
                else:
                    str1 += consonants[c] + 'a'  # Add inherent 'a' vowel
            else:
                str1 += consonants[c]
        elif c in ['\n','\t',' ','!',',','।','-',':','\\','_','?'] or c.isalnum():
            str1 += c.replace('।', '.')
    return str1
```

**Hindi vowel mappings (24):** `अ->a`, `आ->aa`, `इ->i`, `ई->ee`, `उ->u`, `ऊ->oo`, `ऋ->ri`, `ए->e`, `ऐ->ae`, `ओ->o`, `औ->au`, plus 13 matra forms.

**Hindi consonant mappings (42):** Velar (`क->k`, `ख->kh`, `ग->g`, `घ->gh`), Palatal (`च->ch`, `छ->chh`, `ज->j`), Retroflex (`ट->t`, `ठ->th`), Dental, Labial, Semi-vowels, Sibilants, plus nukta variants and complex conjuncts (`क्ष->ksh`, `त्र->tr`, `ज्ञ->gy`).

### HMM-Based ML Transliteration (indictrans)

```
Each language model contains:
  coef_.npy           # HMM coefficient matrix
  classes.npy         # Output character mapping
  intercept_init_.npy # Initial state probabilities
  intercept_trans_.npy# Transition probabilities
  intercept_final_.npy# Final state probabilities
  sparse.vec          # Feature vocabulary

ML Pipeline:
1. UTF-8 -> WX notation (ISO 15919 encoding)
2. Feature extraction: character n-gram context windows
3. HMM prediction: Linear classifier + Viterbi decoder
4. WX -> UTF-8 (target English script)
```

### Non-Indic Language Detection

```python
# fake.py - check_lang_other_than_indic()
def check_lang_other_than_indic(symbolic_name):
    """
    Detects: Greek (Alpha-Omega), Armenian (Ա-Ֆ), Georgian (ა-ჰ),
    Chinese (CJK Unified), Korean (Hangul Syllables)
    Returns: 1 (FAKE) if non-Indic detected, 0 (REAL) otherwise
    """
    return 1 if re.search(r'[Α-Ωα-ωԱ-Ֆა-ჰ一-鿿가-힣]+', symbolic_name, re.UNICODE) else 0
```

### Five-Feature Ensemble Model

**Feature 1: Non-Indic Language Detection (0 or 1)** -- Greek, Armenian, Georgian, Chinese, or Korean characters found.

**Feature 2: Digit Count in Handle (0 or 1)**
```python
def count_numerical_digits(text):
    return sum(c.isdigit() for c in text)

def fake_real_more_than_4_digit(number):
    return 1 if number > 4 else 0
```

**Feature 3: Handle-Name Special Character Correlation (0, 1, or 2)**
```python
def process(follower_handle, cleaned_handle, cleaned_name):
    SPECIAL_CHARS = ('_', '-', '.')
    if any(char in follower_handle for char in SPECIAL_CHARS):
        if not ' ' in cleaned_name:
            if generate_similarity_score(cleaned_handle, cleaned_name) > 80:
                return 0  # REAL
            else:
                return 1  # FAKE
        else:
            return 0  # Multi-word name with separators = REAL
    else:
        return 2  # No special chars = INCONCLUSIVE
```

**Feature 4: RapidFuzz Weighted Similarity Scoring (0-100)**
```python
def generate_similarity_score(handle, name):
    """
    Formula: (2 * partial_ratio + token_sort_ratio + token_set_ratio) / 4
    partial_ratio gets 2x weight for substring/abbreviation matching.
    Tests all name permutations (up to 4! = 24).
    """
    name = name.split()
    if len(name) <= 4:
        name_permutations = [' '.join(p) for p in permutations(name)]
    else:
        name_permutations = name
    similarity_score = -1
    cleaned_handle = handle.replace(' ', '')
    for name in name_permutations:
        cleaned_name = name.replace(' ', '')
        partial_ratio = fuzzz.partial_ratio(cleaned_handle.lower(), cleaned_name.lower())
        token_sort_ratio = fuzzz.token_sort_ratio(cleaned_handle.lower(), cleaned_name.lower())
        token_set_ratio = fuzzz.token_set_ratio(cleaned_handle.lower(), cleaned_name.lower())
        similarity_score = max(similarity_score,
                              (2 * partial_ratio + token_sort_ratio + token_set_ratio) / 4)
    return similarity_score
```

**Feature 5: Indian Name Database Matching (0-100)**
```python
name_data = pd.read_csv('baby_names.csv')
namess = name_data['Baby Names'].str.lower()  # 35,183 names

def check_indian_names(name):
    """Fuzzy match first/last name against entire database. Returns max score."""
    similarity_score = 0
    name = name.split()
    first_name = name[0]
    last_name = name[1] if len(name) >= 2 else None
    for i in namess:
        similarity_score = max(similarity_score, score(i, first_name))
    if last_name and len(last_name) >= 2:
        for i in namess:
            similarity_score = max(similarity_score, score(i, last_name))
    return similarity_score
```

### Ensemble Scoring Functions

```python
# Binary Feature Combination
def process1(fake_real_based_on_lang, number_more_than_4_handle, chhitij_logic):
    """Priority: language -> digits -> special chars. Returns 0/1/2."""
    if fake_real_based_on_lang: return 1  # Non-Indic = FAKE
    if number_more_than_4_handle: return 1  # >4 digits = FAKE
    if chhitij_logic == 1: return 1  # Special char mismatch = FAKE
    elif chhitij_logic == 2: return 2  # INCONCLUSIVE
    return 0  # REAL

# Weighted Final Score
def final(fake_real_based_on_lang, similarity_score,
          number_more_than_4_handle, chhitij_logic):
    """Produces 0.0, 0.33, or 1.0"""
    if fake_real_based_on_lang: return 1       # 100% FAKE
    if 0 < similarity_score <= 40: return 0.33 # Weak FAKE signal
    if number_more_than_4_handle: return 1     # 100% FAKE
    if chhitij_logic == 1: return 1            # 100% FAKE
    elif chhitij_logic == 2: return 0          # REAL
    return 0                                    # Default: REAL
```

### Handle Cleaning (Shared Normalization)

```python
def clean_handle(handle):
    """
    Steps: [_-.] -> space, [^\w\s] -> removed, \d -> removed,
    [^a-zA-Z\s] -> removed, lowercase + strip
    """
    cleaned_handle = re.sub(r'[_\-.]', ' ', handle)
    cleaned_handle = re.sub(r'[^\w\s]', '', cleaned_handle)
    cleaned_handle = re.sub(r'\d', '', cleaned_handle).lower()
    cleaned_handle = re.sub(r'[^a-zA-Z\s]', '', cleaned_handle).strip()
    return cleaned_handle
```

### AWS Data Pipeline -- push.py

```python
# ClickHouse CTE Query -> S3 -> SQS
query = f"""
    INSERT INTO FUNCTION s3(
        'https://gcc-social-data.s3.ap-south-1.amazonaws.com/temp/{file_name}',
        'AKIA...', '...', 'JSONEachRow'
    )
    WITH
        handles AS (
            SELECT Names as handle FROM s3('...creators_handles.csv', '...', 'CSVWithNames')
        ),
        profile_ids AS (
            SELECT ig_id FROM dbt.mart_instagram_account mia
            WHERE handle IN (SELECT handle FROM handles)
        ),
        follower_data AS (
            SELECT log.target_profile_id,
                   JSONExtractString(source_dimensions, 'handle') AS follower_handle,
                   JSONExtractString(source_dimensions, 'full_name') AS follower_full_name
            FROM dbt.stg_beat_profile_relationship_log log
            WHERE target_profile_id IN profile_ids
        ),
        follower_events_data AS (
            SELECT ... FROM _e.profile_relationship_log_events log ...
        ),
        data AS (
            SELECT * FROM follower_data UNION ALL SELECT * FROM follower_events_data
        )
    SELECT mia.handle, follower_handle, follower_full_name
    FROM data INNER JOIN dbt.mart_instagram_account mia ON mia.ig_id = target_profile_id
    GROUP BY handle, follower_handle, follower_full_name
    SETTINGS s3_truncate_on_insert=1
"""
```

**8-Worker Multiprocessing Batch Distribution:**
```python
# 10K lines at a time, 8 parallel workers
with open(file_name, 'r') as f:
    while True:
        batch_lines = list(itertools.islice(f, 10000))
        if not batch_lines: break
        messages = [{'Id': str(i), 'MessageBody': row} for i, row in enumerate(batch_lines)]
        buckets = divide_into_buckets(messages, 8)  # Round-robin
        pool = multiprocessing.Pool(processes=8)
        pool.map(final, buckets)
        pool.close()
        pool.join()
```

### Results Retrieval -- pull.py (Multi-Shard Parallel Kinesis Reader)

```python
def process_shard(shard_id, starting_sequence_number):
    shard_iterator = client.get_shard_iterator(
        StreamName=stream_name, ShardId=shard_id,
        ShardIteratorType='AFTER_SEQUENCE_NUMBER',
        StartingSequenceNumber=starting_sequence_number
    )['ShardIterator']
    while True:
        response = client.get_records(ShardIterator=shard_iterator, Limit=10000)
        if len(response['Records']) < 1: break
        shard_iterator = response['NextShardIterator']
        for record in response['Records']:
            row_dict = dict(zip(column_name, list(json.loads(record['Data']).values())))
            messages.append(row_dict)
        with open(file_name, 'a') as f:
            for message in messages:
                f.write(json.dumps(message) + '\n')

if __name__ == '__main__':
    pool = Pool()
    shards = client.list_shards(StreamName=stream_name)['Shards']
    args = [(shard['ShardId'], shard['SequenceNumberRange']['StartingSequenceNumber'])
            for shard in shards]
    pool.starmap(process_shard, args)
```

### Docker Container

```dockerfile
FROM public.ecr.aws/lambda/python:3.10
RUN yum install -y gcc-c++ pkgconfig poppler-cpp-devel
COPY requirement.txt ./
COPY indic-trans-master ./
RUN pip install -r requirements.txt
RUN pip install .  # Installs indictrans from setup.py (compiles Cython)
RUN cp -r indictrans/models /var/lang/lib/python3.10/site-packages/indictrans/
RUN cp -r indictrans/mappings /var/lang/lib/python3.10/site-packages/indictrans/
COPY svar.csv ./      # 24 vowel mappings
COPY vyanjan.csv ./   # 42 consonant mappings
COPY fake.py ./
COPY baby_names_.csv ./baby_names.csv
CMD [ "fake.handler" ]
```

### Output Schema (16 Fields)

| # | Field | Type | Meaning |
|---|-------|------|---------|
| 1 | `symbolic_name` | str | Name after Unicode symbol normalization |
| 2 | `fake_real_based_on_lang` | 0/1 | Non-Indic language detected |
| 3 | `transliterated_follower_name` | str | Name after Indic -> English transliteration |
| 4 | `decoded_name` | str | Final ASCII-normalized name |
| 5 | `cleaned_handle` | str | Handle after multi-stage cleaning |
| 6 | `cleaned_name` | str | Name after multi-stage cleaning |
| 7 | `chhitij_logic` | 0/1/2 | Special character correlation result |
| 8 | `number_handle` | int | Count of digits in handle |
| 9 | `number_more_than_4_handle` | 0/1 | Digit count exceeds threshold |
| 10 | `similarity_score` | 0-100 | Weighted fuzzy similarity |
| 11 | `fake_real_based_on_fuzzy_score_90` | 0/1 | Similarity above 90 threshold |
| 12 | `process1_` | 0/1/2 | Binary ensemble result |
| 13 | `final_` | 0.0/0.33/1.0 | **Final fake probability** |
| 14 | `numeric_handle` | 0/1 | Purely numeric handle flag |
| 15 | `indian_name_score` | 0-100 | Name database match score |
| 16 | `score_80` | 0/1 | Name score above 80 threshold |

### Performance Characteristics

```
Per-record timing:
  Symbol conversion:     1-5ms
  Language detection:    1-2ms
  Transliteration:       5-10ms (ML inference for non-Hindi)
  Fuzzy scoring:         5-15ms (up to 24 permutations)
  Indian name check:     10-50ms (linear scan of 35,183 names)
  Total:                 50-100ms per follower

Throughput:
  Single Lambda:         10-20 records/second
  8 parallel workers:    80-160 records/second
  Daily batch (100K):    ~10-20 minutes
```

---

## Technical Decisions

### Decision 1: Why Ensemble of 5 Heuristics vs Single ML Model?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **5-Feature Ensemble** | Interpretable, debuggable, no training data needed | Thresholds are manually tuned | **YES** |
| **Random Forest / XGBoost** | Learns complex patterns, handles feature interactions | Needs labeled training data | No |
| **Neural Network (LSTM/BERT)** | Handles text sequences natively | Massive training data, slow inference | No |
| **Single Rule** | Simplest | Misses bot patterns that one metric can't catch | No |

> "We had no labeled dataset of confirmed fake vs real followers. Building a supervised ML model would require manually labeling thousands of accounts. Instead, I identified 5 independent signals that each capture a different bot pattern. Each feature is independently interpretable -- when a follower is flagged, we can explain exactly WHY. The ensemble approach also lets us add new features incrementally without retraining."

**Follow-up: "Would you switch to a supervised model now?"**
> "Yes, now that we've run this system and generated thousands of scored records, those outputs can be spot-checked to create a labeled dataset. I'd train a gradient boosting model using the 5 features as inputs, but keep the heuristic ensemble as a fallback for explainability."

### Decision 2: Why RapidFuzz vs FuzzyWuzzy?

| Library | Speed | Our Choice |
|---------|-------|------------|
| **RapidFuzz 3.3.1** | 10-50x faster (C++ backend) | **YES** |
| **FuzzyWuzzy** | Slow (pure Python fallback) | No |
| **Levenshtein (direct)** | Fast but no partial/token matching | No |

> "RapidFuzz is 10-50x faster because the core algorithms are in C++. Since we run similarity scoring for every name permutation -- up to 24 -- AND scan 35,183 names, performance is critical. In Lambda with cold start constraints, every millisecond matters."

**Follow-up: "Why 3 different fuzzy metrics?"**
> "`partial_ratio` finds substring matches -- handles that are abbreviations. `token_sort_ratio` is order-invariant -- catches 'kumar_rahul' matching 'Rahul Kumar'. `token_set_ratio` handles duplicates and subsets. Partial gets 2x weight because abbreviation is the most common handle pattern."

### Decision 3: Why AWS Lambda vs EC2?

| Approach | Scaling | Cost Model | Our Choice |
|----------|---------|-----------|------------|
| **AWS Lambda + ECR** | Auto-scales to demand | Pay per invocation | **YES** |
| **EC2 Instance** | Manual/ASG | Pay for uptime | No |
| **ECS Fargate** | Task-level | Pay for vCPU/memory | No |

> "Lambda was right because follower analysis is a batch workload -- we don't need a server running 24/7. With Lambda, we pay only for ~100ms per record. EC2 would cost us for idle time between batches. We use ECR containers because the indictrans ML models are too large for Lambda's 250MB limit."

### Decision 4: Why SQS + Kinesis vs Just SQS?

> "Different services for different problems. SQS for input provides reliable delivery with retries and visibility timeouts. For output, Kinesis provides ordered streaming with multi-shard parallel reads and 24-hour retention as a buffer. SQS doesn't do ordered streaming; Kinesis doesn't do reliable retry-based delivery."

### Decision 5: Why HMM-Based Transliteration vs Rule-Based?

> "HMM models capture statistical patterns of how characters map across scripts -- they handle ambiguous mappings that rule-based systems miss. The same Bengali character can transliterate differently depending on context. For Hindi specifically, I used custom rule-based because I needed deterministic, debuggable output for the most common language."

### Decision 6: Why Custom Hindi (svar/vyanjan) vs indictrans for All?

> "Hindi has the most complex diacritics system -- matras, halant, nukta, consonant clusters. The generic HMM model sometimes produced unexpected results for these edge cases. By writing 24 vowel and 42 consonant mappings, we get deterministic output. Since Hindi is our dominant language, accuracy there matters most."

### Decision 7: Why 35K Name Database vs NER Model?

> "An NER model would tell us IF something is a name, but not whether it's a plausible Indian name. Our fake followers often use real-looking but non-Indian names. The 35,183-name database gives us a high-quality Indian reference. The O(35K) per-name scan takes 10-50ms -- acceptable for batch processing."

**Follow-up: "How would you optimize the O(35K) scan?"**
> "BK-tree for edit-distance-based nearest neighbor (O(log n)), trigram indexes for pre-filtering, or Annoy/Faiss for approximate nearest neighbor on character embeddings."

### Decision 8: Why ECR Container vs Lambda Layers?

> "The indictrans library with 10 HMM models is several hundred MB. Add pandas, numpy, rapidfuzz, and the name database -- far exceeds Lambda's 250MB layer limit. ECR supports 10GB. The container also needs gcc-c++ to compile the Cython Viterbi decoder. Trade-off is longer cold start (~5s), but negligible for batch."

### Decision 9: Why 0/0.33/1.0 Scoring vs Continuous Probability?

> "Each level maps to a clear action. 1.0 = automatic filter. 0.33 = human review queue. 0.0 = no fake indicators. A continuous probability like 0.67 would be harder for the business team to act on. The three levels give clear decision boundaries."

---

## Interview Q&A

### Q1: "Explain the ML pipeline."

> "Three phases. Phase 1 is text normalization -- convert 13 Unicode symbol variants to ASCII, detect non-Indic scripts, transliterate 10 Indic scripts to English using HMM models. Phase 2 is feature extraction -- 5 independent features: language detection, digit count, special character correlation, weighted fuzzy similarity, Indian name database matching. Phase 3 is ensemble scoring -- features combined into 0.0 (real), 0.33 (suspicious), or 1.0 (fake)."

### Q2: "How does the HMM-based transliteration work?"

> "The indictrans library uses Hidden Markov Models with 5 pre-trained numpy arrays per language. Input text is converted to WX notation. Character n-grams are extracted as features. The Viterbi algorithm finds the most likely output sequence through the HMM state space. For example, Bengali 'রাহুল' gets decoded through the ben-eng model to produce 'Rahul'."

### Q3: "Explain the RapidFuzz weighted similarity scoring."

> "Formula: `(2 * partial_ratio + token_sort_ratio + token_set_ratio) / 4`. Partial gets 2x weight because handles are often abbreviations. We generate all name permutations (up to 24 for 4-word names) and take the max score, because 'kumar_rahul' should match 'Rahul Kumar'."

### Q4: "How does the 35,183 Indian name database work?"

> "Loaded as a pandas Series at module import. For each follower, we split their cleaned name into first/last parts, then fuzzy-match each against the entire database using the same weighted formula. The max score becomes the `indian_name_score`. Above 80 = real Indian name. The linear scan takes 10-50ms -- acceptable for batch but would need optimization for real-time."

### Q5: "What makes a follower 'fake'?"

> "Strong indicators at 1.0: non-Indic scripts (Greek, Armenian, Chinese, Korean -- real Indian users don't use these), more than 4 random digits, handles with special characters that don't match the display name. Weak signal at 0.33: handle-name similarity between 0-40%. Real indicators: high fuzzy similarity (>90%), multi-word names with separators, high match against Indian name database."

### Q6: "Walk me through the AWS architecture."

> "4-stage pipeline. Stage 1: push.py extracts from ClickHouse using 5-level CTE queries, exports to S3 as JSONEachRow. Stage 2: data split into 10K batches across 8 workers via multiprocessing, sent to SQS. Stage 3: SQS triggers Lambda (ECR container), each invocation runs the ML pipeline and writes to Kinesis. Stage 4: pull.py reads from Kinesis shards in parallel and aggregates into the final JSON file."

### Q7: "How did you achieve the 50% speed improvement?"

> "Four areas: Lambda auto-scaling processes followers concurrently instead of sequentially. 8-worker multiprocessing parallelizes SQS message delivery. ON_DEMAND Kinesis auto-scales shards. Batch processing in 10K chunks with round-robin distribution. The previous approach was single-threaded sequential."

### Q8: "How would you scale to 10 million followers?"

> "Replace linear name database scan with approximate nearest neighbor (BK-tree or trigram index). Increase Lambda concurrency. Use Kinesis enhanced fan-out. The architecture already scales horizontally -- Lambda handles compute, SQS handles queuing, Kinesis handles streaming. Bottleneck at 10M would be the name database scan."

### Q9: "What would v2 look like?"

> "Three changes. Use scored outputs from v1 as training data for an XGBoost classifier that learns optimal thresholds. Add caching for repeat followers across creators. Add monitoring: CloudWatch metrics for Lambda invocations, SQS queue depth, Kinesis utilization, and a dashboard showing fake follower percentages per creator."

### Q10: "What's the Viterbi algorithm in one sentence?"

> "A dynamic programming algorithm that finds the most likely sequence of hidden states in an HMM by computing the maximum probability path through a trellis, in O(T * N^2) time."

---

## Behavioral Stories

### The Impact Story

> "Before this system, content filtering was manual -- someone had to look at follower lists and guess which ones were fake. This was slow and inconsistent.
>
> The automated system processes followers at 50% faster speed with consistent, explainable scoring across three confidence levels. 1.0 catches definite bots. 0.33 flags suspicious accounts for human review. 0.0 validates likely real followers.
>
> This directly maps to the resume bullet -- 'automated content filtering and elevated data processing speed by 50%'. Creators get reliable follower quality metrics, and brands can make informed decisions about influencer partnerships."

### The Hardest Part Story

> "Getting the Hindi transliteration right. Devanagari has this concept of 'inherent vowel' -- every consonant has an implicit 'a' sound unless explicitly suppressed by a halant mark. So 'क' is 'ka', not 'k'. But 'क्' with halant is just 'k'. Getting the process_word() function to handle this correctly for all combinations of consonant clusters, matras, and nukta diacritics took multiple iterations."

### The Unicode Bug Story

> "The nukta handling in Hindi. Some Unicode libraries represent 'ज़' (za) as a single precomposed character, while others use 'ज' + '़' (two separate codepoints). If process_word() only checks for one representation, it misses the other. The fix was checking for the nukta combining character at position i+1 and merging them before dictionary lookup. The createDict.py file has a comment: 'these two are very different, see them in unicode'."

---

## What-If Scenarios

### Scenario 1: "What if a real user has 5+ digits in their handle?"

> **IMPACT:** False positive -- classified as 1.0 (fake). A handle like 'rahul_20031' (birth year + day) would be incorrectly flagged.
>
> **FIX:** For v2, change scoring so >4 digits produces 0.33 instead of 1.0 when `indian_name_score` is above 80. This is exactly where a supervised model would outperform heuristics -- it would learn feature interactions from data.

### Scenario 2: "What if someone uses an unsupported script (Thai, Japanese)?"

> **IMPACT:** Blind spot. Not matched by Indic arrays or non-Indic regex (which only checks Greek, Armenian, Georgian, Chinese, Korean). Falls to unidecode, gets garbled, triggers low similarity -> 0.33 bucket.
>
> **FIX:** Expand the regex to include Thai, Hiragana, Katakana ranges. Or better: detect ANY script that is NOT Latin and NOT one of the 10 supported Indic scripts.

### Scenario 3: "What if Lambda cold starts cause SQS message timeouts?"

> **IMPACT:** SQS visibility timeout is 30s, container cold start is ~5s. If exceeded, SQS re-queues the message, causing duplicates in Kinesis.
>
> **FIX:** Increase VisibilityTimeout to 60s. Add deduplication on follower_handle in pull.py. Use Lambda provisioned concurrency to eliminate cold starts.

### Scenario 4: "What if the name database is missing a common Indian name?"

> **IMPACT:** Low `indian_name_score`, but the overall `final_` score would still be 0.0 (REAL) if other features don't flag it. The ensemble design handles single-feature failures.
>
> **FIX:** Periodically update the database from census data. Add a surname database as a complement.

### Scenario 5: "What if someone crafts a handle to bypass all 5 features?"

> **IMPACT:** A deliberately crafted account that passes all checks IS a false negative. This is the fundamental limitation of the heuristic approach.
>
> **FIX:** v2 would add behavioral signals: follow velocity (10K followers in one hour), profile completeness, network graph analysis, and a supervised model trained on confirmed fakes.

### Scenario 6: "What if ClickHouse is down during batch extraction?"

> **IMPACT:** Entire daily batch fails.
>
> **FIX:** Add retry logic with exponential backoff (`tenacity`). Add Slack/email notifications. Keep a read replica for failover.

### Scenario 7: "What if a creator has 1 million followers?"

> **IMPACT:** 1M records at 100ms each = 28 hours sequential. With 1,000 concurrent Lambdas, ~100 seconds. Real bottleneck is SQS ingestion.
>
> **FIX:** Send 10 follower records per SQS message. Modify Lambda to process batches of 10 per invocation. Reduces invocations and API calls by 10x.

### Detection Gaps Summary

| Gap | Current Behavior | Proposed Fix |
|-----|-----------------|-------------|
| Real user with >4 digits | False positive (1.0) | Weigh against name database score |
| Unsupported scripts | Falls through to unidecode | Expand regex detection |
| Lambda cold starts | Possible SQS re-queuing | Provisioned concurrency |
| Missing names in database | Low score but ensemble compensates | Periodic database updates |
| Sophisticated fake accounts | Not detected | Add behavioral/temporal signals |
| Large creator (1M followers) | Slow processing | Batch records per Lambda |

---

## How to Speak

### Pyramid Method -- Architecture Question

**Level 1 -- Headline:**
> "It's a serverless ML pipeline that detects fake Instagram followers using a 5-feature ensemble model with multi-language NLP support."

**Level 2 -- Structure:**
> "Data flows through 4 stages. Push.py extracts follower data from ClickHouse using CTE queries, exports to S3, distributes across SQS using 8 parallel workers. Lambda picks up each record, runs the ML pipeline -- Unicode normalization, Indic script transliteration, 5-feature extraction, ensemble scoring -- and writes results to Kinesis. Pull.py reads from Kinesis shards in parallel and aggregates into the final file."

**Level 3 -- Go deep on ONE part:**
> "The most interesting part is the NLP pipeline. Indian users write names in 10 scripts. For Hindi, I built a custom transliterator with 24 vowel and 42 consonant mappings that handles nukta diacritics and consonant clusters. For the other 9 languages, I used pre-trained HMM models that do Viterbi decoding. After transliteration, weighted RapidFuzz scoring compares the handle against all name permutations."

**Level 4 -- OFFER:**
> "I can go deeper into the HMM-based transliteration, the RapidFuzz weighted scoring algorithm, or the AWS Lambda serverless architecture -- which interests you?"

### Pivot Phrases

**If they ask about ML:**
> "The ensemble combines 5 independent heuristics. Each captures a different signal -- foreign script detection via Unicode regex, digit counting with threshold, fuzzy scoring using a weighted average of 3 RapidFuzz metrics across all permutations, and a linear scan of 35,183 names with the same fuzzy formula."

**If they ask about NLP:**
> "The biggest challenge is handling 10 Indic scripts plus 13 Unicode symbol variants. Hindi Devanagari has matras, nukta dots, and halant marks for consonant clusters. The indictrans HMM models handle 9 languages; I built a custom 66-mapping lookup for Hindi."

**If they ask about AWS:**
> "5 services orchestrated together. S3 for intermediate storage. SQS with 256KB max, 4-day retention. Lambda in ECR containers for ML. Kinesis ON_DEMAND for auto-scaling output streaming. 8-worker multiprocessing for I/O parallelism."

**If they ask about data engineering:**
> "The ClickHouse query is a 5-level CTE chain: load handles from S3 CSV, map to profile IDs, extract follower data from both historical and real-time tables using JSONExtractString, union, join, deduplicate with GROUP BY. Output goes directly to S3 via ClickHouse's S3 function."

### What Would You Improve?

> "Three things. Optimize the O(35K) name scan with approximate nearest neighbor search. Add caching for repeat followers across creators. Use the scored outputs as training data for a supervised model that learns optimal thresholds automatically."
