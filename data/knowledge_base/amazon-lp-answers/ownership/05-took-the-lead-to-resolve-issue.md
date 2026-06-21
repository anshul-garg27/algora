# Q: Tell me about a time when you took the lead to resolve an issue.

> **LP**: Ownership
> **Primary story**: `G2 — Beat Scraping Engine`
> **Backup story**: `W1 — Silent Kafka Failure`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

About four months into Beat — our Python scraping engine at Good Creator Co. — we started seeing Instagram credentials get revoked. Not rate-limited. Revoked. That meant the actual API key was dead, and we'd paid for it. Within a week we lost three credentials. Each one cost us roughly a month's API budget for that provider.

### Task

I owned Beat. Nobody told me "go fix credential revocations" — there was no JIRA ticket. But I had the access logs, the credential table, and the pager. So it was on me.

### Action

I started with data, not opinions. Pulled the access logs from the past week and joined them against the credential table. The pattern jumped out — when one credential got close to its provider's per-minute limit, the worker that hit the limit kept retrying instead of falling back. Three or four retries in a 60-second window was enough to trip the provider's abuse detector. They didn't just rate-limit, they killed the key.

I had two real options. Patch the retry logic with a longer backoff, or rebuild credential selection to actively rotate before hitting limits. The patch would've been a day. The rebuild was a week. But the patch only fixed the symptom; the next provider with a stricter abuse policy would do the same thing.

I went with the rebuild. Designed credential rotation around three pieces. First, a `disabled_till` TTL on each credential — if it gets close to limit, we mark it disabled with an expiry and fall back to the next available source. Second, a priority-ordered fallback chain per fetch type — for `fetch_profile_by_handle` the order is `graphapi → arraybobo → jotucker → lama → bestsolutions`. Third, weighted random selection for follower fetching — 70% RocketAPI, 30% JoTucker based on cost-per-call.

I also stacked rate limits in front of it. Three levels backed by Redis. Daily global at 20,000/day, per-minute at 60/min, per-handle at 1/sec. Each provider got its own spec on top — `youtube138` at 850/60s, `arraybobo` at 100/30s. So even if rotation logic broke, the rate limiter caught us before the provider did.

For credentials that came from external token refresh — like the Identity service's OAuth flow — I added an AMQP listener so token refresh events updated our credential table in real time, no polling.

### Result

Zero credential revocations after the deploy. We hadn't lost a single key in the eight months I stayed at GCC after that. The system kept scraping at 10K events per second across 73 flows. About 25% faster API responses because we weren't hitting rate-limit backoff penalties as often. And the 30% cost reduction on API spend was a side effect.

The thing I'd say I learned: when the symptom is expensive (a dead $5,000 API key), don't patch the symptom. Fix the design.

---

## Technical depth — if they probe

- **Credential entity with TTL backoff**: PostgreSQL row with `credentials JSONB`, `disabled_till TIMESTAMP`, `enabled BOOLEAN`, `data_access_expired BOOLEAN`. When close to limit, set `disabled_till = now() + provider_specific_ttl`. Next selection skips it.
- **Fallback chain per fetch type**: `available_sources[fetch_type]` is a priority-ordered list. `fetch_enabled_sources()` iterates, calls `CredentialManager.get_enabled_cred(source)`, returns the first one available. Exclusions list lets the caller skip a source that just failed.
- **Stacked rate limiting**: Three nested `async with RateLimiter(...)` blocks per request. Daily, per-minute, per-handle. All Redis-backed so limits are shared across 150+ worker processes. Each provider also has a source-specific spec applied in `make_request_limited()`.
- **AMQP listener for token refresh**: `aio-pika` async consumer on `identity.dx` exchange. Identity service publishes `new_access_token_rk` events when an OAuth token rotates. Beat's `upsert_credential_from_identity` handler updates the credential row.
- **Weighted random for follower fetching**: `random.choices(weights={"rocketapi": 0.7, "jotucker": 0.3})`. RocketAPI is more reliable and slightly more expensive; JoTucker is the fallback share.

---

## Likely follow-ups

**Q: Why not just buy more API quota?**
> We were a 4-person startup. Throwing money at API quota was the lazy answer. The real problem was that our system didn't respect provider limits — quota wouldn't fix that. Rebuild was the right call.

**Q: How did you decide which providers to prioritise?**
> Three things — cost per call, reliability (success rate over 7 days), and feature coverage. GraphAPI was cheapest and most reliable for basic profile lookups so it went first. RocketAPI was the only one that did `fetch_reels_posts` reliably so it was top for that flow.

**Q: What if all providers are limited at once?**
> The crawler raises `NoAvailableSources`. The task is marked `FAILED` with the reason, retry count increments, and the SQL queue retries after backoff. We never block the queue or burn the credential.

**Q: Did you build this alone?**
> The credential rotation design and rate limiter were mine. A senior engineer reviewed the design before I started — caught one issue with my initial weighting (I had it as a hardcoded if/else, he pushed me to use `random.choices` with a config dict so we could tune weights without code changes).

**Q: How did you know it was working?**
> Two signals. Zero new revocations after the deploy — that was the binary check. And the daily API spend dashboard dropped about 30% in the first month because we stopped paying for retries on already-limited credentials.

---

## What NOT to say

- Don't call rate-limited credentials "revoked" — they're separate. Rate limited = temporarily can't use, revoked = permanently dead. The bug was the second turning into the first.
- Don't claim I designed `indic-trans` or trained ML models — that was a different project. This one was infrastructure.
- Don't say "we used Celery" — Beat was custom multiprocessing + asyncio with a SQL task queue, not Celery.
- Avoid "I optimized everything" — this was specifically about credential lifecycle and rate limiting.

---

## Backup story (if asked for another)

W1 — the silent Kafka failure. About six weeks into our GCS sink running, I noticed GCS had stopped receiving data. No alerts. Spent five days digging through SMT NPEs, KEDA rebalance storms, and JVM heap exhaustion. Shipped fixes across PRs #35, #42, #57, #61. Zero data loss because Kafka retention saved us. Wrote a runbook that two other teams used afterwards.
