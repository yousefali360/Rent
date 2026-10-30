"""اختبارات الفلترة الزمنية والتحقق من تاريخ النشر الأصلي بتوقيت مصر (Africa/Cairo)."""

from datetime import datetime, timedelta
from backend.app.services.time_filter import (
    CAIRO_TZ,
    compute_time_window,
    parse_published_date,
    verify_post_date_in_window,
)


def test_compute_time_window_presets():
    """التحقق من حساب فترات 24 ساعة، يومين، 4 أيام، والفترة المخصصة بتوقيت القاهرة."""
    ref = datetime(2026, 10, 10, 15, 0, 0, tzinfo=CAIRO_TZ)

    s_24h, e_24h = compute_time_window("24h", reference_now=ref)
    assert (e_24h - s_24h) == timedelta(hours=24)
    assert s_24h.tzinfo == CAIRO_TZ

    s_2d, e_2d = compute_time_window("2d", reference_now=ref)
    assert (e_2d - s_2d) == timedelta(days=2)

    s_4d, e_4d = compute_time_window("4d", reference_now=ref)
    assert (e_4d - s_4d) == timedelta(days=4)

    s_cust, e_cust = compute_time_window(
        "custom",
        custom_start="2026-10-06T10:00",
        custom_end="2026-10-10T15:00",
        reference_now=ref,
    )
    assert s_cust.day == 6 and s_cust.hour == 10
    assert e_cust.day == 10 and e_cust.hour == 15


def test_parse_arabic_relative_and_absolute_dates():
    """التحقق من تحليل التواريخ النسبية والصريحة بالعربية والإنجليزية."""
    ref = datetime(2026, 10, 10, 15, 0, 0, tzinfo=CAIRO_TZ)

    dt1, _ = parse_published_date("منذ 3 ساعات", reference_now=ref)
    assert dt1 == ref - timedelta(hours=3)

    dt2, _ = parse_published_date("منذ يومين", reference_now=ref)
    assert dt2 == ref - timedelta(days=2)

    dt3, _ = parse_published_date("8 أكتوبر 2026", reference_now=ref)
    assert dt3 is not None
    assert dt3.year == 2026 and dt3.month == 10 and dt3.day == 8

    dt_none, _ = parse_published_date("شقة للإيجار بدون أي إشارة لتاريخ النشر", reference_now=ref)
    assert dt_none is None


def test_verify_post_date_in_window_strict():
    """التحقق من استبعاد المنشورات الأقدم وفصل المنشورات غير المؤكد تاريخها."""
    ref = datetime(2026, 10, 10, 15, 0, 0, tzinfo=CAIRO_TZ)
    start_4d, end_4d = compute_time_window("4d", reference_now=ref)

    recent_dt = ref - timedelta(days=2)
    old_dt = ref - timedelta(days=7)

    assert verify_post_date_in_window(recent_dt, start_4d, end_4d) == "verified_in_range"
    assert verify_post_date_in_window(old_dt, start_4d, end_4d) == "verified_out_of_range"
    assert verify_post_date_in_window(None, start_4d, end_4d) == "unverified"
