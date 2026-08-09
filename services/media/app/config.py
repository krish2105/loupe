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

    # ------------------------------------------------------------- S3 storage
    #
    # Backblaze B2 today, addressed as plain S3 so the same code reaches R2,
    # AWS or MinIO by changing the endpoint. That portability is not
    # decoration: B2 is the current choice only because R2's signup would not
    # take the card, and Oracle halved its free compute tier in June without
    # announcing it. Every free tier under this platform is somebody else's to
    # revise.
    s3_endpoint: str = ""
    s3_region: str = ""
    s3_bucket: str = ""
    s3_key_id: str = ""
    s3_application_key: str = ""

    # How long a presigned segment URL lives. Shorter than the playback token
    # because a segment is re-requested constantly and the playlist that names
    # it is regenerated on every fetch, so there is no benefit to a long one.
    s3_segment_ttl_sec: int = 60 * 60

    # Shared secret for /v1/internal/sign, which lets the transcoder get
    # bucket URLs without holding provider keys of its own. Empty means the
    # endpoint 404s — absent rather than guessable.
    internal_token: str = ""

    # Origins allowed to call this service from a page. Same shape as the core
    # API's, comma-separated, because two services with the same job should not
    # be configured two different ways.
    cors_origins: str = "http://localhost:3000"

    # Where the browser reaches this service. Rewritten playlists point back
    # here for nested playlists, and a relative URL will not do — the player
    # resolves it against the bucket, not against us.
    public_base_url: str = "http://localhost:8002"

    # §5.1: signed playback URLs even for openly licensed content. Short enough
    # that a leaked URL is worthless quickly, long enough to outlast a talk.
    playback_token_ttl_sec: int = 4 * 60 * 60

    # Bunny does not sign its Stream webhooks, so the endpoint is protected by
    # an unguessable path secret instead. See main.py for why that is not
    # treated as sufficient on its own.
    webhook_secret: str = ""

    @property
    def s3_configured(self) -> bool:
        return bool(
            self.s3_endpoint
            and self.s3_region
            and self.s3_bucket
            and self.s3_key_id
            and self.s3_application_key
        )

    @property
    def bunny_configured(self) -> bool:
        return bool(self.bunny_library_id and self.bunny_api_key)

    @property
    def provider(self) -> str:
        """
        Which storage backend is live.

        S3 wins when both are set. Bunny predates it and stays because ADR 0001
        chose it and nothing has disproved that choice — it was never
        provisioned, which is a different thing from being wrong.
        """
        if self.s3_configured:
            return "s3"
        if self.bunny_configured:
            return "bunny"
        return "none"

    @property
    def is_configured(self) -> bool:
        return self.provider != "none"


settings = Settings()
