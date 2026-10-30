"""وحدة استخراج بيانات الإعلانات العقارية العربية والتحقق من روابط المنشورات.

تستخرج الحقول التالية دون اختلاق أي معلومة غير موجودة في المصدر:
- السعر الشهري بالجنيه المصري (مع التمييز عن مبلغ التأمين أو أسعار التمليك)
- عدد الغرف وعدد الحمامات
- المساحة بالمتر المربع
- حالة الفرش (مفروش / غير مفروش - فاضي / نصف فرش)
- المنطقة والمنطقة الفرعية (مع التمييز بين بنها وبنها الجديدة)
- وسيلة التواصل المعلنة (رقم هاتف مصري أو تواصل خاص)
- التحقق من رابط النشور الأصلي (هل هو رابط منشور فعلي أم مجرد رابط جروب/صفحة عام)
- حساب حالة الاستخراج (complete / partial / minimal) ودرجة الثقة (confidence_score)
"""

import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from backend.app.models import ExtractionStatus, UrlVerificationType
from backend.app.services.arabic_nlp import (
    analyze_area_mention,
    convert_arabic_digits,
    normalize_arabic,
)


def verify_facebook_or_post_url(url: Optional[str]) -> Tuple[bool, UrlVerificationType, Optional[str], Optional[str]]:
    """فحص الرابط للتحقق مما إذا كان يشير إلى منشور فعلي أم مجرد الصفحة الرئيسية لجروب/صفحة.

    يعيد:
    (url_verified_as_post, url_type, canonical_post_url, group_or_page_url)
    """
    if not url or not url.strip():
        return False, "unverified", None, None

    cleaned_url = url.strip()
    try:
        parsed = urlparse(cleaned_url)
    except Exception:
        return False, "unverified", None, None

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "unverified", None, None

    host = parsed.netloc.lower()
    path = parsed.path or ""
    query = parse_qs(parsed.query)

    # فحص روابط فيسبوك
    if "facebook.com" in host or "fb.com" in host or "fb.watch" in host:
        # 1. منشور داخل جروب: /groups/{group_id}/posts/{post_id} أو /groups/{group_id}/permalink/{post_id}
        m_group_post = re.search(
            r"(/groups/[^/?#]+)/(?:posts|permalink)/(\d+|[a-zA-Z0-9_-]+)",
            path,
        )
        if m_group_post:
            group_path = m_group_post.group(1)
            group_url = f"https://www.facebook.com{group_path}"
            canonical_post = f"https://www.facebook.com{m_group_post.group(0)}"
            return True, "post", canonical_post, group_url

        # 2. منشور عبر multi_permalinks في رابط جروب
        if "/groups/" in path and "multi_permalinks" in query:
            post_id = query["multi_permalinks"][0]
            m_grp = re.search(r"(/groups/[^/?#]+)", path)
            if m_grp and post_id:
                group_url = f"https://www.facebook.com{m_grp.group(1)}"
                canonical_post = f"{group_url}/posts/{post_id}"
                return True, "post", canonical_post, group_url

        # 3. منشور مباشر في صفحة أو حساب أو رابط مشاركة منشور:
        # /posts/..., /permalink.php?story_fbid=..., /story.php?story_fbid=..., /share/p/..., /reel/..., /videos/...
        if (
            re.search(r"/posts/(\d+|pfbid[a-zA-Z0-9]+)", path)
            or re.search(r"/share/p/[a-zA-Z0-9]+", path)
            or ("story_fbid" in query and ("permalink.php" in path or "story.php" in path))
            or re.search(r"/photos/[^/]+/\d+", path)
        ):
            return True, "post", cleaned_url, None

        # 4. رابط وصول لمنشور محدد داخل جروب عام (/groups/{id}/search/?q=...)
        m_grp_search = re.search(r"^(/groups/[^/?#]+)/search/?$", path)
        if m_grp_search:
            return False, "group_or_page", None, f"https://www.facebook.com{m_grp_search.group(1)}"

        # 5. رابط بحث عام داخل فيسبوك
        if "/search/" in path:
            return False, "search_link", None, None

        # 6. رابط جروب عام أو صفحة عامة فقط بدون معرف منشور
        if re.search(r"^/groups/[^/?#]+/?$", path):
            return False, "group_or_page", None, cleaned_url

        return False, "group_or_page", None, cleaned_url

    # روابط مواقع عقارية عامة أخرى إذا كانت تشير لصفحة إعلان مفردة
    if len(path.strip("/").split("/")) >= 2:
        return True, "post", cleaned_url, None

    return False, "unverified", None, cleaned_url


def extract_monthly_price_egp(text: str) -> Optional[int]:
    """استخراج قيمة الإيجار الشهري بالجنيه المصري بدقة، مع تجنب رقم الهاتف أو التأمين أو المساحة."""
    if not text:
        return None

    cleaned = convert_arabic_digits(text)
    # إزالة أرقام الهواتف المصرية أولاً حتى لا تُقرأ خطأً كأرقام أسعار
    cleaned_no_phones = re.sub(r"\b01[0125]\d{8}\b", " ", cleaned)
    # إزالة الفواصل بين الآلاف مثل 4,500 أو 4.500 (عندما تكون 3 أرقام بعد النقطة)
    cleaned_norm_thousands = re.sub(r"(\d)[,،](\d{3})\b", r"\1\2", cleaned_no_phones)

    norm = normalize_arabic(cleaned_norm_thousands)

    # 1. صيغة "X.Y الف" أو "X ونص الف" مثل "4.5 الف" أو "3 الف"
    m_k = re.search(
        r"(?:الايجار|ايجار|سعر|مطلوب|ب)?\s*(\d+(?:\.\d+)?)\s*(?:الف|آلاف|الاف)(?:\s*و\s*نص|\s*ونصف)?\s*(?:جنيه|ج|شهريا)?",
        cleaned_norm_thousands,
    )
    if m_k:
        val = float(m_k.group(1))
        full_match = m_k.group(0)
        if "ونص" in full_match or "و نص" in full_match:
            val += 0.5
        price = int(val * 1000)
        if 500 <= price <= 50000:
            return price

    # 2. البحث عن السعر المسبوق مباشرة بكلمات الإيجار (الإيجار / ايجار / السعر)
    direct_rent_patterns = [
        r"(?:الايجار|ايجارها|ايجار|السعر|سعر الايجار)\s*(?:الشهري\s*)?[:\-/]?\s*(\d{3,5})\s*(?:جنيه|ج|ج\.م|شهريا|شهري|في الشهر)?",
        r"\b(\d{3,5})\s*(?:جنيه|ج|ج\s*م)\s*(?:شهريا|شهري|في الشهر|ايجار|بالشهر|شهر)",
        r"\b(\d{3,5})\s*(?:شهريا|شهري|في الشهر)\b",
    ]
    for pat in direct_rent_patterns:
        for match in re.finditer(pat, norm):
            candidate = int(match.group(1))
            if 500 <= candidate <= 60000:
                return candidate

    # 3. البحث عن السعر بعد كلمة "مطلوب" أو المتبوع بكلمة "جنيه" بشرط ألا يكون مسبوقًا بكلمة "تأمين"
    fallback_patterns = [
        r"مطلوب\s*[:\-]?\s*(\d{3,5})\s*(?:جنيه|ج)?",
        r"\b(\d{3,5})\s*(?:جنيه|جنيه مصري|ج\s*م|ج\b)",
    ]
    for pat in fallback_patterns:
        for match in re.finditer(pat, norm):
            candidate = int(match.group(1))
            start_idx = max(0, match.start() - 16)
            prefix = norm[start_idx : match.start()]
            if "تامين" in prefix or "عموله" in prefix:
                continue
            if 500 <= candidate <= 60000:
                return candidate

    return None


def extract_rooms_and_bathrooms(text: str) -> Tuple[Optional[int], Optional[int]]:
    """استخراج عدد الغرف وعدد الحمامات إن ذُكرا في النص."""
    if not text:
        return None, None

    norm = normalize_arabic(text)
    rooms: Optional[int] = None
    bathrooms: Optional[int] = None

    # استخراج الغرف (يدعم غرفتين، غرفتان، اوضتين، 2 غرفة، 3 غرف...)
    if re.search(
        r"(?:^|\s|و)(غرفتين|غرفتان|اوضتين|2 غرفه|2 غرف|2 نوم|غرفتين نوم|غرفتين وصاله|اوضتين وصاله)\b",
        norm,
    ):
        rooms = 2
    elif re.search(
        r"(?:^|\s|و)(ثلاث غرف|ثلاثه غرف|ثلاث اوض|3 غرف|3 غرفه|3 اوض|3 نوم|3 وصاله)\b",
        norm,
    ):
        rooms = 3
    elif re.search(
        r"(?:^|\s|و)(اربع غرف|اربعه غرف|4 غرف|4 غرفه|4 نوم)\b",
        norm,
    ):
        rooms = 4
    elif re.search(
        r"(?:^|\s|و)(غرفه واحده|غرفه وصاله|اوضه وصاله|1 غرفه|استوديو|ستوديو)\b",
        norm,
    ):
        rooms = 1
    else:
        m_rooms = re.search(r"\b(\d)\s*(?:غرف|غرفه|اوض|نوم|وصاله)\b", norm)
        if m_rooms:
            val = int(m_rooms.group(1))
            if 1 <= val <= 8:
                rooms = val

    # استخراج الحمامات
    if re.search(r"(?:^|\s|و)(حمامين|حمامان|2 حمام)\b", norm):
        bathrooms = 2
    elif re.search(r"(?:^|\s|و)(3 حمام|ثلاث حمامات)\b", norm):
        bathrooms = 3
    elif re.search(
        r"(?:^|\s|و)(1 حمام|حمام واحد|مطبخ وحمام|حمام ومطبخ|وحمام كبير|وحمام اوفيس|حمام سوبر)\b",
        norm,
    ):
        bathrooms = 1
    else:
        m_bath = re.search(r"\b(\d)\s*(?:حمام|حمامات)\b", norm)
        if m_bath:
            val = int(m_bath.group(1))
            if 1 <= val <= 5:
                bathrooms = val

    return rooms, bathrooms


def extract_area_sqm(text: str) -> Optional[int]:
    """استخراج المساحة بالمتر المربع إن ذُكرت (مثل: 120 متر، 135م، 100 م2)."""
    if not text:
        return None

    cleaned = convert_arabic_digits(text)
    norm = normalize_arabic(cleaned)

    patterns = [
        r"(?:مساحه|مساحتها|المساحه|بمساحه|مساحه حوالي)\s*(?:م2\s*)?(\d{2,3})\s*(?:متر|م2|م)?\b",
        r"\b(\d{2,3})\s*(?:متر مربع|متر|م2)\b",
        r"\b(\d{2,3})\s*م\b(?!\s*(?:ص|مساء|صباحا|بينها))",
    ]
    for pat in patterns:
        m = re.search(pat, norm)
        if m:
            sqm = int(m.group(1))
            if 40 <= sqm <= 600:
                return sqm

    return None


def extract_furnishing_status(text: str) -> Optional[str]:
    """استخراج حالة الفرش إن ذُكرت صراحة في المنشور دون تخمين."""
    if not text:
        return None

    norm = normalize_arabic(text)

    if re.search(r"\b(نصف فرش|نص فرش|فرش جزئي)\b", norm):
        return "نصف فرش"

    if re.search(r"\b(بدون فرش|غير مفروشه|غير مفروش|فاضيه|فاضي|علي المحاره|قانون جديد فاضيه)\b", norm):
        return "غير مفروش (فاضي)"

    if re.search(r"\b(مفروشه|مفروش|فرش كامل|مكيفه ومفروشه|سكن طلاب مفروش)\b", norm):
        return "مفروش"

    # إذا ذُكر "قانون جديد" فقط دون كلمة مفروش، نشير إلى أنه قانون جديد
    if "قانون جديد" in norm:
        return "قانون جديد"

    return None


def extract_contact_info(text: str) -> Optional[str]:
    """استخراج وسيلة التواصل المعلنة في المنشور إذا كانت متاحة ومناسبة للعرض."""
    if not text:
        return None

    cleaned = convert_arabic_digits(text)

    # البحث عن أرقام الهواتف المصرية (010, 011, 012, 015)
    phones = re.findall(r"\b(01[0125]\d{8})\b", cleaned)
    if phones:
        unique_phones = list(dict.fromkeys(phones))
        norm = normalize_arabic(cleaned)
        prefix = "واتساب / هاتف: " if ("واتس" in norm or "whatsapp" in norm) else "هاتف: "
        return prefix + " - ".join(unique_phones[:2])

    norm = normalize_arabic(cleaned)
    if re.search(r"\b(التواصل خاص|تواصل خاص|علي الخاص|رسائل الصفحه|ماسنجر|كومنت)\b", norm):
        return "التواصل عبر رسائل فيسبوك (خاص)"

    return None


def extract_all_post_fields(
    text: str,
    target_area: str = "بنها",
    post_url: Optional[str] = None,
) -> Dict[str, Any]:
    """استخراج جميع الحقول المطلوبة من نص المنشور وحساب درجة الثقة وحالة الاستخراج."""
    area_info = analyze_area_mention(text, target_area=target_area)
    price_egp = extract_monthly_price_egp(text)
    rooms, bathrooms = extract_rooms_and_bathrooms(text)
    area_sqm = extract_area_sqm(text)
    furnishing = extract_furnishing_status(text)
    contact = extract_contact_info(text)
    url_verified, url_type, canonical_post_url, group_url = verify_facebook_or_post_url(post_url)

    # حساب عدد الحقول المستخرجة لتحديد حالة الاستخراج ودرجة الثقة
    extracted_signals = [
        area_info.get("area_mentioned") is not None,
        area_info.get("sub_area") is not None,
        price_egp is not None,
        rooms is not None,
        area_sqm is not None,
        furnishing is not None,
        contact is not None,
        url_verified,
    ]
    count_signals = sum(1 for s in extracted_signals if s)

    if count_signals >= 5:
        extraction_status: ExtractionStatus = "complete"
    elif count_signals >= 2:
        extraction_status = "partial"
    else:
        extraction_status = "minimal"

    # حساب درجة الثقة بين 0.25 و 0.98 بناءً على اكتمال الأدلة
    base_confidence = 0.35
    if area_info.get("matches_target_area"):
        base_confidence += 0.20
    if price_egp is not None:
        base_confidence += 0.15
    if rooms is not None or area_sqm is not None:
        base_confidence += 0.10
    if furnishing is not None or area_info.get("sub_area") is not None:
        base_confidence += 0.08
    if url_verified:
        base_confidence += 0.10

    confidence_score = round(min(0.98, max(0.20, base_confidence)), 2)

    return {
        "area_mentioned": area_info["area_mentioned"],
        "sub_area": area_info["sub_area"],
        "is_new_banha": bool(area_info["is_new_banha"]),
        "matches_target_area": bool(area_info["matches_target_area"]),
        "price_egp": price_egp,
        "rooms_count": rooms,
        "bathrooms_count": bathrooms,
        "area_sqm": area_sqm,
        "furnishing_status": furnishing,
        "contact_info": contact,
        "url_verified": url_verified,
        "url_type": url_type,
        "canonical_post_url": canonical_post_url,
        "inferred_group_url": group_url,
        "extraction_status": extraction_status,
        "confidence_score": confidence_score,
    }
