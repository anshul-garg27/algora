# Q: Describe your working style.

> **LP**: Intro & Closers
> **Primary story**: G1 — ClickHouse migration (deep, async, documented)
> **Backup story**: W1 — Silent Kafka Failure
> **Time budget**: 60–75 seconds spoken

---

## The spoken answer

Three things describe how I actually work, day-to-day.

**One — I write things down before I build them.** Not big design docs. Short notes. For the ClickHouse migration at GCC, the first artifact wasn't code, it was a half-page in our Confluence — current pain, the two options I'd considered, why ClickHouse won, and the rollback plan. That doc saved me twice when the team lead asked "wait, why aren't we just sharding Postgres?" — the answer was already written down.

**Two — I work async by default, sync when stuck.** I batch my deep work in 2 to 3 hour blocks, no Slack, no email. When I get stuck — really stuck, not "this is hard" stuck — I jump on a 15-minute call instead of typing back and forth for an hour. The rule I follow is: if a problem needs more than two Slack messages to explain, it needs a call.

**Three — I ship in small slices.** Even on the audit-logging platform, which was a multi-month build, I shipped the publisher in week one with no consumers wired in, then the GCS sink in week two, then the BigQuery integration in week three. Each piece could be tested in isolation. I'd rather have three small PRs reviewed than one 3,000-line PR sitting for a week.

The shorthand version — I'm a write-then-build, deep-block, small-PRs kind of engineer. I'm not the engineer who jumps on every alert at midnight. I'm the engineer who builds the alert so nobody has to.

---

## Why this works

- **Three concrete habits**, each with a real example. Not "I'm a team player" or "I'm detail-oriented".
- The closing line — "I'm the engineer who builds the alert so nobody has to" — gives them a memorable frame for who you are.
- You signal **maturity** (async by default), **clarity** (write before build), and **discipline** (small slices) without using any of those words.
- The G1 ClickHouse reference plants a hook — they often ask about it next.

---

## Technical depth — if they probe

- **Write-then-build evidence**: the half-page doc for the Postgres→ClickHouse migration named the RabbitMQ buffered sinker (1000 records/batch), the dual-write window (2 weeks), and the cutover plan. When a senior engineer at design review challenged the sinker batch size, the doc had the math — Kafka would've been 3x the cost for our query pattern.
- **Async-first evidence**: at Walmart, I share a "going deep on X for 2 hours" message in the team channel before tunnelling. It saves me from getting interrupted *and* it gives teammates a heads-up if they had context.
- **Small slices evidence**: 87 PRs on the audit-logging GCS sink alone. Average PR ~150 lines. Largest single PR was the Spring Boot 3 migration at 158 files — and even there I split out the test-only changes into a separate PR.

---

## Likely follow-ups

**Q: How do you handle being interrupted in deep-work blocks?**
> The team channel ping covers the predictable case. For unpredictable interrupts — page, urgent question — I take them, but I add a 10-minute "context restore" buffer before going back to deep work. I learned not to fight the interrupt, just account for it.

**Q: What if a teammate prefers sync collaboration?**
> Then we pair. I adapt. The default-async thing is a personal default, not a team rule. The junior I'm mentoring is more comfortable in calls than in writing, so we pair on whiteboards a lot. The async habit is mine, the working style of the pair is whatever works for the pair.

**Q: How do you handle 24/7 on-call?**
> I take it seriously — at Walmart I'm on rotation. But the goal of being on-call is to make on-call boring. Every page that fired during my rotations turned into either a runbook entry, a new alert with better thresholds, or a code fix. The silent Kafka failure incident was the biggest one — I wrote the runbook that's been used twice since.

**Q: What if leadership wants daily stand-ups and lots of meetings?**
> I'll do them. I'm not religious about async. But I'll push back gently if I see a 30-minute meeting on the calendar that could've been three Slack messages and a doc link. The push-back is collegial, not confrontational.

**Q: What kind of feedback do you give in code review?**
> Specific and quick. I aim for first response within 4 hours during working hours. I separate must-fix from nit explicitly — "blocking" vs "nit" tags in my comments. And I pair on the response when it's a junior's PR — the comment is the headline, the pairing is where the real teaching happens.

---

## What NOT to say

- Don't say "I'm flexible" — that's filler. Describe your actual default.
- Don't pretend you love meetings if you don't. Hiring managers can usually tell.
- Don't claim you "thrive under pressure" — every candidate says that, and the question wasn't about pressure.
- Don't make it sound like you don't collaborate. The async default has to come with the "sync when stuck" rule attached.
- Don't ramble past 75 seconds. Three habits, one closing line, done.

---

## Spoken-vs-written delivery note

- Number the three habits out loud — "One...", "Two...", "Three..." — gives the listener a clear structure.
- Slow down on the closing line — "I'm not the engineer who jumps on every alert at midnight. I'm the engineer who builds the alert so nobody has to." It's the punchline.
- The G1 doc reference should sound like a memory, not a citation. "For the ClickHouse migration..." is the right opener.
