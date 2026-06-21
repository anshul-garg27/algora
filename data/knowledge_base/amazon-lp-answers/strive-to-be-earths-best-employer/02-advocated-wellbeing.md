# Q: Describe a time you advocated for a teammate's wellbeing.

> **LP**: Strive to be Earth's Best Employer
> **Primary story**: `W3 — proposed paired 1:1 feedback norm after hard PR comment landed`
> **Backup story**: `W11 — saw junior pulling late nights, paired during day`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Around mid-2024 on the Kafka audit-logging codebase, a senior reviewer left a sharp comment on a peer's PR. The peer had used `ThreadPoolExecutor.DiscardPolicy` to handle backpressure, which silently drops events under load. The reviewer wrote, "This is wrong. Read the JDK docs." Three sentences, no context, ended with a hard rejection. The PR author was a strong engineer but newer to the codebase. The comment landed on him at 11 PM. He responded by 6 AM the next day with the fix.

### Task

Nobody had done anything technically wrong. The reviewer was right about `DiscardPolicy`. The author had taken the feedback and fixed it. But the pattern — late-night blunt rejection, early-morning anxious response — was going to wear someone down. I'd been on both ends of that pattern before. I wanted to change how we did review feedback for substantive issues.

### Action

I went to the reviewer first. Not to confront — to ask. "Your comment was technically right. Could we have given the same feedback in a way that didn't land at 11 PM?" He hadn't thought about the timestamp. He'd written the comment after dinner because his calendar was packed during the day.

I floated a soft norm to him and to the peer separately: for any review comment that requires a non-trivial rewrite, the reviewer pings the author for a quick chat — 15 minutes max — instead of leaving it as a written hard rejection. Daytime, not after-hours. The reasoning was selfish-rational: the chat is faster than three rounds of comment thread, and the author doesn't go to bed with a "this is wrong" message.

Both agreed. I wrote up the norm in two sentences and put it in our team's code-review wiki page. Substantive rewrites → 15-minute chat → then PR comment with the agreed direction. Trivial fixes → comment as usual.

Then I did the part that mattered more. I paired with the PR author on the actual `DiscardPolicy` fix. Not because he needed the technical help — he didn't. But because the fix involved swapping to `CallerRunsPolicy` plus instrumentation, and I wanted him to ship it with backup, not alone. We added queue-depth metrics, a counter for dropped events, and a Grafana alert. Took two hours together.

I also told him explicitly: a hard comment at 11 PM is the reviewer's calendar problem, not your problem. Don't take it home.

### Result

The norm stuck. Within a month, three other engineers started doing the 15-minute chat for substantive comments. Late-night-blunt-rejection happened maybe once more, then mostly stopped. The PR author later said the thing that helped most wasn't the norm — it was being told the comment timing wasn't on him.

A small downstream effect: the queue-depth metric we added during the pairing caught a real production incident two months later — events were getting dropped silently because the dispatcher was undersized. We caught it in 30 minutes instead of 5 days, because we'd instrumented the path.

I think the lesson sits with me more than the team change. Wellbeing at work isn't always about big interventions. Sometimes it's noticing a 11-PM-to-6-AM message pattern and changing one small thing.

---

## Technical depth — if they probe

- **The `DiscardPolicy` bug**: `ThreadPoolExecutor.DiscardPolicy` drops tasks when the queue is full. No exception, no log. Silent data loss. `CallerRunsPolicy` instead runs the task on the caller's thread — applies backpressure to the producer.
- **What we instrumented**: queue depth gauge, rejected-task counter, time-since-last-dispatch histogram. Grafana alert at queue depth > 80%.
- **Why the 15-minute chat works**: most "this is wrong" review comments are actually "I see three options, please discuss." Chat surfaces that. Written comment hides it.

---

## Likely follow-ups

**Q: Why didn't you escalate to the reviewer's manager?**
> Because nothing actually wrong had happened. The review was technically correct. Going to a manager over a tone choice would have created bigger drama than the original issue. Going to the reviewer directly was the right scale of response.

**Q: How did you bring it up without making it personal?**
> I asked a question, not made a statement. "Could we have done this differently?" instead of "you were too harsh." Questions invite reflection. Statements invite defense.

**Q: Did the norm have any downsides?**
> One — for genuinely trivial nits, some reviewers started over-using the chat. We tightened the norm: 15-min chat only when the comment requires a rewrite, not for style. That fixed it.

**Q: What about your own habits?**
> I'd been guilty of the late-night comment pattern too. After this, I'd draft comments after-hours but schedule them to send the next morning. Same content, better arrival time.

---

## What NOT to say

- Don't make the reviewer sound like a villain — he wasn't, he had a packed calendar
- Don't moralize about kindness — frame it as faster + healthier, not just nicer
- Don't claim I fixed reviewer culture — claim I shifted one specific pattern
- Don't skip the production-incident detail — it shows the technical work wasn't a sideshow

---

## Backup story (if asked for another)

During the six-week pairing on the credential-mgmt subgraph, I noticed my mentee's commits had timestamps after midnight three nights in a row. I asked. He said he was making up for "slow" daytime hours. I told him to flip it — pair with me 10 to 11 AM, work in normal hours, log off at 7 PM. His commit timestamps moved. His output went up, not down. He told me later it was the first time at any job someone had told him to *not* work nights.
