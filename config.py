from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Manages all application settings and secrets using Pydantic.
    It automatically loads variables from a .env file and the environment.
    """
    model_config = SettingsConfigDict(env_file=".env")

    # Browserbase Credentials
    BROWSERBASE_API_KEY: str
    BROWSERBASE_PROJECT_ID: str

    # Bubble.io Credentials and URL
    BUBBLE_API_KEY: str
    BUBBLE_WORKFLOW_URL: str

    # Redis URL
    REDIS_URL: str

    # Session Backend Configuration
    SESSION_BACKEND: str = "memory" # "redis" or "memory"

# The settings object will be created and managed by the dependency injection system.