---
name: project-planning-execution
description: Use when Codex needs to take a project from idea to delivery: start from scratch, define scope, build a concrete plan, break work into actionable tasks, drive execution, manage risks, track progress, and iterate after review.
---

# Project Planning + Execution

Turn a rough idea into a verified specification, then build it in small, testable coding steps.

## Part 1: Six-phase specification flow

Use this flow when the user needs a project turned from idea into a concrete SPEC.

1. Phase 0: Verifiable research
   - Gather the minimum evidence needed to avoid guesswork.
   - Separate source-backed facts from assumptions.
   - Capture citations, links, or local proof when available.

2. Phase 1: Blueprint
   - Map the major components or modules.
   - Show the data flow or control flow between parts.
   - Decide the architectural boundaries before writing tasks.

3. Phase 2: Requirements
   - Convert the blueprint into testable requirements.
   - Define acceptance criteria for each important capability.
   - State non-goals and constraints explicitly.

4. Phase 3: Design
   - Fill in implementation details for each component.
   - Specify interfaces, inputs, outputs, and dependencies.
   - Keep design choices traceable back to requirements.

5. Phase 4: Tasks
   - Break design into a sequenced implementation plan.
   - Order tasks so the next useful slice is obvious.
   - Keep tasks small enough to complete and verify quickly.

6. Phase 5: Validation
   - Check coverage from requirements to tasks and results.
   - Verify that the plan is complete enough to start coding.
   - Record gaps, risks, and missing evidence before execution.

## Part 2: Incremental coding

1. Choose the smallest code change
   - Start from the next task in the SPEC.
   - Change one narrow slice of behavior at a time.
   - Prefer a patch that can be understood and reviewed quickly.

2. Implement in a tight loop
   - Inspect the relevant files first.
   - Edit only what is needed for the current step.
   - Keep the change internally consistent before moving on.
   - If the task is larger than one session, split it again.

3. Verify before expanding scope
   - Run the most targeted validation available.
   - Fix errors before adding new features.
   - If the result is unstable, shrink the change and retry.

4. Repeat until delivery
   - Update the spec when new information changes scope, order, or risk.
   - Keep progress visible: `done`, `in progress`, `blocked`, `next`.
   - Compare results against the original success criteria.
   - Record what changed, what remains, and what should happen next.

## Default output shape

When the user asks for planning or coding help, respond with:

- `Phase 0: Research`
- `Phase 1: Blueprint`
- `Phase 2: Requirements`
- `Phase 3: Design`
- `Phase 4: Tasks`
- `Phase 5: Validation`
- `Next Step`

## Guidance

- Ask only for the missing information that materially affects the spec or implementation.
- If the scope is unclear, propose a first-pass SPEC and note assumptions.
- Keep the plan concrete enough that execution can start immediately.
- Prefer iterative delivery over a perfect upfront design.
- Use `/mnt/d/AIcodes/openclaw/skills/project-planning-execution/references/project_artifacts.md` when the user needs a project brief, milestone map, task board, or review template.
- Use `/mnt/d/AIcodes/openclaw/skills/project-planning-execution/references/code_loop.md` when the user is ready to move from planning into code changes.
