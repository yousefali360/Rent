import {
  AppConfigResponse,
  FacebookDirectLink,
  RentalPost,
  SearchRequestPayload,
  SearchResponseData,
  UserImportItemPayload,
} from './types';

const API_BASE = '/api';

export async function fetchAppConfig(): Promise<AppConfigResponse> {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) {
    throw new Error(`فشل تحميل إعدادات النظام (${res.status})`);
  }
  return res.json();
}

export async function executeSearchRequest(
  payload: SearchRequestPayload
): Promise<SearchResponseData> {
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `فشل تنفيذ البحث (${res.status})`);
  }
  return res.json();
}

export async function generateFacebookLinksOnly(
  payload: SearchRequestPayload
): Promise<FacebookDirectLink[]> {
  const res = await fetch(`${API_BASE}/links`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `فشل توليد الروابط (${res.status})`);
  }
  return res.json();
}

export async function importAuthorizedPosts(
  area: string,
  timePreset: SearchRequestPayload['time_preset'],
  customStart: string | null,
  customEnd: string | null,
  items: UserImportItemPayload[]
): Promise<SearchResponseData> {
  const res = await fetch(`${API_BASE}/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      area,
      time_preset: timePreset,
      custom_start: customStart,
      custom_end: customEnd,
      items,
    }),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `فشل استيراد المنشورات (${res.status})`);
  }
  return res.json();
}

export async function fetchSavedResults(): Promise<{
  verified_results: RentalPost[];
  unverified_date_results: RentalPost[];
  total: number;
}> {
  const res = await fetch(`${API_BASE}/results?page=1&page_size=150`);
  if (!res.ok) {
    throw new Error(`فشل استرجاع النتائج المحفوظة (${res.status})`);
  }
  return res.json();
}
