# Q: How do you use Generative AI tools in your day-to-day coding or work?

> **LP**: Learn and Be Curious
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `G6 — Fake-Follower ML`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

April 2025. I was leading the Spring Boot 2.7 to 3.2 migration on cp-nrti-apis — our main supplier API service. 158 files to touch, 74 of them needed `javax.*` to `jakarta.*` import changes, 42 test files needed WebClient mock rewrites. Snyk was already flagging CVEs we couldn't patch without upgrading. Four weeks was the budget.

### Task

Use AI tools — mainly Claude Code and Copilot — to absorb the mechanical work so I could spend my brain on the decisions that mattered.

### Action

I split the work into three buckets: mechanical, semi-mechanical, and judgement.

For the mechanical bucket — `javax.persistence` to `jakarta.persistence` across 74 files — I had Claude generate a Python script that walked directories, did the rename, and produced a side file of "imports where the class behaviour also changed." That side file was 11 files — mostly servlet filters where method signatures shifted in Spring 6. I read each of those by hand. The other 63 were pure rename, verified by compile.

For the semi-mechanical bucket — 42 test files updating from RestTemplate mocks to WebClient mocks. WebClient mocking is a chain of five builders: `webClient.get().uri().headers().retrieve().bodyToMono()`. I asked Claude to generate the mock skeleton, then I read every generated line. Twice I caught it inventing methods that don't exist on the WebClient API — once it used `.body()` instead of `.bodyValue()`. If I'd trusted the output, those tests would have failed CI in a confusing way.

For the judgement bucket — the `.block()` versus full reactive call — I did not use AI. That was a 1:1 with my team lead, prepared with my own analysis: 4 weeks framework-only versus 3 months full reactive, team readiness, scope risk. I chose `.block()`. AI could have given me a list, but the framing — that this was a framework upgrade, not an architecture change — was something I had to own.

The other AI use that mattered: after the migration shipped, we had a heap OOM about six months later. I pasted the heap dump summary into Claude and asked "what classes typically leak under WebClient load." It pointed at HTTP connection pool issues. That hypothesis was right — PR #1528 fixed it with try-with-resources.

### Result

The migration shipped in 4 weeks. 158 files changed, zero customer-impacting issues. I'd say AI cut about 5 days off the mechanical work and gave me a faster path on debugging. But the decisions — `.block()`, canary strategy, 1 week in stage — those stayed mine. The honest summary is AI helped me move faster on what I already knew how to do.

---

## Technical depth — if they probe

- **Claude Code workflow**: terminal-resident agent that can edit multiple files in one pass. I use it for refactors with a clear pattern and a clear stop condition.
- **The mocking trap**: WebClient mocks must match the real fluent API exactly. AI sometimes hallucinates method names. I always run the test against a real WireMock server before trusting the mock.
- **What I won't paste into a hosted model**: anything with real DUNS numbers, supplier identifiers, or auth tokens. Walmart has internal AI endpoints for those — I use them.
- **Where AI hurts juniors**: copy-paste without reading. I tell my junior on the IAM project — explain every line in your PR, even the ones the tool wrote.

---

## Likely follow-ups

**Q: One thing AI got wrong during the SB3 migration?**
> The PostgreSQL enum mapping. It suggested `@JdbcTypeCode(SqlTypes.VARCHAR)`. The right answer is `SqlTypes.NAMED_ENUM`. The VARCHAR version compiled and passed H2 unit tests but failed in our stage environment against real PostgreSQL. That's why we kept a 1-week stage soak.

**Q: How do you stop AI from shipping subtle bugs?**
> Three habits: read every generated line, test against the real downstream (not just mocks), and require code review to question anything AI-shaped. A reviewer asking "why is this here" is the cheapest defence.

**Q: Do you use it for system design?**
> For first-draft brainstorming, yes. Then I throw the draft away and write it myself. AI tends to give safe textbook answers — those are useful as a sanity check, not as the final design.

**Q: What's your favourite use?**
> Runbook drafting. After incidents, AI is great at producing a first-cut post-mortem with sections in the right order. I rewrite the content, but the scaffolding saves real time.

---

## What NOT to say

- Don't claim AI tools wrote the migration. They wrote ~5 days of mechanical work in a 4-week project.
- Don't list every tool — pick the two or three I actually use.
- Don't pretend I always catch AI errors. I've shipped AI-influenced bugs. The fix was tighter review habits.

---

## Backup story (if asked for another)

For the GCC fake-follower ML system, I leaned on AI for the regex work — building Unicode pattern matchers for 10 Indic scripts. Each script has its own Unicode range, and writing those by hand is error-prone. I'd ask Claude to draft the range, then test it against real Bengali, Tamil, and Devanagari names I had in my test set. Caught it twice missing Urdu ligatures. The lesson there was the same: AI gives you 80%, and the last 20% is where the real engineering lives.
