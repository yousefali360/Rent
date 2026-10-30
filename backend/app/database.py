"""وحدة قاعدة البيانات (SQLite في النسخة الأولى مع هيكل متوافق للانتقال إلى PostgreSQL).

تدير:
- جدول المنشورات `rental_posts` لحفظ جميع المنشورات المكتشفة والمستوردة مع حقولها الكاملة.
- جدول سجل عمليات البحث `search_jobs` لتوثيق كل عملية بحث وإحصائياتها.
- الاستعلام مع الفلاتر المتقدمة (المنطقة، المنطقة الفرعية، السعر الأدنى والأعلى، عدد الغرف، حالة الفرش، حالة التحقق من التاريخ) والترقيم (Pagination).
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.config import settings
from backend.app.models import RentalPost


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """إنشاء اتصال بقاعدة بيانات SQLite مع تفعيل Row factory."""
    target_path = db_path or settings.SQLITE_PATH
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """تهيئة جداول قاعدة البيانات والفهارس (Indexes) إن لم تكن موجودة."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rental_posts (
                    id TEXT PRIMARY KEY,
                    original_text TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    post_url TEXT,
                    raw_discovered_url TEXT,
                    url_verified INTEGER NOT NULL DEFAULT 0,
                    url_type TEXT NOT NULL DEFAULT 'unverified',
                    group_or_page_name TEXT,
                    group_or_page_url TEXT,
                    published_at TEXT,
                    published_at_raw TEXT,
                    collected_at TEXT NOT NULL,
                    area_mentioned TEXT,
                    sub_area TEXT,
                    is_new_banha INTEGER NOT NULL DEFAULT 0,
                    price_egp INTEGER,
                    rooms_count INTEGER,
                    bathrooms_count INTEGER,
                    area_sqm INTEGER,
                    furnishing_status TEXT,
                    contact_info TEXT,
                    source_name TEXT NOT NULL,
                    date_verification_status TEXT NOT NULL,
                    extraction_status TEXT NOT NULL DEFAULT 'minimal',
                    confidence_score REAL NOT NULL DEFAULT 0.5,
                    duplicate_of_id TEXT,
                    possible_duplicate_of_id TEXT,
                    similarity_score REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_published_at ON rental_posts(published_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_area ON rental_posts(area_mentioned, sub_area)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_price ON rental_posts(price_egp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_date_status ON rental_posts(date_verification_status)"
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_jobs (
                    job_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    area TEXT NOT NULL,
                    governorate TEXT NOT NULL,
                    time_preset TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    total_fetched INTEGER NOT NULL DEFAULT 0,
                    total_accepted_verified INTEGER NOT NULL DEFAULT 0,
                    total_unverified_date INTEGER NOT NULL DEFAULT 0,
                    total_excluded_old INTEGER NOT NULL DEFAULT 0,
                    total_excluded_irrelevant INTEGER NOT NULL DEFAULT 0,
                    total_excluded_exact_duplicates INTEGER NOT NULL DEFAULT 0,
                    provider_reports_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
    finally:
        conn.close()


def _row_to_rental_post(row: sqlite3.Row) -> RentalPost:
    """تحويل سجل قاعدة البيانات إلى كائن RentalPost."""
    return RentalPost(
        id=row["id"],
        original_text=row["original_text"],
        normalized_text=row["normalized_text"],
        post_url=row["post_url"],
        raw_discovered_url=row["raw_discovered_url"],
        url_verified=bool(row["url_verified"]),
        url_type=row["url_type"],
        group_or_page_name=row["group_or_page_name"],
        group_or_page_url=row["group_or_page_url"],
        published_at=row["published_at"],
        published_at_raw=row["published_at_raw"],
        collected_at=row["collected_at"],
        area_mentioned=row["area_mentioned"],
        sub_area=row["sub_area"],
        is_new_banha=bool(row["is_new_banha"]),
        price_egp=row["price_egp"],
        rooms_count=row["rooms_count"],
        bathrooms_count=row["bathrooms_count"],
        area_sqm=row["area_sqm"],
        furnishing_status=row["furnishing_status"],
        contact_info=row["contact_info"],
        source_name=row["source_name"],
        date_verification_status=row["date_verification_status"],
        extraction_status=row["extraction_status"],
        confidence_score=float(row["confidence_score"]),
        duplicate_of_id=row["duplicate_of_id"],
        possible_duplicate_of_id=row["possible_duplicate_of_id"],
        similarity_score=row["similarity_score"],
    )


def save_rental_posts(
    posts: List[RentalPost], db_path: Optional[Path] = None
) -> int:
    """حفظ أو تحديث مجموعة من المنشورات في قاعدة البيانات."""
    if not posts:
        return 0
    conn = get_db_connection(db_path)
    saved_count = 0
    try:
        with conn:
            for post in posts:
                conn.execute(
                    """
                    INSERT INTO rental_posts (
                        id, original_text, normalized_text, post_url, raw_discovered_url,
                        url_verified, url_type, group_or_page_name, group_or_page_url,
                        published_at, published_at_raw, collected_at, area_mentioned,
                        sub_area, is_new_banha, price_egp, rooms_count, bathrooms_count,
                        area_sqm, furnishing_status, contact_info, source_name,
                        date_verification_status, extraction_status, confidence_score,
                        duplicate_of_id, possible_duplicate_of_id, similarity_score
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        published_at= COALESCE(excluded.published_at, rental_posts.published_at),
                        published_at_raw= COALESCE(excluded.published_at_raw, rental_posts.published_at_raw),
                        collected_at= excluded.collected_at,
                        price_egp= COALESCE(excluded.price_egp, rental_posts.price_egp),
                        rooms_count= COALESCE(excluded.rooms_count, rental_posts.rooms_count),
                        bathrooms_count= COALESCE(excluded.bathrooms_count, rental_posts.bathrooms_count),
                        area_sqm= COALESCE(excluded.area_sqm, rental_posts.area_sqm),
                        furnishing_status= COALESCE(excluded.furnishing_status, rental_posts.furnishing_status),
                        contact_info= COALESCE(excluded.contact_info, rental_posts.contact_info),
                        date_verification_status= excluded.date_verification_status,
                        extraction_status= excluded.extraction_status,
                        confidence_score= excluded.confidence_score,
                        possible_duplicate_of_id= excluded.possible_duplicate_of_id,
                        similarity_score= excluded.similarity_score
                    """,
                    (
                        post.id,
                        post.original_text,
                        post.normalized_text,
                        post.post_url,
                        post.raw_discovered_url,
                        1 if post.url_verified else 0,
                        post.url_type,
                        post.group_or_page_name,
                        post.group_or_page_url,
                        post.published_at,
                        post.published_at_raw,
                        post.collected_at,
                        post.area_mentioned,
                        post.sub_area,
                        1 if post.is_new_banha else 0,
                        post.price_egp,
                        post.rooms_count,
                        post.bathrooms_count,
                        post.area_sqm,
                        post.furnishing_status,
                        post.contact_info,
                        post.source_name,
                        post.date_verification_status,
                        post.extraction_status,
                        post.confidence_score,
                        post.duplicate_of_id,
                        post.possible_duplicate_of_id,
                        post.similarity_score,
                    ),
                )
                saved_count += 1
    finally:
        conn.close()
    return saved_count


def save_search_job_summary(
    job_data: Dict[str, Any], db_path: Optional[Path] = None
) -> None:
    """حفظ ملخص عملية البحث في قاعدة البيانات."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO search_jobs (
                    job_id, created_at, area, governorate, time_preset,
                    period_start, period_end, total_fetched, total_accepted_verified,
                    total_unverified_date, total_excluded_old, total_excluded_irrelevant,
                    total_excluded_exact_duplicates, provider_reports_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_data["job_id"],
                    job_data["created_at"],
                    job_data["area"],
                    job_data["governorate"],
                    job_data["time_preset"],
                    job_data["period_start"],
                    job_data["period_end"],
                    job_data["total_fetched"],
                    job_data["total_accepted_verified"],
                    job_data["total_unverified_date"],
                    job_data["total_excluded_old"],
                    job_data["total_excluded_irrelevant"],
                    job_data["total_excluded_exact_duplicates"],
                    json.dumps(job_data.get("provider_reports", []), ensure_ascii=False),
                ),
            )
    finally:
        conn.close()


def query_saved_posts(
    area: Optional[str] = None,
    sub_area: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    rooms_count: Optional[int] = None,
    furnishing_status: Optional[str] = None,
    date_status: Optional[str] = None,
    include_new_banha: bool = True,
    page: int = 1,
    page_size: int = 50,
    db_path: Optional[Path] = None,
) -> Tuple[List[RentalPost], int]:
    """استرجاع النتائج المحفوظة مع الفلترة المتقدمة والترتيب من الأحدث إلى الأقدم والترقيم."""
    conn = get_db_connection(db_path)
    try:
        conditions: List[str] = ["duplicate_of_id IS NULL"]
        params: List[Any] = []

        if area:
            if area == "بنها" and include_new_banha:
                conditions.append("(area_mentioned IN ('بنها', 'بنها الجديدة') OR area_mentioned IS NULL)")
            else:
                conditions.append("(area_mentioned = ? OR area_mentioned IS NULL)")
                params.append(area)

        if not include_new_banha:
            conditions.append("is_new_banha = 0")

        if sub_area:
            conditions.append("sub_area LIKE ?")
            params.append(f"%{sub_area}%")

        if min_price is not None:
            conditions.append("price_egp IS NOT NULL AND price_egp >= ?")
            params.append(min_price)

        if max_price is not None:
            conditions.append("price_egp IS NOT NULL AND price_egp <= ?")
            params.append(max_price)

        if rooms_count is not None:
            conditions.append("rooms_count = ?")
            params.append(rooms_count)

        if furnishing_status:
            conditions.append("furnishing_status LIKE ?")
            params.append(f"%{furnishing_status}%")

        if date_status:
            conditions.append("date_verification_status = ?")
            params.append(date_status)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        count_row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM rental_posts{where_clause}", params
        ).fetchone()
        total_count = int(count_row["cnt"]) if count_row else 0

        offset = max(0, (page - 1) * page_size)
        query_sql = f"""
            SELECT * FROM rental_posts
            {where_clause}
            ORDER BY
                CASE WHEN published_at IS NOT NULL THEN 0 ELSE 1 END ASC,
                published_at DESC,
                collected_at DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, params + [page_size, offset]).fetchall()
        return [_row_to_rental_post(r) for r in rows], total_count
    finally:
        conn.close()


def get_post_by_id(
    post_id: str, db_path: Optional[Path] = None
) -> Optional[RentalPost]:
    """استرجاع تفاصيل منشور معين بواسطة معرفه الفريد."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM rental_posts WHERE id = ?", (post_id,)
        ).fetchone()
        return _row_to_rental_post(row) if row else None
    finally:
        conn.close()
