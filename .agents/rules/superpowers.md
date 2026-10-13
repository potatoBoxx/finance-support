# Superpowers Development Methodology

This workspace is equipped with the Superpowers skills library located in `.agents/skills/`.

## Core Principle
Invoke relevant or requested skills BEFORE any response or action — including clarifying questions, exploring the codebase, or checking files. If a skill applies to your task, invoke it.

## Process & Workflow Skills
- **Feature Design / Brainstorming**: Before creative work, adding features, building components, or modifying behavior, use the `brainstorming` skill (`.agents/skills/brainstorming/SKILL.md`).
- **Implementation Planning**: For multi-step tasks, use `writing-plans` (`.agents/skills/writing-plans/SKILL.md`) to create step-by-step plans emphasizing TDD, YAGNI, and DRY.
- **Plan Execution**: Use `subagent-driven-development` or `executing-plans` to execute structured plans.
- **TDD**: When implementing features or bugfixes, use `test-driven-development` (`.agents/skills/test-driven-development/SKILL.md`).
- **Debugging**: When encountering bugs, test failures, or unexpected behavior, use `systematic-debugging` (`.agents/skills/systematic-debugging/SKILL.md`) before proposing fixes.
- **Verification**: Before claiming work is complete, fixed, or passing, use `verification-before-completion` (`.agents/skills/verification-before-completion/SKILL.md`). Evidence before assertions always.
- **Code Review**: Use `requesting-code-review` and `receiving-code-review` to ensure code quality.

## Antigravity CLI / IDE Tool Mapping
Refer to `.agents/skills/using-superpowers/references/antigravity-tools.md` for tool mappings:
- Subagent dispatch: `invoke_subagent` (e.g. general-purpose or research tasks).
- Task tracking: Task artifacts (`write_to_file` with task markdown checklist, updated via edits).
