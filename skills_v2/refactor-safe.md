---
name: refactor-safe
description: Refactor existing code with test coverage verification before and after each change
version: 1
---

## Refactoring Protocol

**Pre-condition:** existing test suite must pass before any refactor begins. If no tests exist, generate them first using `pytest-generate` skill.

**Steps:**
1. Run current test suite → capture baseline coverage percentage
2. Identify refactor target: duplication, complexity (cyclomatic > 10), naming, coupling
3. Apply one refactor type at a time (single responsibility per change)
4. Re-run tests after each change — must not drop below baseline coverage
5. Run static analysis: `mypy --strict`, `ruff check`, `bandit` for security
6. Document each change with `# REFACTOR: reason` comment in PR description

## Allowed Refactor Types
- Extract method/function (reduce function length > 40 lines)
- Rename (clarity, convention alignment)
- Extract constant (eliminate magic numbers/strings)
- Dependency injection (replace tight coupling)
- Replace conditional with polymorphism
- Dead code removal (confirm unused with coverage data)

## Forbidden During Refactor
- Changing behavior (if behavior change is needed, that is a separate task)
- Removing tests to make refactor pass
- Introducing new dependencies without justification

## Output Expectations
- Diff showing before/after for each changed file
- Test run output: `X passed, coverage: Y%` (must be >= baseline)
- List of static analysis warnings resolved

## Quality Criteria
- Zero regression: all previously passing tests still pass
- Coverage maintained or improved
- PR reviewable in one reading (no 1000-line diffs)
