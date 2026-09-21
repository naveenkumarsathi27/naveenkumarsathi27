"""
Cost-comparison harness for the Higgsfield pay-as-you-go API.

Runs the SAME prompt across a list of models, records the actual USD cost of
each generation to a CSV, and prints a cheapest-first table. Use it during the
7-day launch window to find your cheapest viable image/video model.

Usage:
    python -m higgsfield.cost_test --kind image
    python -m higgsfield.cost_test --kind video --prompt "a neon city drone shot"
    python -m higgsfield.cost_test --kind image --dry-run   # just print the plan

Edit IMAGE_MODELS / VIDEO_MODELS below with the model slugs and params you want
to compare. Model slugs come from the API catalog (console pricing page).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

from .client import HiggsfieldClient, HiggsfieldError

# ── Models to compare. Fill slugs/params from the API catalog you can see in the
#    console. These are starting guesses spanning cheap→premium; adjust freely. ──
IMAGE_MODELS = [
    {"model": "soul-2",               "params": {"aspect_ratio": "1:1"}},
    {"model": "qwen-image",           "params": {"aspect_ratio": "1:1"}},
    {"model": "ideogram-v3",          "params": {"aspect_ratio": "1:1"}},
    {"model": "recraft-v3",           "params": {"aspect_ratio": "1:1"}},
]

VIDEO_MODELS = [
    {"model": "minimax",       "params": {"duration": 5, "aspect_ratio": "16:9"}},
    {"model": "ltx-video",     "params": {"duration": 5, "aspect_ratio": "16:9"}},
    {"model": "seedance-2.5",  "params": {"duration": 5, "aspect_ratio": "16:9"}},
    {"model": "kling-3.0",     "params": {"duration": 5, "aspect_ratio": "16:9"}},
]

DEFAULT_PROMPTS = {
    "image": "a photorealistic product shot of a ceramic coffee mug on a wooden table, soft morning light",
    "video": "a slow cinematic push-in on a steaming cup of coffee on a wooden table, morning light",
}

RESULTS_CSV = Path(__file__).resolve().parent.parent / "cost_results.csv"


def run(kind: str, prompt: str, dry_run: bool) -> None:
    models = IMAGE_MODELS if kind == "image" else VIDEO_MODELS
    print(f"\n{kind.upper()} cost test — {len(models)} models\nprompt: {prompt}\n")

    if dry_run:
        for m in models:
            print(f"  would run: {m['model']:<16} params={m['params']}")
        print("\n(dry run — no API calls, no charges)")
        return

    client = HiggsfieldClient()
    try:
        print(f"balance before: {client.balance()}\n")
    except HiggsfieldError as e:
        print(f"[warn] balance check failed (verify BALANCE_PATH): {e}\n")

    rows = []
    for m in models:
        model, params = m["model"], m["params"]
        print(f"→ {model} …", end=" ", flush=True)
        try:
            res = client.generate(model, prompt=prompt, **params)
            cost = res.cost_usd
            print(f"{res.status}  cost=${cost if cost is not None else '?'}  "
                  f"outputs={len(res.outputs)}")
            rows.append((model, res.status, cost, params, res.outputs[:1]))
        except HiggsfieldError as e:
            print(f"FAILED: {e}")
            rows.append((model, "error", None, params, [str(e)[:120]]))

    _write_csv(kind, prompt, rows)
    _print_ranking(rows)


def _write_csv(kind, prompt, rows) -> None:
    new = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "kind", "model", "status", "cost_usd", "params", "prompt", "output"])
        ts = dt.datetime.now().isoformat(timespec="seconds")
        for model, status, cost, params, outputs in rows:
            w.writerow([ts, kind, model, status, cost, params, prompt,
                        outputs[0] if outputs else ""])
    print(f"\nlogged → {RESULTS_CSV}")


def _print_ranking(rows) -> None:
    priced = [r for r in rows if r[2] is not None]
    if not priced:
        print("\nNo costs captured — check COST_FIELD mapping in client.py.")
        return
    priced.sort(key=lambda r: r[2])
    print("\ncheapest first:")
    for model, status, cost, *_ in priced:
        print(f"  ${cost:<7.4f}  {model}  ({status})")


def main() -> None:
    p = argparse.ArgumentParser(description="Higgsfield API cost comparison")
    p.add_argument("--kind", choices=["image", "video"], default="image")
    p.add_argument("--prompt", default=None)
    p.add_argument("--dry-run", action="store_true", help="print the plan, make no calls")
    args = p.parse_args()
    prompt = args.prompt or DEFAULT_PROMPTS[args.kind]
    try:
        run(args.kind, prompt, args.dry_run)
    except HiggsfieldError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
