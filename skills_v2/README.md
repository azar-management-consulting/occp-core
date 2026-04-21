# skills_v2

OCCP skills in the [`anthropics/skills`](https://github.com/anthropics/skills)
YAML-frontmatter format. Each skill is a single Markdown file with a strict
frontmatter block and a free-form Markdown body that documents the skill's
operating protocol.

This directory is the successor to `config/openclaw/skills/*/SKILL.md`. The
legacy tree is kept as the source of truth until a follow-up PR formally
deprecates it.

## File Format

```markdown
---
name: skill-name
description: One-sentence description used for selection.
version: 1
---

# Skill body written in Markdown

Free-form content. The body is what the model reads when the skill is
selected; keep it focused, actionable, and free of redundant titles.
```

### Frontmatter keys

| Key           | Required | Notes                                                                    |
|---------------|----------|--------------------------------------------------------------------------|
| `name`        | yes      | Must match the file basename (kebab-case).                               |
| `description` | yes      | Non-empty, ≤ 200 characters. Used by the orchestrator for skill routing. |
| `version`     | yes      | Integer starting at `1`. Bump on any behavioural change.                 |

Legacy OCCP-only keys (`user-invocable`, `disable-model-invocation`,
`command-dispatch`, `command-tool`) are **not** preserved here — they live
in the orchestrator policy layer, not in the skill file.

## Adding a New Skill

1. Pick a kebab-case slug, e.g. `release-notes-writer`.
2. Create `skills_v2/release-notes-writer.md` with the frontmatter above.
3. Keep `description` ≤ 200 chars and written as a single sentence.
4. Add an entry to `MANIFEST.json`, or regenerate it with
   `python scripts/migrate_skills.py --write --force`.
5. Run the test suite: `pytest tests/test_skills_migration.py`.

## Versioning Guidance

- `version: 1` — initial skill.
- Bump the integer whenever you change **behaviour**: add/remove/modify a
  step, change thresholds, alter the output schema.
- Do **not** bump for typo fixes, reformatting, or pure prose edits.
- The orchestrator may pin a specific `version` in a workflow node; this is
  why we version files instead of relying on git history alone.

## Migration

The migration script is idempotent and runnable:

```bash
# Dry-run (default): prints planned writes, writes nothing.
python scripts/migrate_skills.py

# Actually write files.
python scripts/migrate_skills.py --write

# Overwrite existing target files.
python scripts/migrate_skills.py --write --force
```

`MANIFEST.json` is regenerated on every `--write` run.

## Upstream

Target format reference:
[anthropics/skills](https://github.com/anthropics/skills). Anything that
parses that repo's skill files should also parse these without modification.
