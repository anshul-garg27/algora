# Mock Kits — run a real Uber mock with ANY model

Each mock = two parts:

1. **`*_INTERVIEWER.md`** — paste its full contents into any AI chat
   (Claude, ChatGPT, Gemini, anything). The model becomes a calibrated Uber
   interviewer: it presents the problem, answers clarifying questions, refuses
   to over-help, springs the real follow-ups, and grades you on Uber's actual
   scale at the end.
2. **`*.py`** (LLD/DSA only) — the file where YOU write code, with acceptance
   tests at the bottom. HLD/HM mocks are conversation-only, no `.py`.

## Protocol (do it like the real thing)

1. Open the `.py` in your editor. Note the time, set a 45-minute alarm.
2. Paste the INTERVIEWER kit into a fresh AI chat. Say "start".
3. Ask clarifying questions in the chat FIRST (it's graded).
4. Code in the `.py`. Run `python3 <file>` — tests must print PASS.
5. At 45 min, paste your final code into the chat and say "done".
6. Answer the follow-ups live. Get your verdict + feedback.
7. Log the verdict in `../PLAN.md`, then read the matching reference in
   `../lld/` or `../solutions/` and write down the delta.

## Order (matches the 4-week plan)

| Week | Mock | Candidate file | Asked at Uber |
|---|---|---|---|
| 1 | LLD #1: File System (wildcard cd) | `lld_01_file_system.py` | 4x |
| 1 | DSA #1: Ride-log connectivity (DSU) | `dsa_01_dsu_logs.py` | 3x |
| 1 | DSA #5: Haunted House | `dsa_05_haunted_house.py` | 3x |
| 2 | LLD #2: Pub-Sub Message Broker | `lld_02_pubsub_broker.py` | 3x |
| 2 | LLD #3: TTL Store + getRandom | `lld_03_ttl_random_store.py` | 3x |
| 2 | DSA #2: Robots in Grid (Uber original) | `dsa_02_robots_grid.py` | 4x |
| 2 | LLD #4: Parking Lot | `lld_04_parking_lot.py` | 2x |
| 3 | HLD #1: Driver Heatmap / Top-K | conversation only | ~10x archetype |
| 3 | HLD #2: Uber Eats Homepage | conversation only | 3x |
| 3 | DSA #3: Closest Palindrome | `dsa_03_closest_palindrome.py` | 3x |
| 3 | DSA #4: Optimal BST (screening killer) | `dsa_04_optimal_bst.py` | 2x |
| 3 | HLD #3: Stock Alerts / Notifications | conversation only | 3x |
| 4 | LLD #5: Splitwise Engine | `lld_05_splitwise.py` | 2x |
| 4 | HLD #4: Distributed Job Scheduler | conversation only | SDE-4 loop |
| 4 | HM / Behavioral | conversation only | every loop |

Every kit also contains a **retake problem** (a different real Uber question
in the same family) — rerun the kit in a fresh chat for attempt #2:
KV-transactions, rate limiter, hit counter, alien dictionary, fire-escape,
k-th next greater, predict-the-winner, elevator, pricing calculator,
trending dishes, cart service, webhooks, rate-limiter-as-a-service,
longest-subarray-limit.
