"""Laptop-side worker: pull pending submissions from the board, verify, pay USDC on Base, post verdicts.

Run: python3 bounty/worker.py [--loop]. Needs secret/wallet.env, secret/worker.token, ~/.foundry/bin/cast, formal-conjectures
built at FC_COMMIT (see verify.py).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from verify import verify_either

BOARD = os.environ.get("BOARD", "http://3.216.55.66")
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base mainnet, 6 decimals
RPC = "https://mainnet.base.org"
CAST = os.path.expanduser("~/.foundry/bin/cast")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WALLET = dict(line.strip().split("=", 1) for line in open(f"{ROOT}/secret/wallet.env") if "=" in line)
TOKEN = open(f"{ROOT}/secret/worker.token").read().strip()
PROBLEMS = {p["n"]: p for p in json.load(open(f"{ROOT}/bounty/problems.json"))}


def api(path, data=None):
    req = urllib.request.Request(
        BOARD + path, data=json.dumps(data).encode() if data else None, headers={"Content-Type": "application/json", "X-Token": TOKEN}
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def pay(to, usd):
    if os.environ.get("DRY"):
        return "dry-run", ""
    r = subprocess.run(
        [
            CAST,
            "send",
            USDC,
            "transfer(address,uint256)",
            to,
            str(usd * 10**6),
            "--private-key",
            WALLET["PRIVATE_KEY"],
            "--rpc-url",
            RPC,
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode:
        return None, r.stderr[-1000:]
    return json.loads(r.stdout)["transactionHash"], ""


def run_once():
    for s in api("/claims"):
        p = PROBLEMS[s["n"]]
        print(f"#{s['id']} problem {s['n']} {s['decl']} -> {s['address']}", flush=True)
        ok, neg, rep = verify_either(f"{p['namespace']}.{s['decl']}", f"FormalConjectures.ErdosProblems.«{s['n']}»", s["src"])
        v = {"id": s["id"], "ok": ok, "negated": neg, "report": rep, "tx": None}
        if ok:
            tx, err = pay(s["address"], p["payout"])
            v["tx"] = tx
            if not tx:
                v["report"] += f"\n\nVERIFIED BUT PAYMENT FAILED: {err}"
        print(api("/verdict", v), flush=True)


if __name__ == "__main__":
    while True:
        run_once()
        if "--loop" not in sys.argv:
            break
        time.sleep(120)
