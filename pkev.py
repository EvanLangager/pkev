#!/usr/bin/env python3
"""
PKEV — Poker EV Modeling Toolkit (v3.1)

Core idea: Every action creates branches.
We compute EV as a weighted average across branch outcomes.

Commands:
  - reqeq      : required equity for a call
  - callrf     : call EV with realization factor (RF)
  - model      : 3-branch model (fold/call/raise) + scan mode
  - save-spot  : save a spot for later reuse
  - list-spots : list saved spots
  - show-spot  : show one saved spot

Branch model (facing a bet):
  Fold:
    EV = 0

  Call:
    final_pot = pot_after_bet + call
    EV_call = (eq * rf) * final_pot - call

  Raise (2 branches):
    villain folds with probability foldfreq
    villain continues with probability (1 - foldfreq)

    mode="pre"  (default): raise instead of call
      win_when_fold = pot_after_bet

    mode="post": call-then-raise style accounting
      win_when_fold = pot_after_bet + call

    When villain continues:
      addl = raise_to - call
      pot_if_continue = pot_after_bet + raise_to + addl
      EV_continue = (eq * rf) * pot_if_continue - raise_to

    EV_raise = foldfreq * win_when_fold + (1 - foldfreq) * EV_continue
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.spots import get_spot, load_spots, upsert_spot, resolve_value
import rich.console
import rich.theme

pkev_theme = rich.theme.Theme({
    "header": "bold #2DD4BF",
    "text": "#C9D1D9",
    "muted": "#8B949E",
    "positive": "bold #00FF88",
    "negative": "bold #FF4D4D",
    "highlight": "bold white"
})

console = rich.console.Console(theme=pkev_theme)
def print_ev_model(ev_fold, ev_call, ev_raise):
    console.print("\n--- PKEV EV MODEL v3.0 ---\n", style="header")

    console.print(f"EV(FOLD):   {ev_fold:.2f}", style="text")
    console.print(f"EV(CALL):   {ev_call:.2f}", style="text")

    # Highlight best action
    best = max(ev_fold, ev_call, ev_raise)

    if ev_raise == best:
        console.print(f"EV(RAISE):  {ev_raise:.2f}  ✓", style="positive")
    else:
        console.print(f"EV(RAISE):  {ev_raise:.2f}", style="text")

    console.print("")

    if best == ev_raise:
        console.print("Best Action: RAISE", style="positive")
    elif best == ev_call:
        console.print("Best Action: CALL", style="positive")
    else:
        console.print("Best Action: FOLD", style="positive")
# ----------------------------
# Optional imports (fallbacks)
# ----------------------------
try:
    from core.ev import required_equity as _required_equity  # type: ignore
except Exception:
    def _required_equity(call_amount: float, pot: float) -> float:
        return call_amount / (pot + call_amount)


try:
    from core.realization import call_ev_rf as _call_ev_rf  # type: ignore
except Exception:
    def _call_ev_rf(equity: float, realization: float, pot: float, call_amount: float) -> float:
        total_pot = pot + call_amount
        realized_equity = equity * realization
        return (realized_equity * total_pot) - call_amount


try:
    from utils.formatting import to_percent as _to_percent, to_chips as _to_chips  # type: ignore
except Exception:
    def _to_percent(x: float) -> str:
        return f"{x * 100:.2f}%"

    def _to_chips(x: float) -> str:
        return f"{x:,.2f} chips"


# ----------------------------
# Constants / presets
# ----------------------------
RF_PRESETS = {
    "ip": 0.90,
    "oop": 0.70,
}


# ----------------------------
# Helpers
# ----------------------------
def _now_ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _die(msg: str, code: int = 2) -> None:
    raise SystemExit(msg)


def _check_range_01(name: str, value: float) -> None:
    if not (0.0 <= value <= 1.0):
        _die(f"❌ {name} must be between 0 and 1. Got: {value}")


def _check_nonneg(name: str, value: float) -> None:
    if value < 0:
        _die(f"❌ {name} must be >= 0. Got: {value}")


def _resolve_rf(rf: Optional[float], pos: Optional[str]) -> float:
    if pos is not None:
        return RF_PRESETS[pos]
    if rf is None:
        _die("❌ Provide either --rf or --pos (ip/oop).")
    return rf


def _append_csv_row(csv_path: Path, headers: list[str], row: dict) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _frange(start: float, end: float, step: float) -> list[float]:
    """Inclusive float range with rounding safety."""
    if step <= 0:
        _die("❌ scan step must be > 0")

    values: list[float] = []
    x = start
    while x <= end + 1e-9:
        values.append(round(x, 10))
        x += step
    return values


# ----------------------------
# Model math
# ----------------------------
@dataclass(frozen=True)
class ModelInputs:
    pot_before_bet: float
    bet: float
    call: float
    raise_to: float
    foldfreq: float
    eq: float
    rf: float
    mode: str  # "pre" or "post"


@dataclass(frozen=True)
class ModelOutputs:
    ev_fold: float
    ev_call: float
    ev_raise: float
    best_action: str
    edge_vs_call: float


def ev_model_3branch(inp: ModelInputs) -> ModelOutputs:
    pot_after_bet = inp.pot_before_bet + inp.bet

    # Fold
    ev_fold = 0.0

    # Call
    ev_call = _call_ev_rf(inp.eq, inp.rf, pot_after_bet, inp.call)

    # Raise
    addl = inp.raise_to - inp.call
    if addl < 0:
        _die("❌ --raise_to must be >= --call (raise size must be at least a call).")

    if inp.mode == "pre":
        win_when_fold = pot_after_bet
    elif inp.mode == "post":
        win_when_fold = pot_after_bet + inp.call
    else:
        _die("❌ --mode must be 'pre' or 'post'.")

    pot_if_continue = pot_after_bet + inp.raise_to + addl
    ev_continue = (inp.eq * inp.rf) * pot_if_continue - inp.raise_to
    ev_raise = inp.foldfreq * win_when_fold + (1.0 - inp.foldfreq) * ev_continue

    best_action = "FOLD"
    best_ev = ev_fold

    if ev_call > best_ev:
        best_action, best_ev = "CALL", ev_call
    if ev_raise > best_ev:
        best_action, best_ev = "RAISE", ev_raise

    edge_vs_call = best_ev - ev_call

    return ModelOutputs(
        ev_fold=ev_fold,
        ev_call=ev_call,
        ev_raise=ev_raise,
        best_action=best_action,
        edge_vs_call=edge_vs_call,
    )


# ----------------------------
# Parser
# ----------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pkev",
        description="♠️ PKEV v3.1 — Poker EV Modeling Toolkit (branches-first)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Quick usage:\n"
            "  pkev reqeq  --pot 20 --call 10\n"
            "  pkev callrf --pot 10 --call 3 --eq 0.42 --pos oop\n"
            "  pkev save-spot bbvbtn_k72_76s --pot 10 --bet 3 --call 3 --raise_to 12 --eq 0.52 --rf 0.70 --foldfreq 0.35\n"
            "  pkev list-spots\n"
            "  pkev show-spot bbvbtn_k72_76s\n"
            "  pkev model --spot bbvbtn_k72_76s\n"
            "  pkev model --spot bbvbtn_k72_76s --foldfreq 0.45\n"
            "  pkev model --spot bbvbtn_k72_76s --scan foldfreq 0.20 0.60 0.05\n"
            "  pkev model --spot bbvbtn_k72_76s --foldfreq 0.35 --scan eq 0.30 0.60 0.05\n"
            "  pkev model --spot bbvbtn_k72_76s --scan foldfreq 0.00 0.60 0.05 --scan-csv scans/test.csv\n"
            "\n"
            "Branch reminders:\n"
            "  EV = Σ (probability × branch_EV)\n"
            "  RF compresses future-street branches into one number.\n"
            "  Scan mode lets you sweep one variable and compare EV across assumptions.\n"
        ),
    )

    sub = p.add_subparsers(dest="cmd")

    # reqeq
    req = sub.add_parser("reqeq", help="Required equity to call a bet")
    req.add_argument("--pot", type=float, required=True, help="Pot size before calling")
    req.add_argument("--call", type=float, required=True, help="Amount to call")
    req.add_argument("--log", action="store_true", help="Append result to CSV log")
    req.add_argument("--logfile", type=str, default="pkev_log.csv", help="CSV log path")
    req.add_argument("--note", type=str, default="", help="Optional note for log row")

    # callrf
    crf = sub.add_parser("callrf", help="Call EV adjusted for realization factor (RF)")
    crf.add_argument("--pot", type=float, required=True, help="Pot size before calling")
    crf.add_argument("--call", type=float, required=True, help="Amount to call")
    crf.add_argument("--eq", type=float, required=True, help="Equity as decimal (0..1)")
    crf.add_argument("--rf", type=float, default=None, help="Realization factor as decimal (0..1)")
    crf.add_argument("--pos", type=str, choices=["ip", "oop"], default=None, help="RF preset (overrides --rf)")
    crf.add_argument("--log", action="store_true", help="Append result to CSV log")
    crf.add_argument("--logfile", type=str, default="pkev_log.csv", help="CSV log path")
    crf.add_argument("--note", type=str, default="", help="Optional note for log row")

    # model
    mdl = sub.add_parser("model", help="3-branch EV model: fold/call/raise + scan mode")
    mdl.add_argument("--pot", type=float, help="Pot BEFORE villain's bet (pot_before_bet)")
    mdl.add_argument("--bet", type=float, help="Villain bet size")
    mdl.add_argument("--call", type=float, help="Amount to call (usually equals --bet)")
    mdl.add_argument("--raise_to", type=float, help="Total raise size (your total investment)")
    mdl.add_argument("--foldfreq", type=float, help="Villain fold frequency vs your raise (0..1)")
    mdl.add_argument("--eq", type=float, help="Your equity when villain continues (0..1)")
    mdl.add_argument("--rf", type=float, help="Realization factor (0..1)")
    mdl.add_argument("--pos", type=str, choices=["ip", "oop"], default=None, help="RF preset (overrides --rf)")
    mdl.add_argument(
        "--mode",
        type=str,
        choices=["pre", "post"],
        default="pre",
        help=(
            "Raise accounting mode:\n"
            "  pre  = raise instead of call (default)\n"
            "  post = treat raise as call-then-raise accounting"
        ),
    )
    mdl.add_argument("--spot", type=str, help="Load a saved spot by name")
    mdl.add_argument(
        "--scan",
        nargs=4,
        metavar=("FIELD", "START", "END", "STEP"),
        help=(
            "Scan one variable across a range.\n"
            "Allowed fields: foldfreq, eq, rf\n"
            "Example: --scan foldfreq 0.20 0.60 0.05"
        ),
    )
    mdl.add_argument(
        "--scan-csv",
        type=str,
        default=None,
        help="Optional CSV output path for scan results",
    )
    mdl.add_argument("--log", action="store_true", help="Append result to CSV log")
    mdl.add_argument("--logfile", type=str, default="pkev_log.csv", help="CSV log path")
    mdl.add_argument("--note", type=str, default="", help="Optional note for log row")

    # save-spot
    save_spot_parser = sub.add_parser("save-spot", help="Save a poker spot for later reuse.")
    save_spot_parser.add_argument("name", help="Name of the saved spot")
    save_spot_parser.add_argument("--pot", type=float, required=True, help="Pot before villain bet")
    save_spot_parser.add_argument("--bet", type=float, required=True, help="Villain bet amount")
    save_spot_parser.add_argument("--call", type=float, required=True, help="Hero call amount")
    save_spot_parser.add_argument("--raise_to", type=float, required=True, help="Hero raise-to size")
    save_spot_parser.add_argument("--eq", type=float, required=True, help="Hero equity (0 to 1)")
    save_spot_parser.add_argument("--rf", type=float, required=True, help="Realization factor (0 to 1)")
    save_spot_parser.add_argument("--foldfreq", type=float, help="Villain fold frequency (0 to 1)")
    save_spot_parser.add_argument("--note", type=str, help="Optional note about the spot")

    # list-spots
    sub.add_parser("list-spots", help="List all saved poker spots.")

    # show-spot
    show_spot_parser = sub.add_parser("show-spot", help="Show one saved poker spot.")
    show_spot_parser.add_argument("name", help="Saved spot name")

    return p


# ----------------------------
# Command helpers
# ----------------------------
def _resolve_model_inputs(
    args: argparse.Namespace,
    scan_field: str | None = None,
) -> tuple[dict, float | None]:
    spot_data = {}
    if args.spot:
        spot_data = get_spot(args.spot)

    pot = resolve_value(args.pot, spot_data, "pot")
    bet = resolve_value(args.bet, spot_data, "bet")
    call = resolve_value(args.call, spot_data, "call")
    raise_to = resolve_value(args.raise_to, spot_data, "raise_to")
    foldfreq = resolve_value(args.foldfreq, spot_data, "foldfreq")
    eq = resolve_value(args.eq, spot_data, "eq")
    rf_input = resolve_value(args.rf, spot_data, "rf")

    values = {
        "pot": pot,
        "bet": bet,
        "call": call,
        "raise_to": raise_to,
        "foldfreq": foldfreq,
        "eq": eq,
        "rf": rf_input,
    }

    required_fields = {"pot", "bet", "call", "raise_to", "foldfreq", "eq", "rf"}
    if scan_field is not None:
        required_fields.discard(scan_field)

    missing = [name for name in required_fields if values[name] is None]
    if missing:
        _die(f"❌ Missing required model inputs: {', '.join(missing)}")

    _check_nonneg("pot", pot)
    _check_nonneg("bet", bet)
    _check_nonneg("call", call)
    _check_nonneg("raise_to", raise_to)

    if foldfreq is not None:
        _check_range_01("foldfreq", foldfreq)
    if eq is not None:
        _check_range_01("eq", eq)
    if rf_input is not None:
        _check_range_01("rf", rf_input)

    return values, rf_input


# ----------------------------
# Commands
# ----------------------------
def cmd_reqeq(args: argparse.Namespace) -> None:
    _check_nonneg("pot", args.pot)
    _check_nonneg("call", args.call)

    eq = _required_equity(args.call, args.pot)

    print(f"Required Equity: {_to_percent(eq)}")

    if args.log:
        headers = ["timestamp", "command", "pot", "call", "req_equity", "note"]
        row = {
            "timestamp": _now_ts(),
            "command": "reqeq",
            "pot": args.pot,
            "call": args.call,
            "req_equity": eq,
            "note": args.note,
        }
        _append_csv_row(Path(args.logfile), headers, row)


def cmd_callrf(args: argparse.Namespace) -> None:
    _check_nonneg("pot", args.pot)
    _check_nonneg("call", args.call)
    _check_range_01("eq", args.eq)

    rf = _resolve_rf(args.rf, args.pos)
    _check_range_01("rf", rf)

    ev = _call_ev_rf(args.eq, rf, args.pot, args.call)

    print(f"Call EV (RF adjusted): {_to_chips(ev)}  | eq={_to_percent(args.eq)} rf={_to_percent(rf)}")

    if args.log:
        headers = ["timestamp", "command", "pot", "call", "eq", "rf", "ev_call", "note"]
        row = {
            "timestamp": _now_ts(),
            "command": "callrf",
            "pot": args.pot,
            "call": args.call,
            "eq": args.eq,
            "rf": rf,
            "ev_call": ev,
            "note": args.note,
        }
        _append_csv_row(Path(args.logfile), headers, row)


def cmd_model(args: argparse.Namespace) -> None:
    scan_field = args.scan[0] if args.scan else None
    resolved, rf_input = _resolve_model_inputs(args, scan_field=scan_field)

    # ----------------------------
    # Scan mode
    # ----------------------------
    if args.scan:
        field, start_s, end_s, step_s = args.scan

        allowed_fields = {"foldfreq", "eq", "rf"}
        if field not in allowed_fields:
            _die(f"❌ scan field must be one of: {', '.join(sorted(allowed_fields))}")

        try:
            start = float(start_s)
            end = float(end_s)
            step = float(step_s)
        except ValueError:
            _die("❌ scan values must be numeric: START END STEP")

        if start > end:
            _die("❌ scan START must be <= END")

        scan_values = _frange(start, end, step)

        print(f"\n--- Scan: {field} from {start:.2f} to {end:.2f} step {step:.2f} ---")
        if args.spot:
            print(f"Spot: {args.spot}")
        print()
        print(f"{field:<10} {'EV(FOLD)':>10} {'EV(CALL)':>10} {'EV(RAISE)':>11} {'BEST':>8}")

        prev_diff = None
        prev_scan_val = None
        threshold_found = False
        threshold_value = None
        scan_rows = []

        for scan_val in scan_values:
            current = resolved.copy()

            if field == "rf":
                current_rf = scan_val
                _check_range_01("rf", current_rf)
            else:
                current[field] = scan_val
                current_rf = _resolve_rf(current["rf"], args.pos)

            if current["foldfreq"] is not None:
                _check_range_01("foldfreq", current["foldfreq"])
            if current["eq"] is not None:
                _check_range_01("eq", current["eq"])

            inp = ModelInputs(
                pot_before_bet=current["pot"],
                bet=current["bet"],
                call=current["call"],
                raise_to=current["raise_to"],
                foldfreq=current["foldfreq"],
                eq=current["eq"],
                rf=current_rf,
                mode=args.mode,
            )
            out = ev_model_3branch(inp)

            scan_rows.append({
                "spot": args.spot or "",
                "scan_field": field,
                "scan_value": scan_val,
                "pot": current["pot"],
                "bet": current["bet"],
                "call": current["call"],
                "raise_to": current["raise_to"],
                "foldfreq": current["foldfreq"],
                "eq": current["eq"],
                "rf": current_rf,
                "mode": args.mode,
                "ev_fold": out.ev_fold,
                "ev_call": out.ev_call,
                "ev_raise": out.ev_raise,
                "best_action": out.best_action,
            })

            diff = out.ev_raise - out.ev_call

            if prev_diff is not None and prev_scan_val is not None and not threshold_found:
                if prev_diff < 0 and diff >= 0:
                    if diff == prev_diff:
                        threshold_value = scan_val
                    else:
                        fraction = (0 - prev_diff) / (diff - prev_diff)
                        threshold_value = prev_scan_val + fraction * (scan_val - prev_scan_val)
                    threshold_found = True

            label = f"{scan_val:.2%}"

            print(
                f"{label:<10} "
                f"{out.ev_fold:>10.2f} "
                f"{out.ev_call:>10.2f} "
                f"{out.ev_raise:>11.2f} "
                f"{out.best_action:>8}"
            )

            prev_diff = diff
            prev_scan_val = scan_val

        print()

        if args.scan_csv:
            csv_path = Path(args.scan_csv)
            headers = [
                "spot",
                "scan_field",
                "scan_value",
                "pot",
                "bet",
                "call",
                "raise_to",
                "foldfreq",
                "eq",
                "rf",
                "mode",
                "ev_fold",
                "ev_call",
                "ev_raise",
                "best_action",
            ]
            csv_path.parent.mkdir(parents=True, exist_ok=True)

            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(scan_rows)

            print(f"📄 Scan results saved to: {csv_path}")

        if threshold_found and threshold_value is not None:
            print(f"⚡ Raise becomes better than CALL at ~{threshold_value:.2%} {field}\n")
        else:
            print("⚠️ No crossover found in this scan range.\n")

        return

    # ----------------------------
    # Normal single-run mode
    # ----------------------------
    rf = _resolve_rf(rf_input, args.pos)

    inp = ModelInputs(
        pot_before_bet=resolved["pot"],
        bet=resolved["bet"],
        call=resolved["call"],
        raise_to=resolved["raise_to"],
        foldfreq=resolved["foldfreq"],
        eq=resolved["eq"],
        rf=rf,
        mode=args.mode,
    )
    out = ev_model_3branch(inp)

    pot_after_bet = inp.pot_before_bet + inp.bet
    addl = inp.raise_to - inp.call

    print(f"\n--- EV Model (v3.1) ---")
    if args.spot:
        print(f"Spot: {args.spot}")
    print(
        f"Inputs: pot_before_bet={inp.pot_before_bet:.2f} | bet={inp.bet:.2f} -> pot_after_bet={pot_after_bet:.2f} | "
        f"call={inp.call:.2f} | raise_to={inp.raise_to:.2f} (addl={addl:.2f}) | "
        f"foldfreq={_to_percent(inp.foldfreq)} | eq={_to_percent(inp.eq)} | rf={_to_percent(inp.rf)} | mode={inp.mode}"
    )
    print(f"EV(FOLD):  {_to_chips(out.ev_fold)}")
    print(f"EV(CALL):  {_to_chips(out.ev_call)}")
    print(f"EV(RAISE): {_to_chips(out.ev_raise)}")
    print(f"\nBest Action: {out.best_action}")
    print(f"Edge vs CALL: {_to_chips(out.edge_vs_call)}\n")

    if args.log:
        headers = [
            "timestamp", "command", "spot",
            "pot_before_bet", "bet", "pot_after_bet",
            "call", "raise_to", "addl",
            "foldfreq", "eq", "rf", "mode",
            "ev_fold", "ev_call", "ev_raise",
            "best_action", "edge_vs_call",
            "note",
        ]
        row = {
            "timestamp": _now_ts(),
            "command": "model",
            "spot": args.spot or "",
            "pot_before_bet": inp.pot_before_bet,
            "bet": inp.bet,
            "pot_after_bet": pot_after_bet,
            "call": inp.call,
            "raise_to": inp.raise_to,
            "addl": addl,
            "foldfreq": inp.foldfreq,
            "eq": inp.eq,
            "rf": inp.rf,
            "mode": inp.mode,
            "ev_fold": out.ev_fold,
            "ev_call": out.ev_call,
            "ev_raise": out.ev_raise,
            "best_action": out.best_action,
            "edge_vs_call": out.edge_vs_call,
            "note": args.note,
        }
        _append_csv_row(Path(args.logfile), headers, row)


# ----------------------------
# Main
# ----------------------------
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        raise SystemExit(0)

    if args.cmd == "reqeq":
        cmd_reqeq(args)

    elif args.cmd == "callrf":
        cmd_callrf(args)

    elif args.cmd == "model":
        cmd_model(args)

    elif args.cmd == "save-spot":
        spot_values = {
            "pot": args.pot,
            "bet": args.bet,
            "call": args.call,
            "raise_to": args.raise_to,
            "eq": args.eq,
            "rf": args.rf,
        }

        if args.foldfreq is not None:
            spot_values["foldfreq"] = args.foldfreq

        if args.note:
            spot_values["note"] = args.note

        upsert_spot(args.name, spot_values)
        print(f"Saved spot: {args.name}")
        print(json.dumps(spot_values, indent=2))

    elif args.cmd == "list-spots":
        spots = load_spots()
        if not spots:
            print("No saved spots found.")
        else:
            print("--- Saved Spots ---")
            for name in sorted(spots):
                print(name)

    elif args.cmd == "show-spot":
        spot = get_spot(args.name)
        print(f"--- Spot: {args.name} ---")
        print(json.dumps(spot, indent=2))

    else:
        _die(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    main()