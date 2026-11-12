"""Live Sales Coach.

    python main.py                         open the app (live calls or replays)
    python main.py --replay samples/remodeler_too_expensive.txt
    python main.py --replay mycall.wav     replay a recording through Deepgram
    python main.py --replay FILE --headless    replay in the terminal, no window
    python main.py --list-devices          show microphones and loopback devices
"""
from __future__ import annotations

import argparse
import logging
import sys

from coach.config import get, load_config, load_env


def main() -> int:
    ap = argparse.ArgumentParser(description="Live Sales Coach")
    ap.add_argument("--config", help="path to config.yaml")
    ap.add_argument("--replay", metavar="FILE", help="WAV recording or .txt script to replay")
    ap.add_argument("--speed", type=float, help="replay speed multiplier (text scripts)")
    ap.add_argument("--headless", action="store_true", help="run a replay in the terminal without the window")
    ap.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    # Keep HTTP client logs quiet: they can include request metadata.
    for noisy in ("httpx", "httpcore", "anthropic", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    load_env()
    cfg = load_config(args.config)
    if args.speed:
        cfg.setdefault("replay", {})["speed"] = args.speed

    if args.list_devices:
        from coach.audio import print_devices

        print_devices(get(cfg, "audio.backend", "auto"))
        return 0

    if args.headless:
        if not args.replay:
            ap.error("--headless needs --replay FILE")
        from coach.headless import run_headless

        return run_headless(cfg, args.replay, args.verbose)

    from coach.desktop import run_desktop

    return run_desktop(cfg, args.replay)


if __name__ == "__main__":
    sys.exit(main())
