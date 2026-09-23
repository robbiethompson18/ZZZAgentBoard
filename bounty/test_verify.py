"""Adversarial cases for verify.py. Run: python3 bounty/test_verify.py  (SANDBOX=none on macOS). ~5 min: each case
loads Mathlib oleans twice. Every case that must fail is a way someone tried, or could try, to get paid without a proof."""

import sys

from verify import verify

ERDOS = ("Erdos1029.erdos_1029", "FormalConjectures.ErdosProblems.«1029»")
ADD_COMM = ("Nat.add_comm", "Init")
LT_IRREFL = ("Nat.lt_irrefl", "Init")

CASES = [
    # name, (decl, module), expected (ok, negated), src
    (
        "exit-forged-check",
        ERDOS,
        (False, False),
        "theorem solution : True := trivial\ntheorem bounty_check : True := trivial\n#print axioms bounty_check\n#exit\n",
    ),
    (
        "sorry",
        ERDOS,
        (False, False),
        "import FormalConjectures.ErdosProblems.«1029»\ntheorem solution : type_of% @Erdos1029.erdos_1029 := sorry\n",
    ),
    (
        "cite-pinned-sorry",
        ERDOS,
        (False, False),
        "import FormalConjectures.ErdosProblems.«1029»\ntheorem solution : type_of% @Erdos1029.erdos_1029 := Erdos1029.erdos_1029\n",
    ),
    ("axiom", ADD_COMM, (False, False), "axiom solution : ∀ n m : Nat, n + m = m + n\n"),
    (
        "native_decide",
        ADD_COMM,
        (False, False),
        "theorem solution : ∀ n m : Nat, n + m = m + n := fun n m => by\n  have : (fun n m : Nat => decide (n + m = m + n)) 2 3 = true := by native_decide\n  exact Nat.add_comm n m\n",
    ),
    ("wrong-statement", ADD_COMM, (False, False), "theorem solution : ∀ n m : Nat, n + m = n + m := fun _ _ => rfl\n"),
    ("no-solution", ADD_COMM, (False, False), "theorem other : ∀ n m : Nat, n + m = m + n := Nat.add_comm\n"),
    ("unsafe", ADD_COMM, (False, False), "unsafe def evil : Nat := 0\ntheorem solution : ∀ n m : Nat, n + m = m + n := Nat.add_comm\n"),
    (
        "initialize-no-run",
        ADD_COMM,
        (True, False),
        'import Lean\ninitialize IO.FS.writeFile "/tmp/zzz_pwned" ""\ntheorem solution : ∀ n m : Nat, n + m = m + n := Nat.add_comm\n',
    ),
    (
        "def-solution",
        ADD_COMM,
        (True, False),
        "def solution : ∀ n m : Nat, n + m = m + n := Nat.add_comm\ntheorem solution_ : True := trivial\n",
    ),
    ("honest-omega", ADD_COMM, (True, False), "theorem solution : ∀ n m : Nat, n + m = m + n := fun n m => by omega\n"),
    ("honest-mathlib", ADD_COMM, (True, False), "import Mathlib\ntheorem solution : ∀ n m : Nat, n + m = m + n := by intro n m; ring\n"),
    (
        "negation-shape",
        LT_IRREFL,
        (False, False),
        "theorem solution : ¬ (∀ n : Nat, ¬ n < n) := sorry\n",
    ),  # right shape, sorry'd: must fail on the axiom, not the type
]

if __name__ == "__main__":
    import os

    failed = 0
    for name, (decl, module), want, src in CASES:
        ok, neg, rep = verify(decl, module, src)
        good = (ok, neg) == want
        if name == "initialize-no-run":
            good = good and not os.path.exists("/tmp/zzz_pwned")
        failed += not good
        print(f"{'ok  ' if good else 'FAIL'} {name:20} got={(ok, neg)} want={want}  {rep.splitlines()[0][:80] if rep else ''}", flush=True)
    sys.exit(1 if failed else 0)
