"""إعدادات التطبيق وتحميل المتغيرات البيئية من ملف .env دون كشف المفاتيح السرية."""

import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل ملف .env إن وجد
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """إعدادات النظام الأساسية ومفاتيح مزودي البحث المصرح بهم."""

    APP_NAME: str = "محرك البحث عن شقق الإيجار - بنها"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    TIMEZONE: str = os.getenv("TIMEZONE", "Africa/Cairo")

    # قاعدة البيانات (SQLite افتراضيًا مع قابلية الترقية إلى PostgreSQL عبر متغير البيئة)
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'rent_search.db'}")
    SQLITE_PATH: Path = BASE_DIR / "rent_search.db"

    # مفاتيح مزودات البحث العامة (لا تُكشف أبدًا في واجهة المستخدم أو السجلات)
    GOOGLE_CSE_API_KEY: str = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
    GOOGLE_CSE_CX: str = os.getenv("GOOGLE_CSE_CX", "").strip()
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "").strip()
    ENABLE_PUBLIC_WEB_PROVIDER: bool = (
        os.getenv("ENABLE_PUBLIC_WEB_PROVIDER", "true").strip().lower() in ("true", "1", "yes")
    )

    # إعدادات التحديث الدوري (المرحلة الخامسة)
    AUTO_REFRESH_INTERVAL_MINUTES: int = int(os.getenv("AUTO_REFRESH_INTERVAL_MINUTES", "60"))

    @property
    def has_google_cse(self) -> bool:
        return bool(self.GOOGLE_CSE_API_KEY and self.GOOGLE_CSE_CX)

    @property
    def has_serper(self) -> bool:
        return bool(self.SERPER_API_KEY)


settings = Settings()
