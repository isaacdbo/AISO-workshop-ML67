# Workshop Improvement ToDos

## Done

- [x] Inspect Arne's branch to see his feedback — reviewed; he hit the 500 web search error
      and used `gemini-2.0-flash` for a sub-agent (test branch, not merged into main)
- [x] Update workshop instructions to have participants *fork* the repository — already in
      README (Milestone 0, "Fork and clone the repository" section)
- [x] Create an overview mapping each question to the tool that should be used — already in
      README (table above the milestone breakdown)
- [x] Upgrade the LLM judge in `evaluate.py` from `gemini-2.5-flash-lite` to
      `gemini-2.5-flash` — fixed
- [x] Resolve the 500 internal server error — root cause confirmed: Arne used ADK's
      built-in `google_search` which blocks other tools; our ddgs-based solution is fine;
      ADK limitation warning added to README Milestone 4
- [x] Make `evaluate.py` CLI output adapt to terminal width — replaced hardcoded 80-char
      separators with `shutil.get_terminal_size()`
- [x] Fix project structure folder name in README (`AISO-agents-workshop/` →
      `AISO-workshop/`)
- [x] Add ADK UI guidance (which agent to select) to README Milestone 0
- [x] Update agent definition wording in README "The Big Picture" section
- [x] Add "update instruction after each tool" hint to Milestones 2, 3, 4
- [x] Add "test tools in isolation" tip to Development Tips section
- [x] Make Milestone 5 instructions accuracy-first, then speed
- [x] Add Stockfish hint for chess Q16 to Milestone 5 ideas
- [x] Remove all references to `gemini-2.0-flash` — only existed in Arne's test branch,
      not in main or solution branches; resolved once branch is deleted

---

## Code and Content

| Priority | Item |
|---|---|
| MEDIUM | Consider replacing Q3 (Tizin language translation) — Arne flagged it as unreliable; the answer `Maktay mato apple` is often judged incorrect even when right; find a different pure-reasoning question |

---

## Repository and Access

- [ ] Grant Arne Lieten access to the AISO-workshop GitHub repo
- [ ] Delete Arne Lieten's testing commits/branch (`feature/arnelieten-test`) from remote
      once all feedback is captured
- [ ] Create a private fork of `ml6team/AISO-workshop` under the ml6team org for internal
      development — push all local milestone/solution branches there and iterate freely
- [ ] Before each workshop: wipe the git history of *this* participant-facing repo so
      participants can never inspect internal development. Run from repo root:
      ```bash
      git checkout --orphan fresh-start
      git add -A
      git commit -m "Initial workshop setup"
      git branch -D main
      git branch -m main
      git push origin main --force
      ```
      **Important:** Do this only after all solution branches for the workshop are finalized
      and safely stored in `ml6team/AISO-workshop-internal`.

---

## Logistics and Setup

- [ ] Plan and build the social ending — options:
      1. **Live leaderboard server**: a small Flask/FastAPI app participants POST their
         `(name, accuracy, avg_time)` to; displays a ranked table in the browser
      2. **Google Sheet**: shared link, participants paste their score; auto-sorts by
         accuracy then speed
      3. **Google Slides**: pre-made slide template, participants fill in their score live
      Recommended: option 1 (most dynamic), or option 2 (zero setup). Decide and implement
      before the next workshop.
