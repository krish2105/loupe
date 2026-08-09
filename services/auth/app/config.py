from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration for the local identity provider.

    The defaults are development defaults on purpose. This service has no
    production configuration because it has no production deployment.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://localhost:5432/loupe_dev"

    #: Fail-closed guard. See main.py — this service refuses to start anywhere
    #: but a developer's machine.
    environment: str = "local"

    #: The same secret the core API verifies with. Tokens minted here travel the
    #: identical verification path as tokens from a hosted provider; there is no
    #: second code path and no bypass.
    supabase_jwt_secret: str = ""

    #: One hour, matching GoTrue's default, so the refresh path is exercised in
    #: development rather than discovered in production.
    access_token_ttl_seconds: int = 3600

    cors_origins: str = "http://localhost:3000"


settings = Settings()
