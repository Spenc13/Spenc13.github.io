"""Run a replay in the terminal without the desktop window (for quick checks)."""
from __future__ import annotations

import asyncio
import json
import sys

from .config import load_prompts
from .session import CallSession


def run_headless(cfg: dict, replay_path: str, verbose: bool = False) -> int:
    prompts = load_prompts()
    mode = "replay_wav" if replay_path.lower().endswith(".wav") else "replay_text"
    last_coach: dict = {}
    printed: dict = {}

    def emit(kind: str, data: dict) -> None:
        if kind == "line" and data.get("final"):
            if printed.get(data["id"]) == data["text"]:
                return
            printed[data["id"]] = data["text"]
            who = "Rep     " if data["speaker"] == "rep" else "Prospect"
            print(f"  [{data['t']}] {who} {data['text']}")
        elif kind == "signal":
            print(f"    >> local trigger: {data['kind']} / {data['label']}")
        elif kind == "coach" and data.get("state") in ("done", "error"):
            if data["state"] == "error":
                print(f"    !! coach: {data['error']}")
            else:
                print(f"    ** COACH ({data.get('latency_s')}s): Say this next: {data.get('say')}")
                print(f"       Tactic: {data.get('tactic')} | Watch-out: {data.get('watch')}")
            last_coach.update(data)
        elif kind == "health":
            print(f"    -- health: stt={data['stt']['state']} coach={data['coach']['state']} {data['coach']['message']}")
        elif kind == "summary" and data.get("state") in ("done", "error"):
            print("\n=== Post-call summary ===")
            print(json.dumps(data.get("summary") or {"error": data.get("error")}, indent=2))
            print(f"Saved to {data.get('dir')}")
        elif kind == "metrics" and verbose:
            print(f"    .. metrics {data['scores']} overall={data['overall']}")
        elif kind == "toast":
            print(f"    -- {data['text']}")

    async def main() -> None:
        print("Reminder: on real calls, tell the prospect the call is recorded.\n")
        s = CallSession(cfg, prompts, emit, mode, replay_path)
        await s.start()
        await s.wait_ended()
        m = s.metrics.snapshot()
        print("\n=== Metrics ===")
        print(json.dumps({k: m[k] for k in ("rep_share_pct", "rep_wpm", "questions", "objection_count",
                                            "scores", "overall", "recommendations")}, indent=2))

    asyncio.run(main())
    sys.stdout.flush()
    return 0
