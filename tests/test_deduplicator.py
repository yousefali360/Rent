"""اختبارات إزالة التكرارات التامة والاحتفاظ بالمنشورات المشتبه بتكرارها دون دمج خاطئ."""

from backend.app.models import RentalPost
from backend.app.services.deduplicator import deduplicate_posts


def _make_post(
    post_id: str,
    text: str,
    url: str | None = None,
    price: int | None = None,
    rooms: int | None = None,
    sub_area: str | None = None,
) -> RentalPost:
    return RentalPost(
        id=post_id,
        original_text=text,
        post_url=url,
        url_verified=bool(url),
        url_type="post" if url else "unverified",
        collected_at="2026-10-10T15:00:00+03:00",
        area_mentioned="بنها",
        sub_area=sub_area,
        price_egp=price,
        rooms_count=rooms,
        source_name="اختبار",
        date_verification_status="verified_in_range",
    )


def test_exact_duplicate_removed_by_url_or_text():
    """إزالة الإعلان المنشور بنفس الرابط أو النص المتطابق تمامًا مع نفس التفاصيل."""
    p1 = _make_post(
        "p1",
        "شقة للإيجار في بنها الفلل 3 غرف وصالة الإيجار 5000 جنيه",
        url="https://www.facebook.com/groups/g1/posts/111",
        price=5000,
        rooms=3,
        sub_area="الفلل",
    )
    p2 = _make_post(
        "p2",
        "شقه للايجار في بنها الفلل ٣ غرف وصاله الايجار ٥٠٠٠ جنيه",
        url="https://www.facebook.com/groups/g2/posts/222",
        price=5000,
        rooms=3,
        sub_area="الفلل",
    )

    accepted, exact_dups = deduplicate_posts([p1, p2])
    assert len(accepted) == 1
    assert len(exact_dups) == 1
    assert exact_dups[0].duplicate_of_id == "p1"


def test_different_posts_with_similar_text_kept_with_flag():
    """عدم دمج منشورين مختلفين في السعر أو التفاصيل والاكتفاء بالإشارة لاحتمال التكرار عند التشابه."""
    p1 = _make_post(
        "p1",
        "شقة للإيجار في بنها الفلل 3 غرف وصالة تشطيب سوبر لوكس الدور الثالث السعر 4500 جنيه",
        price=4500,
        rooms=3,
        sub_area="الفلل",
    )
    p2 = _make_post(
        "p2",
        "شقة للإيجار في بنها الفلل 3 غرف وصالة تشطيب سوبر لوكس الدور الخامس السعر 5200 جنيه",
        price=5200,
        rooms=3,
        sub_area="الفلل",
    )

    accepted, exact_dups = deduplicate_posts([p1, p2])
    # يجب الاحتفاظ بالمنشورين معًا لأن السعر والدور مختلفان!
    assert len(accepted) == 2
    assert len(exact_dups) == 0
    assert accepted[1].possible_duplicate_of_id == "p1"
