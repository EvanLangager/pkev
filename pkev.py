#!/usr/bin/env python3
import argparse
import sys
from core.ev import required_equity, raise_ev, raise_break_even_fold, raise_branches
from core.realization import call_ev_rf
from core.branches import describe_branches
from utils.formatting import to_percent, to_chips


RF_PRESETS = {
    "ip": 0.90,
    "oop": 0.70,
}


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pkev",
        description="♠️ PKEV v1.2 — Poker EV modeling toolkit",
        epilog=(
            "Examples:\n"
            "  pkev reqeq --pot 23.4 --call 11.4\n"
            "  pkev callrf --eq 0.54 --rf 0.80 --pot 23.4 --call 11.4\n"
            "  pkev callrf --eq 0.54 --pos oop --pot 23.4 --call 11.4\n"
            "  pkev raiseev --pot 10 --bet 3 --raise_to 12 --foldfreq 0.35 --eq 0.45 --rf 0.85\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command")

    req = subparsers.add_parser("reqeq", help="Required equity to call")
    req.add_argument("--pot", type=float, required=True, help="Pot size before calling")
    req.add_argument("--call", type=float, required=True, help="Call amount")

    callrf = subparsers.add_parser("callrf", help="Call EV adjusted for realization factor")
    callrf.add_argument("--eq", type=float, required=True, help="Equity as decimal")
    callrf.add_argument("--rf", type=float, default=None, help="Realization factor as decimal")
    callrf.add_argument("--pos", choices=["ip", "oop"], help="Position preset (overrides --rf)")
    callrf.add_argument("--pot", type=float, required=True, help="Current pot size")
    callrf.add_argument("--call", type=float, required=True, help="Amount to call")

    raise_cmd = subparsers.add_parser("raiseev", help="2-branch raise EV model")
    raise_cmd.add_argument("--pot", type=float, required=True, help="Pot before villain bets")
    raise_cmd.add_argument("--bet", type=float, required=True, help="Villain bet size")
    raise_cmd.add_argument("--raise_to", type=float, required=True, help="Your total raise size")
    raise_cmd.add_argument("--foldfreq", type=float, required=True, help="Villain fold frequency vs raise")
    raise_cmd.add_argument("--eq", type=float, required=True, help="Equity when called")
    raise_cmd.add_argument("--rf", type=float, default=None, help="Realization factor as decimal")
    raise_cmd.add_argument("--pos", choices=["ip", "oop"], help="Position preset (overrides --rf)")
    raise_cmd.add_argument("--verbose", action="store_true", help="Show branch breakdown")

    
    model_cmd = subparsers.add_parser("model", help="3-branch EV model (fold/call/raise)")

    model_cmd.add_argument("--pot", type=float, required=True, help="Pot before villain bet")
    model_cmd.add_argument("--bet", type=float, required=True, help="Villain bet size")
    model_cmd.add_argument("--call", type=float, required=True, help="Amount to call")
    model_cmd.add_argument("--raise_to", type=float, required=True, help="Total raise size")
    model_cmd.add_argument("--foldfreq", type=float, required=True, help="Villain fold frequency vs raise")
    model_cmd.add_argument("--eq", type=float, required=True, help="Equity when called")
    model_cmd.add_argument("--rf", type=float, default=None, help="Realization factor")
    model_cmd.add_argument("--pos", choices=["ip", "oop"], help="RF preset (overrides --rf)")
    model_cmd.add_argument("--verbose", action="store_true", help="Show branch breakdown")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "reqeq":
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Call", args.call)

        eq = required_equity(args.call, args.pot)

        print("=== PKEV: Required Equity ===")
        print(f"Pot:             {to_chips(args.pot)}")
        print(f"Call:            {to_chips(args.call)}")
        print(f"Required Equity: {to_percent(eq)}")
        return

    if args.command == "callrf":
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Call", args.call)
        validate_unit_interval("Equity", args.eq)

        rf = resolve_rf(args)
        ev = call_ev_rf(args.eq, rf, args.pot, args.call)

        print("=== PKEV: Call EV (RF Adjusted) ===")
        print(f"Pot:      {to_chips(args.pot)}")
        print(f"Call:     {to_chips(args.call)}")
        print(f"Equity:   {to_percent(args.eq)}")
        print(f"RF:       {to_percent(rf)}")
        print(f"Call EV:  {to_chips(ev)}")
        return

    if args.command == "raiseev":
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Bet", args.bet)
        validate_non_negative("Raise size", args.raise_to)
        validate_unit_interval("Fold frequency", args.foldfreq)
        validate_unit_interval("Equity", args.eq)
    
    if args.command == "model":
        validate_non_negative("Pot", args.pot)
        validate_non_negative("Bet", args.bet)
        validate_non_negative("Call", args.call)
        validate_non_negative("Raise size", args.raise_to)

        validate_unit_interval("Fold frequency", args.foldfreq)
        validate_unit_interval("Equity", args.eq)

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

    print("=== PKEV: EV Model ===")
    print(f"EV(FOLD):   {to_chips(ev_fold)}")
    print(f"EV(CALL):   {to_chips(ev_call)}")
    print(f"EV(RAISE):  {to_chips(ev_raise)}")
    print("")
    print(f"Best Action: {best_action}")
    print(f"Edge vs CALL: {to_chips(edge_vs_call)}")

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

        print("=== PKEV: Raise EV ===")
        print(f"Pot before bet:        {to_chips(args.pot)}")
        print(f"Villain bet:           {to_chips(args.bet)}")
        print(f"Raise to:              {to_chips(args.raise_to)}")
        print(f"Fold frequency:        {to_percent(args.foldfreq)}")
        print(f"Equity when called:    {to_percent(args.eq)}")
        print(f"RF:                    {to_percent(rf)}")
        print(f"Final pot if called:   {to_chips(final_pot_if_called)}")
        print(f"Raise EV:              {to_chips(ev)}")

        if args.verbose:
            print("Branch Breakdown:")
            print(describe_branches(branches))
        if be_fold is None:
            print("Break-even foldfreq:   undefined")
        else:
            print(f"Break-even foldfreq:   {to_percent(be_fold)}")
        return


if __name__ == "__main__":
    main()