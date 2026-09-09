# Lean verifier sandbox — read before building the proof-bounty tier

Compiling a submitted Lean file is running untrusted code. The payout is automatic, so a verifier
bug is a direct drain. Design so the only trusted judge is the Lean kernel, then re-check the kernel.

## Why compile = code execution

- `lake build` evaluates `lakefile.lean` (arbitrary Lean/IO). Never run lake on submitted input.
- Elaboration runs user code: `#eval`, macros, custom elaborators, `initialize` blocks, and
  `run_cmd` all execute at compile time with full IO.
- So: one `lean` invocation on one file, in a throwaway environment with no network.

## Isolation (per submission)

- Fresh container or microVM (gVisor / Firecracker; a Docker container with `--network none` is the
  minimum). Non-root user. Read-only filesystem except a scratch dir.
- Prebuilt, pinned Mathlib oleans mounted read-only. `LEAN_PATH` set explicitly.
- Limits: wall-clock (10 min is generous), memory (8 GB), no outbound network, kill on exit.
- Toolchain and Mathlib commit pinned in the harness, not chosen by the submitter.

## Statement pinning

The submitter must not be able to state the theorem. Otherwise they prove something else.

1. `Problem.lean` (yours, compiled ahead of time) defines `def statement : Prop := <pinned>`.
   Use fully qualified `_root_.` names and `set_option autoImplicit false`.
2. The harness writes the final file: `import Problem` + their preamble (helper lemmas allowed) +
   `theorem solution : Problem.statement := by <their proof>` + the checks below.
3. Their preamble can't redefine `Problem.statement` (name clash errors), but it can shadow
   definitions the statement's *text* mentions. That's why the statement lives in a prebuilt olean
   and the harness appends the theorem line itself: `solution`'s type is the constant, not text.

## Checks after compile

- `#print axioms solution` must be a subset of `{propext, Classical.choice, Quot.sound}`.
  `sorryAx` = sorry. `Lean.ofReduceBool` = `native_decide` (trusts the compiler; reject).
- Run `lean4checker` on the produced olean. It replays every declaration through a fresh kernel and
  catches environment tampering done via metaprogramming (`addDecl` bypasses, `setEnv`) that
  `#print axioms` cannot see.
- Reject files containing `unsafe`, `implemented_by`, `extern`, or `partial` in the preamble. Cheap
  grep; the kernel rejects most of these anyway but the error messages are worse.

## Payout gating

- Statement faithfulness is a human problem, not a kernel problem. Attest each pinned statement
  *before* it goes live (or take it from a community-reviewed source like DeepMind's
  formal-conjectures) so claim-time is fully automatic.
- Pay from a wallet holding only that problem's cap. Log every accepted submission for later review.
- Idempotent: first verified proof per problem wins; later ones get a "solved" response, no pay.

## Practice first

`~/repos/lean-first-proofs` has five core-Lean exercises. `#print axioms` at the bottom of Ex5
shows the same check the verifier does.
