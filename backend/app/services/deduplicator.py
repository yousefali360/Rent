"""وحدة إزالة التكرارات واكتشاف الإعلانات المتشابهة المنشورة في عدة جروبات.

تعتمد على:
1. تطابق رابط المنشور الأصلي (إن كان متحققًا منه كمنشور فعلي).
2. تطابق النص بعد التطبيع العربي الكامل.
3. حساب تشابه النص مع مقارنة السعر والمنطقة الفرعية وعدد الغرف وتاريخ النشر.
4. قاعدة عدم الدمج الخاطئ: عند وجود شك (تشابه نصي جزئي أو اختلاف في السعر/المنطقة/الغرف)،
   يتم الاحتفاظ بالنتيجتين مع وضع إشارة `possible_duplicate_of_id` («قد تكون مكررة»).
"""

from difflib import SequenceMatcher
from typing import List, Set, Tuple

from backend.app.models import RentalPost
from backend.app.services.arabic_nlp import normalize_arabic


def compute_text_similarity(norm_a: str, norm_b: str) -> float:
    """حساب نسبة التشابه بين نصين مطبّعين باستخدام مزيج من Jaccard للكلمات و SequenceMatcher."""
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    words_a: Set[str] = {w for w in norm_a.split() if len(w) > 1}
    words_b: Set[str] = {w for w in norm_b.split() if len(w) > 1}
    if not words_a or not words_b:
        return SequenceMatcher(None, norm_a, norm_b).ratio()

    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    jaccard = intersection / union if union else 0.0
    seq_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()

    return round((jaccard * 0.55) + (seq_ratio * 0.45), 3)


def deduplicate_posts(
    posts: List[RentalPost],
) -> Tuple[List[RentalPost], List[RentalPost]]:
    """فحص قائمة المنشورات لفصل النسخ المكررة تطابقًا تامًا وتحديد المشتبه بتكرارها.

    يعيد:
    (unique_and_flagged_posts, exact_duplicates_excluded)
    - المنشورات المكررة تطابقًا تامًا (نفس رابط المنشور أو تطابق نصي >= 0.96 مع نفس التفاصيل) تُستبعد.
    - المنشورات المتشابهة جزئيًا (بين 0.65 و 0.95) أو التي يتشابه نصها لكن نحتاط لعدم دمج إعلانين مختلفين
      يُحتفظ بها كلها مع تعيين `possible_duplicate_of_id` و `similarity_score`.
    """
    accepted: List[RentalPost] = []
    excluded_exact: List[RentalPost] = []

    for candidate in posts:
        cand_norm = candidate.normalized_text or normalize_arabic(candidate.original_text)
        candidate.normalized_text = cand_norm

        is_exact_dup = False
        best_possible_dup_id = None
        best_similarity = 0.0

        for existing in accepted:
            exist_norm = existing.normalized_text or normalize_arabic(existing.original_text)

            # 1. تطابق رابط المنشور الفعلي المتحقق منه
            if (
                candidate.url_verified
                and existing.url_verified
                and candidate.post_url
                and existing.post_url
                and candidate.post_url.rstrip("/") == existing.post_url.rstrip("/")
            ):
                candidate.duplicate_of_id = existing.id
                candidate.similarity_score = 1.0
                excluded_exact.append(candidate)
                is_exact_dup = True
                break

            # 2. حساب تشابه النص بعد التطبيع
            sim = compute_text_similarity(cand_norm, exist_norm)

            # التحقق من تعارض التفاصيل الجوهرية (سعر مختلف تمامًا أو عدد غرف مختلف أو منطقة فرعية مختلفة)
            price_conflict = (
                candidate.price_egp is not None
                and existing.price_egp is not None
                and candidate.price_egp != existing.price_egp
            )
            rooms_conflict = (
                candidate.rooms_count is not None
                and existing.rooms_count is not None
                and candidate.rooms_count != existing.rooms_count
            )
            sub_area_conflict = (
                candidate.sub_area is not None
                and existing.sub_area is not None
                and candidate.sub_area != existing.sub_area
            )
            new_banha_conflict = candidate.is_new_banha != existing.is_new_banha

            has_detail_conflict = (
                price_conflict or rooms_conflict or sub_area_conflict or new_banha_conflict
            )

            # إذا كان النص متطابقًا تقريبًا (>= 0.96) ولا يوجد أي تعارض في السعر أو المنطقة أو الغرف
            if sim >= 0.96 and not has_detail_conflict:
                candidate.duplicate_of_id = existing.id
                candidate.similarity_score = sim
                excluded_exact.append(candidate)
                is_exact_dup = True
                break

            # عند وجود تشابه ملحوظ (>= 0.62) أو نفس السعر والمنطقة والغرف مع تشابه نصي متوسط (>= 0.50)
            # لا ندمج المنشورين بل نحتفظ بهما مع الإشارة إلى أنهما قد يكونان مكررين
            same_key_specs = (
                candidate.price_egp is not None
                and candidate.price_egp == existing.price_egp
                and candidate.rooms_count is not None
                and candidate.rooms_count == existing.rooms_count
                and candidate.sub_area == existing.sub_area
                and not new_banha_conflict
            )

            if (sim >= 0.62 and not new_banha_conflict) or (same_key_specs and sim >= 0.48):
                if sim > best_similarity:
                    best_similarity = sim
                    best_possible_dup_id = existing.id

        if not is_exact_dup:
            if best_possible_dup_id:
                candidate.possible_duplicate_of_id = best_possible_dup_id
                candidate.similarity_score = best_similarity
            accepted.append(candidate)

    return accepted, excluded_exact
