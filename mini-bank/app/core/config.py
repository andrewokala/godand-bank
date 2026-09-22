from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_access_token_expire_minutes: int = 15
    redis_url: str

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()