"""Application settings loaded from environment variables / 從環境變數載入應用程式設定。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by API and migrations.

    API 與 migration 共用的執行設定。
    """

    app_name: str = "BiteMap API"
    app_environment: str = "development"
    database_url: str = "postgresql+asyncpg://bitemap:bitemap_local_dev_only@127.0.0.1:5433/bitemap"
    api_cors_origins: str = "http://localhost:3000"
    admin_session_cookie: str = "bitemap_admin_session"
    admin_session_hours: int = 8
    public_map_result_limit: int = 250
    geocoding_provider: str = "nominatim"
    geocoding_user_agent: str = "BiteMap/0.1 (local development)"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        # Split comma-separated origins so local and deployed environments use one setting.
        # 將逗號分隔的來源拆開，讓本機與部署環境共用同一個設定。
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def secure_cookies(self) -> bool:
        """Only allow plaintext cookies in local development / 僅本機開發允許非 HTTPS Cookie。"""
        return self.app_environment not in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    # Cache settings once per process to avoid repeatedly reading .env files.
    # 每個程序只載入一次設定，避免重複讀取 .env 檔案。
    return Settings()
