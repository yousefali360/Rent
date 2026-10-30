"""اختبارات التكامل لنقاط النهاية (API Endpoints) والمرونة عند غياب أو تعطل أحد المصادر."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.main import app


@pytest.mark.asyncio
async def test_health_and_config_endpoints(tmp_path, monkeypatch):
    """التحقق من عمل /api/health و /api/config وضبط المنطقة الزمنية على Africa/Cairo."""
    monkeypatch.setattr(settings, "SQLITE_PATH", tmp_path / "test_rent.db")
    init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_health = await client.get("/api/health")
        assert resp_health.status_code == 200
        data_h = resp_health.json()
        assert data_h["status"] == "ok"
        assert data_h["timezone"] == "Africa/Cairo"

        resp_cfg = await client.get("/api/config")
        assert resp_cfg.status_code == 200
        data_c = resp_cfg.json()
        assert data_c["default_area"] == "بنها"
        assert data_c["default_time_preset"] == "4d"
        assert "شقة للإيجار في بنها" in data_c["default_keywords"]


@pytest.mark.asyncio
async def test_user_import_and_time_filtering_pipeline(tmp_path, monkeypatch):
    """اختبار استيراد منشورات حقيقية وفصل المؤكد زمنيًا عن غير المؤكد واستبعاد القديم."""
    monkeypatch.setattr(settings, "SQLITE_PATH", tmp_path / "test_rent.db")
    init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "area": "بنها",
            "time_preset": "4d",
            "items": [
                {
                    "text": "شقة للإيجار في بنها الفلل 3 غرف وصالة و 2 حمام مساحة 130 متر الإيجار 4500 جنيه للتواصل 01012345678",
                    "post_url": "https://www.facebook.com/groups/banha.rent/posts/987654321/",
                    "group_or_page_name": "شقق للايجار في بنها",
                    "published_at_text": "منذ 4 ساعات",
                },
                {
                    "text": "شقة مفروشة للايجار في بنها كفر الجزار غرفتين وصالة السعر 3800 جنيه",
                    "post_url": "https://www.facebook.com/groups/banha.rent/",
                    "group_or_page_name": "عقارات بنها",
                    "published_at_text": "",  # بدون تاريخ نشر -> يجب أن يذهب لقسم تاريخ النشر غير مؤكد
                },
                {
                    "text": "شقة للايجار في بنها المنشية 3 غرف الإيجار 3000 جنيه",
                    "post_url": "https://www.facebook.com/groups/banha.rent/posts/111222333/",
                    "published_at_text": "منذ 14 يوم",  # أقدم من 4 أيام -> يجب أن يُستبعد!
                },
            ],
        }
        resp = await client.post("/api/import", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # المنشور القديم (منذ 14 يوم) تم استبعاده
        assert data["total_excluded_old"] >= 1

        # المنشور الأول مؤكد التاريخ وضمن آخر 4 أيام، ورابطه متحقق منه كمنشور أصلي
        verified_ids = [p["id"] for p in data["verified_results"]]
        assert len(verified_ids) >= 1
        v_post = next(p for p in data["verified_results"] if p["price_egp"] == 4500)
        assert v_post["sub_area"] == "الفلل"
        assert v_post["rooms_count"] == 3
        assert v_post["bathrooms_count"] == 2
        assert v_post["area_sqm"] == 130
        assert v_post["url_verified"] is True
        assert v_post["post_url"] == "https://www.facebook.com/groups/banha.rent/posts/987654321"

        # المنشور الثاني (بدون تاريخ نشر، وبرابط جروب عام فقط) يظهر في قسم «تاريخ النشر غير مؤكد»
        unv_post = next(p for p in data["unverified_date_results"] if p["price_egp"] == 3800)
        assert unv_post["date_verification_status"] == "unverified"
        assert unv_post["url_verified"] is False
        assert unv_post["post_url"] is None  # لم يُعتمد رابط الجروب كرابط منشور أصلي!
        assert unv_post["group_or_page_url"] == "https://www.facebook.com/groups/banha.rent/"
