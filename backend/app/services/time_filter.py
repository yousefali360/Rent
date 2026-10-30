"""وحدة الفلترة الزمنية والتحقق الصارم من تاريخ النشر الأصلي بتوقيت مصر (Africa/Cairo).

تلتزم بالقواعد التالية:
- المنطقة الزمنية: Africa/Cairo دائمًا.
- دعم الفترات: آخر 24 ساعة (24h)، آخر يومين (2d)، آخر 4 أيام (4d - افتراضي)، وفترة مخصصة (custom).
- تطبيق الفلترة على تاريخ نشر المنشور الأصلي فقط، وليس تاريخ جلب أو فهرسة النتيجة.
- إذا كان تاريخ النشر معروفًا وأقدم من الفترة المطلوبة -> verified_out_of_range (يُستبعد).
- إذا تعذر التحقق من تاريخ النشر الأصلي -> unverified (يُعرض في قسم مستقل «تاريخ النشر غير مؤكد»).
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from backend.app.models import DateVerificationStatus, TimePreset
from backend.app.services.arabic_nlp import convert_arabic_digits, normalize_arabic

CAIRO_TZ = ZoneInfo("Africa/Cairo")

ARABIC_MONTHS = {
    "يناير": 1,
    "فبراير": 2,
    "مارس": 3,
    "ابريل": 4,
    "أبريل": 4,
    "مايو": 5,
    "يونيو": 6,
    "يوليو": 7,
    "اغسطس": 8,
    "أغسطس": 8,
    "سبتمبر": 9,
    "اكتوبر": 10,
    "أكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
}

ENGLISH_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def now_cairo() -> datetime:
    """الوقت الحالي بتوقيت القاهرة (Africa/Cairo)."""
    return datetime.now(CAIRO_TZ)


def ensure_cairo_tz(dt: datetime) -> datetime:
    """ضمان ارتباط كائن التاريخ والوقت بالمنطقة الزمنية Africa/Cairo."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CAIRO_TZ)
    return dt.astimezone(CAIRO_TZ)


def compute_time_window(
    preset: TimePreset = "4d",
    custom_start: Optional[str] = None,
    custom_end: Optional[str] = None,
    reference_now: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """حساب بداية ونهاية الفترة الزمنية بدقة بتوقيت Africa/Cairo."""
    end_dt = ensure_cairo_tz(reference_now) if reference_now else now_cairo()

    if preset == "24h":
        start_dt = end_dt - timedelta(hours=24)
        return start_dt, end_dt
    if preset == "2d":
        start_dt = end_dt - timedelta(days=2)
        return start_dt, end_dt
    if preset == "4d":
        start_dt = end_dt - timedelta(days=4)
        return start_dt, end_dt

    if preset == "custom":
        if not custom_start or not custom_end:
            raise ValueError("يجب تحديد تاريخ ووقت البداية والنهاية عند اختيار فترة مخصصة.")
        parsed_start = parse_iso_or_datetime_input(custom_start)
        parsed_end = parse_iso_or_datetime_input(custom_end, is_end_of_day_if_date_only=True)
        if not parsed_start or not parsed_end:
            raise ValueError("صيغة تاريخ البداية أو النهاية غير صالحة.")
        if parsed_start > parsed_end:
            raise ValueError("تاريخ بداية الفترة يجب أن يكون قبل تاريخ النهاية.")
        return parsed_start, parsed_end

    # القيمة الافتراضية الآمنة: آخر 4 أيام
    return end_dt - timedelta(days=4), end_dt


def parse_iso_or_datetime_input(
    value: str, is_end_of_day_if_date_only: bool = False
) -> Optional[datetime]:
    """تحليل مدخلات التاريخ القياسية (ISO 8601 أو YYYY-MM-DD) وربطها بتوقيت القاهرة."""
    if not value or not value.strip():
        return None
    raw = convert_arabic_digits(value.strip())

    # إذا كان تاريخًا فقط بصيغة YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        dt = datetime.strptime(raw, "%Y-%m-%d")
        if is_end_of_day_if_date_only:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt.replace(tzinfo=CAIRO_TZ)

    # استبدال Z بـ +00:00 لدعم fromisoformat
    iso_candidate = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_candidate)
        return ensure_cairo_tz(dt)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt == "%Y/%m/%d" and is_end_of_day_if_date_only:
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=CAIRO_TZ)
        except ValueError:
            continue

    return None


def parse_published_date(
    text_or_date: Optional[str], reference_now: Optional[datetime] = None
) -> Tuple[Optional[datetime], Optional[str]]:
    """استخراج وتحليل تاريخ النشر الأصلي من نص تاريخ مباشر أو من مقتطف منشور.

    يعيد: (كائن_التاريخ_بتوقيت_القاهرة, النص_الزمني_المكتشف)
    إذا لم يُعثر على تاريخ نشر حقيقي، يعيد (None, None).
    """
    if not text_or_date or not text_or_date.strip():
        return None, None

    ref = ensure_cairo_tz(reference_now) if reference_now else now_cairo()
    cleaned = convert_arabic_digits(text_or_date.strip())

    # 1. محاولة التحليل المباشر بصيغة ISO أو تاريخ قياسي
    direct_dt = parse_iso_or_datetime_input(cleaned)
    if direct_dt:
        return direct_dt, text_or_date.strip()

    norm = normalize_arabic(cleaned)

    # 2. تعبيرات فورية ("الآن"، "لسه منشور"، "منذ لحظات"، "just now")
    if re.search(r"\b(الان|لسه منشور|منذ لحظات|منذ ثواني|just now)\b", norm):
        return ref, "الآن"

    # 3. الدقائق: "منذ 15 دقيقة" / "قبل 10 دقائق" / "15 mins ago" / "15m ago"
    m_min = re.search(
        r"(?:منذ|قبل)\s*(\d+)\s*(?:دقيقه|دقايق|دقائق|د)\b|(\d+)\s*(?:mins?|minutes?)\s*ago\b",
        norm,
    )
    if m_min:
        mins = int(m_min.group(1) or m_min.group(2))
        return ref - timedelta(minutes=mins), m_min.group(0)

    if re.search(r"(?:منذ|قبل)\s*(?:دقيقه|دقيقة)\b", norm):
        return ref - timedelta(minutes=1), "منذ دقيقة"

    # 4. الساعات: "منذ ساعة" / "منذ ساعتين" / "منذ 5 ساعات" / "3 hours ago"
    if re.search(r"(?:منذ|قبل)\s*ساعه\b", norm):
        return ref - timedelta(hours=1), "منذ ساعة"
    if re.search(r"(?:منذ|قبل)\s*ساعتين\b", norm):
        return ref - timedelta(hours=2), "منذ ساعتين"

    m_hr = re.search(
        r"(?:منذ|قبل)\s*(\d+)\s*(?:ساعات|ساعه|س)\b|(\d+)\s*(?:hours?|hrs?)\s*ago\b",
        norm,
    )
    if m_hr:
        hours = int(m_hr.group(1) or m_hr.group(2))
        return ref - timedelta(hours=hours), m_hr.group(0)

    # 5. أمس / امبارح / yesterday
    if re.search(r"\b(امس|امبارح|اول امس|اول امبارح|yesterday)\b", norm):
        if "اول امس" in norm or "اول امبارح" in norm:
            return ref - timedelta(days=2), "أول أمس"
        # فحص ما إذا كان مذكورًا معه ساعة محددة مثل "أمس الساعة 6"
        m_hr_clock = re.search(r"الساعه\s*(\d{1,2})", norm)
        target = ref - timedelta(days=1)
        if m_hr_clock:
            hr = int(m_hr_clock.group(1))
            if ("مساء" in norm or "م" in norm) and hr < 12:
                hr += 12
            if 0 <= hr <= 23:
                target = target.replace(hour=hr, minute=0, second=0)
        return target, "أمس"

    # 6. الأيام: "منذ يوم" / "منذ يومين" / "قبل يومين" / "منذ 3 أيام" / "3 days ago"
    if re.search(r"(?:منذ|قبل)\s*يوم\b", norm):
        return ref - timedelta(days=1), "منذ يوم"
    if re.search(r"(?:منذ|قبل)\s*يومين\b", norm):
        return ref - timedelta(days=2), "منذ يومين"

    m_day = re.search(
        r"(?:منذ|قبل)\s*(\d+)\s*(?:ايام|يوم)\b|(\d+)\s*(?:days?)\s*ago\b",
        norm,
    )
    if m_day:
        days = int(m_day.group(1) or m_day.group(2))
        return ref - timedelta(days=days), m_day.group(0)

    # 7. الأسابيع: "منذ أسبوع" / "منذ اسبوعين" / "منذ 3 اسابيع"
    if re.search(r"(?:منذ|قبل)\s*اسبوع\b", norm):
        return ref - timedelta(days=7), "منذ أسبوع"
    if re.search(r"(?:منذ|قبل)\s*اسبوعين\b", norm):
        return ref - timedelta(days=14), "منذ أسبوعين"
    m_week = re.search(r"(?:منذ|قبل)\s*(\d+)\s*(?:اسابيع|اسبوع)\b|(\d+)\s*weeks?\s*ago\b", norm)
    if m_week:
        weeks = int(m_week.group(1) or m_week.group(2))
        return ref - timedelta(days=weeks * 7), m_week.group(0)

    # 8. التواريخ العربية الصريحة: مثل "8 أكتوبر 2026" أو "9 اكتوبر"
    for month_name, month_num in ARABIC_MONTHS.items():
        norm_month = normalize_arabic(month_name)
        pattern = rf"\b(\d{{1,2}})\s+{re.escape(norm_month)}(?:\s+(\d{{4}}))?\b"
        m_ar_date = re.search(pattern, norm)
        if m_ar_date:
            day = int(m_ar_date.group(1))
            year = int(m_ar_date.group(2)) if m_ar_date.group(2) else ref.year
            try:
                dt = datetime(year, month_num, day, 12, 0, tzinfo=CAIRO_TZ)
                return dt, m_ar_date.group(0)
            except ValueError:
                pass

    # 9. التواريخ الإنجليزية في مقتطفات البحث: مثل "Oct 8, 2026" أو "8 Oct 2026"
    lower_clean = cleaned.lower()
    m_en1 = re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b",
        lower_clean,
    )
    if m_en1:
        month_num = ENGLISH_MONTHS[m_en1.group(1)[:3]]
        day = int(m_en1.group(2))
        year = int(m_en1.group(3))
        try:
            return datetime(year, month_num, day, 12, 0, tzinfo=CAIRO_TZ), m_en1.group(0)
        except ValueError:
            pass

    m_en2 = re.search(
        r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{4})\b",
        lower_clean,
    )
    if m_en2:
        day = int(m_en2.group(1))
        month_num = ENGLISH_MONTHS[m_en2.group(2)[:3]]
        year = int(m_en2.group(3))
        try:
            return datetime(year, month_num, day, 12, 0, tzinfo=CAIRO_TZ), m_en2.group(0)
        except ValueError:
            pass

    # 10. صيغة YYYY-MM-DD أو YYYY/MM/DD داخل النص
    m_ymd = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", cleaned)
    if m_ymd:
        year, month, day = int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3))
        try:
            return datetime(year, month, day, 12, 0, tzinfo=CAIRO_TZ), m_ymd.group(0)
        except ValueError:
            pass

    return None, None


def verify_post_date_in_window(
    published_dt: Optional[datetime],
    window_start: datetime,
    window_end: datetime,
) -> DateVerificationStatus:
    """التحقق الصارم مما إذا كان تاريخ نشر المنشور الأصلي يقع ضمن الفترة المطلوبة.

    - إذا كان التاريخ غير معروف (None) -> 'unverified'
    - إذا كان التاريخ ضمن [window_start, window_end] -> 'verified_in_range'
    - إذا كان التاريخ أقدم من window_start أو خارج النطاق -> 'verified_out_of_range'
    """
    if published_dt is None:
        return "unverified"

    pub_cairo = ensure_cairo_tz(published_dt)
    start_cairo = ensure_cairo_tz(window_start)
    end_cairo = ensure_cairo_tz(window_end)

    # السماح بهامش 5 دقائق لنهاية الفترة لتفادي فروق الثواني أثناء التنفيذ
    if start_cairo <= pub_cairo <= (end_cairo + timedelta(minutes=5)):
        return "verified_in_range"

    return "verified_out_of_range"
