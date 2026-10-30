"""وحدة الاستيراد المصرح به الذي يبدأه المستخدم بنفسه (User-Initiated Authorized Import).

تتيح للمستخدم نسخ نصوص أو روابط المنشورات العامة التي يشاهدها في متصفحه داخل الجروبات العامة
أو نتائج بحث فيسبوك ولصقها في التطبيق ليقوم النظام بـ:
- تطبيع النص العربي وفحص سياق الإيجار.
- التحقق من تاريخ النشر الأصلي بتوقيت مصر (Africa/Cairo) ومقارنته بالفترة الزمنية المحددة.
- استخراج السعر، الغرف، الحمامات، المساحة، حالة الفرش، المنطقة الفرعية، ووسيلة التواصل.
- التحقق من رابط المنشور الأصلي واكتشاف التكرارات.
"""

from typing import List
from backend.app.models import UserImportItem
from backend.app.providers.base import RawCandidatePost
from backend.app.services.time_filter import now_cairo


def convert_user_imports_to_candidates(
    items: List[UserImportItem],
) -> List[RawCandidatePost]:
    """تحويل المدخلات التي استوردها المستخدم يدويًا إلى مرشحات جاهزة للمعالجة والفلترة."""
    collected_iso = now_cairo().isoformat()
    candidates: List[RawCandidatePost] = []

    for item in items:
        text_clean = item.text.strip()
        if not text_clean:
            continue
        candidates.append(
            RawCandidatePost(
                raw_text=text_clean,
                url=item.post_url.strip() if item.post_url else None,
                title=item.group_or_page_name.strip() if item.group_or_page_name else None,
                group_or_page_name=(
                    item.group_or_page_name.strip() if item.group_or_page_name else None
                ),
                group_or_page_url=(
                    item.group_or_page_url.strip() if item.group_or_page_url else None
                ),
                published_at_hint=(
                    item.published_at_text.strip() if item.published_at_text else None
                ),
                source_name="استيراد مصرح به (بواسطة المستخدم)",
                collected_at=collected_iso,
            )
        )

    return candidates
