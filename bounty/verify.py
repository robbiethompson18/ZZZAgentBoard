"""Verify a Lean submission against a pinned formal-conjectures declaration, in two sandboxed steps.

verify(decl, module, src) -> (ok, negated, report)

1. compile: `lean -o Submission.olean` in a throwaway container: no network, read-only toolchain and oleans, non-root,
   memory/pid/time caps. Everything it prints is untrusted and is only echoed back to the submitter as the report.
   Plain runc, not gVisor: an escape is worth the wallet balance, which is kept small on purpose, and gVisor's private
   page cache put the mmapped Mathlib oleans inside the memory cap (OOM on the 8GB box).
2. judge: `judge/` (trusted, depends on core Lean only) loads the olean in a second container that sees nothing else
   from step 1, replays every declaration through a fresh kernel, and checks `solution`'s type and axioms against the
   pinned declaration. Only its JSON verdict decides anything. See judge/Judge.lean and docs/lean-verifier-sandbox.md.

SANDBOX=none runs both steps directly on the host: local dev only (the macOS toolchain can't run in a linux container).
"""

import json
import os
import shutil
import subprocess
import tempfile

FC_DIR = os.path.expanduser("~/repos/formal-conjectures")
FC_COMMIT = "b82b08faa9006484021c12005ab41287fb2ffb69"
TOOLCHAIN = os.path.expanduser("~/.elan/toolchains/leanprover--lean4---v4.33.1")
JUDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "judge/.lake/build/bin/judge")
TIMEOUT = 1200
SANDBOX = os.environ.get("SANDBOX", "docker")
IMAGE = "zzz-sandbox"  # ubuntu:24.04 + libgmp10, built in verifier-userdata.sh
# Host paths -> container paths. The toolchain is mounted at the same path it has on the host so the judge's
# `findSysroot` (which resolves `lean` on PATH) and LEAN_PATH agree without rewriting.
MOUNTS = {FC_DIR: "/fc", TOOLCHAIN: TOOLCHAIN}


def lean_path(scratch):
    """LEAN_PATH as `lake env` computes it, with host prefixes swapped for container ones; scratch last so nothing in it can shadow a trusted module."""
    raw = subprocess.run(["lake", "env", "printenv", "LEAN_PATH"], cwd=FC_DIR, capture_output=True, text=True, check=True).stdout.strip()
    parts = raw.split(":") + [scratch]
    if SANDBOX == "none":
        return ":".join(parts)
    return ":".join(next((p.replace(h, c, 1) for h, c in MOUNTS.items() if p.startswith(h)), p) for p in parts)


def run(cmd, scratch, env, timeout):
    """Run cmd with scratch as cwd/writable dir, sandboxed unless SANDBOX=none. Returns (returncode, output)."""
    if SANDBOX == "none":
        r = subprocess.run(cmd, cwd=scratch, env={**os.environ, **env}, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout + r.stderr
    name = "zzz-" + os.path.basename(scratch)
    docker = [
        "docker", "run", "--rm", "--name", name, "--network", "none", "--read-only", "--user", "1000:1000",
        "--memory", "7g", "--memory-swap", "7g", "--pids-limit", "256", "--tmpfs", "/tmp:size=512m",
        "--security-opt", "no-new-privileges", "--cap-drop", "ALL", "-w", "/work", "-v", f"{scratch}:/work",
    ]  # fmt: skip
    for h, c in MOUNTS.items():
        docker += ["-v", f"{h}:{c}:ro"]
    for k, v in env.items():
        docker += ["-e", f"{k}={v}"]
    try:
        r = subprocess.run(docker + [IMAGE] + cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        raise
    return r.returncode, r.stdout + r.stderr


def verify(decl, module, src, archive=None):
    """archive: directory to keep both scratch dirs and full logs in afterwards (forensics), else they are deleted."""
    work = tempfile.mkdtemp(prefix="sub-")
    judge_dir = tempfile.mkdtemp(prefix="judge-")
    os.chmod(work, 0o777)
    os.chmod(judge_dir, 0o777)
    # Where each scratch dir appears to the process running in it.
    W = "/work" if SANDBOX != "none" else None
    try:
        with open(f"{work}/Submission.lean", "w") as f:
            f.write(src)
        try:
            rc, out = run(
                [f"{TOOLCHAIN}/bin/lean", f"--root={W or work}", "-DmaxHeartbeats=4000000", "-o", "Submission.olean", "Submission.lean"],
                work,
                {"LEAN_PATH": lean_path(W or work)},
                TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return False, False, f"compile timeout after {TIMEOUT}s"
        open(f"{work}/compile.log", "w").write(out)
        if rc != 0 or not os.path.exists(f"{work}/Submission.olean"):
            return False, False, "compile failed:\n" + out[-4000:]
        # Only the olean crosses into the judge. Anything else the compile step wrote to its scratch dir stays behind.
        shutil.copy(f"{work}/Submission.olean", judge_dir)
        shutil.copy(JUDGE, judge_dir)
        try:
            rc, out = run(
                [f"{W or judge_dir}/judge", module, decl],
                judge_dir,
                {"LEAN_PATH": lean_path(W or judge_dir), "PATH": f"{TOOLCHAIN}/bin:/usr/bin:/bin"},
                600,
            )
        except subprocess.TimeoutExpired:
            return False, False, "judge timeout"
        open(f"{judge_dir}/judge.log", "w").write(out)
        try:
            v = json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return False, False, "judge produced no verdict:\n" + out[-2000:]
        if not v["ok"]:
            return False, False, v["error"][-4000:]
        return True, v["negated"], f"ok ({'refutation' if v['negated'] else 'proof'}) axioms={sorted(v['axioms'])}"
    finally:
        for d in (work, judge_dir):
            if archive:
                os.makedirs(archive, exist_ok=True)
                shutil.move(d, archive)
            else:
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    import sys

    ok, neg, rep = verify(sys.argv[1], sys.argv[2], open(sys.argv[3]).read())
    print("PASS" if ok else "FAIL", "refutation" if neg else "", "\n", rep)
    sys.exit(0 if ok else 1)
