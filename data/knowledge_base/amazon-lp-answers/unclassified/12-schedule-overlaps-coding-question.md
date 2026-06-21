# Q: How would you calculate schedule overlaps if each course has different timings on different days of the week?

> **LP**: Unclassified (technical / coding question, redirect back to behavioural)
> **Primary story**: None — this is a technical question
> **Backup story**: W8 — DC Inventory Search API (if they want a related work example)
> **Time budget**: 60 seconds technical + 30 seconds redirect

---

## How to read this question

This is a **technical mini-question** that sometimes drops into hiring-manager rounds. They're testing whether you can think on your feet about a small algorithm — not asking for a coded solution on paper.

Two moves to make:

1. **Give a clean, structured answer in 60 seconds.** Show you can think about data structures and edge cases.
2. **Redirect to a real example** of a similar pattern from your actual work — even better if you can connect it to W8 (DC inventory bulk-search) which has a similar "match this against that" shape.

---

## The spoken answer (60 seconds technical)

I'd model each course session as a tuple — `(day_of_week, start_time, end_time)`. A course with classes Monday 10–11 AM and Wednesday 2–3 PM becomes two tuples.

Flatten all courses into one big list of `(day, start, end, course_id)` tuples. Group by day. Within each day, sort by `start`. Then sweep the sorted list and check if the current session's `start` is before the previous session's `end` — that's an overlap.

For the runtime — if there are N total sessions across all courses, the sort dominates at O(N log N). The sweep is linear. Memory is O(N) for the flattened list.

Two edge cases I'd ask about. **One** — back-to-back sessions: does 11 AM end conflict with 11 AM start? Usually no, but I'd confirm with the requirement. **Two** — sessions crossing midnight (rare but real for some adult-education systems). I'd model them as two separate tuples splitting at midnight if needed.

If the use case is "show all overlaps for one course against everything else", I'd build a lookup keyed by day — `dict[day] -> sorted list of (start, end, course_id)` — and binary-search for the candidate sessions to check against. That gets per-query lookup down to O(log N + K) where K is the number of overlaps for that course.

That's the shape. I can write the code if you'd like.

---

## The 30-second redirect

A nearby example from real work — at Walmart I built a DC Inventory bulk-search API. Same shape: a supplier sends up to 100 GTINs, and we have to match each one against three internal sources — a GTIN→CID lookup, a supplier-authorisation table, and the EI inventory API. The data structures and the "match this against that" sweep aren't the same as schedule overlap, but the pattern is — group, sort, sweep, check. I used `CompletableFuture.allOf` to parallelise the three lookups and got query time down 40 percent.

Happy to go deeper into either the schedule problem or the DC Inventory API.

---

## Why this works

- **Clean structure** — model, flatten, group, sort, sweep. Five words, five steps.
- **Edge cases named** — back-to-back, midnight crossings — without diving into a code rabbit hole.
- **Runtime called out** — O(N log N), O(N) memory. Signals you think about complexity.
- **Redirect bridges to real work** — W8 isn't the same problem, but the data-modelling instinct is the same, and you control the conversation back to a story you have depth on.

---

## Technical depth — if they probe

- **Sweep line algorithm**: classic interval-overlap pattern. Sort intervals by start time, sweep left-to-right, maintain a running `max_end_seen`. If current `start < max_end_seen`, overlap exists.
- **Per-day grouping**: schedule overlap is fundamentally a per-day problem (Monday's classes don't conflict with Tuesday's). Grouping by day cuts the per-group `N` and lets the sort+sweep scale linearly in the worst case (one day with all sessions).
- **For "find overlaps with a specific course"**: precompute the per-day sorted list. For each session of the query course, binary-search the day's list for the position where this session would insert. The conflicting sessions are the immediate neighbours plus any further ones whose `start < this.end`. O(log N + K).
- **For a streaming/online version**: an interval tree (augmented BST keyed on start, with each node tracking subtree max-end) supports O(log N) insert and O(log N + K) overlap query. Overkill for a static schedule, useful if courses are added incrementally.

---

## Likely follow-ups

**Q: What if there are 10,000 courses with 100,000 sessions each?**
> The flatten-and-sort is still O(N log N) — that's a billion sessions, sortable on a single machine but slow. I'd partition by day first (max 7 partitions), then sort each in parallel. Or if it's a periodic compute, I'd run it as a Spark or Beam job grouping by `day_of_week`.

**Q: How would you persist this in a database?**
> Two tables. `course(id, name)` and `session(course_id, day_of_week, start_time, end_time)`. Index on `(day_of_week, start_time)` so the per-day sweep is a single index scan. Overlap query becomes a self-join with `s1.start_time < s2.end_time AND s1.end_time > s2.start_time AND s1.day = s2.day`.

**Q: What if start and end times are stored as text like "10:30 AM"?**
> First thing — convert to minutes-from-midnight as integers on read. Comparing strings on "10:30 AM" vs "10:30 PM" lexically is a bug factory. Either store as `time` type (Postgres), or as `int minutes_from_midnight`.

**Q: Can you sketch the code?**
> Sure. Pseudocode: `sessions = [(day, start, end, id) for course in courses for (day, start, end) in course.sessions]; by_day = groupby(sessions, key=day); for day, group in by_day: sort group by start; sweep with max_end_seen; emit overlap when start < max_end_seen`. Real code would be 15–20 lines in Python.

**Q: How does this connect to your Walmart work?**
> The closest is the DC Inventory bulk-search — same "group, sort, match" pattern across 100 GTINs and three internal data sources. Different problem, same data-modelling reflex. The reflex is: model the entity, normalise to a uniform tuple, group by the natural axis, then sweep.

---

## What NOT to say

- Don't try to write production-ready code on the spot. They asked for an approach, not a binary.
- Don't go past 60 seconds on the technical part. The redirect is where you reclaim time.
- Don't fake confidence on edge cases you haven't thought about. "I'd ask about back-to-back sessions" is the right level.
- Don't pretend the schedule problem is what you did at Walmart. Acknowledge it's a different problem, then bridge to the shape that's similar.

---

## Backup story (W8 — DC Inventory Search API)

The closest production-shape match. Bulk-search API where suppliers send up to 100 GTINs, each matched against a GTIN→CID lookup (UberKey API), supplier authorisation (PostgreSQL `supplier_gtin_items` table with index on `site_id, gtin, global_duns`), and DC inventory state (EI internal API). Parallelised with `CompletableFuture.allOf`, 40% latency reduction. The matching pattern — "for each input, look up across three sources" — is structurally similar to "for each schedule, find overlaps across days". Different problem, same data-modelling instinct.

---

## Spoken-vs-written delivery note

- Stay calm. They're testing how you think under a small surprise, not your algorithm chops.
- Slow down on the data model — "I'd model each course session as a tuple". Get that right and the rest flows.
- The redirect should sound natural, not like you're escaping the question. "A nearby example from real work..." is the right framing.
- Total: 60 + 30. If you've gone over 90 seconds, you've gold-plated.
