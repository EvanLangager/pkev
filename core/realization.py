def call_ev_rf(equity, realization, pot, call_amount):
    total_pot = pot + call_amount
    realized_equity = equity * realization
    return (realized_equity * total_pot) - call_amount