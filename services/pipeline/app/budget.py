from __future__ import annotations

from datetime import date

"""
The transcription cost ceiling — §10.3.

    "Enforce a hard monthly cap on transcription minutes inside the worker.
     Not by discipline — by code."

Same shape as the ingest quota ledger, and for the same reason: a limit that
lives in someone's head is not a limit. This one reads the month's spend back
from the database before each job, so a worker restarted in a loop cannot spend
the cap repeatedly.
"""


class BudgetExhausted(RuntimeError):
    """Raised before a transcription that would exceed the month's cap."""


def month_of(day: date) -> date:
    return day.replace(day=1)


async def ensure_budget(pool, minutes_cap: int, today: date) -> None:
    """Create this month's row if it is missing. Idempotent."""
    await pool.execute(
        """
        INSERT INTO transcription_budget (month, minutes_cap)
        VALUES ($1, $2)
        ON CONFLICT (month) DO NOTHING
        """,
        month_of(today),
        minutes_cap,
    )


async def reserve(pool, minutes: int, today: date) -> None:
    """
    Reserve minutes before transcribing, or refuse.

    The UPDATE is conditional, so two workers racing cannot both pass the check
    — the second one's WHERE clause fails against the already-incremented row
    rather than reading a stale value.
    """
    updated = await pool.fetchval(
        """
        UPDATE transcription_budget
        SET minutes_spent = minutes_spent + $2, updated_at = now()
        WHERE month = $1 AND minutes_spent + $2 <= minutes_cap
        RETURNING minutes_spent
        """,
        month_of(today),
        max(0, minutes),
    )

    if updated is None:
        row = await pool.fetchrow(
            "SELECT minutes_spent, minutes_cap FROM transcription_budget WHERE month = $1",
            month_of(today),
        )
        if row is None:
            raise BudgetExhausted(
                f"no transcription budget for {month_of(today)}. "
                "ensure_budget() must run before reserving."
            )
        raise BudgetExhausted(
            f"transcription budget for {month_of(today)}: "
            f"{row['minutes_spent']}/{row['minutes_cap']} minutes used; "
            f"a further {minutes} would exceed the cap."
        )
