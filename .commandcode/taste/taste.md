# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# model
- Use Opus 4.8 (1M context) as the default model for all Algora modes. Sonnet 4.6 and Haiku 4.5 are secondary options. Confidence: 0.85
- For behavioral mode, the user pre-loads all deep-dive project files (resume, story bank, exemplars, voice rubric, technical depth seeds) into ONE chat session upfront and reuses that same session for all subsequent behavioral answers in that interview prep cycle. Prompt design should assume the model has already seen all inlined context and does not need per-turn tool searches — confirm which Opus variant to reference in prompts (1M vs 200K) before writing system prompts that lock in a context window. Confidence: 0.80

# workflow
- Use ultracode effort level (xhigh + dynamic workflow orchestration) for all Algora development sessions. Confidence: 0.85

# communication
- When explaining complex technical concepts (segment trees, DSU rollback, etc.), include a Hinglish block alongside English — plain Hindi-English mix that makes the concept grokkable fast. Confidence: 0.80

# architecture
- For live-interview modes, the speakable opener must stream within 30s–1min (the time a candidate takes to read a problem). Extended thinking before the opener defeats the purpose. Confidence: 0.75
- Use self-signed HTTPS certs for local dev so the Web Speech API (mic) works on iPhone/iPad over hotspot — secure context is required. Confidence: 0.70
- Per-session workspace isolation: each session writes to its own workspace/<session-slug>/ directory to prevent concurrent file collisions. Confidence: 0.70

# integration
- The Algora app runs on laptop as server and is accessible from iPhone/iPad on the same network via the laptop's local IP. History should sync across all devices accessing the same server. Confidence: 0.70

# interview-prep
- In interview-prep planning, help the user identify 2-3 "hero / anchor" stories with widest cross-LP coverage (e.g. an audit-log family story that maps to Ownership + Dive Deep + Failure + Earn Trust). The user explicitly tags certain stories as "hero stories that we can tell in everything" — treat those as the priority pairing targets when building the question-to-story mapping matrix. Confidence: 0.70
- When the user marks a story with "(HERO STORY)" or says it can be told "in everything / for most questions", treat it as the default fallback for any question type where no clean primary story exists — use it liberally as a backup across LPs, not just its primary pairing. The user is explicitly granting permission to over-rely on these. Confidence: 0.75
- The user is open to synthesizing/co-articulating a behavioral story from a real-but-partial situation (e.g. "when I created the Spring Boot JAR, my lead pushed back on who maintains it, I wrote a doc and convinced them") to fill an LP gap. This is grounded reconstruction, NOT invention — keep all facts/numbers/people/tech real to their work, just shape the STAR narrative to fit the LP. The user explicitly wants Claude Opus 4.8 to AUTONOMOUSLY generate plausible specific details (test types, document content, manager's pushback phrasing) based on the real anchor — do NOT block on user-verification for every detail. Surface the synthesized story for user review only at the final draft stage, not per-detail. Confidence: 0.85
- Behavioral answers should target 3-5 minutes of speaking per answer. Don't impose hard per-question-type word/time caps or strict "cut if exceeds" rules in the prompt — let Opus 4.8 autonomously decide the right length based on the question, the story's depth, and what's narratable. The user explicitly rejected a proposed per-question-type budget table (TMAY 60-90s, behavioral 90-120s, etc.) and a ≤200-word hard cap as "kam lagega" — they want the Say-it script to breathe for a real interview answer. Confidence: 0.80

# interview-prep
- Stories in `data/profile/story_bank.md` must be backed by items actually present on the resume (`data/profile/resume_profile.md`). If a story is not on the resume, do not include it as a primary/backup story in the bank — flag it to the user and ask before adding. Confidence: 0.92
- When the user lists which stories they are personally most confident telling, treat that list as the canonical "safe to use" set — never propose a story outside it as primary, and ask before adding any story they didn't list. Confidence: 0.80
- When the user explicitly excludes a company or story set (e.g. "payu ka kuch nahi bolna hai"), remove or quarantine those stories from the active story bank even if they're on the resume. Don't include them in the pairing guide, voice exemplars, or layered primary/backup lists. Confidence: 0.85
- For behavioral answers, generation latency cap: max 15-30 seconds for thinking/planning, then start streaming the actual answer. The user is fine with the model autonomously generating specifics (test types, document content, exact phrasing) as long as facts are grounded in the story card — the prompt should be designed so Opus 4.8 can produce a quality answer without blocking on per-detail user input. Confidence: 0.85
- For behavioral prompt structure: stream a 3-4 line opener IMMEDIATELY (first restatement + situation line + opening of action) so the user can begin speaking out loud within seconds, then the model can search/read for deeper details and continue the full answer. The user explicitly wants "bolna toh start karunga" — streaming the speakable opener first is non-negotiable over waiting for a single fully-formed answer. Confidence: 0.85

# workflow
- When the user asks for "PHD-level thinking" / strategic analysis / "socho is baare me", respond with analysis and recommendations ONLY — do NOT touch any files, do NOT start implementing. Wait for explicit "kar do" / "start karo" before editing. The user wants the thinking artifact first, the code change as a separate step. Confidence: 0.90

# workflow
- For destructive/sweeping edits to existing project files (story_bank, voice_exemplars, pairing guides, etc.), use `edit_file` (surgical edits), NOT `write_file` (full overwrite). Before each batch, explicitly list every section/card/line that will be removed or changed, then wait for the user to confirm with "haan kar do" before touching the file. The user wants git-diff-style transparency, not silent overwrites. Confidence: 0.85

# workflow
- Don't fix working code preemptively — if the user is on a feature path and existing code "works," don't redirect them to cleanup/bugfixes mid-flow. Offer them as a SEPARATE menu item at the end. Confidence: 0.80
- Before implementing a feature, do a PHD-level deep-dive of the relevant subsystem: trace the full data path through backend→frontend→UI, explain prompts/system-prompt blocks being used, and surface smells/quirks. The user wants understanding FIRST, code SECOND. Confidence: 0.85

# interview-prompt-design
- For coding interview mode, when multiple correct/standard approaches exist, the §6b "optimal" code should use the SIMPLEST one to explain out loud. The more advanced/canonical variant (e.g. depth-alignment LCA vs ancestor-set fold) goes in §9 as "Can We Optimize Further?" — lead with what the candidate can narrate cleanly under interview pressure. Confidence: 0.92
- In §4 of the coding interview output, the brute force approach must be a clearly visible, dedicated section with its own narration — not just a single row in a comparison table. The user explicitly flagged that "table-only" brute force was insufficient. Confidence: 0.85
- The clarifying-questions count in §1 should be 3-4 targeted questions (up to 5 if genuinely warranted). The user wants this number consistent across all related prompt blocks. Confidence: 0.80

# frontend
- Add follow-up quick-action buttons to the chat (e.g. "brute force", "optimal", "explanation") that re-prompt Algora within the same conversation thread and stream the answer inline — not a new conversation. User wants contextual follow-ups, not fresh sessions. Confidence: 0.75

# interview-prompt-design
- When designing starter prompts intended for use in EXTERNAL (non-Algora) chats — e.g. claude.ai web, terminal claude CLI, or a fresh Opus session — never reference local filesystem paths like `data/profile/resume_profile.md` as "files the model should read". External chats have no access to the local repo. Either paste the full file contents inline directly in the prompt body, or explicitly instruct the model to confirm "no local files available, will work from inlined context only" before proceeding. The Algora-server context is not portable to a standalone chat. Confidence: 0.70

