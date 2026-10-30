"""المصدر الثاني: محركات البحث العامة المفهرسة وجالب المنشورات المباشرة (Pluggable Public Search Engine Providers).

يدعم استبدال وإضافة مزودي البحث دون إعادة كتابة التطبيق:
1. PublicWebIndexProvider (مطور):
   - يبحث في الفهرس العام (Yahoo Search + DuckDuckGo + منصات العقارات المصرية العامة) عن:
     أ) روابط المنشورات المباشرة داخل جروبات فيسبوك العامة (`/groups/.../permalink/...` و `/groups/.../posts/...`).
     ب) أحدث المنشورات المفهرسة خلال الساعات والأيام الأخيرة (`btf=d` / `btf=w`).
     ج) إعلانات الإيجار المباشرة في بنها على المنصات العقارية العامة (مثل Dubizzle و Aqarmap).
   - يجلب بيانات OpenGraph العامة (`og:title`, `og:description`, `og:url`) لروابط منشورات فيسبوك المباشرة
     للحصول على النص الكامل للمنشور واسم الجروب الفعلي والرابط المباشر الدقيق.
2. Google Custom Search JSON API (`GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_CX`)
3. Serper.dev Google Search API (`SERPER_API_KEY`)
"""

import asyncio
import math
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.app.config import settings
from backend.app.models import ProviderExecutionReport
from backend.app.providers.base import BaseSearchProvider, RawCandidatePost
from backend.app.services.time_filter import now_cairo


# أشهر الجروبات العامة النشطة لشقق وعقارات بنها على فيسبوك لاستخراج روابط البوستات المباشرة منها
KNOWN_BANHA_PUBLIC_GROUP_IDS = [
    ("341365830770481", "شقق بنها للتمليك و للايجار"),
    ("1260358428598103", "شقق مفروشة بنها للإيجار"),
    ("567807180770634", "جروب عقارات مدينة بنها"),
    ("1498767735039592", "شقق بنها للايجار"),
    ("863196182366224", "عقارات بنها ايجار وتمليك"),
    ("781299894768923", "كفر الجزار - بنها"),
]


def _sanitize_error_message(err: Exception) -> str:
    """تنظيف رسائل الخطأ لضمان عدم تسريب أي مفاتيح API أو روابط سرية."""
    msg = str(err)
    msg = re.sub(r"key=[A-Za-z0-9_\-]+", "key=***REDACTED***", msg)
    msg = re.sub(r"cx=[A-Za-z0-9_:\-]+", "cx=***REDACTED***", msg)
    return msg[:240]


def _compute_days_restrict(window_start: datetime, window_end: datetime) -> int:
    """حساب عدد الأيام المطلوبة لفلتر التاريخ في محركات البحث العامة."""
    delta_seconds = max(3600.0, (window_end - window_start).total_seconds())
    return max(1, math.ceil(delta_seconds / 86400.0))


def build_targeted_facebook_web_queries(
    area: str,
    keywords: List[str],
    include_new_banha: bool = True,
) -> List[str]:
    """إنشاء استعلامات عربية تستهدف روابط Facebook العامة (المنشورات والجروبات والصفحات)."""
    clean_area = area.strip() or "بنها"
    queries = [
        f'site:facebook.com ("شقة" OR "شقه" OR "شقق") ("للإيجار" OR "للايجار" OR "إيجار") "{clean_area}"',
        f'site:facebook.com/groups ("شقة" OR "شقه" OR "شقق") ("للايجار" OR "للإيجار") "{clean_area}"',
        f'site:facebook.com ("شقة مفروشة" OR "شقة من المالك" OR "قانون جديد") "{clean_area}"',
    ]
    if clean_area == "بنها" and include_new_banha:
        queries.append(
            'site:facebook.com ("شقة" OR "شقق") ("للايجار" OR "للإيجار") ("الفلل" OR "كفر الجزار" OR "أتريب" OR "بنها الجديدة")'
        )
    return queries


def _extract_group_or_page_title(raw_title: Optional[str]) -> Optional[str]:
    """استخراج اسم الجروب أو الصفحة من عنوان نتيجة البحث إن توفر."""
    if not raw_title:
        return None
    cleaned = re.sub(r"^Facebook\s+https?://[^\s]+\s*(?:›\s*[^\s]+\s*)*", "", raw_title, flags=re.IGNORECASE)
    cleaned = re.sub(r"^دوبيزل\s+https?://[^\s]+\s*(?:›\s*[^\s]+\s*)*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[-|•]\s*Facebook.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[-|•]\s*فيسبوك.*$", "", cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def _split_leading_date_from_snippet(snippet: str) -> Tuple[Optional[str], str]:
    """فصل بادئة التاريخ في مقتطفات البحث (مثل '6 hours ago · ' أو 'May 23, 2026 · ') عن نص المنشور."""
    if not snippet:
        return None, ""

    # فحص وجود فاصل ' · ' في بداية المقتطف
    if " · " in snippet:
        first_chunk, rest = snippet.split(" · ", 1)
        if len(first_chunk.strip()) <= 28 and re.search(
            r"\b(ago|hours?|days?|mins?|minutes?|yesterday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|منذ|أمس|امس|ساعة|ساعات|يوم|أيام)\b",
            first_chunk.strip(),
            re.IGNORECASE,
        ):
            return first_chunk.strip(), rest.strip()

    # فحص وجود "منذ X ساعات/أيام" داخل مقتطفات دوبيزل/فيسبوك
    m_ar_rel = re.search(
        r"\b(منذ\s+\d+\s*(?:ساعات|ساعة|ساعه|أيام|ايام|يوم|دقائق|دقيقة)|منذ\s+(?:ساعة|ساعتين|يوم|يومين))\b",
        snippet,
    )
    if m_ar_rel:
        return m_ar_rel.group(1), snippet

    # فحص وجود '22h · Public' في نهاية المقتطف
    m_fb_tail = re.search(r"\b(\d+)\s*([hd])\s*·\s*Public\b", snippet, re.IGNORECASE)
    if m_fb_tail:
        num = m_fb_tail.group(1)
        unit = "hours ago" if m_fb_tail.group(2).lower() == "h" else "days ago"
        cleaned_body = snippet[: m_fb_tail.start()].strip()
        return f"{num} {unit}", cleaned_body

    return None, snippet.strip()


def _build_in_group_direct_post_url(group_url: str, post_text: str) -> str:
    """بناء رابط يفتح المنشور المحدد مباشرة داخل الجروب العام باستخدام عبارته المميزة."""
    base_group = group_url.rstrip("/")
    # استخراج أول 7 كلمات عربية/رقمية مميزة من نص المنشور للبحث عنها مباشرة داخل الجروب
    words = re.findall(r"[\u0600-\u06FF0-9]{2,}", post_text)
    stop_words = {"في", "من", "على", "علي", "الى", "إلى", "عن", "او", "أو", "كل", "بها"}
    meaningful = [w for w in words if w not in stop_words][:7]
    query_phrase = " ".join(meaningful) if meaningful else "شقة للايجار"
    return f"{base_group}/search/?q={quote(query_phrase)}"


class GoogleCSEProvider(BaseSearchProvider):
    """مزود بحث Google Custom Search JSON API الرسمي."""

    provider_id = "google_cse"
    provider_name = "محرك بحث Google Custom Search API"

    async def search(
        self,
        area: str,
        keywords: List[str],
        window_start: datetime,
        window_end: datetime,
        include_new_banha: bool = True,
    ) -> Tuple[List[RawCandidatePost], ProviderExecutionReport]:
        if not settings.has_google_cse:
            return [], ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="skipped_no_credentials",
                message=(
                    "اختياري (غير مفعّل لعدم إضافة GOOGLE_CSE_API_KEY في .env) — يعمل الجالب المباشر بدونه تلقائيًا."
                ),
            )

        days = _compute_days_restrict(window_start, window_end)
        queries = build_targeted_facebook_web_queries(area, keywords, include_new_banha)
        candidates: List[RawCandidatePost] = []
        collected_iso = now_cairo().isoformat()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for q in queries[:3]:
                    resp = await client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params={
                            "key": settings.GOOGLE_CSE_API_KEY,
                            "cx": settings.GOOGLE_CSE_CX,
                            "q": q,
                            "dateRestrict": f"d{days}",
                            "hl": "ar",
                            "gl": "eg",
                            "num": 10,
                        },
                    )
                    if resp.status_code != 200:
                        return candidates, ProviderExecutionReport(
                            provider_id=self.provider_id,
                            provider_name=self.provider_name,
                            status="error" if not candidates else "partial",
                            fetched_count=len(candidates),
                            message=f"أعاد مزود Google CSE رمز الحالة {resp.status_code}.",
                            error_detail=f"HTTP {resp.status_code}",
                        )

                    data = resp.json()
                    items = data.get("items", [])
                    for item in items:
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        link = item.get("link", "")
                        pagemap = item.get("pagemap", {})
                        metatags = (pagemap.get("metatags") or [{}])[0]

                        pub_hint = (
                            metatags.get("article:published_time")
                            or metatags.get("og:updated_time")
                        )
                        date_prefix, cleaned_snippet = _split_leading_date_from_snippet(snippet)
                        if not pub_hint and date_prefix:
                            pub_hint = date_prefix

                        candidates.append(
                            RawCandidatePost(
                                raw_text=cleaned_snippet or title,
                                url=link,
                                title=title,
                                group_or_page_name=_extract_group_or_page_title(title),
                                published_at_hint=pub_hint,
                                source_name=self.provider_name,
                                collected_at=collected_iso,
                            )
                        )

            return candidates, ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="success",
                fetched_count=len(candidates),
                message=f"تم جلب {len(candidates)} نتيجة مفهرسة من Google Custom Search.",
            )
        except Exception as exc:
            return candidates, ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="error",
                fetched_count=len(candidates),
                message="تعذر الاتصال بـ Google Custom Search API.",
                error_detail=_sanitize_error_message(exc),
            )


class SerperProvider(BaseSearchProvider):
    """مزود بحث Serper.dev (واجهة Google Search السريعة) القابل للاستبدال."""

    provider_id = "serper"
    provider_name = "محرك بحث Serper (Google Search API)"

    async def search(
        self,
        area: str,
        keywords: List[str],
        window_start: datetime,
        window_end: datetime,
        include_new_banha: bool = True,
    ) -> Tuple[List[RawCandidatePost], ProviderExecutionReport]:
        if not settings.has_serper:
            return [], ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="skipped_no_credentials",
                message=(
                    "اختياري (غير مفعّل لعدم إضافة SERPER_API_KEY في .env) — يعمل الجالب المباشر بدونه تلقائيًا."
                ),
            )

        days = _compute_days_restrict(window_start, window_end)
        queries = build_targeted_facebook_web_queries(area, keywords, include_new_banha)
        candidates: List[RawCandidatePost] = []
        collected_iso = now_cairo().isoformat()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for q in queries[:3]:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        headers={
                            "X-API-KEY": settings.SERPER_API_KEY,
                            "Content-Type": "application/json",
                        },
                        json={
                            "q": q,
                            "gl": "eg",
                            "hl": "ar",
                            "tbs": f"qdr:d{days}",
                            "num": 15,
                        },
                    )
                    if resp.status_code != 200:
                        return candidates, ProviderExecutionReport(
                            provider_id=self.provider_id,
                            provider_name=self.provider_name,
                            status="error" if not candidates else "partial",
                            fetched_count=len(candidates),
                            message=f"أعاد مزود Serper رمز الحالة {resp.status_code}.",
                            error_detail=f"HTTP {resp.status_code}",
                        )

                    data = resp.json()
                    for item in data.get("organic", []):
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        link = item.get("link", "")
                        date_str = item.get("date")
                        date_prefix, cleaned_snippet = _split_leading_date_from_snippet(snippet)

                        candidates.append(
                            RawCandidatePost(
                                raw_text=cleaned_snippet or title,
                                url=link,
                                title=title,
                                group_or_page_name=_extract_group_or_page_title(title),
                                published_at_hint=date_str or date_prefix,
                                source_name=self.provider_name,
                                collected_at=collected_iso,
                            )
                        )

            return candidates, ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="success",
                fetched_count=len(candidates),
                message=f"تم جلب {len(candidates)} نتيجة مفهرسة من Serper API.",
            )
        except Exception as exc:
            return candidates, ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="error",
                fetched_count=len(candidates),
                message="تعذر الاتصال بـ Serper API.",
                error_detail=_sanitize_error_message(exc),
            )


class PublicWebIndexProvider(BaseSearchProvider):
    """جالب المنشورات المباشرة من الفهرس العام وجروبات فيسبوك العامة ومنصات العقارات المصرية."""

    provider_id = "public_web"
    provider_name = "جالب منشورات فيسبوك العامة والمنصات العقارية"

    @staticmethod
    def _unwrap_yahoo_url(href: str) -> str:
        if not href:
            return ""
        m = re.search(r"/RU=([^/]+)/", href)
        if m:
            return unquote(m.group(1))
        return href

    @staticmethod
    async def _enrich_facebook_permalink_opengraph(
        client: httpx.AsyncClient, url: str
    ) -> Dict[str, Optional[str]]:
        """جلب بيانات OpenGraph العامة لمنشور فيسبوك مباشر للحصول على النص الكامل واسم الجروب والرابط الرسمي."""
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                    "Accept-Language": "ar-EG,ar;q=0.9",
                },
                timeout=6.0,
            )
            if resp.status_code != 200:
                return {}
            soup = BeautifulSoup(resp.text, "html.parser")
            og_desc = soup.find("meta", property="og:description")
            og_title = soup.find("meta", property="og:title")
            og_url = soup.find("meta", property="og:url")

            desc_text = og_desc.get("content", "").strip() if og_desc else None
            title_text = og_title.get("content", "").strip() if og_title else None
            canonical_url = og_url.get("content", "").strip() if og_url else None

            group_name = None
            if title_text and "|" in title_text:
                first_part = title_text.split("|")[0].strip()
                if first_part and first_part.lower() != "facebook":
                    group_name = first_part

            return {
                "description": desc_text,
                "group_name": group_name,
                "canonical_url": canonical_url,
            }
        except Exception:
            return {}

    async def _fetch_yahoo_query(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        query: str,
        btf: Optional[str] = None,
    ) -> List[Dict[str, Optional[str]]]:
        """تنفيذ استعلام واحد على فهرس Yahoo العام مع التحكم في التزامن لتجنب الحجب."""
        params: Dict[str, str] = {"p": query}
        if btf:
            params["btf"] = btf
        async with sem:
            await asyncio.sleep(0.12)
            try:
                resp = await client.get(
                    "https://search.yahoo.com/search", params=params, timeout=12.0
                )
                if resp.status_code != 200:
                    return []
                soup = BeautifulSoup(resp.text, "html.parser")
                items: List[Dict[str, Optional[str]]] = []
                for el in soup.select("div.algo"):
                    a = el.select_one("h3.title a") or el.select_one("a")
                    comp = el.select_one(".compText")
                    if not a:
                        continue
                    real_url = self._unwrap_yahoo_url(str(a.get("href", "")))
                    title = a.get_text(" ", strip=True)
                    snippet = comp.get_text(" ", strip=True) if comp else ""
                    if not real_url or not snippet:
                        continue
                    items.append(
                        {
                            "url": real_url,
                            "title": title,
                            "snippet": snippet,
                        }
                    )
                return items
            except Exception:
                return []

    async def _fetch_aqarmap_banha_listings(
        self, client: httpx.AsyncClient, area: str
    ) -> List[RawCandidatePost]:
        """جلب إعلانات شقق الإيجار المباشرة في بنها من منصة عقارماب العامة مع روابطها المباشرة."""
        if area.strip() not in ("بنها", "بنها الجديدة"):
            return []
        collected_iso = now_cairo().isoformat()
        urls = [
            "https://aqarmap.com.eg/ar/for-rent/apartment/qalyubia/banha-city/",
            "https://aqarmap.com.eg/ar/for-rent/furnished-apartment/qalyubia/banha-city/",
        ]
        results: List[RawCandidatePost] = []
        seen_hrefs: Set[str] = set()

        for page_url in urls:
            try:
                resp = await client.get(page_url, timeout=10.0)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = str(a_tag["href"])
                    if "/ar/listing/" not in href or "for-rent" not in href:
                        continue
                    text = a_tag.get_text(" ", strip=True)
                    if not text or len(text) < 18 or "شقق للإيجار بنها" in text:
                        continue
                    full_url = (
                        href
                        if href.startswith("http")
                        else f"https://aqarmap.com.eg{href}"
                    )
                    if full_url in seen_hrefs:
                        continue
                    seen_hrefs.add(full_url)

                    enriched_text = (
                        text
                        if "للايجار" in text or "للإيجار" in text
                        else f"شقة للإيجار في بنها — {text}"
                    )
                    results.append(
                        RawCandidatePost(
                            raw_text=enriched_text,
                            url=full_url,
                            title="إعلان مباشر — عقارماب بنها",
                            group_or_page_name="منصة عقارماب (بنها)",
                            group_or_page_url=page_url,
                            published_at_hint=None,
                            source_name="منصة عقارماب (رابط إعلان مباشر)",
                            collected_at=collected_iso,
                        )
                    )
            except Exception:
                continue
        return results

    async def search(
        self,
        area: str,
        keywords: List[str],
        window_start: datetime,
        window_end: datetime,
        include_new_banha: bool = True,
    ) -> Tuple[List[RawCandidatePost], ProviderExecutionReport]:
        if not settings.ENABLE_PUBLIC_WEB_PROVIDER:
            return [], ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="skipped_no_credentials",
                message="تم تعطيل مزود الويب العام من الإعدادات.",
            )

        clean_area = area.strip() or "بنها"
        days = _compute_days_restrict(window_start, window_end)
        btf_param = "d" if days <= 1 else "w"
        collected_iso = now_cairo().isoformat()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        query_specs: List[Tuple[str, Optional[str]]] = [
            (f"site:facebook.com/groups شقة للايجار {clean_area}", btf_param),
            (f"site:facebook.com/groups شقق للايجار في {clean_area}", btf_param),
            (f"site:facebook.com شقة مفروشة {clean_area} للايجار", btf_param),
            (f"site:facebook.com permalink شقه للايجار {clean_area}", None),
            (f"site:facebook.com permalink شقة للايجار {clean_area}", None),
            (f"site:dubizzle.com.eg/ad شقة للايجار {clean_area}", None),
        ]

        if clean_area == "بنها":
            query_specs.extend(
                [
                    ("site:facebook.com شقة للايجار بنها الفلل OR اتريب OR كفر الجزار", btf_param),
                    ("site:facebook.com/groups/341365830770481 شقه للايجار", None),
                    ("site:facebook.com/groups/567807180770634 شقه للايجار", None),
                    ("site:facebook.com/groups/1260358428598103 شقة مفروشة للايجار", None),
                    ("site:facebook.com/groups/341365830770481 شقه للايجار المنشيه OR الفلل", None),
                    ("site:facebook.com/groups/567807180770634 شقه للايجار الفلل OR المرور", None),
                    ("site:facebook.com/groups/781299894768923 شقه للايجار", None),
                ]
            )

        candidates: List[RawCandidatePost] = []
        seen_keys: Set[str] = set()
        sem = asyncio.Semaphore(2)

        try:
            async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
                search_tasks = [
                    self._fetch_yahoo_query(client, sem, q, btf) for q, btf in query_specs
                ]
                aqarmap_task = self._fetch_aqarmap_banha_listings(client, clean_area)

                all_lists = await asyncio.gather(*search_tasks, return_exceptions=True)
                aqarmap_candidates = await aqarmap_task

                raw_items: List[Dict[str, Optional[str]]] = []
                for res in all_lists:
                    if isinstance(res, list):
                        raw_items.extend(res)

                for item in raw_items:
                    raw_url = (item.get("url") or "").strip()
                    raw_title = (item.get("title") or "").strip()
                    raw_snippet = (item.get("snippet") or "").strip()

                    date_hint, clean_snippet = _split_leading_date_from_snippet(raw_snippet)
                    group_title = _extract_group_or_page_title(raw_title)

                    for known_id, known_name in KNOWN_BANHA_PUBLIC_GROUP_IDS:
                        if known_id in raw_url:
                            group_title = known_name
                            break

                    best_text = clean_snippet
                    if not best_text or len(best_text) < 12:
                        continue

                    group_url_val: Optional[str] = None
                    final_url = raw_url
                    if (
                        "facebook.com/groups/" in raw_url
                        and "/permalink/" not in raw_url
                        and "/posts/" not in raw_url
                    ):
                        m_grp = re.search(
                            r"(https?://(?:www\.|business\.)?facebook\.com/groups/[^/?#]+)",
                            raw_url,
                        )
                        if m_grp:
                            group_url_val = m_grp.group(1).replace(
                                "business.facebook.com", "www.facebook.com"
                            )
                            final_url = _build_in_group_direct_post_url(
                                group_url_val, best_text
                            )

                    dedup_key = f"{final_url}|{best_text[:55]}"
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)

                    source_label = "فيسبوك (رابط بوست مباشر)"
                    if "dubizzle.com.eg" in raw_url:
                        source_label = "دوبيزل مصر (رابط إعلان مباشر)"
                    elif group_url_val and "/search/?q=" in final_url:
                        source_label = f"فيسبوك — {group_title or 'جروب عام'}"

                    candidates.append(
                        RawCandidatePost(
                            raw_text=best_text,
                            url=final_url,
                            title=raw_title,
                            group_or_page_name=group_title,
                            group_or_page_url=group_url_val,
                            published_at_hint=date_hint,
                            source_name=source_label,
                            collected_at=collected_iso,
                        )
                    )

                candidates.extend(aqarmap_candidates)

            return candidates, ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="success",
                fetched_count=len(candidates),
                message=(
                    f"تم جلب {len(candidates)} منشور وإعلان عقاري مباشر من جروبات فيسبوك العامة والمنصات المفتوحة وتحليلها."
                ),
            )
        except Exception as exc:
            return candidates, ProviderExecutionReport(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                status="error" if not candidates else "partial",
                fetched_count=len(candidates),
                message="حدث خطأ جزئي أثناء جلب المنشورات العامة.",
                error_detail=_sanitize_error_message(exc),
            )
