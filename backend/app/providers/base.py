"""الواجهة الأساسية المجردة (Abstract Base Class) لمزودي البحث لضمان قابلية التوسعة والاستبدال."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple
from pydantic import BaseModel

from backend.app.models import ProviderExecutionReport


class RawCandidatePost(BaseModel):
    """نتيجة خام واردة من أحد مزودي البحث قبل التطبيع والفلترة الزمنية وإزالة التكرار."""

    raw_text: str
    url: Optional[str] = None
    title: Optional[str] = None
    group_or_page_name: Optional[str] = None
    group_or_page_url: Optional[str] = None
    published_at_hint: Optional[str] = None
    source_name: str
    collected_at: str


class BaseSearchProvider(ABC):
    """واجهة موحدة لأي مزود بحث خارجي أو داخلي."""

    provider_id: str = "base"
    provider_name: str = "مزود بحث أساسي"

    @abstractmethod
    async def search(
        self,
        area: str,
        keywords: List[str],
        window_start: datetime,
        window_end: datetime,
        include_new_banha: bool = True,
    ) -> Tuple[List[RawCandidatePost], ProviderExecutionReport]:
        """تنفيذ البحث وإرجاع قائمة المرشحات الخام مع تقرير حالة المزود."""
        raise NotImplementedError
