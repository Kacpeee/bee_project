from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Adresy wewnetrzne (Python/httpx - siec Docker)
    stac_api_url: str = "http://stac-api:8080"
    backend_url: str = "http://backend:8000"
    titiler_url: str = "http://titiler:80"
    tipg_url: str = "http://tipg:8083"

    # Adresy publiczne (MapLibre JS w przegladarce - localhost)
    public_titiler_url: str = "http://localhost:8082"
    public_tipg_url: str = "http://localhost:8083"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
