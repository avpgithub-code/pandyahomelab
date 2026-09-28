# Claude Prompting Guide

*A practical reference for using Claude effectively and efficiently — across the chat
interface, the API, and Claude Code.*

> Grounded in Anthropic's official prompt-engineering documentation for the current
> model generation (Claude Opus 4.7, Opus 4.6, Sonnet 4.6, Haiku 4.5). Treat this as a
> living document: re-check the source docs when you upgrade models, since prompting
> guidance shifts between generations.
>
> Source of truth: `https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview`

---

## How to use this guide

You don't need to apply every technique on every prompt. Most everyday requests just
need the first three foundational principles. Reach for the advanced sections (tool use,
thinking, agentic workflows) when you're building automations, using the API, or running
long agentic coding sessions.

A simple mental model: **treat Claude like a brilliant new colleague who is fast and
capable but has no prior context on your norms, your project, or your preferences.** The
clearer your brief, the better the result.

---

## Part 1 — Foundational principles

These four principles do most of the heavy lifting. If you only learn this section, you'll
already be in the top tier of prompters.

### 1. Be clear and direct

State exactly what you want. Specify the output format, the constraints, and the level of
detail. If you want "above and beyond" effort, ask for it explicitly rather than hoping
Claude infers it from a vague prompt.

The golden rule: *show your prompt to someone with no context on the task and ask them to
follow it. If they'd be confused, Claude will be too.*

When the order or completeness of steps matters, lay them out as a numbered list.

**Weak:** "Help me with my classifier code."

**Strong:** "Review the FastAPI route handler in `app/routes/predict.py`. Identify any
bugs in the image-preprocessing step, explain each one, and propose a fix. Keep the
explanation concise and show only the changed lines."

### 2. Add context and motivation

Telling Claude *why* you want something helps it generalize correctly. Claude is smart
enough to extrapolate from a stated goal to behaviors you didn't spell out.

**Weak:** "Always respond in plain text."

**Strong:** "Respond in plain text without markdown formatting, because the output gets
piped directly into a terminal log that doesn't render markdown."

The second version means Claude will make sensible related choices (e.g. avoiding tables
and fancy symbols) without you listing them.

### 3. Use examples (few-shot / multishot prompting)

Examples are one of the most reliable ways to steer output format, tone, and structure.
A few well-chosen examples beat paragraphs of description.

Good examples are:

- **Relevant** — they mirror your real use case.
- **Diverse** — they cover edge cases and vary enough that Claude doesn't latch onto an
  unintended pattern.
- **Structured** — wrap each in `<example>` tags (and the set in `<examples>` tags) so
  Claude can tell examples apart from instructions.

Aim for 3–5 examples. You can even ask Claude to critique your examples for relevance and
diversity, or to generate more from a seed set.

### 4. Structure prompts with XML tags

Claude is specifically tuned to pay attention to XML tags. When a prompt mixes
instructions, context, data, and examples, wrapping each part in its own tag prevents
Claude from confusing one for another.

```
<instructions>
Summarize the meeting transcript below into 5 bullet points, then list any action items.
</instructions>

<transcript>
{{paste transcript here}}
</transcript>
```

Tips: use consistent, descriptive tag names, and nest tags when content has a natural
hierarchy (e.g. `<documents>` containing multiple `<document>` blocks).

#### Do I need the angle brackets? (a note for beginners)

No. The `<>` tags are **optional, not required syntax.** Claude isn't a programming
language or a command line — you're writing in plain English, and there's no format you
have to get "right" or the prompt breaks. Every bracketed prompt in this guide would also
work written as a normal paragraph.

So what are the tags for? They're just **labels you put around different parts of a
prompt** to keep them visually separated. Claude was trained to notice these tags and
treat them as section markers, so on a longer prompt they stop Claude from confusing one
part for another. A tag is simply an opening marker and a matching closing marker (the
closing one has a slash):

```
<context>
...your background info goes here...
</context>
```

The word inside is entirely your choice — there's no official list. `<context>`,
`<task>`, `<email>`, `<instructions>` are all just made-up labels describing what's
inside. The only rule worth following is to use the **same word** in the opening and
closing tag so the pair matches.

Rule of thumb:

- **Short, simple request?** Skip the tags — plain prose is cleaner.
- **Longer prompt where you paste in content** (an email, a document, code)? The tags
  earn their keep, because they make it unmistakable where *your instructions* end and
  *the pasted material* begins.

For example, the tag draws a clean fence around the pasted text so Claude doesn't mistake
something inside it for an instruction:

```
Summarize the email below in three bullet points.

<email>
{{paste the whole email here}}
</email>
```

When in doubt, just write naturally. Clarity matters far more than any formatting.

### Bonus: Give Claude a role

A single sentence assigning a role focuses tone and expertise. In the API this goes in the
`system` prompt; in chat you can just say it.

> "You are a senior MLOps engineer reviewing infrastructure-as-code for a home-lab
> deployment. Prioritize reproducibility and security."

---

## Part 2 — Controlling output and format

The current models are more concise and literal than earlier generations. They calibrate
response length to perceived task complexity — short for lookups, long for open-ended
analysis. If you need a specific style, say so.

### Tell Claude what to do, not what to avoid

This is the single most effective formatting lever.

- Instead of: "Don't use markdown."
- Try: "Write your response as smoothly flowing prose paragraphs."

### Match your prompt style to the output you want

If you write your prompt in dense markdown, you'll tend to get dense markdown back.
Writing your prompt in clean prose nudges Claude toward prose. Mirroring your desired
output style in the prompt itself improves steerability.

### Control verbosity explicitly

To reduce verbosity:

> "Provide concise, focused responses. Skip non-essential context and keep examples
> minimal."

Positive examples of the concision you want work better than a list of "don'ts."

### Plain-text math

The current models default to LaTeX for math. If you want plain text, instruct it
directly: ask for standard text characters (`/` for division, `*` for multiplication,
`^` for exponents) and no LaTeX or markup notation.

---

## Part 3 — Tool use and taking action

This section matters most for the API, Claude Code, and chat with tools/connectors
enabled.

### Be explicit when you want action

The current models follow instructions literally. "Can you suggest some changes?" may get
you suggestions rather than edits. If you want Claude to *do* the thing, say "implement,"
"edit the file," "run," etc.

To make Claude action-oriented by default (system prompt):

```
<default_to_action>
By default, implement changes rather than only suggesting them. If intent is unclear,
infer the most useful likely action and proceed, using tools to discover missing details
instead of guessing.
</default_to_action>
```

To make it more cautious by default, invert that: tell it to research and recommend rather
than act unless explicitly asked.

### Don't over-prompt tool usage

Older advice ("CRITICAL: you MUST use this tool…") now causes *over*-triggering. The
current models are already proactive. Use normal phrasing — "Use this tool when…" — and
dial back aggressive, all-caps insistence.

### Parallel tool calls

The current models can run independent tool calls in parallel (e.g. reading several files
at once). They usually do this well unprompted, but you can push it toward ~100%:

```
<use_parallel_tool_calls>
If you intend to call multiple tools with no dependencies between them, make all the
independent calls in parallel rather than sequentially. Only sequence calls when one
depends on another's output. Never guess missing parameters.
</use_parallel_tool_calls>
```

---

## Part 4 — Thinking and reasoning

### Let Claude think, but don't over-engineer the steps

General instructions like "think thoroughly before answering" often outperform a
hand-written step-by-step plan — Claude's own reasoning frequently exceeds what you'd
prescribe.

### Ask Claude to self-check

A reliable accuracy booster, especially for code and math:

> "Before you finish, verify your answer against [these test cases / this requirement]."

### Curb overthinking when it's not needed

If Claude is exploring too many threads or revisiting decisions:

```
When deciding how to approach a problem, choose an approach and commit to it. Avoid
revisiting decisions unless new information directly contradicts your reasoning.
```

On the API, the cleaner lever is the **effort** parameter (see Part 6) — lowering effort
reduces thinking and token spend; raising it deepens reasoning.

---

## Part 5 — Agentic and long-horizon work

For multi-step automations and long Claude Code sessions.

### State tracking across long tasks

The current models excel at long-horizon work and tracking state. To get the most out of
this:

- **Use structured formats** (JSON) for things like test results or task status.
- **Use freeform notes** for general progress.
- **Use git** as a state log and checkpoint system — the models are very good at this.
- **Emphasize incremental progress** — a few things at a time, fully completed, beats
  attempting everything at once.

### Balance autonomy and safety

Without guidance, an agentic Claude may take hard-to-reverse actions. Add a guardrail:

```
Consider the reversibility and impact of your actions. Take local, reversible actions
(editing files, running tests) freely, but ask before anything destructive or
hard-to-reverse: deleting files/branches, dropping tables, rm -rf, git push --force,
git reset --hard, or anything visible to others (pushing code, commenting on PRs,
sending messages). Don't use destructive shortcuts (e.g. --no-verify) to get past
obstacles.
```

This pairs naturally with your pandyaHomeLab dev-nas / prod-nas split — you want Claude
freewheeling on feature branches but cautious near `main` and ports 80/8080/443.

### Reduce unwanted file creation

The current models sometimes create scratch files while iterating. To keep things tidy:

> "If you create any temporary files or helper scripts for iteration, remove them at the
> end of the task."

### Curb over-engineering

The current models can over-build — extra abstractions, unrequested features, defensive
code for impossible cases. To keep solutions minimal:

```
Avoid over-engineering. Only make changes directly requested or clearly necessary.
Don't add features, refactors, or "improvements" beyond what was asked. Don't add
docstrings/comments to code you didn't change. Don't add error handling for scenarios
that can't happen — validate only at system boundaries. Don't create abstractions for
one-time operations. The right complexity is the minimum needed for the current task.
```

### Ground answers in the actual code (anti-hallucination)

```
<investigate_before_answering>
Never speculate about code you have not opened. If I reference a specific file, read it
before answering. Investigate relevant files before making claims about the codebase.
</investigate_before_answering>
```

---

## Part 6 — API and Claude Code specifics

These apply when you're calling the API directly or using Claude Code — relevant to your
AWS / CI-CD plans.

### The `effort` parameter

Trades intelligence against speed and token cost:

- **`max`** — highest intelligence; can over-think and show diminishing returns. Test it
  on genuinely hard tasks.
- **`xhigh`** — best default for coding and agentic work.
- **`high`** — balanced; recommended minimum for intelligence-sensitive work.
- **`medium`** — cost-sensitive work that can trade off some intelligence.
- **`low`** — short, scoped, latency-sensitive tasks only.

Note: the current models respect effort *strictly* at the low end — they scope work to
exactly what was asked. If you see shallow reasoning on hard problems, raise effort rather
than prompting around it.

### Adaptive thinking (current default)

The current models use adaptive thinking (`thinking: {type: "adaptive"}`) and decide when
and how much to think based on effort and query complexity. This replaces the older
manual `budget_tokens` approach. Set a generous `max_tokens` (64k is a good starting point
at high/xhigh effort) so there's room to think and act.

```python
client.messages.create(
    model="claude-opus-4-7",
    max_tokens=64000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},   # max | xhigh | high | medium | low
    messages=[{"role": "user", "content": "..."}],
)
```

### Frontend / design note

The current models have a strong default "house style" (warm cream backgrounds, serif
display fonts, terracotta accents) that suits editorial/portfolio work but looks wrong for
dashboards, dev tools, or enterprise apps. Two reliable ways to break it: specify a
concrete alternative palette and typography, or ask the model to propose several distinct
directions and pick one before building. Generic negatives ("make it clean," "don't use
cream") just shift it to a different fixed style rather than producing variety.

### Prefilled responses are gone

Starting with the 4.6 generation, prefilling the final assistant turn is no longer
supported and returns a 400 error. Use explicit instructions, XML format tags, or a
"start your response with…" instruction instead.

---

## Part 7 — Quick-reference cheat sheet

| Goal | Lever |
|------|-------|
| Better results, fewer surprises | Be specific; state format + constraints |
| Claude generalizes correctly | Explain *why* (motivation) |
| Consistent format/tone | 3–5 structured `<example>` blocks |
| Clean parsing of complex prompts | XML tags around each content type |
| Less verbose output | "Be concise" + positive example |
| More/less verbose | Tell it what to do, not what to avoid |
| Claude acts vs. suggests | Say "implement/edit/run" explicitly |
| Avoid destructive actions | Reversibility guardrail prompt |
| Deeper reasoning (API) | Raise `effort` (high / xhigh) |
| Lower cost/latency (API) | Lower `effort`; cap `max_tokens` |
| Stop over-engineering | "Only make changes directly requested" |
| Stop hallucinated code claims | "Read the file before answering" |
| Long task across sessions | Track state in git + JSON; incremental progress |

---

## Part 8 — Reusable prompt templates

### Code review

```
<role>You are a senior engineer reviewing a pull request.</role>

<task>
Review the code in <files> below. Report every issue you find — including low-severity or
uncertain ones. For each: file + line, what's wrong, why it matters, and a suggested fix.
Include a confidence level and severity estimate.
</task>

<files>
{{paste code}}
</files>
```

### Document / explainer

```
<audience>Non-technical home users with no ML background.</audience>

<task>
Explain how an image classifier works, using one concrete everyday analogy. Keep it under
300 words. Plain prose, no jargon, no bullet lists.
</task>
```

### Structured extraction

```
<instructions>
Extract the fields below from the document. Return ONLY valid JSON, no preamble or
markdown fences. If a field is absent, use null.
</instructions>

<schema>
{ "title": string, "date": string|null, "owner": string|null, "action_items": string[] }
</schema>

<document>
{{paste document}}
</document>
```

### Research / synthesis

```
<success_criteria>
A successful answer cites at least 3 independent sources and flags any disagreement
between them.
</success_criteria>

<task>
Research {{topic}}. Develop competing hypotheses as you go, track your confidence, and
verify claims across multiple sources before concluding.
</task>
```

---

## Part 9 — A worked example (start here if you're new)

The best way to see these principles is to watch one prompt improve. Here's a simple,
everyday task: asking Claude to write a reply to an email.

### The weak version

> write a reply to this email saying I can't make the meeting

It works, but Claude has to guess almost everything: How formal? How long? Do you want to
suggest a new time, or just decline? What's your relationship to the person? You'll likely
get something generic that needs editing.

### The strong version

It's not longer because it's fancy — it's longer because it answers the questions Claude
would otherwise have to guess.

```
<context>
My colleague Sarah invited me to a project kickoff meeting on Thursday at 2pm. I have a
conflict and can't attend, but I genuinely want to be involved in this project. We have a
friendly, informal working relationship.
</context>

<task>
Write a short reply that declines Thursday's meeting but proposes Friday morning as an
alternative, and makes clear I'm still keen to be part of the project.
</task>

<constraints>
- Keep it under 100 words.
- Warm and friendly tone, not stiff or corporate.
- Don't apologize more than once.
</constraints>
```

### Why each part helps

The **context** block is the *who, what, and why*. "Friendly, informal relationship"
sets the tone without describing it abstractly, and "I genuinely want to be involved" is
the motivation — it's why Claude writes a warm decline that leans into rescheduling
rather than a flat "no." This is the single biggest upgrade over the weak version.

The **task** says exactly what the reply should accomplish: decline, propose Friday
morning, signal continued interest — three concrete goals, not one vague one.

The **constraints** control the shape: length, tone, and one specific "don't" (paired
with positive goals, per the "tell Claude what to do" principle).

The takeaway: every good prompt does three jobs — **give context (including the why),
state the goal clearly, and set the constraints.** Even a one-line prompt benefits from
keeping those three in mind. And remember (see the beginner note in Part 1): the tags here
are optional. The same prompt works as a plain paragraph; the labels just make the three
jobs easy to see.

---

## Notes for the chat interface specifically

Most of the above applies everywhere, but a few chat-only conveniences are worth knowing:

- **Projects** let you store standing instructions and a knowledge base reused across all
  chats in that project — a natural home for this guide and your project conventions.
- **Styles** customize Claude's writing voice; **user preferences** (Settings → Profile)
  store durable formatting/tone preferences applied to new chats.
- Features like web search, extended/deep research, and file creation are toggled in the
  chat input or settings.

---

*End of guide. Re-verify against the official docs after any model upgrade.*
