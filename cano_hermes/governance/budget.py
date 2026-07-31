from dataclasses import dataclass


@dataclass
class BudgetLedger:
    daily_limit_usd: float
    spent_usd: float = 0.0

    def can_spend(self, amount: float) -> bool:
        return amount >= 0 and self.spent_usd + amount <= self.daily_limit_usd

    def record(self, amount: float) -> None:
        if not self.can_spend(amount):
            raise ValueError("Budget limit exceeded")
        self.spent_usd += amount
