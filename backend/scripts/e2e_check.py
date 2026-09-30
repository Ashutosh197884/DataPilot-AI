"""End-to-end verification: run both demo queries against the live API."""
import json
import sys
import time
import urllib.request

BASE = "http://localhost:8000/api/v1"


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def wait_workflow(wid: str, timeout_s: float = 30.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        wf = call("GET", f"/workflows/{wid}")
        if wf["status"] in ("COMPLETED", "FAILED"):
            return wf
        time.sleep(0.5)
    raise TimeoutError(f"workflow {wid} did not finish in {timeout_s}s")


def main() -> int:
    project = call("GET", "/projects")[0]
    print(f"project: {project['id']}")

    for label, q in [
        ("HARRISON-DEMO", "Compare rainfall and wheat production across Haryana districts from 2020 to 2025."),
        ("EV-DEMO", "Compare EV sales in India from 2022 to 2025 and identify the fastest-growing manufacturers."),
    ]:
        print(f"\n=== {label}: {q}")
        res = call("POST", "/queries", {"project_id": project["id"], "query": q})
        wf = wait_workflow(res["workflow_id"])
        print(f"workflow status: {wf['status']}")
        for s in wf["steps"]:
            mark = {"COMPLETED": "+", "FAILED": "x", "RUNNING": ">", "PENDING": " "}[s["status"]]
            extra = ""
            if s["type"] == "validate" and s.get("output"):
                extra = f" -> {s['output'].get('summary', '')}"
            if s["type"] == "collect" and s.get("output"):
                extra = f" -> {s['output'].get('rows')} rows"
            print(f"  [{mark}] {s['number']:>2}. {s['title']:<38} {s['status']}{extra}")
            if s["status"] == "FAILED":
                print("      ERROR:", s.get("error"))

        if wf["status"] != "COMPLETED":
            print("!! WORKFLOW FAILED — stopping")
            return 1

        dash = call("GET", f"/workflows/{res['workflow_id']}/dashboard")
        print("  KPIs:", json.dumps(dash["kpis"]))
        print("  charts:", [(c["type"], c["title"], len(c["data"])) for c in dash["charts"]])
        print("  insights:")
        for i in dash["insights"]:
            print(f"    - [{i['kind']}] {i['title']}")
        print(f"  quality: {dash['quality']['score']}% (dups={dash['quality']['duplicates']}, invalid={dash['quality']['invalid']})")

        ev = call("GET", f"/workflows/{res['workflow_id']}/evidence")
        first = ev["evidence_items"][0] if ev["evidence_items"] else {}
        print(f"  evidence items: {len(ev['evidence_items'])}; transformations on first: {len(first.get('transformations', []))}")
        print("  source_reference:", first.get("source_reference"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
