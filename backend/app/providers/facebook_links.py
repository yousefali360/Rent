"""المصدر الأول: مولّد روابط البحث المخصصة في Facebook للفترة الزمنية والمنطقة والكلمات المفتاحية.

يلتزم بالقيود الصارمة:
- عدم افتراض وجود API رسمي يقرأ جميع منشورات الجروبات العامة.
- عدم طلب كلمة مرور Facebook أو تخزين الكوكيز.
- توليد روابط بحث مباشرة تفتح داخل Facebook في متصفح المستخدم مع تفعيل فلتر «الأحدث» (Recent Posts)
  وفلتر الجروبات العامة وأحياء المنطقة.
"""

import base64
import json
from datetime import datetime
from typing import List
from urllib.parse import quote

from backend.app.models import AREAS_DIRECTORY, FacebookDirectLink
from backend.app.services.arabic_nlp import build_combined_search_queries


def _encode_fb_recent_filter(start_dt: datetime, end_dt: datetime) -> str:
    """بناء معامل الفلترة بترميز Base64 الخاص بفيسبوك لترتيب المنشورات من الأحدث إلى الأقدم."""
    # فيسبوك يدعم فلتر recent_posts: {"rp_chrono_sort:0": "{\"name\":\"chronosort\",\"args\":\"\"}"}
    filter_obj = {
        "rp_chrono_sort:0": json.dumps({"name": "chronosort", "args": ""}),
    }
    raw_json = json.dumps(filter_obj, separators=(",", ":"))
    return base64.b64encode(raw_json.encode("utf-8")).decode("ascii")


def generate_facebook_search_links(
    area: str,
    keywords: List[str],
    window_start: datetime,
    window_end: datetime,
    include_new_banha: bool = True,
) -> List[FacebookDirectLink]:
    """توليد روابط بحث فيسبوك المباشرة والمصنفة حسب الكلمات المفتاحية والمنطقة والفترة الزمنية."""
    clean_area = area.strip() or "بنها"
    recent_filter_b64 = _encode_fb_recent_filter(window_start, window_end)
    links: List[FacebookDirectLink] = []

    # 1. روابط المنشورات الحديثة (مرتبة زمنيًا من الأحدث للأقدم عبر فلتر فيسبوك)
    combined_queries = build_combined_search_queries(
        area=clean_area,
        keywords=keywords,
        include_new_banha=include_new_banha,
    )

    for idx, query_str in enumerate(combined_queries[:8]):
        encoded_q = quote(query_str)
        recent_url = (
            f"https://www.facebook.com/search/posts?q={encoded_q}"
            f"&filters={quote(recent_filter_b64)}"
        )
        links.append(
            FacebookDirectLink(
                title=f"منشورات حديثة: {query_str}",
                query_text=query_str,
                url=recent_url,
                category="recent_posts",
                description=(
                    f"بحث مباشر في منشورات فيسبوك العامة عن «{query_str}» مرتبة حسب الأحدث "
                    f"(للفترة من {window_start.strftime('%Y-%m-%d %H:%M')} إلى {window_end.strftime('%Y-%m-%d %H:%M')})."
                ),
            )
        )

    # 2. روابط البحث في الجروبات العامة الخاصة بالمنطقة
    group_queries = [
        f"شقق للايجار في {clean_area}",
        f"عقارات {clean_area} للايجار",
        f"شقق {clean_area} من المالك",
        f"سكن طلاب وعائلات {clean_area}",
    ]
    for gq in group_queries:
        encoded_gq = quote(gq)
        group_search_url = f"https://www.facebook.com/search/groups?q={encoded_gq}"
        links.append(
            FacebookDirectLink(
                title=f"جروبات عامة: {gq}",
                query_text=gq,
                url=group_search_url,
                category="public_groups",
                description=f"استكشاف الجروبات العامة المفتوحة الخاصة بـ «{gq}» لتصفح أحدث منشوراتها.",
            )
        )

    # 3. روابط بحث مخصصة للأحياء الفرعية داخل المنطقة (مثل أحياء بنها)
    area_meta = AREAS_DIRECTORY.get(clean_area)
    if area_meta:
        sub_areas = area_meta.get("sub_areas", [])
        for sub in sub_areas[:8]:
            if sub == "بنها الجديدة" and not include_new_banha:
                continue
            sub_q = f"شقة للإيجار {clean_area} {sub}" if sub != "بنها الجديدة" else "شقة للإيجار بنها الجديدة"
            encoded_sq = quote(sub_q)
            sub_url = (
                f"https://www.facebook.com/search/posts?q={encoded_sq}"
                f"&filters={quote(recent_filter_b64)}"
            )
            links.append(
                FacebookDirectLink(
                    title=f"حي / منطقة: {sub}",
                    query_text=sub_q,
                    url=sub_url,
                    category="sub_area",
                    description=f"بحث مخصص عن شقق الإيجار في منطقة «{sub}» مرتب حسب أحدث المنشورات.",
                )
            )

    return links
