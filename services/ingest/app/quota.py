from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

"""
The quota ledger — §4.2 rule 2.

    "Maintain an explicit quota ledger. Log consumption per run. Fail closed
     when the budget is exhausted."

§15 lists quota exhaustion as a live risk, and the mitigation is this plus a
fail-closed check in the worker. The important word is *closed*: when the
budget runs out the run stops, rather than continuing and hoping.

The ledger is not a counter in memory. It reads the day's spend back from the
database before it starts, so a second run on the same day cannot spend the
budget twice — which is exactly what a retried cron job would do.
"""


class QuotaExhausted(RuntimeError):
    """Raised when a call would exceed the day's budget. Never caught to retry."""


@dataclass
class QuotaLedger:
    pool: object
    provider: str
    daily_limit: int
    run_date: date
    spent: int = 0
    entries: list[tuple[str, int, int]] = field(default_factory=list)

    @classmethod
    async def open(cls, pool, provider: str, daily_limit: int, today: date) -> QuotaLedger:
        already = await pool.fetchval(
            """
            SELECT COALESCE(sum(units_spent), 0)
            FROM ingest_quota_ledger
            WHERE provider = $1 AND run_date = $2
            """,
            provider,
            today,
        )
        return cls(
            pool=pool,
            provider=provider,
            daily_limit=daily_limit,
            run_date=today,
            spent=int(already or 0),
        )

    @property
    def remaining(self) -> int:
        return max(0, self.daily_limit - self.spent)

    def check(self, units: int) -> None:
        """Fail closed. Called *before* the request, never after."""
        if self.spent + units > self.daily_limit:
            raise QuotaExhausted(
                f"{self.provider}: {self.spent}/{self.daily_limit} units spent today; "
                f"a further {units} would exceed the budget. Stopping."
            )

    def record(self, operation: str, units: int, items_fetched: int = 0) -> None:
        self.spent += units
        self.entries.append((operation, units, items_fetched))

    async def flush(self) -> None:
        """
        Persist what this run spent.

        Written even when the run fails, because a failed run still consumed
        units — a ledger that only records successes would drift under exactly
        the conditions it exists to catch.
        """
        if not self.entries:
            return

        await self.pool.executemany(
            """
            INSERT INTO ingest_quota_ledger
                (run_date, provider, operation, units_spent, items_fetched)
            VALUES ($1, $2, $3, $4, $5)
            """,
            [
                (self.run_date, self.provider, operation, units, items)
                for operation, units, items in self.entries
            ],
        )
        self.entries.clear()
