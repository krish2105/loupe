from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration, read from the environment.

    §14: nothing in the repository, ever. Every value here comes from a platform
    secret manager in staging and production, and from an untracked .env locally.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://localhost:5432/loupe_dev"
    environment: str = "local"

    #: Browsers refuse cross-origin requests without this, and the web app is
    #: always a different origin from the services. Comma-separated.
    cors_origins: str = "http://localhost:3000"

    # Supabase signs access tokens with this. Verifying locally avoids a network
    # round-trip on every history write, which happens every ten seconds of
    # playback per viewer.
    supabase_jwt_secret: str = ""

    # §10.3: the transcription cost ceiling is enforced by code, not discipline.
    # The worker reads this before starting a job and refuses when it is spent.
    transcription_minutes_cap: int = 3000

    # §4.2: the ingest worker fails closed when the day's quota is gone.
    ingest_daily_quota_units: int = 10_000

    # §5: this service never calls a model. Composing an AI playlist is the AI
    # service's job; owning and authorising the resulting playlist is this one's.
    # The URL is how that boundary is crossed.
    ai_service_url: str = "http://127.0.0.1:8031"


settings = Settings()
