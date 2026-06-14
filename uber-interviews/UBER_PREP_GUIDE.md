# Uber Interview Prep Guide — What the Last 12 Months Actually Show

*Synthesized from 44 EngineBogie experiences (Jun 2025 – Jun 2026, 12 offers / 32 rejections)
plus ~130 LeetCode Discuss posts from the same window. Generated 2026-06-10.*

---

## 1. The Process (know the shape before the content)

A full SDE-1/SDE-2/Senior loop in India looks like this, almost without exception:

| Stage | Format | Notes |
|---|---|---|
| **OA** | CodeSignal/HackerRank, 65–90 min, 2–4 problems, camera-proctored | Medium–Hard. Juniors: pure elimination ("disqualification round"). ~3/4 solved is the typical bar. |
| **BPS / Screening** | 60 min, 1 Medium-Hard DSA (sometimes + short design chat) | Elimination. Officially "Business Phone Screen". |
| **Onsite: DSA ×1–2** | 45 min each | Working code + all test cases + complexity. Follow-ups guaranteed. |
| **Onsite: Machine Coding / LLD** | 45 min, often on HackerRank | **Runnable** code expected, not just class diagrams. Concurrency follow-ups common. |
| **Onsite: HLD** | 45–60 min | SDE-2 and above. Often led by Staff engineer or run as Bar Raiser. |
| **HM / Managerial** | 30–105 min | STAR-style behavioral + past-project architecture deep dive. Can turn fully technical. |

**Process facts to internalize:**
- **Strict timeboxes.** Multiple reports: "they won't go even a minute beyond the allocated 45 minutes."
- **Verdict mechanics:** rounds are graded Strong Hire / Hire / Lean Hire / No. One candidate with all-YES but no Strong-YES was rejected: *"needed at least one Strong YES."* "Borderline hire" → team-matching limbo.
- **Hiring drives** compress the whole onsite into one day (9 AM–6 PM).
- **Reschedules and ghosting are normal** (one senior was rescheduled 5–6 times; several report week-long silences). Follow up politely; don't read meaning into delays.
- A **practice link** for the interview platform is shared beforehand — actually use it.

---

## 2. DSA — what actually repeats (highest signal section)

Uber re-uses a small pool of questions with skins ("riders", "drivers", "hubs", "zones"). These exact problems appeared **multiple times in the last 12 months**:

### Tier 1 — asked 3+ times, prepare cold
| Problem | Pattern |
|---|---|
| **Closest Palindrome to N** (LC 564) + variants (next palindrome > N, min appends to make palindrome) | Math/casework on digits |
| **Alien Dictionary** (LC 269) + Course Schedule I/II | Topological sort |
| **Robots in a Grid — blocker distance query** (Uber original, repeated since 2024) | Grid prefix distances / simulation |
| **Earliest time network fully connected from logs** + follow-up with *cancellation/edge deletion* | **DSU** (and thinking about deletions) |
| **Haunted House — max group size with [L,R] constraints** (HackerRank original) | Sorting + greedy/binary search |
| **File System (mkdir/cd/pwd) with wildcard** | N-ary tree + parsing (LLD-flavored DSA) |
| **Hit Counter / sliding-window Counter class (last 5 min)** + TTL KV store + O(1) insert/delete/getRandom (+ thread-safe variant) | Data-structure design |

### Tier 2 — asked twice
- **Optimal BST from words + frequencies** (interval DP) — screening round, Nov 2025 & May 2026, called "toughest round"
- **Predict the Winner / Optimal Game Strategy** (minimax DP)
- **Minimum Edge Reversals so every node reachable** (re-rooting on tree)
- **Minimum Time to Reach Exit before Fire Spreads** (multi-source BFS + binary search on answer)
- **Sorted Squares reorder + k-th by magnitude follow-up** (two pointers → binary search)
- **Longest Subarray with |diff| ≤ limit** (sliding window + monotonic deques)
- **Minimum Path Sum** (grid DP), **Min Cost to Connect Hubs** `min(|dx|,|dy|)` (MST with edge reduction + DSU)
- **Thief→Bank path avoiding police patrol radius k** (multi-source BFS preprocessing; follow-up: per-station radius)
- **Making a Large Island / Number of Islands II** (DSU again)
- **K-th Next Greater Element indices** (monotonic structures, hard)
- **Microservice start cycles** (BFS-ish dependency simulation)

### Pattern frequency (what to drill, in order)
1. **Graphs**: DSU/Union-Find (by far #1), multi-source BFS, topological sort, Dijkstra/weighted BFS (currency conversion), tree diameter/radius, re-rooting
2. **Grids with Uber skins**: shortest path with constraints, spreading processes (fire/virus/oranges), spatial queries
3. **Heaps / Top-K / streaming**: top-K frequent items in a stream comes up in DSA *and* HLD
4. **Monotonic stack/deque + sliding window**
5. **DP**: interval (OBST), game theory (minimax), grid, DP-on-trees
6. **Palindromes & digit math**
7. **Design-a-data-structure**: time-windowed counters, TTL stores, schedulers, seat allocation (LC 855-style "UberShuttle")
8. **String parsing**: calculator/expression evaluation (`add(3, sub(3,2))`), word search/ladder/break, tries

### How DSA rounds are judged (from candidate feedback)
- **Brute force → optimize out loud.** Interviewers actively push toward optimal; one candidate noted the interviewer wanted optimal *before* baseline code — state your target complexity early.
- **Pick the right algorithm class.** A candidate solved Word Ladder with DFS+DP, all tests passed — **still got negative feedback** (shortest path ⇒ BFS). The algorithm choice is graded, not just the output.
- **Run the code.** Interviewers make you execute against sample tests; "production" follow-ups ("what unit tests? what breaks in prod?") appear even in DSA rounds.
- **Approach > completion (sometimes).** Offers were given with incomplete code where the approach and communication were crisp; intern offer note: "clarity of thought and communication valued more than perfect code."

---

## 3. Machine Coding / LLD — **the #1 rejection round**

This is where the most "everything else positive, but..." rejections happened (an SDE-1 with strong DSA + behavioral feedback was cut purely on LLD; an SSE with 3 good DSA rounds failed machine coding; "100+ interviews" poster fell at Uber's round 3 = LLD).

**Repeated problems (last 12 months):**
- **File System APIs (mkdir, cd, pwd) + wildcard `cd`** — 4×, current favorite
- **In-memory Kafka / topic-based pub-sub message broker, multi-threaded, with offset replay** — 3×
- **Meeting/conference-room scheduler (`canSchedule`, min rooms)** — 3×
- **Parking Lot** — still asked (intern + SDE-1 loops)
- **Vending Machine** — 2×
- **TTL key-value store with active counts**, **O(1) getRandom (+ thread-safe)**, **Hit Counter**
- Others seen once: Splitwise LLD, movie rating system with critic weightage, voter management, Connect Four, train platform manager, collaborative editor (Google Docs), Uber Eats **pricing calculator**, car/flight reservation, instagram LLD ("production-ready code with sample tests + concurrency" expected)
- **Multithreading specials**: print 0-even-odd with 3 threads, two-tier cache refresh (single-flight per instance), task executor with `blockUntilComplete`

**The bar:**
1. **Working, runnable code in ~45 minutes** — bare-bones working beats elaborate incomplete. Budget: ~10 min requirements/class sketch, ~25 min core code, ~10 min edge cases/tests.
2. **OOP + a design pattern where natural** (strategy, factory, observer), clean entity boundaries.
3. **Concurrency follow-up is near-guaranteed** for SDE-2+: thread-safety of your store, locks vs concurrent collections, single-flight refresh.
4. Practice in a **plain editor/HackerRank-style environment** with no IDE autocomplete, in your strongest language, with a memorized skeleton (how you do enums, interfaces, maps-of-queues, `synchronized`/mutex idioms) so zero time is lost on boilerplate.

---

## 4. HLD / System Design (SDE-2 and above)

**Recurring archetypes — 80% of last year's questions fall in these five buckets:**

1. **Real-time aggregation / Top-K / trending / heatmap** *(the Uber favorite — ~10 occurrences)*
   - Driver location heatmap (geohash, per-minute buckets, 20-min real-time view + 24h batch view)
   - Top-K heavy hitters in a stream; trending dishes/posts dashboards; restaurant order metrics (1h/1d/1w windows); e-commerce popularity ranking; real-time monitoring system (push vs pull, TSDB, 5/10-min windows)
   - **Drill**: count-min sketch vs exact counts, stream processing (Kafka + Flink-style), windowed aggregation, Redis sorted sets, geohashing, hot-partition handling
2. **Food delivery domain** (it's Uber — expect an Uber Eats skin)
   - Uber Eats homepage (2×, incl. "for train travelers" PNR variant), Zomato/Swiggy clone, cart management service, nearby restaurants (Yelp-style geo search)
3. **Notification / alerting / webhooks**
   - Stock price alerts, generic notification fan-out service, webhook delivery
4. **Messaging & infra**
   - Kafka-like distributed broker (partitions, replication, WAL, consumer groups), distributed cron/job scheduler (100M tasks/day), chat app
5. **Misc**: Splitwise (+ debt-simplification graph discussion), recommendation system, live cricket scores (Cricbuzz), config-driven UI/BFF (frontend track), Android SDK design (mobile track)

**How it's graded (explicit feedback from rejections):**
- A senior candidate gave technically deep answers and was rejected for **"not asking enough clarifying questions at the start."** Spend the first 5–10 minutes on functional/non-functional requirements and scale numbers, *visibly*.
- Interviewers ask for **concrete API signatures** (path, request body, response), **schema design**, and **database choice justification** — not just boxes.
- Expect deep dives: sharding/partitioning strategy, caching layers and extensibility, consistency trade-offs, failure handling.
- HM/Bar-Raiser rounds can morph into HLD — one L4's "behavioral" HM round was entirely HLD + language internals.

---

## 5. Hiring Manager / Behavioral

**The single most-asked question across the entire dataset (6×): "Walk me through the design/architecture of your past project."** Treat your own project as a system design interview: components, interactions, key decisions, trade-offs, challenges, your specific contribution, measurable impact.

Other repeats: conflict within/across team (4×), why leave / why Uber (4×), cross-team collaboration (2×), end-to-end delivery approach (2×), proudest project (2×), ownership beyond your role, mentoring someone, learning a new technology, prioritizing conflicting deadlines, inclusive environment, "heart or head person?", code-quality habits.

**What works (from offer-getters):**
- One successful SDE-2 spent two days building a **"Work Document"** mapping every project to STAR (Situation-Task-Action-Result) before the managerial round — directly credited it for the offer. CARL (Context-Action-Result-Learning) also referenced.
- **Don't fabricate** — a candidate's explicit tip: "don't lie or make up an answer, be honest."
- Every round matters: one SDE-2 cleared all tech rounds, treated behavioral casually, got a rare *second* behavioral round, and was rejected ("lacked design experience" feedback). HM is a real elimination round at Uber, not a chat.
- Uber leans on ownership/"go-getter" framing and situational ("what would you do if…") prompts.

---

## 6. OA specifics (junior roles live or die here)

- **Format:** 70 min/4Q (CodeSignal GCA-style, 300 pts each) or 65–90 min/3Q (HackerRank). Scores like 556/600 passed; "solved 3 of 4" is the working bar. Camera + strict proctoring.
- **Question mix:** Q1 easy implementation; Q2–Q3 implementation-heavy strings/arrays (spiral matrix sums, vowel-consonant sorting, command parsing); last question genuinely hard (segment-tree/monotonic/k-th next greater, MST with edge reduction, GCD-clustering with SPF sieve, DSU).
- **Strategy posts agree:** the penultimate/last question is the time sink — bank the easy ones first, return to the hard one. Speed of implementation matters as much as algorithms; practice typing out clean brute-force fast.
- Note: OA repeats too — the city-hubs MST, GCD zone clusters, and k-th-next-greater set appeared in *multiple* candidates' OAs across months.

---

## 7. Kya dhyan rakhna hai — the checklist

**Before the loop**
- [ ] Drill the Tier-1 question list above until they're reflex.
- [ ] 5–6 timed 45-min machine-coding reps (file system, pub-sub broker, scheduler, parking lot, TTL store) with **runnable** code + a concurrency pass on each.
- [ ] Prepare the 5 HLD archetypes; for each: requirements → estimates → APIs (with bodies) → schema → architecture → 2 deep dives.
- [ ] Build your STAR Work Document + rehearse your past-project architecture walkthrough (it *will* be asked).
- [ ] Practice on the actual platform (CodeSignal/HackerRank multi-file) via the practice link.

**During every round**
- [ ] Ask clarifying questions out loud before solving — it is explicitly scored.
- [ ] State brute force + its complexity, announce the optimal target, then code.
- [ ] Shortest-path smell ⇒ BFS/Dijkstra, not DFS. Choose the canonical algorithm.
- [ ] Watch the clock: working subset > perfect fragment. Leave 10 min for edge cases/tests.
- [ ] Expect the follow-up: k-th variant, deletion variant, streaming variant, thread-safe variant, "what if N lists / 10M days of data."
- [ ] Complexity analysis unprompted, every time.

**Mindset / logistics**
- [ ] One Strong Hire somewhere in the loop matters more than uniform "fine" — pick your strongest round and over-deliver there.
- [ ] Reschedules/ghosting ≠ rejection. Follow up after ~1 week, stay warm.
- [ ] Same-day drives are marathons — eat, and don't let round 1 mood bleed into round 2.
- [ ] Rejected? Cooldown exists but reapplication works — multiple offer-getters were on attempt #2/#3 (one cleared on the 3rd L4 attempt).

---

## 8. Suggested 4-week plan (SDE-2 target)

| Week | Focus |
|---|---|
| **1** | Tier-1/Tier-2 DSA list + DSU/BFS/topo-sort drills; 1 OA simulation (70 min, 4Q) |
| **2** | Machine coding: file system, pub-sub broker, meeting scheduler, TTL store, parking lot — all timed, all runnable; concurrency idioms in your language |
| **3** | HLD: heatmap/top-K, Uber Eats, notifications, job scheduler, Kafka-lite — one per day, written out end-to-end; mock with a friend, practice *asking requirements first* |
| **4** | Behavioral Work Document + project-architecture walkthrough; 2 full mock loops; second OA simulation; review weak spots |

*Data sources: `data.json` in this folder (655 questions; filter Source = EngineBogie for verified loop data, Newest sort for freshness), enginebogie.com experience pages, leetcode.com/discuss Uber tag.*
