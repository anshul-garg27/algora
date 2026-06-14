# STAR Work Document — fill this before the HM round
*A real Uber offer-getter spent 2 days building exactly this and credited it
for selection. Fill every section in writing. Rehearse out loud twice.*

## Part 1: The Project Architecture Walkthrough (THE most-asked question, 6x)

Pick your most significant project. Prepare it like a system design answer
about your own work — 5 minutes uninterrupted, then survive 15 min of probing.

```
PROJECT: ________________________________________
One-line pitch (what + for whom + scale): _______

CONTEXT: team size, your role, duration
ARCHITECTURE (draw it once on paper, be able to redraw in 60s):
  - components & how they talk:
  - data stores and WHY each was chosen:
  - scale numbers (QPS, data size, users) — REAL numbers:
KEY DECISIONS (need 3, each with the road not taken):
  1. We chose ____ over ____ because ____. Trade-off accepted: ____
  2. ...
  3. ...
WHAT BROKE / hardest challenge: ____
  how we found it, what I did, what changed after:
YOUR SPECIFIC PIECE (the #1 HM probe — "we" answers fail):
  "I personally designed/built/decided ____"
MEASURABLE IMPACT: latency/cost/revenue/users number: ____
WHAT YOU'D DO DIFFERENTLY NOW: ____ (honest, technical)
```

Probes to survive (rehearse answers): Why that DB? What was the QPS really?
What happens if component X dies? Why didn't you just use <obvious alt>?
What part was yours vs the team's? What would you change today?

## Part 2: Story Bank — 8 stories, STAR format

Rule: every story = Situation (2 lines, with stakes) → Task (your charter) →
Action (I, not we; 3-5 concrete steps) → Result (NUMBER + what you learned).
One story can serve 2 questions, but never use the same story twice in one
interview. Real Uber tip from an offer-getter: **never fabricate** — probes go
sideways into details and fabrication snaps.

| # | Prompt (asked at Uber) | Your story title | S/T/A/R filled? |
|---|---|---|---|
| 1 | Conflict within/across team (4x) | | ☐ |
| 2 | Ownership beyond your role | | ☐ |
| 3 | A major decision: options & criteria | | ☐ |
| 4 | Conflicting deadlines, prioritization | | ☐ |
| 5 | Mentored someone / inclusion | | ☐ |
| 6 | Learned a new technology fast | | ☐ |
| 7 | Proudest project | | ☐ |
| 8 | A failure + what changed after | | ☐ |

Conflict-story checklist (most-probed): the disagreement was about a real
trade-off (not a personality); you sought data / made the decision criteria
explicit; the resolution names what YOU conceded or changed; the relationship
survived. "I was right and they accepted it" = red flag answer.

## Part 3: Motivation answers (asked 4x, graded harder than you think)

- **Why leave current company?** Forward-looking, never bitter. Formula:
  "I've done ___ (proud), the next thing I want is ___ scale/problem, which
  Uber has and we don't."
- **Why Uber specifically?** Name SOMETHING REAL: H3 geo-indexing, the
  marketplace dispatch problem, Uber's Kafka-scale data infra, a specific
  Uber Eng blog post. Generic "scale and impact" earned a real follow-up:
  "name something specific." Have two specifics ready.
- **Heart or head person?** (actually asked at L3 HM) — either answer works
  WITH an example; the trap is answering without one.

## Part 4: Your questions for them (3 ready)

Good: "What does the team's on-call/incident culture look like?" /
"What separates an L4 who's promoted in 18 months from one who stalls?" /
"What's the team's biggest technical bet this year?"
Avoid: comp, WLB phrasing in the HM round (save for recruiter).

## Part 5: Situational drills (Uber loves "what would you do if…")

Prepare a 60-second judgment framework, not scripts: clarify impact → name
options → pick one with a reason → state the guardrail.
- Ship-or-slip: feature due tomorrow, you find a bug affecting 1% users.
- Teammate consistently misses their part of YOUR deliverable.
- PM demands a hack that adds prod risk.
- You disagree with your manager's technical direction.
