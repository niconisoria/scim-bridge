from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    scim_bearer_token: str
    redis_url: str = "redis://redis:6379"
    brivo_base_url: str = "http://mock-brivo:8001"
    brivo_rate_limit: int = 20
    scim_base_url: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
