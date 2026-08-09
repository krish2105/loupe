from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://localhost:5432/loupe_dev"
    environment: str = "local"

    #: Use WhisperX and bge-m3 rather than the fixture and hashing fallbacks.
    #: Both fall back automatically when their packages are absent, so setting
    #: this on a machine without them is safe rather than fatal.
    use_real_models: bool = False

    #: §10.3: "Enforce a hard monthly cap on transcription minutes inside the
    #: worker. Not by discipline — by code."
    transcription_minutes_cap: int = 3000

    batch_size: int = 20
    max_retries: int = 3


settings = Settings()
