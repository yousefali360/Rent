"""وحدة معالجة النصوص العربية وتطبيعها ومطابقة سياق إعلانات الإيجار وتمييز المناطق.

تدعم:
- توحيد همزات الألف (أ، إ، آ، ٱ -> ا)
- توحيد التاء المربوطة والهاء في نهاية الكلمات (ة -> ه)
- توحيد الياء والألف المقصورة (ى -> ي)
- إزالة التشكيل والتطويل (الكشيدة)
- تحويل الأرقام العربية المشرقية (٠-٩) إلى أرقام قياسية (0-9)
- دعم اختلافات: شقة / شقه / شقق، للإيجار / للايجار، إيجار / ايجار
- التمييز الدقيق بين «بنها» و«بنها الجديدة» دون دمجهما تلقائيًا بلا سياق
- فحص السياق للتأكد من أن المنشور إعلان إيجار عقاري وليس مجرد ذكر عابر لكلمة «شقة»
"""

import re
from typing import Dict, List, Optional, Set, Tuple

# إزالة الحركات والتشكيل والتطويل
TASHKEEL_PATTERN = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u0640]")

# جدول تحويل الأرقام العربية/الفارسية إلى أرقام غربية قياسية
ARABIC_DIGITS_MAP = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)

# مرادفات وتصريفات كلمات العقار السكني
PROPERTY_TERMS_RAW = [
    "شقة",
    "شقه",
    "شقق",
    "ستوديو",
    "استوديو",
    "أستوديو",
    "دور",
    "رووف",
    "روف",
    "دوبلكس",
    "سكن",
    "مسكن",
    "غرفة",
    "غرفه",
    "غرف",
]

# مرادفات وتصريفات الإيجار
RENTAL_TERMS_RAW = [
    "للايجار",
    "للإيجار",
    "ايجار",
    "إيجار",
    "آيجار",
    "تأجير",
    "تاجير",
    "للتأجير",
    "للتاجير",
    "قانون جديد",
    "مفروش",
    "مفروشة",
    "مفروشه",
    "شهري",
    "شهريا",
    "شهرياً",
    "تأمين",
    "تامين",
    "مطلوب مستأجر",
    "مطلوب مستاجر",
    "سكن طلاب",
    "سكن طالبات",
    "سكن مغتربين",
    "سكن عائلي",
]

# مؤشرات البيع فقط أو السياقات غير العقارية لاستبعاد المنشورات غير ذات الصلة
SALE_ONLY_TERMS_RAW = [
    "للبيع فقط",
    "تمليك فقط",
    "تقسيط على",
    "مقدم تعاقد",
    "تسهيلات في السداد",
]

NON_REAL_ESTATE_CONTEXT_RAW = [
    "شقة في الجنة",
    "شقه في الجنه",
    "تنظيف شقق",
    "شركة تنظيف",
    "نقل عفش",
    "ونش رفع اثاث",
    "مكافحة حشرات",
    "تشطيب شقق",
    "اعمال نقاشة",
    "سباكة وكهرباء",
]


def convert_arabic_digits(text: str) -> str:
    """تحويل الأرقام العربية المشرقية (٠١٢٣٤٥٦٧٨٩) إلى أرقام قياسية (0123456789)."""
    if not text:
        return ""
    return text.translate(ARABIC_DIGITS_MAP)


def normalize_arabic(text: str, keep_newlines: bool = False) -> str:
    """تطبيع النص العربي للمقارنة والبحث وإزالة التكرار مع الحفاظ على بنية الكلمات.

    ملاحظة: يُستخدم هذا النص للمطابقة فقط، بينما يُحفظ النص الأصلي لعرضه للمستخدم.
    """
    if not text:
        return ""

    # 1. تحويل الأرقام
    res = convert_arabic_digits(text)

    # 2. إزالة التشكيل والتطويل
    res = TASHKEEL_PATTERN.sub("", res)

    # 3. توحيد همزات الألف
    res = re.sub(r"[أإآٱ]", "ا", res)

    # 4. توحيد التاء المربوطة إلى هاء
    res = res.replace("ة", "ه")

    # 5. توحيد الألف المقصورة إلى ياء
    res = res.replace("ى", "ي")

    # 6. توحيد الهمزة على واو/ياء في الكلمات الشائعة (مثل مسؤول/مسئول)
    res = res.replace("ؤ", "و").replace("ئ", "ي")

    # 7. تنظيف علامات الترقيم غير الضرورية مع الإبقاء على الأرقام والحروف
    if keep_newlines:
        res = re.sub(r"[^\w\s\n]", " ", res)
        res = re.sub(r"[ \t]+", " ", res)
    else:
        res = re.sub(r"[^\w\s]", " ", res)
        res = re.sub(r"\s+", " ", res)

    return res.strip().lower()


# القوائم المطبّعة للمقارنة السريعة
PROPERTY_TERMS_NORM: List[str] = list({normalize_arabic(t) for t in PROPERTY_TERMS_RAW})
RENTAL_TERMS_NORM: List[str] = list({normalize_arabic(t) for t in RENTAL_TERMS_RAW})
SALE_ONLY_NORM: List[str] = list({normalize_arabic(t) for t in SALE_ONLY_TERMS_RAW})
NON_REAL_ESTATE_NORM: List[str] = list({normalize_arabic(t) for t in NON_REAL_ESTATE_CONTEXT_RAW})


def expand_arabic_keyword_variants(keyword: str) -> List[str]:
    """توليد الاختلافات الإملائية العربية للكلمة المفتاحية لضمان شمولية البحث."""
    kw = keyword.strip()
    if not kw:
        return []

    variants: Set[str] = {kw}

    # تباديل التاء المربوطة والهاء
    if "ة" in kw:
        variants.add(kw.replace("ة", "ه"))
    if kw.endswith("ه") or "شقه " in kw:
        variants.add(re.sub(r"شقه\b", "شقة", kw))
        variants.add(re.sub(r"مفروشه\b", "مفروشة", kw))

    # تباديل همزة إيجار / للإيجار
    for v in list(variants):
        if "للإيجار" in v:
            variants.add(v.replace("للإيجار", "للايجار"))
        if "للايجار" in v:
            variants.add(v.replace("للايجار", "للإيجار"))
        if "إيجار" in v:
            variants.add(v.replace("إيجار", "ايجار"))
        if "ايجار" in v and "للايجار" not in v:
            variants.add(v.replace("ايجار", "إيجار"))

    # إضافة الجمع والمفرد لكلمة شقة / شقق
    for v in list(variants):
        if "شقة" in v:
            variants.add(v.replace("شقة", "شقق"))
        elif "شقق" in v:
            variants.add(v.replace("شقق", "شقة"))

    return sorted(variants)


def build_combined_search_queries(
    area: str,
    keywords: List[str],
    include_new_banha: bool = True,
) -> List[str]:
    """دمج الكلمات المفتاحية والمنطقة لبناء استعلامات بحث عربية ذكية ومتنوعة."""
    clean_area = area.strip() or "بنها"
    queries: List[str] = []

    # 1. استعلامات مباشرة شاملة للمنطقة
    base_combinations = [
        f"شقة للإيجار في {clean_area}",
        f"شقه للايجار {clean_area}",
        f"شقق للايجار في {clean_area}",
        f"شقة مفروشة للإيجار {clean_area}",
        f"شقة من المالك {clean_area} ايجار",
        f"شقة قانون جديد {clean_area}",
    ]

    if clean_area == "بنها":
        # إضافة أشهر مناطق بنها الفرعية لاكتشاف المنشورات التي تذكر الحي مع بنها
        base_combinations.extend(
            [
                "شقة للإيجار بنها الفلل",
                "شقة للايجار بنها كفر الجزار",
                "شقة للايجار بنها أتريب أو المنشية",
                "شقة للايجار بنها الأهرام أو الحرس الوطني",
            ]
        )
        if include_new_banha:
            base_combinations.append("شقة للإيجار بنها الجديدة")

    for q in base_combinations:
        if q not in queries:
            queries.append(q)

    # 2. دمج أي كلمات مخصصة أضافها المستخدم مع اسم المنطقة إن لم تكن متضمنة
    norm_area = normalize_arabic(clean_area)
    for kw in keywords:
        kw_clean = kw.strip()
        if not kw_clean:
            continue
        norm_kw = normalize_arabic(kw_clean)
        if norm_area in norm_kw:
            if kw_clean not in queries:
                queries.append(kw_clean)
        else:
            combined = f"{kw_clean} {clean_area}"
            if combined not in queries:
                queries.append(combined)

    return queries


def analyze_area_mention(
    text: str, target_area: str = "بنها"
) -> Dict[str, Optional[object]]:
    """تحليل ذكر المنطقة والتمييز الدقيق بين «بنها» و«بنها الجديدة» والمناطق الفرعية.

    لا يعتبر «بنها» و«بنها الجديدة» مكانًا واحدًا تلقائيًا دون سياق:
    - إذا ذكر النص «بنها الجديدة» فقط، يتم تصنيف `area_mentioned="بنها الجديدة"` و `is_new_banha=True`.
    - إذا ذكر النص «بنها» (أو أحد أحيائها مثل الفلل، أتريب، كفر الجزار...) دون «بنها الجديدة»،
      يتم تصنيف `area_mentioned="بنها"` و `is_new_banha=False`.
    - إذا ذكر الاثنين معًا، يتم توضيح ذلك.
    """
    norm = normalize_arabic(text)
    norm_target = normalize_arabic(target_area)

    # فحص بنها الجديدة أولاً
    new_banha_norm = normalize_arabic("بنها الجديدة")
    has_new_banha = new_banha_norm in norm

    # إزالة عبارة "بنها الجديده" مؤقتًا لفحص ما إذا كانت "بنها" العادية مذكورة أيضًا بشكل مستقل
    norm_without_new_banha = norm.replace(new_banha_norm, " ")
    has_regular_banha = norm_target in norm_without_new_banha

    # فحص الأحياء الفرعية والمعالم الشهيرة في بنها
    sub_areas_map = {
        "الفلل": ["الفلل", "حي الفلل", "منطقه الفلل", "الفيلل", "الفيلل القديمه", "الفلل القديمه", "بعد الفحص", "قبل الفحص", "كوبري الفحص"],
        "كفر الجزار": ["كفر الجزار", "كفرالجزار"],
        "أتريب": ["اتريب", "أتريب", "حي اتريب", "شارع اتريب"],
        "المنشية": ["المنشيه", "منشيه النور", "المنشية", "محيط المنشيه", "عمارات بور سعيد"],
        "الأهرام": ["الاهرام", "شارع الاهرام", "منطقه الاهرام"],
        "الحرس الوطني": ["الحرس الوطني", "مساكن الحرس", "منشيه الحرس الوطني"],
        "وسط البلد / المحطة": ["وسط البلد", "شارع فريد ندا", "فريد ندا", "المحطه", "محطه قطار بنها", "سعد زغلول", "شارع المحطه", "التوحيد والنور", "ابراج الامل", "مديريه الامن", "الرياح التوفيقي"],
        "كفر السرايا": ["كفر السرايا", "السرايا", "شارع المرور", "شارع التجاره", "ش تجاره"],
        "الكورنيش / البحر": ["الكورنيش", "كورنيش النيل", "كورنيش بنها", "البحر", "عزبه البرنس", "علي النيل"],
        "عزبة الزراعة": ["عزبه الزراعه", "كلية الزراعة", "كليه الزراعه"],
        "الشدية": ["الشديه", "الشدية", "وابور الثلج", "شارع الترعه"],
        "حي الزهور": ["حي الزهور", "الزهور", "الزهور الجديده"],
        "مساكن طابا / الموقف": ["مساكن طابا", "مصنع السبيلي", "شارع الموقف", "موقف بنها"],
        "منطقة العلوم / الجامعة": ["منطقه علوم", "كليه الطب", "مستشفي بنها الجامعي", "خدمه اجتماعيه", "شارع خدمه اجتماعيه", "قصر الثقافه", "نقابه الصيادله", "قسم تاني بنها"],
        "الرملة": ["الرمله", "الرملة"],
        "بطا": ["بطا", "قريه بطا"],
        "بنها الجديدة": ["بنها الجديده", "بنها الجديدة"],
    }

    detected_sub_areas: List[str] = []
    for canonical_sub, aliases in sub_areas_map.items():
        if canonical_sub == "بنها الجديدة":
            continue
        for alias in aliases:
            norm_alias = normalize_arabic(alias)
            # مطابقة كلمة كاملة لتجنب التداخل الجزئي
            if re.search(rf"\b{re.escape(norm_alias)}\b", norm_without_new_banha):
                detected_sub_areas.append(canonical_sub)
                break

    sub_area = "، ".join(detected_sub_areas) if detected_sub_areas else None

    if has_new_banha and not has_regular_banha and not detected_sub_areas:
        return {
            "area_mentioned": "بنها الجديدة",
            "sub_area": "بنها الجديدة",
            "is_new_banha": True,
            "matches_target_area": target_area in ("بنها", "بنها الجديدة"),
        }

    if has_regular_banha or detected_sub_areas:
        area_label = target_area
        if has_new_banha:
            sub_area = f"{sub_area} / بنها الجديدة" if sub_area else "بنها الجديدة"
        return {
            "area_mentioned": area_label,
            "sub_area": sub_area,
            "is_new_banha": has_new_banha and not detected_sub_areas,
            "matches_target_area": True,
        }

    # التحقق من محافظات أو مدن أخرى إن غير المستخدم المنطقة
    if norm_target and norm_target in norm:
        return {
            "area_mentioned": target_area,
            "sub_area": None,
            "is_new_banha": False,
            "matches_target_area": True,
        }

    return {
        "area_mentioned": None,
        "sub_area": sub_area,
        "is_new_banha": False,
        "matches_target_area": False,
    }


def is_rental_listing(text: str) -> Tuple[bool, str]:
    """فحص سياق المنشور للتأكد من أنه إعلان عرض شقة للإيجار وليس طلب بحث أو بيع فقط.

    يُعيد: (هل_هو_إعلان_إيجار: bool, سبب_القبول_أو_الرفض: str)
    """
    if not text or len(text.strip()) < 8:
        return False, "نص قصير جدًا لا يحتوي على تفاصيل إعلان"

    norm = normalize_arabic(text)
    lower_raw = text.lower()

    if any(
        eng_meta in lower_raw
        for eng_meta in ["about this group", "view discussions", "recent listing activity"]
    ):
        return False, "وصف تعريفي للمجموعة وليس منشور شقة"

    # 1. استبعاد السياقات غير العقارية (نقل عفش، تنظيف، أدعية، وصف الجروب العام فقط)
    for phrase in NON_REAL_ESTATE_NORM:
        if phrase in norm:
            if normalize_arabic("شقة للايجار") not in norm:
                return False, f"سياق غير عقاري ({phrase})"

    if any(
        meta_phrase in norm
        for meta_phrase in [
            normalize_arabic("الغرض من المجموعة مساعدة"),
            normalize_arabic("مرحبا بكم في المجموعة الرسمية"),
            normalize_arabic("للبيع والشراء للاراضي وسوق للعقارات"),
            normalize_arabic("اعثر على افضل شقق للايجار"),
            normalize_arabic("يقدم دوبيزل مصر"),
            normalize_arabic("قارن بالصور والاسعار بين"),
            normalize_arabic("شقق محلات اراضي مصانع"),
        ]
    ):
        return False, "وصف عام لمجموعة أو صفحة فهرس وليس منشور شقة محدد"

    # 2. استبعاد منشورات «مطلوب شقة» (شخص يبحث عن شقة وليس شقة معروضة للإيجار)
    if re.search(
        r"\b(مطلوب|محتاج|محتاجه|عايز|عايزه|عاوز|عاوزه|ابحث عن|بندور علي)\s+(?:ضروري\s+|عاجل\s+)?(شقه|شقق|سكن|استوديو|غرفه)\b",
        norm,
    ):
        return False, "طلب بحث عن شقة (مطلوب شقة) وليس عرض إيجار"

    # 3. التحقق من وجود كلمة تدل على العقار (شقة، شقق، شقتين، ستوديو، رووف، دور...)
    has_property = any(
        re.search(rf"\b{re.escape(term)}\b", norm) or term in norm
        for term in PROPERTY_TERMS_NORM + [normalize_arabic("شقتين"), normalize_arabic("اوضتين")]
    )
    if not has_property:
        return False, "لا يحتوي على مفردات عقار سكني (شقة/شقق/ستوديو)"

    # 4. التحقق من وجود سياق إيجار واضح
    has_rental = any(term in norm for term in RENTAL_TERMS_NORM)

    # فحص حالات البيع فقط (تمليك/للبيع دون أي إشارة للإيجار في نفس المنشور)
    has_sale_word = (
        normalize_arabic("للبيع") in norm or normalize_arabic("تمليك") in norm
    )
    if has_sale_word and not (
        normalize_arabic("للايجار") in norm or normalize_arabic("ايجار") in norm
    ):
        return False, "إعلان بيع/تمليك فقط وليس إيجارًا"

    # إذا كان عنوان الجروب يحتوي على "للايجار" ولكن نص المنشور نفسه يقول "شقة للبيع" أو "عقار للبيع" فقط
    if re.search(r"\b(شقه للبيع|شقه لقطه للبيع|شقه مميزه للبيع|شقه للتمليك|منزل لقطه للبيع|للبيع عماره|عقار تجاري كامل للبيع)\b", norm):
        if normalize_arabic("او الايجار") not in norm and normalize_arabic("او للايجار") not in norm:
            return False, "إعلان بيع داخل جروب عام"

    for sale_only in SALE_ONLY_NORM:
        if sale_only in norm and normalize_arabic("ايجار") not in norm:
            return False, "إعلان تمليك/تقسيط فقط"

    if not has_rental:
        has_rooms_and_price = bool(
            re.search(r"\b(\d+|غرفتين|غرفتان|ثلاث|اوضتين)\s*(غرف|غرفه|وصاله)\b", norm)
            and re.search(r"\b\d{3,5}\s*(جنيه|ج|شهريا)\b", norm)
        )
        if not has_rooms_and_price:
            return False, "يذكر كلمة شقة دون سياق إيجار"

    return True, "إعلان إيجار عقاري مطابق للسياق"
