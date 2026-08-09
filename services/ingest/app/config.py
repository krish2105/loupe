from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Ingest worker configuration.

    §5 boundary: this service owns referenced-content sync and quota
    accounting. It writes Class B rows and nothing else — no media, no
    transcripts, no user data.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://localhost:5432/loupe_dev"
    environment: str = "local"

    # Empty selects the fixture provider. §4.2 rule 1 permits only the nightly
    # batch to touch a third-party API at all, and never its search endpoint.
    youtube_api_key: str = ""

    # §4.2 rule 2: the ledger fails closed when the budget is exhausted. The
    # real quota is 10,000 units a day; this is deliberately far below it so a
    # runaway loop hits our ceiling long before the provider's.
    daily_quota_units: int = 2000

    # How far back to walk each channel. A page is 50 items and costs 1 unit.
    max_pages_per_channel: int = 2


settings = Settings()
