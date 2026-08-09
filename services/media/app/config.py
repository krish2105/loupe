from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Media service configuration.

    §5 boundary: this service is the sole holder of media provider credentials.
    No other service reads these values, and none of them appear in a response
    body — the whole point of the boundary is that a playback URL leaving here
    is already signed, so nothing downstream needs the key that signed it.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://localhost:5432/loupe_dev"
    environment: str = "local"

    # Bunny Stream. Empty locally; the service reports itself unconfigured
    # rather than refusing to start, matching how the web app handles Supabase.
    bunny_library_id: str = ""
    bunny_api_key: str = ""
    # Pull zone hostname that serves the HLS manifests, e.g. loupe.b-cdn.net
    bunny_pull_zone: str = ""
    # CDN token authentication key. Separate from the API key: one signs
    # management calls, the other signs playback URLs.
    bunny_token_key: str = ""

    # §5.1: signed playback URLs even for openly licensed content. Short enough
    # that a leaked URL is worthless quickly, long enough to outlast a talk.
    playback_token_ttl_sec: int = 4 * 60 * 60

    # Bunny does not sign its Stream webhooks, so the endpoint is protected by
    # an unguessable path secret instead. See main.py for why that is not
    # treated as sufficient on its own.
    webhook_secret: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.bunny_library_id and self.bunny_api_key)


settings = Settings()
