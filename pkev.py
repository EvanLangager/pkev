#!/usr/bin/env python3
import argparse
import sys
from core.ev import required_equity, raise_ev, raise_break_even_fold, raise_branches
from core.realization import call_ev_rf
from core.branches import describe_branches
from utils.formatting import to_percent, to_chips
from core.model import compare_actions, get_action
from core.actions import make_raise_action

RF_PRESETS = {
    "ip": 0.90,
    "oop": 0.70,
}

def show_startup():
    console.print("\nPoker Math Toolkit", style="header")
    console.print("v3.1 — Every Action Creates Branches\n", style="muted")

    console.print("Usage:", style="highlight")
    console.print("  pkev [command] [options]\n", style="text")

    console.print("Commands:", style="highlight")
    console.print("  reqeq      Calculate required equity for a call", style="text")
    console.print("  callrf     EV of calling with realization factor (RF)", style="text")
    console.print("  model      3-branch EV model (fold/call/raise)", style="text")
    console.print("  save-spot  Save a spot for later reuse", style="text")
    console.print("  list-spots List all saved spots", style="text")
    console.print("  show-spot  Show one saved spot\n", style="text")

    console.print("Examples:", style="highlight")
    console.print("  pkev reqeq --pot 50 --call 15", style="text")
    console.print("  pkev model --scan eq 0.30 0.60 0.05", style="text")
    console.print("  pkev model --scan rf 0.50 1.00 0.05\n", style="text")

def die(message: str) -> None:
    print(f"❌ {message}")
    sys.exit(1)


def validate_non_negative(name: str, value: float) -> None:
    if value < 0:
        die(f"{name} must be a non-negative number.")


def validate_unit_interval(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        die(f"{name} must be between 0 and 1.")


def resolve_rf(args) -> float:
    rf = args.rf
    if getattr(args, "pos", None) is not None:
        rf = RF_PRESETS[args.pos]

    if rf is None:
        die("You must provide either --rf or --pos.")

    validate_unit_interval("Realization factor", rf)
    return rf


def print_header(title: str) -> None:
    print(f"\n♠️  PKEV v1.2  |  {title}\n")


def line(label: str, value: str) -> str:
    return f"{label:<22} {value}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pkev",
        description="♠️ PKEV v1.2 — Poker EV modeling toolkit for branch based decisions",
        epilog=(
            "Examples:\n"
            "  pkev reqeq --pot 23.4 --call 11.4\n"
            "  pkev callrf --eq 0.54 --rf 0.80 --pot 23.4 --call 11.4\n"
            "  pkev callrf --eq 0.54 --pos oop --pot 23.4 --call 11.4\n"
            "  pkev raiseev --pot 10 --bet 3 --raise_to 12 --foldfreq 0.35 --eq 0.45 --rf 0.85\n"
            "  pkev raiseev --pot 10 --bet 3 --raise_to 12 --foldfreq 0.35 --eq 0.45 --rf 0.85 --verbose\n"
            "  pkev model --pot 10 --bet 3 --call 3 --raise_to 12 --foldfreq 0.35 --eq 0.45 --rf 0.85\n"
            "  pkev model --pot 10 --bet 3 --call 3 --raise_to 12 --foldfreq 0.35 --eq 0.45 --rf 0.85 --verbose\n"
            "  pkev model --pot 10 --bet 3 --call 3 --raise_to 12 --eq 0.45 --rf 0.85 --scan foldfreq 0.00 1.00 0.05\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command")

    req = subparsers.add_parser("reqeq", help="Compute required equity to call")
    req.add_argument("--pot", type=float, required=True, help="Pot size before calling")
    req.add_argument("--call", type=float, required=True, help="Call amount")

    callrf = subparsers.add_parser("callrf", help="Compute call EV with realization factor")
    callrf.add_argument("--eq", type=float, required=True, help="Equity as decimal")
    callrf.add_argument("--rf", type=float, default=None, help="Realization factor as decimal")
    callrf.add_argument("--pos", choices=["ip", "oop"], help="Position preset (overrides --rf)")
    callrf.add_argument("--pot", type=float, required=True, help="Current pot size")
    callrf.add_argument("--call", type=float, required=True, help="Amount to call")

    raise_cmd = subparsers.add_parser("raiseev", help="Compute raise EV with branch breakdown")
    raise_cmd.add_argument("--pot", type=float, required=True, help="Pot before villain bets")
    raise_cmd.add_argument("--bet", type=float, required=True, help="Villain bet size")
    raise_cmd.add_argument("--raise_to", type=float, required=True, help="Your total raise size")
    raise_cmd.add_argument("--foldfreq", type=float, required=True, help="Villain fold frequency vs raise")
    raise_cmd.add_argument("--eq", type=float, required=True, help="Equity when called")
    raise_cmd.add_argument("--rf", type=float, default=None, help="Realization factor as decimal")
    raise_cmd.add_argument("--pos", choices=["ip", "oop"], help="Position preset (overrides --rf)")
    raise_cmd.add_argument("--verbose", action="store_true", help="Show branch breakdown")

    model_cmd = subparsers.add_parser(
    "model",
    help="Compare EV of fold, call, and raise in one spot"
)
    model_cmd.add_argument("--pot", type=float, required=True, help="Pot before villain bet")
    model_cmd.add_argument("--bet", type=float, required=True, help="Villain bet size")
    model_cmd.add_argument("--call", type=float, required=True, help="Amount to call")
    model_cmd.add_argument("--raise_to", type=float, required=True, help="Total raise size")
    model_cmd.add_argument("--foldfreq", type=float, help="Villain fold frequency vs raise")
    model_cmd.add_argument("--eq", type=float, required=True, help="Equity when called")
    model_cmd.add_argument("--rf", type=float, default=None, help="Realization factor")
    model_cmd.add_argument("--pos", choices=["ip", "oop"], help="RF preset (overrides --rf)")
    model_cmd.add_argument("--verbose", action="store_true", help="Show branch breakdown")
    model_cmd.add_argument(
        "--scan",
        nargs=4,
        metavar=("FIELD", "START", "END", "STEP"),
        help="Scan a variable: foldfreq, eq, rf",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        show_startup()
	raise SystemExit(0)

    if args.command == "reqeq":
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Call", args.call)

        eq = required_equity(args.call, args.pot)

        print_header("REQUIRED EQUITY")
        print(line("Pot:", to_chips(args.pot)))
        print(line("Call:", to_chips(args.call)))
        print("")
        print(line("Required Equity:", to_percent(eq)))
        return

    if args.command == "callrf":
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Call", args.call)
        validate_unit_interval("Equity", args.eq)

        rf = resolve_rf(args)
        ev = call_ev_rf(args.eq, rf, args.pot, args.call)

        print_header("CALL EV (RF AdjustED)")
        print(line("Pot:", to_chips(args.pot)))
        print(line("Call:", to_chips(args.call)))
        print(line("Equity:", to_percent(args.eq)))
        print(line("RF:", to_percent(rf)))
        print("")
        print(line("Call EV:", to_chips(ev)))
        return

    if args.command == "raiseev":
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Bet", args.bet)
        validate_non_negative("Raise size", args.raise_to)
        validate_unit_interval("Fold frequency", args.foldfreq)
        validate_unit_interval("Equity", args.eq)

        if args.raise_to <= args.bet:
            die("--raise_to must be greater than --bet.")

        rf = resolve_rf(args)

        ev = raise_ev(
            eq=args.eq,
            rf=rf,
            pot=args.pot,
            bet=args.bet,
            raise_to=args.raise_to,
            foldfreq=args.foldfreq,
        )

        branches = raise_branches(
            eq=args.eq,
            rf=rf,
            pot=args.pot,
            bet=args.bet,
            raise_to=args.raise_to,
            foldfreq=args.foldfreq,
        )
        
        be_fold = raise_break_even_fold(
            eq=args.eq,
            rf=rf,
            pot=args.pot,
            bet=args.bet,
            raise_to=args.raise_to,
        )

        final_pot_if_called = args.pot + args.bet + args.raise_to + (args.raise_to - args.bet)

        print_header("RAISE EV")
        print(line("Pot before bet:", to_chips(args.pot)))
        print(line("Villain bet:", to_chips(args.bet)))
        print(line("Raise to:", to_chips(args.raise_to)))
        print(line("Fold frequency:", to_percent(args.foldfreq)))
        print(line("Equity:", to_percent(args.eq)))
        print(line("RF:", to_percent(rf)))
        print(line("Final pot if called:", to_chips(final_pot_if_called)))
        print("")
        print(line("Raise EV:", to_chips(ev)))

        if args.verbose:
            print("\nBranch Breakdown:")
            print(describe_branches(branches))

        if be_fold is None:
            print(line("Break-even foldfreq:", "undefined"))
        else:
            print(line("Break-even foldfreq:", to_percent(be_fold)))
        return

    if args.command == "model":
        # basic validation
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Bet", args.bet)
        validate_non_negative("Call", args.call)
        validate_non_negative("Raise size", args.raise_to)
        validate_unit_interval("Equity", args.eq)

        if args.scan:
            field, start_s, end_s, step_s = args.scan
            start = float(start_s)
            end = float(end_s)
            step = float(step_s)

            if field not in ["foldfreq", "eq", "rf"]:
                die("scan field must be one of: foldfreq, eq, rf")
            print_header(f"SCAN: {field.upper()}")

            print(f"{field:<10} {'EV(FOLD)':>10} {'EV(CALL)':>10} {'EV(RAISE)':>11} {'BEST':>8}")
            print("-" * 54)

            x = start
            while x <= end + 1e-9:
                scan_value = round(x, 10)

                current_foldfreq = args.foldfreq if args.foldfreq is not None else 0.0
                current_eq = args.eq
                current_rf = args.rf

                if field == "foldfreq":
                    current_foldfreq = scan_value
                elif field == "eq":
                    current_eq = scan_value
                elif field == "rf":
                    current_rf = scan_value

                rf = current_rf if current_rf is not None else resolve_rf(args)

                pot_after_bet = args.pot + args.bet

                ev_fold = 0.0
                ev_call = call_ev_rf(current_eq, rf, pot_after_bet, args.call)

                ev_raise = raise_ev(
                    eq=current_eq,
                    rf=rf,
                    pot=args.pot,
                    bet=args.bet,
                    raise_to=args.raise_to,
                    foldfreq=current_foldfreq,
                )

                if ev_raise >= ev_call and ev_raise >= ev_fold:
                    best_action = "RAISE"
                elif ev_call >= ev_fold:
                    best_action = "CALL"
                else:
                    best_action = "FOLD"

                print(
                    f"{scan_value:<10.2f}"
                    f"{ev_fold:>10.2f}"
                    f"{ev_call:>10.2f}"
                    f"{ev_raise:>11.2f}"
                    f"{best_action:>8}"
                )

                x = round(x + step, 10)

            return

        # non-scan flow: ensure foldfreq provided
        if args.foldfreq is None:
            die("--foldfreq is required for model when not scanning.")
        validate_unit_interval("Fold frequency", args.foldfreq)

        if args.raise_to <= args.bet:
            die("--raise_to must be greater than --bet.")

        rf = resolve_rf(args)

        pot_after_bet = args.pot + args.bet

        # --- FOLD ---
        ev_fold = 0.0

        # --- CALL ---
        ev_call = call_ev_rf(args.eq, rf, pot_after_bet, args.call)

        # --- RAISE ---
        ev_raise = raise_ev(
            eq=args.eq,
            rf=rf,
            pot=args.pot,
            bet=args.bet,
            raise_to=args.raise_to,
            foldfreq=args.foldfreq,
        )

        # --- BEST ACTION ---
        best_action = max(
            [("FOLD", ev_fold), ("CALL", ev_call), ("RAISE", ev_raise)],
            key=lambda x: x[1],
        )[0]

        edge_vs_call = max(ev_fold, ev_call, ev_raise) - ev_call

        print_header("EV MODEL")

        print(line("Pot before bet:", to_chips(args.pot)))
        print(line("Villain bet:", to_chips(args.bet)))
        print(line("Call:", to_chips(args.call)))
        print(line("Raise to:", to_chips(args.raise_to)))
        print(line("Fold frequency:", to_percent(args.foldfreq)))
        print(line("Equity:", to_percent(args.eq)))
        print(line("RF:", to_percent(rf)))

        print("")
        print(line("EV(FOLD):", to_chips(ev_fold)))
        print(line("EV(CALL):", to_chips(ev_call)))
        print(line("EV(RAISE):", to_chips(ev_raise)))

        print("")
        print(line("Best Action:", best_action))
        print(line("Edge vs CALL:", to_chips(edge_vs_call)))

        if args.verbose:
            branches = raise_branches(
                eq=args.eq,
                rf=rf,
                pot=args.pot,
                bet=args.bet,
                raise_to=args.raise_to,
                foldfreq=args.foldfreq,
            )

            print("\nRaise Branch Breakdown:")
            print(describe_branches(branches))

        return


if __name__ == "__main__":
    main()
