from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    AI service configuration.

    §5 boundary: this service owns all prompts and model routing. No other
    service holds a model key, and none of them contains a prompt — which is
    what makes swapping Gemini for Groq a change to one directory.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://localhost:5432/loupe_dev"
    environment: str = "local"

    #: Browsers refuse cross-origin requests without this, and the web app is
    #: always a different origin from the services. Comma-separated.
    cors_origins: str = "http://localhost:3000"

    #: §5.2 selects Gemini Flash as primary with Groq as fallback. With neither
    #: set, answering is extractive — which cannot hallucinate, so it is a
    #: defensible baseline rather than a degraded mode.
    gemini_api_key: str = ""
    groq_api_key: str = ""

    #: Must match the model that embedded the chunks. Mismatch is caught at
    #: query time rather than producing meaningless similarity scores.
    use_real_embeddings: bool = True


settings = Settings()
