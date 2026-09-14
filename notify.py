"""Email new posts and claim verdicts via SNS. Run by notify.timer on the box; state in notify.json."""

import json
import os
import sqlite3

import boto3  # preinstalled on Ubuntu cloud images; publishes via the instance role

STATE = "notify.json"
state = json.load(open(STATE)) if os.path.exists(STATE) else {"post": 0, "claim": 0, "verdicts": []}
c = sqlite3.connect("board.db")
msgs = []
for i, key, body in c.execute("select id, key, body from posts where id > ? order by id", (state["post"],)):
    msgs.append((f"post #{i}", f"key: {key[:80]}\n\n{body}"))
    state["post"] = i
for i, n, decl, address, status, report in c.execute("select id, n, decl, address, status, report from claims order by id"):
    if i > state["claim"]:
        msgs.append((f"claim #{i} on Erdős {n}", f"{decl}\n{address}\nstatus: {status}"))
        state["claim"] = i
    if status != "pending" and i not in state["verdicts"]:
        msgs.append((f"verdict #{i}: {status} (Erdős {n})", f"{decl}\n{address}\n\n{(report or '')[-1500:]}"))
        state["verdicts"].append(i)
sns = boto3.client("sns")
for subject, body in msgs:
    sns.publish(TopicArn=os.environ["TOPIC"], Subject=f"[zzz] {subject}"[:100], Message=body)
json.dump(state, open(STATE, "w"))
