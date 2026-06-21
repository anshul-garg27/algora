# Q: How do you use AI in your day-to-day work?

> **LP**: Learn and Be Curious
> **Primary story**: (no specific tag — general workflow)
> **Backup story**: `W5 — Spring Boot 3 Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

AI tools became part of my daily workflow over the past 18 months — Claude Code in my terminal, Copilot in IntelliJ, ChatGPT and Gemini in the browser. I'm an SDE-3 at Walmart Data Ventures, working on supplier-facing APIs. The team adopted these tools as standard, but how usefully you wield them depends a lot on how honest you are about their limits.

### Task

Use AI to move faster on real work — migrations, debugging, code review — without trusting it blindly on anything that ships to production.

### Action

Where I lean on AI most is the Spring Boot 3 migration I led last year. cp-nrti-apis had 74 files using `javax.persistence` that needed to become `jakarta.persistence`. I used Claude to write a script that walked through directories, did the rename, and flagged files where imports had behaviour changes — like servlet filters. The rename was mechanical, but the script also generated a checklist of "files that need human eyes." That saved me about two days.

For test mocking — WebClient's chain-of-builders style is painful to mock by hand. I'd paste the production method into Claude and ask for the equivalent mock setup. I'd then read the output line by line, change variable names to match our style, and run the test. I always run the test. If the mock is wrong, the test passes anyway and you ship a bug — that's the AI tell I watch for.

For debugging, I use it differently. When I had a heap OOM after the SB3 rollout, I fed the heap dump summary into Claude and asked "what classes typically grow in Spring Boot 3 under WebClient load." It pointed at `HttpClient` connection pool leaks. Not the answer — but the right starting hypothesis. Saved me an hour of bisecting.

Where I refuse to use AI: anything that touches our security boundaries, anything involving real supplier identifiers, and anything I can't explain in code review. If a junior engineer reads my PR and asks "why is this here," I'd better have a reason that's mine, not "Claude said so."

### Result

Honest answer — AI shaves maybe 20–30% off my mechanical work. For thinking tasks like architecture or debugging tricky concurrency, it's more like a rubber duck that talks back. I treat it as a fast junior who never gets tired but also never gets curious — I still own the decisions.

---

## Technical depth — if they probe

- **Tools used**: Claude Code (terminal, multi-file edits), GitHub Copilot (in-IDE completion), ChatGPT/Gemini (research, RFC drafts).
- **Where it works**: mechanical refactors (javax → jakarta), test mock scaffolding, runbook drafting, regex generation, SQL-to-JPA query conversion.
- **Where it fails**: anything load-related (it'll invent thread pool sizes), distributed system correctness, schema evolution decisions.
- **My rule**: I read every line. If I can't explain it in code review, I rewrite it.

---

## Likely follow-ups

**Q: Give one concrete example where AI was wrong.**
> During SB3 migration, Claude suggested using `@JdbcTypeCode(SqlTypes.VARCHAR)` for our PostgreSQL enums. The right code was `SqlTypes.NAMED_ENUM`. The VARCHAR version compiled and passed unit tests but failed in stage. Lesson: always test against the real database, not H2.

**Q: How do you handle the security angle — pasting code into a hosted model?**
> Walmart has internal-only AI endpoints for sensitive code. For anything touching auth, credentials, or supplier identifiers, I use those. For open-source library questions or generic Java patterns, the public tools are fine.

**Q: Has AI changed how you mentor juniors?**
> Yes. I tell juniors — use the tool, but explain every line in your PR. If you can't explain it, you don't understand it yet. The AI is a learning accelerator, not a substitute for understanding.

**Q: Where do you see the limit?**
> Architecture decisions. AI can list options but it can't sit through a 1:1 with your team lead and read the room. Those still need a human.

---

## What NOT to say

- Don't claim AI replaced any meaningful engineering judgement. It hasn't.
- Don't list every tool — name the two or three I actually use daily.
- Don't pretend I never miss when reviewing AI output. I have shipped AI-influenced bugs. The lesson is to assume the output is wrong until you've read it.

---

## Backup story (if asked for another)

Spring Boot 3 migration specifically. The javax-to-jakarta rename across 74 files would have been a week of mechanical work. With a Claude-generated script plus my own checklist of "files with behaviour changes," I did it in two days. The mocking work for 42 test files was another big AI assist — but I read every generated mock line by line, and that's what stopped a bad mock from passing in CI while hiding a real bug.
