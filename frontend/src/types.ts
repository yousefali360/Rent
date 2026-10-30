export type TimePreset = '24h' | '2d' | '4d' | 'custom';
export type DateVerificationStatus = 'verified_in_range' | 'verified_out_of_range' | 'unverified';
export type ExtractionStatus = 'complete' | 'partial' | 'minimal';
export type UrlVerificationType = 'post' | 'group_or_page' | 'search_link' | 'unverified';

export interface FacebookDirectLink {
  title: string;
  query_text: string;
  url: string;
  category: 'recent_posts' | 'public_groups' | 'general_posts' | 'sub_area';
  description: string;
}

export interface ProviderExecutionReport {
  provider_id: string;
  provider_name: string;
  status: 'success' | 'partial' | 'skipped_no_credentials' | 'error';
  fetched_count: number;
  accepted_count: number;
  excluded_old_count: number;
  excluded_irrelevant_count: number;
  unverified_date_count: number;
  message: string;
  error_detail?: string | null;
}

export interface RentalPost {
  id: string;
  original_text: string;
  normalized_text: string;
  post_url?: string | null;
  raw_discovered_url?: string | null;
  url_verified: boolean;
  url_type: UrlVerificationType;
  group_or_page_name?: string | null;
  group_or_page_url?: string | null;
  published_at?: string | null;
  published_at_raw?: string | null;
  collected_at: string;
  area_mentioned?: string | null;
  sub_area?: string | null;
  is_new_banha: boolean;
  price_egp?: number | null;
  rooms_count?: number | null;
  bathrooms_count?: number | null;
  area_sqm?: number | null;
  furnishing_status?: string | null;
  contact_info?: string | null;
  source_name: string;
  date_verification_status: DateVerificationStatus;
  extraction_status: ExtractionStatus;
  confidence_score: number;
  duplicate_of_id?: string | null;
  possible_duplicate_of_id?: string | null;
  similarity_score?: number | null;
}

export interface SearchRequestPayload {
  area: string;
  governorate: string;
  include_new_banha: boolean;
  keywords: string[];
  time_preset: TimePreset;
  custom_start?: string | null;
  custom_end?: string | null;
  providers: string[];
}

export interface SearchResponseData {
  job_id: string;
  status: 'completed' | 'running' | 'failed';
  area: string;
  governorate: string;
  timezone: string;
  period_start: string;
  period_end: string;
  time_preset: TimePreset;
  total_fetched: number;
  total_accepted_verified: number;
  total_unverified_date: number;
  total_excluded_old: number;
  total_excluded_irrelevant: number;
  total_excluded_exact_duplicates: number;
  facebook_direct_links: FacebookDirectLink[];
  provider_reports: ProviderExecutionReport[];
  verified_results: RentalPost[];
  unverified_date_results: RentalPost[];
  disclaimer: string;
}

export interface AreaMetadata {
  name: string;
  governorate: string;
  aliases: string[];
  distinct_nearby: string[];
  sub_areas: string[];
}

export interface AppConfigResponse {
  default_area: string;
  default_governorate: string;
  default_time_preset: TimePreset;
  timezone: string;
  current_time_cairo: string;
  default_period_start: string;
  default_period_end: string;
  default_keywords: string[];
  areas_directory: Record<string, AreaMetadata>;
  providers: {
    id: string;
    name: string;
    configured: boolean;
    requires_key: boolean;
  }[];
}

export interface UserImportItemPayload {
  text: string;
  post_url?: string;
  group_or_page_name?: string;
  group_or_page_url?: string;
  published_at_text?: string;
}
