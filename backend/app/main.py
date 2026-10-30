"""تطبيق FastAPI الرئيسي لمحرك البحث العربي عن شقق الإيجار في بنها.

يوفر نقاط النهاية المطلوبة في المواصفات:
- POST /api/search — بدء البحث بالفلاتر المطلوبة (المنطقة، الكلمات المفتاحية، الفترة الزمنية، المصادر).
- POST /api/import — استيراد منشورات أو روابط عامة مصرح بها بدأها المستخدم بنفسه.
- POST /api/links — توليد روابط البحث المخصصة لفيسبوك فوريًا حسب الفلاتر.
- GET /api/results — استرجاع النتائج المحفوظة مع الفلاتر المتقدمة والترقيم (Pagination).
- GET /api/results/{post_id} — تفاصيل منشور معين.
- GET /api/config — استرجاع إعدادات المناطق والكلمات الافتراضية وحالة المزودات.
- GET /api/health — التحقق من عمل التطبيق والمنطقة الزمنية وحالة قاعدة البيانات.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.database import (
    get_post_by_id,
    init_db,
    query_saved_posts,
    save_rental_posts,
    save_search_job_summary,
)
from backend.app.models import (
    AREAS_DIRECTORY,
    DEFAULT_KEYWORDS,
    FacebookDirectLink,
    ProviderExecutionReport,
    RentalPost,
    SearchRequest,
    SearchResponse,
    UserImportRequest,
)
from backend.app.providers.base import RawCandidatePost
from backend.app.providers.facebook_links import generate_facebook_search_links
from backend.app.providers.user_import import convert_user_imports_to_candidates
from backend.app.providers.web_search import (
    GoogleCSEProvider,
    PublicWebIndexProvider,
    SerperProvider,
)
from backend.app.services.pipeline import process_candidates_pipeline
from backend.app.services.time_filter import compute_time_window, now_cairo


# سجل داخلي لحالة التحديث الدوري (المرحلة الخامسة)
_periodic_state: Dict[str, Any] = {
    "enabled": False,
    "interval_minutes": settings.AUTO_REFRESH_INTERVAL_MINUTES,
    "last_run_at": None,
    "last_status": "idle",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """تهيئة قاعدة البيانات عند بدء تشغيل الخادم."""
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="محرك بحث عربي لجمع وفلترة منشورات شقق الإيجار العامة في بنها ومحافظة القليوبية",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """التحقق من أن التطبيق يعمل بشكل سليم مع عرض التوقيت المحلي لمصر وحالة المزودات."""
    current_cairo = now_cairo()
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timezone": "Africa/Cairo",
        "current_time_cairo": current_cairo.isoformat(),
        "providers_configured": {
            "facebook_links": True,
            "user_authorized_import": True,
            "public_web": settings.ENABLE_PUBLIC_WEB_PROVIDER,
            "google_cse": settings.has_google_cse,
            "serper": settings.has_serper,
        },
        "periodic_refresh": _periodic_state,
    }


@app.get("/api/config")
async def get_search_config() -> Dict[str, Any]:
    """إرجاع القيم الافتراضية للمناطق والأحياء الفرعية والكلمات المفتاحية وحالة المزودات."""
    current_cairo = now_cairo()
    default_start, default_end = compute_time_window("4d", reference_now=current_cairo)
    return {
        "default_area": "بنها",
        "default_governorate": "القليوبية",
        "default_time_preset": "4d",
        "timezone": "Africa/Cairo",
        "current_time_cairo": current_cairo.isoformat(),
        "default_period_start": default_start.isoformat(),
        "default_period_end": default_end.isoformat(),
        "default_keywords": DEFAULT_KEYWORDS,
        "areas_directory": AREAS_DIRECTORY,
        "providers": [
            {
                "id": "facebook_links",
                "name": "مولّد روابط بحث Facebook والجروبات العامة",
                "configured": True,
                "requires_key": False,
            },
            {
                "id": "public_web",
                "name": "فهرس الويب العام (صفحات فيسبوك المفهرسة)",
                "configured": settings.ENABLE_PUBLIC_WEB_PROVIDER,
                "requires_key": False,
            },
            {
                "id": "google_cse",
                "name": "Google Custom Search API",
                "configured": settings.has_google_cse,
                "requires_key": True,
            },
            {
                "id": "serper",
                "name": "Serper.dev Google Search API",
                "configured": settings.has_serper,
                "requires_key": True,
            },
        ],
    }


@app.post("/api/links", response_model=List[FacebookDirectLink])
async def create_facebook_links(req: SearchRequest) -> List[FacebookDirectLink]:
    """توليد روابط البحث المخصصة لفيسبوك والجروبات العامة بناءً على الفلاتر الزمنية والجغرافية."""
    try:
        window_start, window_end = compute_time_window(
            preset=req.time_preset,
            custom_start=req.custom_start,
            custom_end=req.custom_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return generate_facebook_search_links(
        area=req.area,
        keywords=req.keywords,
        window_start=window_start,
        window_end=window_end,
        include_new_banha=req.include_new_banha,
    )


@app.post("/api/search", response_model=SearchResponse)
async def execute_search(req: SearchRequest) -> SearchResponse:
    """تنفيذ البحث عبر المزودات المحددة مع الفلترة الزمنية الصارمة بتوقيت مصر وإزالة التكرارات."""
    try:
        window_start, window_end = compute_time_window(
            preset=req.time_preset,
            custom_start=req.custom_start,
            custom_end=req.custom_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = f"search_{uuid.uuid4().hex[:12]}"

    # 1. توليد روابط البحث المخصصة لفيسبوك والجروبات العامة
    fb_links = generate_facebook_search_links(
        area=req.area,
        keywords=req.keywords,
        window_start=window_start,
        window_end=window_end,
        include_new_banha=req.include_new_banha,
    )

    provider_reports: List[ProviderExecutionReport] = [
        ProviderExecutionReport(
            provider_id="facebook_links",
            provider_name="مولّد روابط بحث Facebook والجروبات العامة",
            status="success",
            fetched_count=len(fb_links),
            accepted_count=len(fb_links),
            message=f"تم توليد {len(fb_links)} رابط بحث مباشر مخصص لفيسبوك والجروبات العامة والأحياء الفرعية.",
        )
    ]

    # 2. تشغيل مزودات البحث العامة المختارة بشكل متوازٍ وآمن (دون توقف النظام عند تعطل أحدها)
    provider_map = {
        "public_web": PublicWebIndexProvider(),
        "google_cse": GoogleCSEProvider(),
        "serper": SerperProvider(),
    }

    tasks = []
    selected_providers = []
    for pid in req.providers:
        if pid in provider_map:
            selected_providers.append(provider_map[pid])
            tasks.append(
                provider_map[pid].search(
                    area=req.area,
                    keywords=req.keywords,
                    window_start=window_start,
                    window_end=window_end,
                    include_new_banha=req.include_new_banha,
                )
            )

    raw_candidates: List[RawCandidatePost] = []
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for prov, res in zip(selected_providers, results):
            if isinstance(res, Exception):
                provider_reports.append(
                    ProviderExecutionReport(
                        provider_id=prov.provider_id,
                        provider_name=prov.provider_name,
                        status="error",
                        message="حدث خطأ غير متوقع أثناء استعلام المزود.",
                        error_detail=str(res)[:200],
                    )
                )
            else:
                cands, rep = res
                raw_candidates.extend(cands)
                provider_reports.append(rep)

    # 3. دمج المنشورات المحفوظة مسبقًا في قاعدة البيانات لإعادة فحصها ضمن الفترة الزمنية المختارة
    existing_posts, _ = query_saved_posts(
        area=req.area,
        include_new_banha=req.include_new_banha,
        page=1,
        page_size=250,
    )
    for ep in existing_posts:
        raw_candidates.append(
            RawCandidatePost(
                raw_text=ep.original_text,
                url=ep.post_url or ep.raw_discovered_url,
                title=ep.group_or_page_name,
                group_or_page_name=ep.group_or_page_name,
                group_or_page_url=ep.group_or_page_url,
                published_at_hint=ep.published_at or ep.published_at_raw,
                source_name=ep.source_name,
                collected_at=ep.collected_at,
            )
        )

    # 4. تشغيل خط أنابيب المعالجة العربية والتحقق الزمني واستخراج البيانات وإزالة التكرار
    verified_results, unverified_date_results, stats = process_candidates_pipeline(
        candidates=raw_candidates,
        area=req.area,
        window_start=window_start,
        window_end=window_end,
        include_new_banha=req.include_new_banha,
    )

    # 5. حفظ المنشورات الصالحة وملخص البحث في قاعدة البيانات
    all_to_save = verified_results + unverified_date_results
    save_rental_posts(all_to_save)

    save_search_job_summary(
        {
            "job_id": job_id,
            "created_at": now_cairo().isoformat(),
            "area": req.area,
            "governorate": req.governorate,
            "time_preset": req.time_preset,
            "period_start": window_start.isoformat(),
            "period_end": window_end.isoformat(),
            "total_fetched": stats["total_fetched"],
            "total_accepted_verified": stats["accepted_verified"],
            "total_unverified_date": stats["accepted_unverified_date"],
            "total_excluded_old": stats["excluded_old"],
            "total_excluded_irrelevant": stats["excluded_irrelevant"],
            "total_excluded_exact_duplicates": stats["excluded_exact_duplicates"],
            "provider_reports": [r.model_dump() for r in provider_reports],
        }
    )

    _periodic_state["last_run_at"] = now_cairo().isoformat()
    _periodic_state["last_status"] = "completed"

    return SearchResponse(
        job_id=job_id,
        status="completed",
        area=req.area,
        governorate=req.governorate,
        timezone="Africa/Cairo",
        period_start=window_start.isoformat(),
        period_end=window_end.isoformat(),
        time_preset=req.time_preset,
        total_fetched=stats["total_fetched"],
        total_accepted_verified=stats["accepted_verified"],
        total_unverified_date=stats["accepted_unverified_date"],
        total_excluded_old=stats["excluded_old"],
        total_excluded_irrelevant=stats["excluded_irrelevant"],
        total_excluded_exact_duplicates=stats["excluded_exact_duplicates"],
        facebook_direct_links=fb_links,
        provider_reports=provider_reports,
        verified_results=verified_results,
        unverified_date_results=unverified_date_results,
    )


@app.post("/api/import", response_model=SearchResponse)
async def import_user_posts(req: UserImportRequest) -> SearchResponse:
    """استيراد منشورات أو روابط عامة مصرح بها قام المستخدم بنسخها من الجروبات العامة."""
    try:
        window_start, window_end = compute_time_window(
            preset=req.time_preset,
            custom_start=req.custom_start,
            custom_end=req.custom_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    imported_candidates = convert_user_imports_to_candidates(req.items)

    # جلب المنشورات المحفوظة مسبقًا لفحص التكرار معها
    existing_posts, _ = query_saved_posts(area=req.area, page=1, page_size=250)
    all_candidates = list(imported_candidates)
    for ep in existing_posts:
        all_candidates.append(
            RawCandidatePost(
                raw_text=ep.original_text,
                url=ep.post_url or ep.raw_discovered_url,
                title=ep.group_or_page_name,
                group_or_page_name=ep.group_or_page_name,
                group_or_page_url=ep.group_or_page_url,
                published_at_hint=ep.published_at or ep.published_at_raw,
                source_name=ep.source_name,
                collected_at=ep.collected_at,
            )
        )

    verified_results, unverified_date_results, stats = process_candidates_pipeline(
        candidates=all_candidates,
        area=req.area,
        window_start=window_start,
        window_end=window_end,
        include_new_banha=True,
    )

    save_rental_posts(verified_results + unverified_date_results)

    fb_links = generate_facebook_search_links(
        area=req.area,
        keywords=DEFAULT_KEYWORDS,
        window_start=window_start,
        window_end=window_end,
        include_new_banha=True,
    )

    report = ProviderExecutionReport(
        provider_id="user_import",
        provider_name="استيراد مصرح به (بواسطة المستخدم)",
        status="success",
        fetched_count=len(imported_candidates),
        accepted_count=stats["accepted_verified"],
        excluded_old_count=stats["excluded_old"],
        excluded_irrelevant_count=stats["excluded_irrelevant"],
        unverified_date_count=stats["accepted_unverified_date"],
        message=f"تم تحليل واستيراد {len(imported_candidates)} عنصر مدخل بنجاح.",
    )

    return SearchResponse(
        job_id=f"import_{uuid.uuid4().hex[:10]}",
        status="completed",
        area=req.area,
        governorate="القليوبية",
        timezone="Africa/Cairo",
        period_start=window_start.isoformat(),
        period_end=window_end.isoformat(),
        time_preset=req.time_preset,
        total_fetched=stats["total_fetched"],
        total_accepted_verified=stats["accepted_verified"],
        total_unverified_date=stats["accepted_unverified_date"],
        total_excluded_old=stats["excluded_old"],
        total_excluded_irrelevant=stats["excluded_irrelevant"],
        total_excluded_exact_duplicates=stats["excluded_exact_duplicates"],
        facebook_direct_links=fb_links,
        provider_reports=[report],
        verified_results=verified_results,
        unverified_date_results=unverified_date_results,
    )


@app.get("/api/results")
async def list_saved_results(
    area: Optional[str] = Query(default=None, description="فلتر المنطقة"),
    sub_area: Optional[str] = Query(default=None, description="فلتر الحي أو المنطقة الفرعية"),
    min_price: Optional[int] = Query(default=None, ge=0, description="الحد الأدنى للسعر بالجنيه"),
    max_price: Optional[int] = Query(default=None, ge=0, description="الحد الأقصى للسعر بالجنيه"),
    rooms_count: Optional[int] = Query(default=None, ge=1, description="عدد الغرف"),
    furnishing_status: Optional[str] = Query(default=None, description="حالة الفرش"),
    date_status: Optional[str] = Query(
        default=None, description="حالة التحقق من التاريخ (verified_in_range / unverified)"
    ),
    include_new_banha: bool = Query(default=True, description="تضمين بنها الجديدة"),
    page: int = Query(default=1, ge=1, description="رقم الصفحة"),
    page_size: int = Query(default=50, ge=1, le=200, description="عدد العناصر في الصفحة"),
) -> Dict[str, Any]:
    """استرجاع النتائج المحفوظة مع الفلترة المتقدمة والترقيم."""
    posts, total = query_saved_posts(
        area=area,
        sub_area=sub_area,
        min_price=min_price,
        max_price=max_price,
        rooms_count=rooms_count,
        furnishing_status=furnishing_status,
        date_status=date_status,
        include_new_banha=include_new_banha,
        page=page,
        page_size=page_size,
    )
    verified = [p for p in posts if p.date_verification_status == "verified_in_range"]
    unverified = [p for p in posts if p.date_verification_status == "unverified"]
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": posts,
        "verified_results": verified,
        "unverified_date_results": unverified,
    }


@app.get("/api/results/{post_id}", response_model=RentalPost)
async def get_single_result(post_id: str) -> RentalPost:
    """استرجاع تفاصيل منشور معين بواسطة معرفه الفريد."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="لم يتم العثور على المنشور المطلوب.")
    return post


# تقديم ملفات الواجهة الأمامية المبنية (frontend/dist) إن وجدت لتسهيل التشغيل الموحد
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        target = FRONTEND_DIST / full_path
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
