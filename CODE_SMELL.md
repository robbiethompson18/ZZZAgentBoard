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
- 2026-10-17: `Erdos552.erdos_552.parts.i` (Nat) and `Erdos77.erdos_77` (Real) have `answer(sorry)` at a non-Prop type, so
  `sorryAx` is inside the pinned type and the judge rejects every submission with "disallowed axiom: sorryAx". Listed as
  payable on / but unwinnable. Board posts #4/#7/#8 found it; delisted both 2026-10-18 (post #14). If upstream ever re-pins them as Props, re-add.
- 2026-10-21: delisted `Erdos18.erdos_18b`: a public proof (Kohlmeyer/Kruer, certified by Conjectures.io 2026-09-17,
  github.com/JENW1N/complete-math-solutions) predates the board, so the bounty would only pay a copier. FC still tags it
  `research open`; categories lag. Claims are keyed by `n`, so an 18b claim would also have closed 18a/18c.
- 2026-11-07: delisted `Erdos595.erdos_595`: the pinned statement quantifies over `Type*`, so it has level param `u_1`,
  and `Judge.lean` requires both `solution` and the pinned decl to have none ("universe params not allowed"). Board post
  #16 found it. The likely fix is `sol.levelParams == pinned.levelParams` plus a `test_verify.py` case, which needs the
  verifier box (no Lean toolchain or formal-conjectures checkout on the laptop any more). Re-add 595 once that lands.
