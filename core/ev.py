# core/ev.py

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


def raise_ev(eq: float, rf: float, pot: float, bet: float, raise_to: float, foldfreq: float) -> float:
    """
    2-branch raise model.

    Convention:
      pot = pot BEFORE villain bets
      bet = villain bet size
      raise_to = total raise size (raise-to amount)
      foldfreq = probability villain folds to the raise

    If villain folds: we win pot + bet.
    If villain calls: both players put in (raise_to - bet) more.
    We realize eq*rf of final pot, and we pay our additional_raise.
    """
    if not (0 <= eq <= 1):
        raise ValueError("Equity must be between 0 and 1")
    if not (0 <= rf <= 1):
        raise ValueError("RF must be between 0 and 1")
    if not (0 <= foldfreq <= 1):
        raise ValueError("Fold frequency must be between 0 and 1")
    if pot <= 0 or bet <= 0 or raise_to <= 0:
        raise ValueError("pot, bet, and raise_to must be positive")
    if raise_to <= bet:
        raise ValueError("raise_to must be greater than bet")

    additional_raise = raise_to - bet
    pot_after_bet = pot + bet
    final_pot = pot_after_bet + 2 * additional_raise

    ev_fold_branch = foldfreq * pot_after_bet
    ev_called = (eq * rf * final_pot) - additional_raise
    ev_call_branch = (1 - foldfreq) * ev_called

    return ev_fold_branch + ev_call_branch


def breakeven_fold_raise(eq: float, rf: float, pot: float, bet: float, raise_to: float) -> float:
    """
    Returns foldfreq where EV_raise = 0 under the same raise model.
    Clamped to [0, 1].
    """
    if raise_to <= bet:
        return 1.0

    additional_raise = raise_to - bet
    pot_after_bet = pot + bet
    final_pot = pot_after_bet + 2 * additional_raise

    # A = EV when called (unweighted)
    A = (eq * rf * final_pot) - additional_raise

    # EV = F*pot_after_bet + (1-F)*A
    # 0 = A + F*(pot_after_bet - A)
    denom = (pot_after_bet - A)
    if denom == 0:
        return 1.0

    F = (-A) / denom

    if F < 0:
        return 0.0
    if F > 1:
        return 1.0
    return F

def raise_ev(eq: float, rf: float, pot: float, bet: float, raise_to: float, foldfreq: float) -> float:
    if not (0 <= eq <= 1):
        raise ValueError("Equity must be between 0 and 1")
    if not (0 <= rf <= 1):
        raise ValueError("RF must be between 0 and 1")
    if not (0 <= foldfreq <= 1):
        raise ValueError("Fold frequency must be between 0 and 1")
    if pot <= 0 or bet <= 0 or raise_to <= 0:
        raise ValueError("pot, bet, and raise_to must be positive")
    if raise_to <= bet:
        raise ValueError("raise_to must be greater than bet")

    additional_raise = raise_to - bet
    pot_after_bet = pot + bet
    final_pot = pot_after_bet + 2 * additional_raise

    ev_fold_branch = foldfreq * pot_after_bet
    ev_called = (eq * rf * final_pot) - additional_raise
    ev_call_branch = (1 - foldfreq) * ev_called

    return ev_fold_branch + ev_call_branch


def breakeven_fold_raise(eq: float, rf: float, pot: float, bet: float, raise_to: float) -> float:
    if raise_to <= bet:
        return 1.0

    additional_raise = raise_to - bet
    pot_after_bet = pot + bet
    final_pot = pot_after_bet + 2 * additional_raise

    A = (eq * rf * final_pot) - additional_raise
    denom = (pot_after_bet - A)
    if denom == 0:
        return 1.0

    F = (-A) / denom
    if F < 0:
        return 0.0
    if F > 1:
        return 1.0
    return F