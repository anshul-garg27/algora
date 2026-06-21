# Fake Follower Detection ML System - Complete Interview Guide

> **Resume Bullet Covered:** Bullet 7 - "Automated content filtering and elevated data processing speed by 50%"
> **Company:** Good Creator Co. (GCC) - Influencer analytics platform
> **Repo:** `fake_follower_analysis`

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [01-technical-implementation.md](./01-technical-implementation.md) | Full code walkthrough: 5-feature ensemble, transliteration, AWS pipeline |
| [02-technical-decisions.md](./02-technical-decisions.md) | 10 "Why X not Y?" decisions with follow-ups |
| [03-interview-qa.md](./03-interview-qa.md) | Q&A bank covering ML, NLP, AWS, serverless |
| [04-how-to-speak.md](./04-how-to-speak.md) | Speaking guide with pitches, stories, pivots |
| [05-scenario-questions.md](./05-scenario-questions.md) | 10 "What if?" scenario questions |

---

## 30-Second Pitch

> "At GCC, I built an ML-powered fake follower detection system for Instagram analytics. The core challenge was that Indian users write names in 10 different scripts - Hindi, Bengali, Tamil, Urdu, and more - so you can't just string-match a handle against a name. I built a 5-feature ensemble model that transliterates Indic scripts to English using HMM-based ML models, does weighted fuzzy matching with RapidFuzz, validates against a 35,000-name Indian name database, and detects bot patterns like non-Indic scripts and excessive digits. The whole thing runs on a serverless AWS Lambda pipeline with SQS and Kinesis, processing followers 50% faster than the previous approach."

---

## Key Numbers to Memorize

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

---

## Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: DATA EXTRACTION (push.py)                                         │
│  ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐       │
│  │  ClickHouse DB  │ →  │  S3 JSON Export  │ →  │  Local Download  │       │
│  │  CTE Queries    │    │  JSONEachRow     │    │  10K line batches│       │
│  └─────────────────┘    └──────────────────┘    └──────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                         8-worker multiprocessing
                                    │
                                    v
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: MESSAGE DISTRIBUTION (push.py)                                    │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │  SQS Queue: creator_follower_in                              │           │
│  │  256KB max | 4-day retention | 30s visibility timeout        │           │
│  └──────────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                          SQS Event Trigger
                                    │
                                    v
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: ML PROCESSING (fake.py in AWS Lambda ECR Container)               │
│  ┌───────────────┐  ┌──────────────────┐  ┌───────────────────────┐        │
│  │ 13 Unicode    │→ │ 10 Indic Script  │→ │ 5-Feature Ensemble    │        │
│  │ Symbol Norm   │  │ Transliteration  │  │ Model Scoring         │        │
│  └───────────────┘  └──────────────────┘  └───────────────────────┘        │
│                                                                             │
│  Features: Language | Digits | Special Chars | Fuzzy Match | Name DB        │
│  Output: 0.0 (REAL) | 0.33 (WEAK FAKE) | 1.0 (FAKE)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                          Kinesis put_record
                                    │
                                    v
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 4: RESULTS AGGREGATION (pull.py)                                     │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │  Kinesis Stream: creator_out (ON_DEMAND auto-scaling)        │           │
│  │  → Multi-shard parallel read → JSON output file              │           │
│  └──────────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ML Pipeline Diagram

```
INPUT: {follower_handle, follower_full_name}
                    |
     +--------------+--------------+
     |                             |
     v                             v
 HANDLE PATH                   NAME PATH
 clean_handle()                symbol_name_convert() [13 Unicode variants]
 - Remove _-. → space               |
 - Remove digits                     v
 - Remove special chars         check_lang_other_than_indic()
 - Lowercase                    [Greek, Armenian, Chinese, Korean]
     |                               |
     |                               v
     |                          detect_language() → process_word() [Hindi]
     |                                           → Transliterator() [9 others]
     |                               |
     |                               v
     |                          uni_decode() → ASCII normalization
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
         process1() → Binary (0/1/2)
         final()    → Weighted (0.0 / 0.33 / 1.0)
                    |
                    v
         OUTPUT: 16-field response
```

---

## Top 5 Interview Questions

### 1. "Tell me about an ML system you built"
> Use the 90-second pitch above. Focus on the NLP complexity of 10 Indic scripts.

### 2. "Why 5 heuristic features instead of a neural network?"
> Domain-specific rules are more interpretable and debuggable for this problem. Each feature catches a different bot pattern. No labeled training data was available.

### 3. "How do you handle multilingual text?"
> HMM-based ML models for 10 Indic scripts via indictrans library. Custom Hindi transliteration using svar/vyanjan CSV mappings for better accuracy.

### 4. "How did you achieve the 50% speed improvement?"
> Serverless Lambda auto-scaling + 8-worker multiprocessing for SQS ingestion + ON_DEMAND Kinesis auto-scaling + batch processing in 10K chunks.

### 5. "What's the accuracy of your model?"
> Three confidence levels instead of binary. 1.0 catches definite fakes (foreign scripts, excessive digits). 0.33 flags suspicious accounts. 0.0 is default real. The ensemble approach means each feature independently catches different bot patterns.

---

## Technology Stack

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

## Files in This Folder

```
12-gcc-fake-follower-ml/
├── README.md                          # This file
├── 01-technical-implementation.md     # Full code walkthrough
├── 02-technical-decisions.md          # 10 "Why X not Y?" decisions
├── 03-interview-qa.md                 # Q&A bank
├── 04-how-to-speak.md                 # Speaking guide with pitches
└── 05-scenario-questions.md           # 10 "What if?" scenarios
```

---

*Last Updated: February 2026*
