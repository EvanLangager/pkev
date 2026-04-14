from core.branches import Branch, weighted_ev


def required_equity(call_amount, pot):
    return call_amount / (pot + call_amount)


def break_even_fold(risk, reward):
    return risk / (risk + reward)


def call_ev(equity, pot, call_amount):
    total_pot = pot + call_amount
    return (equity * total_pot) - call_amount


def bluff_ev(pot, bet, fold_percentage):
    win_when_fold = fold_percentage * pot
    lose_when_called = (1 - fold_percentage) * bet
    return win_when_fold - lose_when_called


def raise_branches(eq: float, rf: float, pot: float, bet: float, raise_to: float, foldfreq: float) -> list[Branch]:
    if not (0 <= eq <= 1):
        raise ValueError("Equity must be between 0 and 1")
    if not (0 <= rf <= 1):
        raise ValueError("RF must be between 0 and 1")
    if not (0 <= foldfreq <= 1):
        raise ValueError("Fold frequency must be between 0 and 1")
    if pot < 0 or bet < 0 or raise_to < 0:
        raise ValueError("pot, bet, and raise_to must be non-negative")
    if raise_to <= bet:
        raise ValueError("raise_to must be greater than bet")

    reward_when_fold = pot + bet
    final_pot_if_called = pot + bet + raise_to + (raise_to - bet)
    ev_when_called = (eq * rf * final_pot_if_called) - raise_to

    return [
        Branch("villain folds", foldfreq, reward_when_fold),
        Branch("villain continues", 1 - foldfreq, ev_when_called),
    ]


def raise_ev(eq: float, rf: float, pot: float, bet: float, raise_to: float, foldfreq: float) -> float:
    branches = raise_branches(eq, rf, pot, bet, raise_to, foldfreq)
    return weighted_ev(branches)


def raise_break_even_fold(eq, rf, pot, bet, raise_to):
    reward_when_fold = pot + bet
    final_pot_if_called = pot + bet + raise_to + (raise_to - bet)
    realized_eq = eq * rf
    ev_when_called = (realized_eq * final_pot_if_called) - raise_to

    denominator = reward_when_fold - ev_when_called
    if denominator == 0:
        return None

    f = -ev_when_called / denominator

    if f < 0:
        return 0.0
    if f > 1:
        return 1.0
    return f
