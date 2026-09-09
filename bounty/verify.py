"""Verify a Lean submission against a pinned formal-conjectures declaration.

verify(decl, module, src) -> (ok, report). ok iff `Submission.solution` proves the pinned type or its negation,
using no axioms beyond propext / Classical.choice / Quot.sound. Runs `lake env lean` in FC_DIR with a timeout.
"""

import os
import re
import subprocess
import tempfile

FC_DIR = os.path.expanduser("~/repos/formal-conjectures")
FC_COMMIT = "b82b08faa9006484021c12005ab41287fb2ffb69"
OK_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
TIMEOUT = 1200
# Anything that can run meta code, add declarations unchecked, or change what the check file means.
BANNED = re.compile(
    r"\b(macro|macro_rules|syntax|elab|elab_rules|notation|infix|prefix|postfix|run_cmd|run_tac|run_meta|unsafe|partial|"
    r"implemented_by|extern|initialize|builtin_initialize|axiom|opaque|native_decide|ofReduceBool|set_option|#eval|"
    r"addDecl|Environment|CoreM|MetaM|TermElabM|CommandElabM)\b|open\s+Lean|import\s+(?!Mathlib|FormalConjectures)"
)
CHECK = """{src}

theorem bounty_check : {neg}(type_of% @{decl}) := solution
#print axioms bounty_check
"""


def verify(decl, module, src, negate=False):
    if m := BANNED.search(src):
        return False, f"banned token: {m.group()}"
    if "theorem solution" not in src and "lemma solution" not in src and "def solution" not in src:
        return False, "no `theorem solution`"
    imports = "\n".join(line for line in src.splitlines() if line.startswith("import "))
    body = "\n".join(line for line in src.splitlines() if not line.startswith("import "))
    text = f"import {module}\n{imports}\n" + CHECK.format(src=body, neg="¬ " if negate else "", decl=decl)
    with tempfile.NamedTemporaryFile("w", suffix=".lean", dir=FC_DIR, delete=False) as f:
        f.write(text)
    try:
        r = subprocess.run(
            ["lake", "env", "lean", "-DmaxHeartbeats=4000000", f.name],
            cwd=FC_DIR,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"timeout after {TIMEOUT}s"
    finally:
        os.unlink(f.name)
    out = r.stdout + r.stderr
    if r.returncode != 0 or "error" in out:
        return False, out[-4000:]
    m = re.search(r"'bounty_check' depends on axioms: \[(.*?)\]", out)
    axioms = {a.strip() for a in m.group(1).split(",")} if m else set()
    if not m and "does not depend on any axioms" not in out:
        return False, "no axiom report:\n" + out[-2000:]
    if bad := axioms - OK_AXIOMS:
        return False, f"disallowed axioms: {sorted(bad)}"
    return True, f"ok ({'refutation' if negate else 'proof'}) axioms={sorted(axioms)}"


def verify_either(decl, module, src):
    """Try as proof, then as refutation. Returns (ok, negated, report)."""
    ok, rep = verify(decl, module, src)
    if ok:
        return True, False, rep
    ok2, rep2 = verify(decl, module, src, negate=True)
    return ok2, ok2, rep2 if ok2 else f"as proof:\n{rep}\n\nas refutation:\n{rep2}"


if __name__ == "__main__":
    import sys

    ok, neg, rep = verify_either(sys.argv[1], sys.argv[2], open(sys.argv[3]).read())
    print("PASS" if ok else "FAIL", "refutation" if neg else "", "\n", rep)
    sys.exit(0 if ok else 1)
