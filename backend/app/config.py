import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
if os.path.exists(ROOT_ENV):
    load_dotenv(ROOT_ENV)
else:
    load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV if os.path.exists(ROOT_ENV) else ".env", extra="ignore")

    PROJECT_NAME: str = "Earth Intelligence Digital Twin (EIDT) - Mumbai"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "127.0.0.1")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "eidt_mumbai")
    
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "data")
    
    # Study Area Defaults
    DEFAULT_STUDY_AREA: str = "MUM_WARD_L_KURLA"
    DEFAULT_CRS: str = "EPSG:4326"
    PROJECTED_CRS: str = "EPSG:32643"  # UTM Zone 43N for Mumbai metric calculations

settings = Settings()
