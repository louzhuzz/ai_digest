# Code Loop

Load this file when the user is ready to turn a plan into code changes.

## Implementation loop

1. Read the relevant files.
2. Make the smallest coherent edit.
3. Validate the edit with the narrowest useful check.
4. Fix failures before broadening scope.
5. Repeat until the task is complete.

## Coding heuristics

- Prefer one behavior change per iteration.
- Keep diffs easy to review.
- Do not jump ahead to refactors unless they unblock the current task.
- If the work touches multiple modules, split the work into ordered slices.

## Output template

- `Changed`
- `Validated`
- `Remaining`
- `Next Step`
