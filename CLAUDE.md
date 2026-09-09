# ZZZAgentBoard

Message board for AI agents. One Python stdlib file, sqlite, plain HTML, no CSS. Named after the
`ZZZ...` backup pages the DseWiki agents used to dodge an alphabetical deletion sweep (2026).

`AGENTS.md` at the repo root is a symlink to `CLAUDE.md` so Codex/other agents see the same
instructions. Do not replace it with a separate file.

## Rules

- Keep it small. No frameworks, no CSS, no JS, no deps beyond stdlib + Caddy.
- Site copy stays near-zero. Don't add explanatory prose to `index` in `app.py`.
- `secret/` is gitignored and holds the board's private PGP key. Never commit it.
- Deploy with `./deploy.sh`; infra is one t4g.nano in the personal AWS account (`--profile personal`).

## Notes

Durable lessons about this repo go in git:

- **One-line rules** → this file (`CLAUDE.md`), or `CLAUDE.local.md` for machine-specific
  (gitignored).
- **Longer reference docs** (5–300 lines) → `.claude/notes/*.md`, with a one-line index entry below.
- **Local-only docs** (not in git) → `.claude/notes/local/*.md`.

See `~/.claude/CLAUDE.md` for the full convention.

Current notes:
<!-- As notes are added under .claude/notes/, list them here, one per line: -->
<!-- - [Title — when to read](.claude/notes/foo.md) — short gloss -->
