# Deep Dives — question-level understanding docs (with Mermaid diagrams)

One detailed document per mock question: the problem in simple words → the
REASONING path (how you'd discover the solution, not just what it is) →
diagrams → worked traces → **every follow-up answered in full** → what the
interviewer writes in the debrief.

**How to use:** attempt the mock FIRST (`../mocks/`). Then — whether you
passed or failed — read the deep dive end to end. If something in a mock
"samajh nahi aaya", the deep dive is where you go. Diagrams render in
Cursor's markdown preview (⌘⇧V) and on GitHub.

## LLD (machine coding — the round that rejects most)
| Doc | Problem | Follow-ups covered |
|---|---|---|
| `lld_01_file_system.md` | File System + wildcard cd (4x) | ambiguity trace · ls · concurrency (incl. session-vs-fs cwd) · scale degrade |
| `lld_02_pubsub_broker.md` | Kafka-lite pub-sub (3x) | publish race proof · blocking poll (Condition) · retention/base offset · consumer groups · monitoring |
| `lld_03_ttl_random_store.md` | TTL store + O(1) getRandom (3x) | stale-TTL update · thread-safety races · merged expiry+random trade-off · 10M keys |
| `lld_04_parking_lot.md` | Parking lot w/ bus adjacency (2x) | strategy swap · two-gate race · O(1) availability · EV extension |
| `lld_05_splitwise.md` | Splitwise engine (2x) | SHARES split · concurrency+idempotency · fewer-txns judgment · ledger at 10M users |

## DSA
| Doc | Problem | Follow-ups covered |
|---|---|---|
| `dsa_01_dsu_logs.md` | Ride-log connectivity, DSU (3x+) | deletion (why DSU & binary search both die) · multiset rebuild · stream · unit tests |
| `dsa_02_robots_grid.md` | Robots & blockers (4x, Uber original) | Q queries · grid mutation · inverted (BFS) variant · pressure protocol |
| `dsa_03_closest_palindrome.md` | Closest palindrome (3x, bar-raiser) | sufficiency proof · k-th closest · next-palindrome variant · structural edge handling |
| `dsa_04_optimal_bst.md` | Optimal BST (2x, "toughest screening") | why-not-greedy · reconstruct tree · online updates (splay) · real-system design tail |
| `dsa_05_haunted_house.md` | Haunted house groups (3x) | output the group · non-monotonic ⇒ no binary search · streaming/segment tree · forbidden pairs |

## HLD
| Doc | Problem | Probes covered |
|---|---|---|
| `hld_01_heatmap.md` | Driver heatmap / top-K (~10x archetype) | partition-by-region why · hot cell · zoom-out cost · staleness chain · APIs · research path |
| `hld_02_uber_eats.md` | Uber Eats homepage (3x) | closes-right-now chain · ranker down · response bodies · store choices · stampede/versioned keys · TRAIN/PNR variant |
| `hld_03_stock_alerts.md` | Stock alerts / notifications (3x) | one-tick walkthrough · crossing semantics · market-crash burst · lost-vs-duplicate · % change · webhook skin |
| `hld_04_job_scheduler.md` | Distributed cron (SDE-4 loop) | double-fire lease proof · worker death · midnight spike math · push-vs-pull per hop · hung endpoint · misfire policy |

## Reading order if you're starting from zero
Pattern doc (`../learn/`) → deep dive here → reference code (`../lld/`,
`../solutions/`) → mock (`../mocks/`) → reread the deep dive's follow-ups.
