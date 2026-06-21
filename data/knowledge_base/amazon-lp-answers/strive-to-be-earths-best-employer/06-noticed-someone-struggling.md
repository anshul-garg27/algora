# Q: Describe a time you noticed someone struggling and helped.

> **LP**: Strive to be Earth's Best Employer
> **Primary story**: `W11 — junior pulling late nights, paired during day + introduced to senior architects`
> **Backup story**: `G7 — peer struggling with Go basics, paired on first 3 PRs`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Around week three of pairing with the SDE-1 on the credential-mgmt subgraph. He'd been doing fine technically. But I noticed something in the GitHub activity. His commit timestamps over a Monday-to-Wednesday stretch were 11:47 PM, 1:14 AM, 12:38 AM, 2:02 AM. Four nights in a row, all after midnight. His standup updates the next mornings were fine — he was getting the work done. But the pattern wasn't sustainable.

### Task

Nobody had asked me to notice this. He hadn't complained. His output was on track. The easy thing would have been to assume he was an adult and let him manage his own hours. The right thing was harder — bring it up without making it sound like surveillance.

### Action

Thursday's 10 AM session, I closed my laptop and asked. "I noticed your commits have been late. What's going on?"

He got a bit defensive at first. Said he was just trying to make up for being "slow" during the day. He felt like our 10 AM pairing was helpful but cost him an hour of solo coding time, so he was reclaiming it at night.

I told him that wasn't how the math worked. The hour of pairing was saving him two hours of pull-request rework later. He was net up, not net down. He hadn't seen it that way.

Then I told him the harder part. The late-night pattern wasn't a productivity choice. It was a confidence thing. He was working extra hours because he felt behind. I'd been in the same pattern in my first year and it had taken me eight months to figure out it was making me worse, not better.

I made a specific ask. I wanted him to stop logging in after 8 PM for two weeks. If he hit a hard problem at 6 PM, write it down, leave it. We'd pick it up at 10 AM the next day. He pushed back. I told him: try it for two weeks. If your output goes down, you can go back to nights.

I also did something separate. I introduced him to two staff engineers in the org. One coffee chat each. I told him the agenda was just "ask them anything about career paths." The real agenda was: see what staff engineers actually do day-to-day. They go home at 6 PM. They take vacations. They don't ship code at 2 AM. Modeling does more than telling.

### Result

He took the two-week test. His commit timestamps moved into normal hours by week two. His PR velocity stayed flat — same output, fewer hours. By week four he had energy in our 10 AM sessions that he'd been missing in weeks one through three.

The staff-engineer coffee chats had a separate effect I didn't predict. He came back from the second one and told me he hadn't realized senior engineers had ever felt unsure about their work. The conversation had been more reassuring than any of mine.

Six months later he was the one telling new joiners on the team to log off at a reasonable hour. The pattern doesn't fully break unless someone teaches it forward.

The thing I'd flag honestly: I almost didn't bring it up. It felt invasive — looking at commit timestamps and then commenting on them. The reason I went ahead was that I'd been on his side of the pattern, and nobody had told me until I'd burned out. I didn't want to be the senior who watched it happen.

---

## Technical depth — if they probe

- **Why the commit timestamps were the signal**: His Slack status was always "available." His standup updates were fine. The GitHub activity log was the only honest data.
- **The two-week test framing**: A hard rule feels like control. A two-week experiment feels like data collection. He bought in because it was reversible.
- **Why the staff-engineer coffee chats**: I could tell him senior engineers don't work 2 AM all I wanted. Hearing it from two of them moved the needle.

---

## Likely follow-ups

**Q: Was it appropriate to look at his commit timestamps?**
> Borderline. I justified it because we were pair-mentoring and his work was effectively my work too. I wouldn't pull timestamps on a peer I wasn't actively mentoring.

**Q: What if he'd said the late nights were just his preference?**
> Then I'd have asked one follow-up — is your daytime energy good? If he said yes, fine, he's a night owl. The signal that mattered was him saying he felt "slow" during the day. That was the real issue.

**Q: How do you balance noticing vs. surveilling?**
> Notice when you have a real reason to be looking. Bring it up directly when you do, instead of letting it shape your private read of someone.

**Q: Did you tell his manager?**
> No. There was nothing to escalate. He was meeting his commitments. The late-night pattern was something he and I could work on directly.

---

## What NOT to say

- Don't make it sound like I was hovering — say I noticed because we were actively pairing
- Don't moralize about work-life balance — talk about the specific cost (worse pairing energy, not "burnout in general")
- Don't claim I fixed his work hours — claim I gave him a two-week experiment that he chose to extend
- Don't skip the "I almost didn't bring it up" — it makes the answer credible

---

## Backup story (if asked for another)

At GCC, a peer who'd just joined had his first three Go PRs rejected for race conditions. He was getting frustrated and quiet in standups. I noticed and asked. Paired with him for one hour on `go test -race`, watched the panic together, helped him fix the first one himself. After that he ran `-race` in pre-commit. He told me the help mattered less than someone noticing he was struggling before he had to ask.
