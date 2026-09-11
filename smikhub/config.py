from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    # Токен отдельного бота-проверяльщика подписок (добавляется рекламодателем в админы
    # канала/чата). Не обязателен для запуска основного бота/API — нужен только для
    # smikhub.checkbot и для верификации admin-статуса при создании заказа.
    check_bot_token: str | None = None
    database_url: str = "sqlite+aiosqlite:///./smikhub.db"
    fernet_key: str
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Telegram user id платформы, имеющих доступ к /admin (через запятую).
    admin_user_ids: str = ""

    # Send Crypto Pay API (пополнение/вывод баланса). Не обязателен для запуска —
    # без него "Кабинет" остаётся с просмотром баланса без реальных платежей.
    send_api_token: str | None = None
    send_api_base_url: str = "https://pay.send.tg/api"

    @property
    def admin_ids(self) -> set[int]:
        return {int(part) for part in self.admin_user_ids.split(",") if part.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
