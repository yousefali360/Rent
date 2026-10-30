"""اختبارات وحدة معالجة النصوص العربية والتطبيع والتمييز بين بنها وبنها الجديدة وفحص السياق."""

from backend.app.services.arabic_nlp import (
    analyze_area_mention,
    convert_arabic_digits,
    expand_arabic_keyword_variants,
    is_rental_listing,
    normalize_arabic,
)


def test_normalize_arabic_variations():
    """التحقق من توحيد شقة/شقه، للإيجار/للايجار، إيجار/ايجار، وتحويل الأرقام العربية."""
    assert normalize_arabic("شقة") == normalize_arabic("شقه")
    assert normalize_arabic("للإيجار") == normalize_arabic("للايجار")
    assert normalize_arabic("إيجار") == normalize_arabic("ايجار")
    assert convert_arabic_digits("السعر ٤٥٠٠ جنيه") == "السعر 4500 جنيه"


def test_expand_arabic_keyword_variants():
    """التحقق من توليد الاختلافات الإملائية للكلمات المفتاحية."""
    variants = expand_arabic_keyword_variants("شقة للإيجار")
    assert "شقة للإيجار" in variants
    assert "شقه للايجار" in variants
    assert "شقق للإيجار" in variants


def test_distinguish_banha_and_new_banha():
    """التحقق من عدم دمج «بنها» و«بنها الجديدة» تلقائيًا دون سياق."""
    info_regular = analyze_area_mention("شقة للإيجار في بنها منطقة الفلل الدور الثالث")
    assert info_regular["area_mentioned"] == "بنها"
    assert info_regular["sub_area"] == "الفلل"
    assert info_regular["is_new_banha"] is False

    info_new = analyze_area_mention("شقة مفروشة للإيجار في بنها الجديدة قريبة من الجامعة")
    assert info_new["area_mentioned"] == "بنها الجديدة"
    assert info_new["is_new_banha"] is True


def test_is_rental_listing_context():
    """التحقق من قبول إعلانات الإيجار واستبعاد إعلانات التمليك فقط أو السياقات غير العقارية."""
    ok, _ = is_rental_listing("شقة للايجار في بنها الفلل 3 غرف وصالة السعر 4500 جنيه")
    assert ok is True

    sale_ok, _ = is_rental_listing("شقة للبيع تمليك في بنها 140 متر كاش أو بالتقسيط")
    assert sale_ok is False

    non_re_ok, _ = is_rental_listing("شركة تنظيف شقق ونقل عفش في بنها بأحدث المعدات")
    assert non_re_ok is False

    just_word_ok, _ = is_rental_listing("ذهبت اليوم إلى شقة صديقي في القاهرة")
    assert just_word_ok is False
