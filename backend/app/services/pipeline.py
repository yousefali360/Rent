"""خط أنابيب المعالجة المتكامل (Processing Pipeline) لتحويل المرشحات الخام إلى منشورات موثقة.

يمر كل منشور بالمراحل التالية:
1. فحص السياق العربي للتأكد أنه إعلان إيجار عقاري حقيقي (`is_rental_listing`).
2. استخراج البيانات (السعر، الغرف، الحمامات، المساحة، الفرش، المنطقة الفرعية، التواصل، التحقق من الرابط).
3. التحقق الصارم من تاريخ النشر الأصلي مقارنة بنافذة البحث الزمنية (`Africa/Cairo`).
4. استبعاد المنشورات الأقدم من الفترة المطلوبة (`verified_out_of_range`).
5. فصل المنشورات التي تعذر التأكد من تاريخ نشرها في قائمة مستقلة (`unverified`).
6. إزالة التكرارات التامة والإشارة إلى التكرارات المحتملة دون دمج خاطئ.
7. ترتيب النتائج المؤكدة من الأحدث إلى الأقدم حسب تاريخ النشر الأصلي.
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Tuple

from backend.app.models import RentalPost
from backend.app.providers.base import RawCandidatePost
from backend.app.services.arabic_nlp import (
    analyze_area_mention,
    is_rental_listing,
    normalize_arabic,
)
from backend.app.services.deduplicator import deduplicate_posts
from backend.app.services.extractor import extract_all_post_fields
from backend.app.services.time_filter import (
    parse_published_date,
    verify_post_date_in_window,
)


def _generate_stable_post_id(norm_text: str, post_url: str | None) -> str:
    """توليد معرف داخلي فريد ومستقر بناءً على الرابط المتحقق منه أو النص المطبّع."""
    basis = post_url.strip().lower() if post_url else norm_text[:280]
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"post_{digest}"


def process_candidates_pipeline(
    candidates: List[RawCandidatePost],
    area: str,
    window_start: datetime,
    window_end: datetime,
    include_new_banha: bool = True,
) -> Tuple[List[RentalPost], List[RentalPost], Dict[str, int]]:
    """تشغيل خط أنابيب الفلترة والاستخراج والتحقق من التاريخ وإزالة التكرار."""
    stats = {
        "total_fetched": len(candidates),
        "excluded_irrelevant": 0,
        "excluded_old": 0,
        "excluded_exact_duplicates": 0,
        "accepted_verified": 0,
        "accepted_unverified_date": 0,
    }

    preliminary_posts: List[RentalPost] = []

    for cand in candidates:
        # 1. التحقق من أن النص يمثل إعلان إيجار عقاري في السياق
        is_valid_rental, _reason = is_rental_listing(cand.raw_text)
        if not is_valid_rental:
            stats["excluded_irrelevant"] += 1
            continue

        # 2. استخراج الحقول والتحقق من الرابط والمنطقة
        extracted = extract_all_post_fields(
            text=cand.raw_text,
            target_area=area,
            post_url=cand.url,
        )
        if not extracted["area_mentioned"] and cand.group_or_page_name:
            area_info = analyze_area_mention(
                f"{cand.group_or_page_name} {cand.raw_text}", target_area=area
            )
            if area_info["area_mentioned"]:
                extracted["area_mentioned"] = area_info["area_mentioned"]
                if not extracted["sub_area"]:
                    extracted["sub_area"] = area_info["sub_area"]

        # استبعاد نتائج البحث العام التي لا تذكر المنطقة المستهدفة لا في النص ولا في اسم الجروب
        if (
            not extracted["area_mentioned"]
            and cand.source_name != "استيراد مصرح به من المستخدم"
        ):
            stats["excluded_irrelevant"] += 1
            continue

        # إذا اختار المستخدم استبعاد "بنها الجديدة" وكان المنشور يخص بنها الجديدة فقط
        if not include_new_banha and extracted["is_new_banha"]:
            stats["excluded_irrelevant"] += 1
            continue

        # 3. استخراج وتحليل تاريخ النشر الأصلي (وليس تاريخ الفهرسة)
        pub_dt, pub_raw = None, None
        if cand.published_at_hint:
            pub_dt, pub_raw = parse_published_date(
                cand.published_at_hint, reference_now=window_end
            )
        if pub_dt is None:
            # محاولة اكتشاف تاريخ منشور صريح داخل نص المنشور نفسه
            pub_dt, pub_raw = parse_published_date(cand.raw_text, reference_now=window_end)

        # 4. التحقق من وقوع تاريخ النشر الأصلي ضمن الفترة الزمنية المحددة
        date_status = verify_post_date_in_window(pub_dt, window_start, window_end)
        if date_status == "verified_out_of_range":
            stats["excluded_old"] += 1
            continue

        norm_text = normalize_arabic(cand.raw_text)
        canonical_post_url = extracted["canonical_post_url"]
        inferred_group_url = cand.group_or_page_url or extracted["inferred_group_url"]

        post_id = _generate_stable_post_id(norm_text, canonical_post_url)

        post_obj = RentalPost(
            id=post_id,
            original_text=cand.raw_text,
            normalized_text=norm_text,
            post_url=canonical_post_url,  # لا نضع رابطًا غير متحقق منه كرابط منشور أصلي!
            raw_discovered_url=cand.url,
            url_verified=extracted["url_verified"],
            url_type=extracted["url_type"],
            group_or_page_name=cand.group_or_page_name,
            group_or_page_url=inferred_group_url,
            published_at=pub_dt.isoformat() if pub_dt else None,
            published_at_raw=pub_raw or cand.published_at_hint,
            collected_at=cand.collected_at,
            area_mentioned=extracted["area_mentioned"],
            sub_area=extracted["sub_area"],
            is_new_banha=extracted["is_new_banha"],
            price_egp=extracted["price_egp"],
            rooms_count=extracted["rooms_count"],
            bathrooms_count=extracted["bathrooms_count"],
            area_sqm=extracted["area_sqm"],
            furnishing_status=extracted["furnishing_status"],
            contact_info=extracted["contact_info"],
            source_name=cand.source_name,
            date_verification_status=date_status,
            extraction_status=extracted["extraction_status"],
            confidence_score=extracted["confidence_score"],
        )
        preliminary_posts.append(post_obj)

    # 5. إزالة التكرارات التامة ووضع علامات الاشتباه بالتكرار
    unique_posts, exact_dups = deduplicate_posts(preliminary_posts)
    stats["excluded_exact_duplicates"] = len(exact_dups)

    # 6. فصل المنشورات المؤكدة زمنيًا عن المنشورات غير المؤكد تاريخ نشرها
    verified_results: List[RentalPost] = []
    unverified_date_results: List[RentalPost] = []

    for p in unique_posts:
        if p.date_verification_status == "verified_in_range":
            verified_results.append(p)
        else:
            unverified_date_results.append(p)

    # 7. ترتيب النتائج المؤكدة من الأحدث إلى الأقدم حسب تاريخ النشر الأصلي
    verified_results.sort(
        key=lambda x: (x.published_at or "", x.confidence_score),
        reverse=True,
    )
    # ترتيب النتائج غير المؤكدة بحيث تظهر روابط بوستات فيسبوك المباشرة (/permalink/ و /posts/) أولاً
    unverified_date_results.sort(
        key=lambda x: (
            1 if (x.url_verified and x.post_url and "facebook.com" in x.post_url) else 0,
            1 if x.url_verified else 0,
            x.confidence_score,
            1 if x.price_egp else 0,
            x.collected_at,
        ),
        reverse=True,
    )

    stats["accepted_verified"] = len(verified_results)
    stats["accepted_unverified_date"] = len(unverified_date_results)

    return verified_results, unverified_date_results, stats
