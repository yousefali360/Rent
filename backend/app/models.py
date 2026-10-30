"""نماذج البيانات (Pydantic Models) الخاصة بالمنشورات وطلبات البحث والفلاتر."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# الكلمات المفتاحية الافتراضية المطلوبة في المواصفات
DEFAULT_KEYWORDS: List[str] = [
    "شقة",
    "شقه",
    "شقق",
    "للايجار",
    "للإيجار",
    "إيجار",
    "شقة للإيجار",
    "شقة للايجار",
    "شقق للايجار في بنها",
    "شقة للإيجار في بنها",
    "شقة مفروشة بنها",
    "شقة من المالك بنها",
]


# قاموس المناطق والمحافظات القابل للتوسعة مستقبلاً
AREAS_DIRECTORY = {
    "بنها": {
        "name": "بنها",
        "governorate": "القليوبية",
        "aliases": ["بنها", "مدينة بنها", "بندر بنها"],
        "distinct_nearby": ["بنها الجديدة"],
        "sub_areas": [
            "الفلل",
            "كفر الجزار",
            "أتريب",
            "المنشية",
            "الأهرام",
            "الحرس الوطني",
            "وسط البلد",
            "كفر السرايا",
            "الكورنيش",
            "منشية النور",
            "عزبة الزراعة",
            "الشدية",
            "بنها الجديدة",
            "حي الزهور",
            "الرملة",
            "بطا",
            "ميت راضي",
        ],
    },
    "طوخ": {
        "name": "طوخ",
        "governorate": "القليوبية",
        "aliases": ["طوخ", "مدينة طوخ", "مركز طوخ"],
        "distinct_nearby": [],
        "sub_areas": ["وسط البلد", "مشتهر", "برشوم", "كفر منصور"],
    },
    "قليوب": {
        "name": "قليوب",
        "governorate": "القليوبية",
        "aliases": ["قليوب", "قليوب المحطة", "قليوب البلد"],
        "distinct_nearby": [],
        "sub_areas": ["قليوب المحطة", "قليوب البلد", "بطن الجبل"],
    },
    "شبرا الخيمة": {
        "name": "شبرا الخيمة",
        "governorate": "القليوبية",
        "aliases": ["شبرا الخيمة", "شبرا الخيمه"],
        "distinct_nearby": [],
        "sub_areas": ["بهتيم", "مسطرد", "الشارع الجديد", "المؤسسة", "كلية الزراعة"],
    },
    "العبور": {
        "name": "العبور",
        "governorate": "القليوبية",
        "aliases": ["العبور", "مدينة العبور"],
        "distinct_nearby": ["العبور الجديدة"],
        "sub_areas": ["الحي الأول", "الحي الثاني", "الحي التاسع", "الشباب", "المستقبل"],
    },
}


TimePreset = Literal["24h", "2d", "4d", "custom"]
DateVerificationStatus = Literal["verified_in_range", "verified_out_of_range", "unverified"]
ExtractionStatus = Literal["complete", "partial", "minimal"]
UrlVerificationType = Literal["post", "group_or_page", "search_link", "unverified"]


class FacebookDirectLink(BaseModel):
    """رابط بحث مخصص داخل فيسبوك مع وصفه ونوعه."""

    title: str
    query_text: str
    url: str
    category: Literal["recent_posts", "public_groups", "general_posts", "sub_area"]
    description: str


class ProviderExecutionReport(BaseModel):
    """تقرير حالة تنفيذ كل مصدر بحث بشفافية تامة."""

    provider_id: str
    provider_name: str
    status: Literal["success", "partial", "skipped_no_credentials", "error"]
    fetched_count: int = 0
    accepted_count: int = 0
    excluded_old_count: int = 0
    excluded_irrelevant_count: int = 0
    unverified_date_count: int = 0
    message: str = ""
    error_detail: Optional[str] = None


class RentalPost(BaseModel):
    """النموذج الكامل لبيانات منشور شقة للإيجار وفق البند رقم 6 من المواصفات."""

    id: str = Field(..., description="معرف داخلي فريد")
    original_text: str = Field(..., description="نص المنشور أو المقتطف المتاح دون تعديل")
    normalized_text: str = Field(default="", description="النص بعد التطبيع للمقارنة")
    post_url: Optional[str] = Field(default=None, description="رابط المنشور الأصلي المتحقَّق منه")
    raw_discovered_url: Optional[str] = Field(default=None, description="الرابط الخام المكتشف من المصدر")
    url_verified: bool = Field(default=False, description="هل الرابط يعود لمنشور فعلي أم مجرد جروب/صفحة")
    url_type: UrlVerificationType = Field(default="unverified")
    group_or_page_name: Optional[str] = Field(default=None, description="اسم الجروب أو الصفحة إن توفر")
    group_or_page_url: Optional[str] = Field(default=None, description="رابط الجروب أو الصفحة إن توفر")
    published_at: Optional[str] = Field(
        default=None, description="تاريخ ووقت النشر الأصليان بتوقيت Africa/Cairo"
    )
    published_at_raw: Optional[str] = Field(
        default=None, description="النص الأصلي للتاريخ كما ورد في المصدر"
    )
    collected_at: str = Field(..., description="تاريخ ووقت جمع النتيجة بتوقيت Africa/Cairo")
    area_mentioned: Optional[str] = Field(default=None, description="المنطقة المذكورة في المنشور")
    sub_area: Optional[str] = Field(default=None, description="المنطقة الفرعية إن ذُكرت")
    is_new_banha: bool = Field(
        default=False, description="علامة توضح ما إذا كان المنشور يخص بنها الجديدة تحديدًا"
    )
    price_egp: Optional[int] = Field(default=None, description="السعر الشهري بالجنيه المصري إذا ذُكر")
    rooms_count: Optional[int] = Field(default=None, description="عدد الغرف إذا ذُكر")
    bathrooms_count: Optional[int] = Field(default=None, description="عدد الحمامات إذا ذُكر")
    area_sqm: Optional[int] = Field(default=None, description="المساحة بالمتر المربع إذا ذُكرت")
    furnishing_status: Optional[str] = Field(default=None, description="حالة الفرش إذا ذُكرت")
    contact_info: Optional[str] = Field(
        default=None, description="طريقة التواصل المعلنة في المنشور إذا كانت متاحة"
    )
    source_name: str = Field(..., description="مصدر البيانات")
    date_verification_status: DateVerificationStatus = Field(
        ..., description="حالة التحقق من تاريخ النشر"
    )
    extraction_status: ExtractionStatus = Field(
        default="minimal", description="حالة استخراج الحقول"
    )
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0, description="درجة الثقة")
    duplicate_of_id: Optional[str] = Field(default=None, description="معرف المنشور الأصلي إن كان مكررًا")
    possible_duplicate_of_id: Optional[str] = Field(
        default=None, description="معرف منشور قد يكون مشابهًا عند وجود شك"
    )
    similarity_score: Optional[float] = Field(default=None, description="نسبة التشابه مع منشور آخر")


class SearchRequest(BaseModel):
    """طلب بدء البحث بالفلاتر الزمنية والجغرافية والكلمات المفتاحية."""

    area: str = Field(default="بنها", description="المنطقة المستهدفة")
    governorate: str = Field(default="القليوبية", description="المحافظة")
    include_new_banha: bool = Field(
        default=True,
        description="تضمين بنها الجديدة في البحث مع تمييزها بوضوح عن بنها البلد/المدينة",
    )
    keywords: List[str] = Field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    time_preset: TimePreset = Field(default="4d", description="الفترة الزمنية المختارة")
    custom_start: Optional[str] = Field(
        default=None, description="بداية الفترة المخصصة بصيغة ISO (Africa/Cairo)"
    )
    custom_end: Optional[str] = Field(
        default=None, description="نهاية الفترة المخصصة بصيغة ISO (Africa/Cairo)"
    )
    providers: List[str] = Field(
        default_factory=lambda: ["facebook_links", "public_web", "google_cse", "serper"],
        description="مصادر البحث المطلوب تشغيلها",
    )


class UserImportItem(BaseModel):
    """عنصر واحد يقوم المستخدم باستيراده يدويًا من منشور عام شاهده."""

    text: str = Field(..., min_length=5, description="نص المنشور كما ظهر للمستخدم")
    post_url: Optional[str] = Field(default=None, description="رابط المنشور الأصلي إن توفر")
    group_or_page_name: Optional[str] = Field(default=None, description="اسم الجروب أو الصفحة")
    group_or_page_url: Optional[str] = Field(default=None, description="رابط الجروب أو الصفحة")
    published_at_text: Optional[str] = Field(
        default=None,
        description="تاريخ النشر كما ظهر في المنشور (مثل: منذ 3 ساعات، أمس الساعة 8 م، أو 2026-10-09T14:00)",
    )


class UserImportRequest(BaseModel):
    """طلب استيراد منشور أو عدة منشورات عامة بدأه المستخدم بنفسه."""

    area: str = Field(default="بنها")
    time_preset: TimePreset = Field(default="4d")
    custom_start: Optional[str] = None
    custom_end: Optional[str] = None
    items: List[UserImportItem]


class SearchResponse(BaseModel):
    """استجابة عملية البحث شاملة الإحصائيات والروابط والتقارير والنتائج."""

    job_id: str
    status: Literal["completed", "running", "failed"]
    area: str
    governorate: str
    timezone: str = "Africa/Cairo"
    period_start: str
    period_end: str
    time_preset: TimePreset
    total_fetched: int
    total_accepted_verified: int
    total_unverified_date: int
    total_excluded_old: int
    total_excluded_irrelevant: int
    total_excluded_exact_duplicates: int
    facebook_direct_links: List[FacebookDirectLink]
    provider_reports: List[ProviderExecutionReport]
    verified_results: List[RentalPost]
    unverified_date_results: List[RentalPost]
    disclaimer: str = (
        "النتائج المعروضة تمثل المحتوى العام الذي أمكن الوصول إليه بشكل مشروع من المصادر المتاحة، "
        "وليست فهرسًا كاملًا لجميع منشورات فيسبوك. يتم التحقق من تاريخ النشر الأصلي بتوقيت مصر (Africa/Cairo)، "
        "وتُفصل المنشورات التي تعذّر التأكد من تاريخ نشرها في قسم مستقل."
    )
