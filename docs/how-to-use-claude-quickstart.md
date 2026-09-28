# How to Use Claude Effectively — Quick Start

*A one-page beginner's companion to the full `claude-prompting-guide.md`.*

---

## The one idea behind everything

Treat Claude like a sharp new colleague who is capable and fast but has **no context** on
you, your work, or your preferences. The clearer your brief, the better the result.

---

## The three habits that cover most of it

**1. Give context — including the *why*.**
Don't just say what you want; say who it's for and what you're trying to achieve. The
motivation lets Claude make good judgment calls you didn't spell out.

> "Explain Docker volumes" → a textbook answer.
> "Explain Docker volumes — I'm setting up persistent storage for a model on my Synology
> NAS and keep losing data on container restarts" → an answer aimed at *your* situation.

**2. State the goal and constraints clearly.**
Be specific about the output: format, length, tone, level of detail. If you want it
thorough, ask for thorough; if you want three bullet points, say three. Claude follows
instructions fairly literally — vagueness in, vagueness out.

**3. Iterate instead of restarting.**
Your first prompt doesn't have to be perfect. Get a draft, then steer: "make it shorter,"
"more technical," "you missed the error-handling case." A short back-and-forth usually
beats crafting one giant perfect prompt.

---

## Five things that make Claude genuinely more useful

- **Give it the real material, not a description.** Paste the code, upload the document,
  share the actual error message. Claude reasoning over your real content beats Claude
  guessing from a summary. (When pasting a big chunk, put your question *after* it.)
- **Ask Claude to check its own work.** On anything where correctness matters, add
  "verify this against the requirements before you finish." It catches a surprising
  number of mistakes — especially in code and math.
- **Use Projects for ongoing work.** Drop your standing context (guides, conventions,
  reference docs) into a Project's knowledge base, and every chat in that Project starts
  already knowing it. Biggest efficiency gain for repeated work — you stop re-explaining
  yourself.
- **Match the tool to the task.** Turn on web search for current info, file creation for
  documents you'll keep, and use Claude Code for agentic, multi-step work in a repo.
- **Set durable preferences once.** Settings → Profile lets you store tone/format
  preferences that apply to new chats automatically.

---

## The whole philosophy in one example

**Weak:**

> write a reply to this email saying I can't make the meeting

**Strong:**

```
<context>
My colleague Sarah invited me to a project kickoff on Thursday at 2pm. I can't attend but
I genuinely want to be involved, and we have a friendly, informal relationship.
</context>

<task>
Write a short reply that declines Thursday but proposes Friday morning instead, and makes
clear I'm still keen to be part of the project.
</task>

<constraints>
- Under 100 words.
- Warm and friendly, not stiff or corporate.
- Don't apologize more than once.
</constraints>
```

Every good prompt does three jobs: **give context (with the why), state the goal, set the
constraints.**

> **Note:** the `<>` tags are *optional labels*, not required syntax. The same prompt
> works as a plain paragraph — the tags just make the three jobs easy to see, and they
> help most when you're pasting in content (an email, a document, code) so Claude can
> tell your instructions apart from the pasted material.

---

## 10-second checklist before you hit enter

1. Did I say **who/what it's for** (context + why)?
2. Did I state the **goal** specifically?
3. Did I set **constraints** (length, format, tone)?
4. Did I **give the real material** instead of describing it?

If correctness matters, add: *"check your work before finishing."*

---

*For the full reference — output control, tool use, thinking, agentic workflows, API and
Claude Code specifics, and reusable templates — see `claude-prompting-guide.md`.
Re-verify against the official docs after any model upgrade.*
