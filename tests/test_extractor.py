"""اختبارات استخراج الأسعار والتفاصيل والتحقق من روابط المنشورات الأصلية."""

from backend.app.services.extractor import (
    extract_all_post_fields,
    extract_area_sqm,
    extract_contact_info,
    extract_furnishing_status,
    extract_monthly_price_egp,
    extract_rooms_and_bathrooms,
    verify_facebook_or_post_url,
)


def test_extract_monthly_price_egp():
    """التحقق من استخراج السعر الشهري بالجنيه وتجاهل رقم الهاتف أو التأمين."""
    assert extract_monthly_price_egp("شقة للإيجار في بنها الفلل الإيجار 4500 جنيه شهريا ت 01012345678") == 4500
    assert extract_monthly_price_egp("شقه للايجار بكفر الجزار مطلووب 3,200 ج") == 3200
    assert extract_monthly_price_egp("شقة مفروشة بنها السعر ٤٠٠٠ جنيه") == 4000
    assert extract_monthly_price_egp("شقة للإيجار في بنها ايجار 3.5 الف جنيه") == 3500
    # عدم اختلاق سعر عند غيابه
    assert extract_monthly_price_egp("شقة للإيجار في بنها الفلل التواصل خاص 01099887766") is None


def test_extract_rooms_bathrooms_and_sqm():
    """التحقق من استخراج عدد الغرف والحمامات والمساحة."""
    rooms, baths = extract_rooms_and_bathrooms("شقة ٣ غرف وصالة و ٢ حمام سوبر لوكس")
    assert rooms == 3
    assert baths == 2

    rooms2, baths2 = extract_rooms_and_bathrooms("شقة غرفتين وصالة وحمام واحد")
    assert rooms2 == 2
    assert baths2 == 1

    assert extract_area_sqm("شقة مساحة ١٣٠ متر في أتريب") == 130
    assert extract_area_sqm("شقة 115م تشطيب سوبر لوكس") == 115


def test_extract_furnishing_and_contact():
    """التحقق من استخراج حالة الفرش وطريقة التواصل."""
    assert extract_furnishing_status("شقة مفروشة بالكامل للإيجار في بنها") == "مفروش"
    assert extract_furnishing_status("شقة فاضية قانون جديد للإيجار") == "غير مفروش (فاضي)"
    assert extract_furnishing_status("شقة للإيجار بدون ذكر فرش") is None

    contact = extract_contact_info("للتواصل واتس أو فون 01234567890")
    assert contact is not None and "01234567890" in contact


def test_verify_facebook_post_url_vs_group_root():
    """التحقق من التمييز بين رابط منشور فعلي ورابط الصفحة الرئيسية للجروب."""
    is_post, utype, canonical, grp = verify_facebook_or_post_url(
        "https://www.facebook.com/groups/banha.flats/posts/123456789012345/"
    )
    assert is_post is True
    assert utype == "post"
    assert canonical == "https://www.facebook.com/groups/banha.flats/posts/123456789012345"
    assert grp == "https://www.facebook.com/groups/banha.flats"

    # رابط الجروب العام فقط بدون معرف منشور لا يُعتمد كرابط منشور أصلي
    is_post_grp, utype_grp, canonical_grp, grp_only = verify_facebook_or_post_url(
        "https://www.facebook.com/groups/banha.flats/"
    )
    assert is_post_grp is False
    assert utype_grp == "group_or_page"
    assert canonical_grp is None
    assert grp_only == "https://www.facebook.com/groups/banha.flats/"


def test_extract_all_post_fields_no_hallucination():
    """التحقق من عدم اختلاق أي حقل غير موجود في النص الأصلي."""
    res = extract_all_post_fields("شقة للإيجار في بنها", target_area="بنها", post_url=None)
    assert res["area_mentioned"] == "بنها"
    assert res["price_egp"] is None
    assert res["rooms_count"] is None
    assert res["bathrooms_count"] is None
    assert res["area_sqm"] is None
    assert res["furnishing_status"] is None
    assert res["contact_info"] is None
    assert res["url_verified"] is False
