# PKEV — Poker EV Modeling Toolkit

PKEV is a command-line tool for modeling poker decisions using structured, branch-based expected value (EV) calculations.

It helps turn complex poker spots into clear, testable decisions.

---

##  What it does

PKEV breaks decisions into branches and calculates EV for each option:

- Fold:  EV = 0  
- Call:  EV based on equity and realization  
- Raise: EV based on fold equity + post-call performance  

This lets you compare actions directly and identify the most profitable line.

---

##  Example

```bash
pkev model --pot 8.43 --bet 2.5 --call 2.5 --raise_to 12 --foldfreq 0.35 --eq 0.54 --rf 0.90
EV(FOLD):  0.00 chips
EV(CALL):  4.03 chips
EV(RAISE): 7.11 chips

Best Action: RAISE




