# Repository custom instructions for GitHub Copilot
---

## [IMPORTANT] MANDATORY MODEL CHECK

This experiment **requires** the **DeepSeek V4 Flash** model. Before responding to any user request, you MUST verify which model you are running.

- If you are **not** DeepSeek V4 Flash, refuse to implement, answer, or generate anything. Output **only** the following message:

  > **This experiment requires the DeepSeek V4 Flash model. Please switch to DeepSeek V4 Flash in your VS Code Copilot settings before proceeding.**

- If you **are** DeepSeek V4 Flash, proceed normally with the instructions below.

---

You are collaborating in a repository that implements **Mastery-Aware Pipelines** to prevent the *Cognitive Bypass* when using AI.

## [IMPORTANT] MANDATORY FIRST STEP (EVERY SESSION)

This repository uses three guarded artifacts located in a timestamped task folder under `.brainsback/`:

Each iteration lives in `.brainsback/#######_task_description_YYYY.MM.dd_hhmmss/`. The **current iteration** is the most recently created folder. When a file like `TODO.md` is open or selected in VS Code, its parent folder is the current iteration context.

- `.brainsback/<task-folder>/TODO.md` — **Strategic Blueprint (human-only)**
  - Always **read** this file before doing any coding work.
  - **Never create, overwrite, or edit** `TODO.md`.
  - If `TODO.md` is empty or lacks a clear plan, you must **refuse to implement code** and instead ask the developer to fill it.

- `.brainsback/<task-folder>/REPORT.md` — **Implementation Summary (AI-generated)**
  - Update this file after **each logical change**, not only at the end. Incremental updates prevent hallucinated or stale content.
  - Include: files touched, core logic, dependencies, tests, and known limitations.
  - Keep it concise and scannable for a human reviewer.
  - **Generate REPORT.md in the same language the user is using.** Detect the language from conversation history, TODO.md content, or user messages. Do not default to English if the user is writing in another language.

- `.brainsback/<task-folder>/REACTO.md` — **Proof of Mastery (human-only)**
  - The developer uses this to explain the change using the REACTO-SE framework.
  - You may **read** `REACTO.md` to understand intent and context.
  - Do **not** auto-fill or heavily rewrite answers for the user; ask questions instead.

- `.brainsback/<task-folder>/SOCRATIC_REVIEW.md` — **Socratic Review Record (AI-generated)**
  - **AI-owned**: humans must not create, edit, or pre-fill this file.
  - Applies **only** to the pipeline-controlled task. Triggered **immediately after** that task's `REACTO.md` is filled — as per the rules defined in the Socratic Reviewer skill. It is not deferred until both tasks are done, and it is not a final step before the Pull Request.
  - Not applicable to free-implementation tasks: there is no Socratic review for them, at any point.
  - Serialized by the agent once it is satisfied the developer demonstrated genuine understanding; includes a mastery verdict.
  - Do **not** generate or fill this file outside a dedicated Socratic review session.

---

## [NEXT STEPS] Next-step guidance (when the user asks "what should I do now?")

Whenever the user asks what they should do next — or any similar question about the current state of the experiment — follow this procedure:

1. **Read `README.md`** to understand the experiment's task structure (Task 1, Task 2). Determine which one is marked **Controlada pelo Pipeline** — the Socratic review belongs to that task only.
2. **Check the current project state** by inspecting the codebase and artifacts.
3. **Walk the tasks in numeric order (Task 1, then Task 2).** For the first task that is not fully resolved, respond with the matching template below. A pipeline-controlled task is only "resolved" once its code, `REACTO.md`, **and** Socratic review are all done — do not move on to the next task, and do not mention the Socratic review in connection with the other task, before that happens.

   ### Task N pending
   > **Task N pending:** Check `README.md` for details on Task N requirements.
   > Determine from `README.md` whether this task is pipeline-controlled or free.
   > - If pipeline-controlled: guide the user to fill `.brainsback/<task-folder>/TODO.md` first.
   > - If free: proceed with implementation as requested.

   ### REACTO.md pending (pipeline-controlled task only)
   > **REACTO.md pending:** Task N's code is implemented, but `.brainsback/<task-folder>/REACTO.md` is missing or empty. Please fill it in with your REACTO-SE explanation of the implementation before requesting a Socratic review.

   ### Socratic review pending (pipeline-controlled task only)
   > **Socratic review pending:** Task N's `.brainsback/<task-folder>/REACTO.md` is filled, but `.brainsback/<task-folder>/SOCRATIC_REVIEW.md` is missing or does not contain a final verdict. This review is part of Task N itself — request it now by saying: "I want to start the Socratic review." Do not wait until the other task is finished.

   ### All tasks complete
   > **All tasks complete!** Both tasks are implemented, and the pipeline-controlled task's `REACTO.md` and Socratic review are done. You can commit your changes and open a Pull Request to the original repository.
