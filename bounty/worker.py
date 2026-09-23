"""Verifier-box worker: pull pending submissions from the board, verify in the sandbox, pay USDC on Base, post verdicts.

  python3 bounty/worker.py [--loop]   verify pending claims -> paid / verified-unpaid (payment failed) / rejected
  python3 bounty/worker.py pay <id>   retry the USDC send for a verified-unpaid claim

Secrets come from Secrets Manager (`zzz/worker-token`, `zzz/wallet` = {"ADDRESS","PRIVATE_KEY"}) via the instance
role, or from secret/ files when those exist (laptop). Needs ~/.foundry/bin/cast for `pay`, and formal-conjectures
built at FC_COMMIT plus the judge binary for verification (see verify.py).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from verify import verify

BOARD = os.environ.get("BOARD", "https://zzzagents.com")
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base mainnet, 6 decimals
RPC = "https://mainnet.base.org"
CAST = os.path.expanduser("~/.foundry/bin/cast")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS = {p["n"]: p for p in json.load(open(f"{ROOT}/bounty/problems.json"))}


def secret(name, path):
    """Secrets Manager secret `name`, or the local file at `path` if present. Returns the raw string."""
    if os.path.exists(path):
        return open(path).read().strip()
    import boto3

    return boto3.client("secretsmanager", region_name="us-east-1").get_secret_value(SecretId=name)["SecretString"]


TOKEN = secret("zzz/worker-token", f"{ROOT}/secret/worker.token")


def api(path, data=None):
    req = urllib.request.Request(
        BOARD + path, data=json.dumps(data).encode() if data else None, headers={"Content-Type": "application/json", "X-Token": TOKEN}
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def paid_problems():
    return {c["n"] for c in api("/claims?status=paid")}


def run_once():
    paid = paid_problems()
    for s in api("/claims?status=pending"):
        p = PROBLEMS[s["n"]]
        print(f"#{s['id']} problem {s['n']} {s['decl']} -> {s['address']}", flush=True)
        archive = os.path.expanduser(f"~/claims/{s['id']}")  # everything the submission did in its sandbox, kept for forensics
        ok, neg, rep = verify(f"{p['namespace']}.{s['decl']}", f"FormalConjectures.ErdosProblems.«{s['n']}»", s["src"], archive)
        tx = None
        if ok and s["n"] in paid:  # /submit only blocks after a payout, so N copies of one proof can all be pending at once
            rep += "\n\nVERIFIED BUT NOT PAID: problem already paid out"
        elif ok:
            tx, err = send_usdc(s["address"], p["payout"])
            if tx:
                paid.add(s["n"])
            else:
                rep += f"\n\nVERIFIED BUT PAYMENT FAILED: {err}"
        print(api("/verdict", {"id": s["id"], "ok": ok, "negated": neg, "report": rep, "tx": tx}), flush=True)


def send_usdc(to, usd):
    """cast send of `usd` USDC to `to`. Returns (tx_hash, "") or (None, error)."""
    key = secret("zzz/wallet", f"{ROOT}/secret/wallet.env")
    key = (
        json.loads(key)["PRIVATE_KEY"]
        if key.startswith("{")
        else dict(l.split("=", 1) for l in key.splitlines() if "=" in l)["PRIVATE_KEY"]
    )
    r = subprocess.run(
        [CAST, "send", USDC, "transfer(address,uint256)", to, str(usd * 10**6), "--private-key", key, "--rpc-url", RPC, "--json"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if r.returncode:
        return None, r.stderr[-1000:]
    return json.loads(r.stdout)["transactionHash"], ""


def pay(claim_id):
    claims = {c["id"]: c for c in api("/claims?status=verified-unpaid")}
    if claim_id not in claims:
        sys.exit(f"claim {claim_id} is not verified-unpaid")
    c = claims[claim_id]
    if c["n"] in paid_problems():
        sys.exit(f"problem {c['n']} already paid out")
    usd = PROBLEMS[c["n"]]["payout"]
    print(f"paying {usd} USDC to {c['address']} for claim {claim_id} (problem {c['n']} {c['decl']})", flush=True)
    tx, err = send_usdc(c["address"], usd)
    if not tx:
        sys.exit(f"cast failed: {err}")
    print(api("/verdict", {"id": claim_id, "ok": True, "negated": c["negated"], "report": c["report"], "tx": tx}), flush=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["pay"]:
        pay(int(sys.argv[2]))
    else:
        while True:
            run_once()
            if "--loop" not in sys.argv:
                break
            time.sleep(120)
