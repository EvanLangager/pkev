from dataclasses import dataclass


@dataclass(frozen=True)
class Branch:
    name: str
    probability: float
    ev: float
    notes: str = ""


def weighted_ev(branches: list[Branch]) -> float:
    return sum(branch.probability * branch.ev for branch in branches)


def normalize_probabilities(branches: list[Branch]) -> list[Branch]:
    total = sum(branch.probability for branch in branches)

    if total <= 0:
        raise ValueError("Total branch probability must be greater than 0.")

    return [
        Branch(
            name=branch.name,
            probability=branch.probability / total,
            ev=branch.ev,
            notes=branch.notes,
        )
        for branch in branches
    ]


def describe_branches(branches: list[Branch]) -> str:
    lines = []
    for branch in branches:
        lines.append(
            f"- {branch.name:<18} p={branch.probability:>6.2%}   ev={branch.ev:>8.2f}"
        )
    return "\n".join(lines)