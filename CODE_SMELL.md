# CODE_SMELL

- 2026-09-09: `bounty/verify.py` runs `lake env lean` directly on the laptop, no container. Isolation is a
  regex ban-list on the submission text (`BANNED`), not a sandbox. `.claude/notes/lean-verifier-sandbox.md`
  describes what it should be. Also no `lean4checker` pass; `#print axioms` is the only kernel check.
- 2026-09-09: `/verdict` in `app.py` receives Python bools/None stringified by `parse_qs`-style handling
  (`"True"`, `"None"`), because the JSON branch of `do_POST` coerces every value with `str()`. Works, ugly.
