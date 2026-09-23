# CODE_SMELL

- 2026-09-21: the docker sandbox path in `bounty/verify.py` is only exercised on the verifier box (macOS toolchain can't
  run in the linux container); laptop runs use `SANDBOX=none`. Judge/type/axiom logic is identical either way.
- 2026-09-21: `pay` in `worker.py` passes the private key to `cast` as an argv, visible in `ps` on the box for the
  seconds the send takes. Fine while the box is single-user; fix with `--keystore` or `--private-key` via env if not.
- 2026-09-09: `/verdict` in `app.py` receives Python bools/None stringified by `parse_qs`-style handling
  (`"True"`, `"None"`), because the JSON branch of `do_POST` coerces every value with `str()`. Works, ugly.
- 2026-09-22: no test exercises a *genuine* refutation being accepted (`negated=True` → pay). Every real pinned
  statement is an open problem, so it needs a fake pinned module with a false `sorry`'d theorem on LEAN_PATH.
  The logic is one line (`sol.type == mkNot pinned.type`) but it's the only paying path with zero coverage.
