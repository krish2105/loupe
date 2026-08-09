from datetime import date

import pytest

from app.quota import QuotaExhausted, QuotaLedger


class FakePool:
    def __init__(self, already_spent: int = 0) -> None:
        self.already_spent = already_spent
        self.written: list[tuple] = []

    async def fetchval(self, *_args):
        return self.already_spent

    async def executemany(self, _sql, rows):
        self.written.extend(rows)


class TestFailClosed:
    """
    §4.2 rule 2: "Fail closed when the budget is exhausted."

    The word that matters is *closed*. These assert the ledger refuses rather
    than warns, because §15 lists quota exhaustion as a live risk and a warning
    that the worker ignores is not a mitigation.
    """

    async def test_it_refuses_a_call_that_would_exceed_the_budget(self):
        ledger = await QuotaLedger.open(FakePool(), "youtube", 100, date(2026, 8, 9))
        ledger.record("playlistItems.list", 99)

        with pytest.raises(QuotaExhausted):
            ledger.check(2)

    async def test_a_call_that_exactly_fits_is_allowed(self):
        ledger = await QuotaLedger.open(FakePool(), "youtube", 100, date(2026, 8, 9))
        ledger.record("playlistItems.list", 98)

        ledger.check(2)  # 98 + 2 == 100, which is within budget.

    async def test_it_counts_what_earlier_runs_already_spent(self):
        """
        The check that makes a retried cron job safe.

        An in-memory counter would let a second run on the same day spend the
        whole budget again, which is precisely what a retry does.
        """
        ledger = await QuotaLedger.open(
            FakePool(already_spent=95), "youtube", 100, date(2026, 8, 9)
        )

        assert ledger.spent == 95
        assert ledger.remaining == 5
        with pytest.raises(QuotaExhausted):
            ledger.check(10)


class TestLedgerPersistence:
    async def test_entries_are_written_with_their_operation(self):
        pool = FakePool()
        ledger = await QuotaLedger.open(pool, "youtube", 1000, date(2026, 8, 9))

        ledger.record("channels.list", 1)
        ledger.record("playlistItems.list", 2, items_fetched=50)
        await ledger.flush()

        assert len(pool.written) == 2
        operations = {row[2] for row in pool.written}
        assert operations == {"channels.list", "playlistItems.list"}
        assert sum(row[3] for row in pool.written) == 3

    async def test_flushing_twice_does_not_double_count(self):
        pool = FakePool()
        ledger = await QuotaLedger.open(pool, "youtube", 1000, date(2026, 8, 9))
        ledger.record("channels.list", 1)

        await ledger.flush()
        await ledger.flush()

        assert len(pool.written) == 1
