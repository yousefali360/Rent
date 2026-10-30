import React, { useEffect, useMemo, useState } from 'react';
import {
  Building2,
  MapPin,
  Search,
  Calendar,
  Heart,
  ExternalLink,
  SlidersHorizontal,
  CheckCircle2,
  AlertCircle,
  Phone,
  MessageCircle,
  Sparkles,
  Bed,
  Bath,
  Maximize2,
  Armchair,
  Clock,
  RefreshCw,
  X,
  Copy,
  Check,
  Eye,
  Plus,
  Compass,
  Layers,
  TableProperties,
  LayoutGrid,
} from 'lucide-react';

import {
  executeSearchRequest,
  fetchAppConfig,
  generateFacebookLinksOnly,
  importAuthorizedPosts,
} from './api';
import {
  AppConfigResponse,
  FacebookDirectLink,
  ProviderExecutionReport,
  RentalPost,
  TimePreset,
} from './types';

const FALLBACK_DEFAULT_KEYWORDS: string[] = [
  'شقة',
  'شقه',
  'شقق',
  'للايجار',
  'للإيجار',
  'إيجار',
  'شقة للإيجار',
  'شقة للايجار',
  'شقق للايجار في بنها',
  'شقة للإيجار في بنها',
  'شقة مفروشة بنها',
  'شقة من المالك بنها',
];

const BANHA_NEIGHBORHOODS = [
  { id: '', name: 'جميع الأحياء', icon: '🌐' },
  { id: 'الفلل', name: 'حي الفلل', icon: '✨' },
  { id: 'الكورنيش', name: 'كورنيش النيل', icon: '🌊' },
  { id: 'وسط البلد', name: 'وسط البلد والمحطة', icon: '🚆' },
  { id: 'منطقة العلوم', name: 'منطقة الجامعة والطب', icon: '🎓' },
  { id: 'مساكن طابا', name: 'مساكن طابا والموقف', icon: '🏢' },
  { id: 'كفر الجزار', name: 'كفر الجزار', icon: '🌳' },
  { id: 'أتريب', name: 'حي أتريب', icon: '🏛️' },
  { id: 'المنشية', name: 'المنشية', icon: '🏘️' },
  { id: 'الأهرام', name: 'شارع الأهرام', icon: '📍' },
  { id: 'الحرس الوطني', name: 'الحرس الوطني', icon: '🛡️' },
  { id: 'بنها الجديدة', name: 'بنها الجديدة', icon: '🏙️' },
];

function formatCairoDateTime(isoStr?: string | null): string {
  if (!isoStr) return 'غير محدد';
  try {
    const dt = new Date(isoStr);
    if (Number.isNaN(dt.getTime())) return isoStr;
    return new Intl.DateTimeFormat('ar-EG', {
      timeZone: 'Africa/Cairo',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(dt);
  } catch {
    return isoStr;
  }
}

export function App() {
  // إعدادات التطبيق من الخادم
  const [config, setConfig] = useState<AppConfigResponse | null>(null);

  // حقول البحث الأساسية
  const [area, setArea] = useState<string>('بنها');
  const [governorate, setGovernorate] = useState<string>('القليوبية');
  const [includeNewBanha, setIncludeNewBanha] = useState<boolean>(true);
  const [keywords, setKeywords] = useState<string[]>(FALLBACK_DEFAULT_KEYWORDS);
  const [newKeywordInput, setNewKeywordInput] = useState<string>('');

  // الفلاتر الزمنية (الافتراضي: آخر 4 أيام - 4d)
  const [timePreset, setTimePreset] = useState<TimePreset>('4d');
  const [customStart, setCustomStart] = useState<string>('');
  const [customEnd, setCustomEnd] = useState<string>('');
  const [periodStartIso, setPeriodStartIso] = useState<string>('');
  const [periodEndIso, setPeriodEndIso] = useState<string>('');

  // حالة البحث والنتائج
  const [searchStatus, setSearchStatus] = useState<
    'idle' | 'searching' | 'completed' | 'error'
  >('idle');
  const [statusMessage, setStatusMessage] = useState<string>(
    'جاهز للبحث في المنشورات العامة حسب الفترة الزمنية المحددة بتوقيت مصر (Africa/Cairo).'
  );
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // الإحصائيات والتقارير والنتائج
  const [totalFetched, setTotalFetched] = useState<number>(0);
  const [totalAcceptedVerified, setTotalAcceptedVerified] = useState<number>(0);
  const [totalUnverifiedDate, setTotalUnverifiedDate] = useState<number>(0);
  const [totalExcludedOld, setTotalExcludedOld] = useState<number>(0);
  const [totalExcludedIrrelevant, setTotalExcludedIrrelevant] = useState<number>(0);
  const [totalExcludedDuplicates, setTotalExcludedDuplicates] = useState<number>(0);

  const [fbLinks, setFbLinks] = useState<FacebookDirectLink[]>([]);
  const [fbCategoryFilter, setFbCategoryFilter] = useState<string>('all');
  const [providerReports, setProviderReports] = useState<ProviderExecutionReport[]>([]);
  const [verifiedPosts, setVerifiedPosts] = useState<RentalPost[]>([]);
  const [unverifiedPosts, setUnverifiedPosts] = useState<RentalPost[]>([]);

  // فلاتر النتائج والتصفية (Housely Controls)
  const [categoryTab, setCategoryTab] = useState<'all' | 'rent' | 'furnished' | 'students' | 'commercial'>('all');
  const [subAreaFilter, setSubAreaFilter] = useState<string>('');
  const [minPriceFilter, setMinPriceFilter] = useState<string>('');
  const [maxPriceFilter, setMaxPriceFilter] = useState<string>('');
  const [roomsFilter, setRoomsFilter] = useState<string>('');
  const [furnishingFilter, setFurnishingFilter] = useState<string>('');
  const [showFiltersTray, setShowFiltersTray] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');

  // المحفوظات / المفضلة (Local Storage Favorites)
  const [favoriteIds, setFavoriteIds] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('housely_banha_favorites');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [showFavoritesModal, setShowFavoritesModal] = useState<boolean>(false);

  // معاينة تفاصيل العقار (Property Details Modal)
  const [selectedPostForModal, setSelectedPostForModal] = useState<RentalPost | null>(null);

  // نموذج الاستيراد المصرح به (بواسطة المستخدم)
  const [showImportPanel, setShowImportPanel] = useState<boolean>(false);
  const [importText, setImportText] = useState<string>('');
  const [importUrl, setImportUrl] = useState<string>('');
  const [importGroupName, setImportGroupName] = useState<string>('');
  const [importGroupUrl, setImportGroupUrl] = useState<string>('');
  const [importDateText, setImportDateText] = useState<string>('');
  const [isImporting, setIsImporting] = useState<boolean>(false);

  // التحديث الدوري والتنبيهات
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // حفظ المفضلة محليًا
  useEffect(() => {
    try {
      localStorage.setItem('housely_banha_favorites', JSON.stringify(favoriteIds));
    } catch {
      // ignore storage errors
    }
  }, [favoriteIds]);

  const toggleFavorite = (postId: string) => {
    setFavoriteIds((prev) =>
      prev.includes(postId) ? prev.filter((id) => id !== postId) : [...prev, postId]
    );
  };

  // تحميل الإعدادات الأولية
  useEffect(() => {
    let mounted = true;
    async function init() {
      try {
        const cfg = await fetchAppConfig();
        if (!mounted) return;
        setConfig(cfg);
        setArea(cfg.default_area || 'بنها');
        setGovernorate(cfg.default_governorate || 'القليوبية');
        setKeywords(cfg.default_keywords || FALLBACK_DEFAULT_KEYWORDS);
        setPeriodStartIso(cfg.default_period_start);
        setPeriodEndIso(cfg.default_period_end);

        if (cfg.default_period_start && cfg.default_period_end) {
          setCustomStart(cfg.default_period_start.slice(0, 16));
          setCustomEnd(cfg.default_period_end.slice(0, 16));
        }

        await handleStartSearch(
          cfg.default_area || 'بنها',
          cfg.default_governorate || 'القليوبية',
          true,
          cfg.default_keywords || FALLBACK_DEFAULT_KEYWORDS,
          '4d',
          null,
          null
        );
      } catch (err: unknown) {
        if (!mounted) return;
        const msg = err instanceof Error ? err.message : 'تعذر الاتصال بالخادم الخلفي';
        setErrorBanner(msg);
      }
    }
    init();
    return () => {
      mounted = false;
    };
  }, []);

  // التحديث الدوري
  useEffect(() => {
    if (!autoRefreshEnabled) return;
    const timer = window.setInterval(() => {
      handleStartSearch(
        area,
        governorate,
        includeNewBanha,
        keywords,
        timePreset,
        timePreset === 'custom' ? customStart : null,
        timePreset === 'custom' ? customEnd : null
      );
    }, 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [
    autoRefreshEnabled,
    area,
    governorate,
    includeNewBanha,
    keywords,
    timePreset,
    customStart,
    customEnd,
  ]);

  async function handleStartSearch(
    targetArea = area,
    targetGov = governorate,
    incNewBanha = includeNewBanha,
    targetKeywords = keywords,
    preset = timePreset,
    cStart: string | null = timePreset === 'custom' ? customStart : null,
    cEnd: string | null = timePreset === 'custom' ? customEnd : null
  ) {
    setErrorBanner(null);
    setSearchStatus('searching');
    setStatusMessage('جاري توليد روابط البحث وفحص المصادر العامة والفلترة الزمنية بتوقيت مصر...');

    try {
      const response = await executeSearchRequest({
        area: targetArea,
        governorate: targetGov,
        include_new_banha: incNewBanha,
        keywords: targetKeywords,
        time_preset: preset,
        custom_start: cStart,
        custom_end: cEnd,
        providers: ['facebook_links', 'public_web', 'google_cse', 'serper'],
      });

      setPeriodStartIso(response.period_start);
      setPeriodEndIso(response.period_end);
      setTotalFetched(response.total_fetched);
      setTotalAcceptedVerified(response.total_accepted_verified);
      setTotalUnverifiedDate(response.total_unverified_date);
      setTotalExcludedOld(response.total_excluded_old);
      setTotalExcludedIrrelevant(response.total_excluded_irrelevant);
      setTotalExcludedDuplicates(response.total_excluded_exact_duplicates);

      setFbLinks(response.facebook_direct_links);
      setProviderReports(response.provider_reports);
      setVerifiedPosts(response.verified_results);
      setUnverifiedPosts(response.unverified_date_results);

      setSearchStatus('completed');
      setStatusMessage(
        `اكتمل البحث بنجاح لمنطقة «${response.area}» — تم فحص ${response.total_fetched} منشور، وتوثيق ${response.total_accepted_verified} منشورًا حديثًا.`
      );
    } catch (err: unknown) {
      setSearchStatus('error');
      const msg = err instanceof Error ? err.message : 'حدث خطأ أثناء تنفيذ البحث';
      setErrorBanner(msg);
      setStatusMessage('تعذر إكمال البحث؛ يرجى مراجعة رسالة الخطأ.');
    }
  }

  async function handleQuickRegenerateLinks(nextPreset: TimePreset) {
    setTimePreset(nextPreset);
    if (nextPreset !== 'custom') {
      try {
        const links = await generateFacebookLinksOnly({
          area,
          governorate,
          include_new_banha: includeNewBanha,
          keywords,
          time_preset: nextPreset,
          custom_start: null,
          custom_end: null,
          providers: ['facebook_links'],
        });
        setFbLinks(links);
      } catch {
        // handled in search
      }
    }
  }

  function handleAddKeyword(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = newKeywordInput.trim();
    if (!trimmed) return;
    if (!keywords.includes(trimmed)) {
      setKeywords([...keywords, trimmed]);
    }
    setNewKeywordInput('');
  }

  function handleRemoveKeyword(kwToRemove: string) {
    if (keywords.length <= 1) return;
    setKeywords(keywords.filter((k) => k !== kwToRemove));
  }

  async function handleUserImportSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!importText.trim()) return;
    setIsImporting(true);
    setErrorBanner(null);

    try {
      const response = await importAuthorizedPosts(
        area,
        timePreset,
        timePreset === 'custom' ? customStart : null,
        timePreset === 'custom' ? customEnd : null,
        [
          {
            text: importText.trim(),
            post_url: importUrl.trim() || undefined,
            group_or_page_name: importGroupName.trim() || undefined,
            group_or_page_url: importGroupUrl.trim() || undefined,
            published_at_text: importDateText.trim() || undefined,
          },
        ]
      );

      setPeriodStartIso(response.period_start);
      setPeriodEndIso(response.period_end);
      setTotalFetched(response.total_fetched);
      setTotalAcceptedVerified(response.total_accepted_verified);
      setTotalUnverifiedDate(response.total_unverified_date);
      setTotalExcludedOld(response.total_excluded_old);
      setTotalExcludedIrrelevant(response.total_excluded_irrelevant);
      setTotalExcludedDuplicates(response.total_excluded_exact_duplicates);
      setVerifiedPosts(response.verified_results);
      setUnverifiedPosts(response.unverified_date_results);

      setImportText('');
      setImportUrl('');
      setImportGroupName('');
      setImportGroupUrl('');
      setImportDateText('');
      setShowImportPanel(false);
      setStatusMessage(
        'تم استيراد المنشور وتحليل بياناته والتحقق من تاريخه وإضافته للنتائج بنجاح.'
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'فشل استيراد المنشور';
      setErrorBanner(msg);
    } finally {
      setIsImporting(false);
    }
  }

  function copyToClipboard(text: string, idKey: string) {
    navigator.clipboard.writeText(text);
    setCopiedId(idKey);
    window.setTimeout(() => {
      setCopiedId((prev) => (prev === idKey ? null : prev));
    }, 2000);
  }

  // فلترة المنشورات حسب التبويبات والفلاتر الثانوية
  const filterPostList = (list: RentalPost[]): RentalPost[] => {
    return list.filter((post) => {
      if (!includeNewBanha && post.is_new_banha) return false;

      // تبويبات Housely
      if (categoryTab === 'furnished') {
        if (!post.furnishing_status || !post.furnishing_status.includes('مفروش')) return false;
      } else if (categoryTab === 'students') {
        const text = post.original_text.toLowerCase();
        if (!text.includes('طلبه') && !text.includes('طالبات') && !text.includes('جامعه') && !text.includes('طب')) {
          return false;
        }
      } else if (categoryTab === 'commercial') {
        const text = post.original_text.toLowerCase();
        if (!text.includes('اداري') && !text.includes('عياده') && !text.includes('مكتب')) {
          return false;
        }
      }

      // الحي الفرعي
      if (subAreaFilter && (!post.sub_area || !post.sub_area.includes(subAreaFilter))) {
        return false;
      }

      // السعر
      if (minPriceFilter) {
        const minVal = Number(minPriceFilter);
        if (!Number.isNaN(minVal) && (post.price_egp === null || post.price_egp === undefined || post.price_egp < minVal)) {
          return false;
        }
      }
      if (maxPriceFilter) {
        const maxVal = Number(maxPriceFilter);
        if (!Number.isNaN(maxVal) && (post.price_egp === null || post.price_egp === undefined || post.price_egp > maxVal)) {
          return false;
        }
      }

      // الغرف
      if (roomsFilter) {
        const rVal = Number(roomsFilter);
        if (rVal === 4) {
          if (!post.rooms_count || post.rooms_count < 4) return false;
        } else if (post.rooms_count !== rVal) {
          return false;
        }
      }

      // الفرش
      if (furnishingFilter) {
        if (!post.furnishing_status || !post.furnishing_status.includes(furnishingFilter)) {
          return false;
        }
      }

      return true;
    });
  };

  const filteredVerifiedPosts = useMemo(
    () => filterPostList(verifiedPosts),
    [
      verifiedPosts,
      categoryTab,
      includeNewBanha,
      subAreaFilter,
      minPriceFilter,
      maxPriceFilter,
      roomsFilter,
      furnishingFilter,
    ]
  );

  const filteredUnverifiedPosts = useMemo(
    () => filterPostList(unverifiedPosts),
    [
      unverifiedPosts,
      categoryTab,
      includeNewBanha,
      subAreaFilter,
      minPriceFilter,
      maxPriceFilter,
      roomsFilter,
      furnishingFilter,
    ]
  );

  const allPostsCombined = useMemo(
    () => [...verifiedPosts, ...unverifiedPosts],
    [verifiedPosts, unverifiedPosts]
  );

  const favoritePosts = useMemo(
    () => allPostsCombined.filter((p) => favoriteIds.includes(p.id)),
    [allPostsCombined, favoriteIds]
  );

  const filteredFbLinks = useMemo(() => {
    if (fbCategoryFilter === 'all') return fbLinks;
    return fbLinks.filter((l) => l.category === fbCategoryFilter);
  }, [fbLinks, fbCategoryFilter]);

  const totalExcludedAll =
    totalExcludedOld + totalExcludedIrrelevant + totalExcludedDuplicates;

  return (
    <div className="housely-app" dir="rtl">
      {/* 1. TOP NAVBAR (Housely Real Estate Bar) */}
      <header className="housely-navbar">
        <div className="housely-nav-container">
          <div className="housely-brand">
            <div className="housely-logo-icon">
              <Building2 size={24} strokeWidth={2.4} />
            </div>
            <div className="housely-brand-titles">
              <h1>
                Housely <span>بنها</span>
              </h1>
              <p>محرك البحث الذكي عن شقق الإيجار</p>
            </div>
          </div>

          <div className="housely-nav-location">
            <MapPin size={16} />
            <span>
              {area} — {governorate}
            </span>
          </div>

          <div className="housely-nav-actions">
            <button
              type="button"
              className="nav-btn favorites-btn"
              onClick={() => setShowFavoritesModal(true)}
              title="عرض العقارات المحفوظة"
            >
              <Heart size={16} fill={favoriteIds.length > 0 ? '#e11d48' : 'none'} />
              <span>المحفوظات</span>
              {favoriteIds.length > 0 && <span className="fav-badge">{favoriteIds.length}</span>}
            </button>

            <button
              type="button"
              className="nav-btn primary"
              onClick={() => setShowImportPanel(true)}
            >
              <Plus size={16} />
              <span>استيراد إعلان</span>
            </button>

            <button
              type="button"
              className={`nav-btn ${autoRefreshEnabled ? 'primary' : ''}`}
              onClick={() => setAutoRefreshEnabled((prev) => !prev)}
              title="تحديث دوري تلقائي كل 5 دقائق"
            >
              <RefreshCw size={15} className={autoRefreshEnabled ? 'spin-icon' : ''} />
              <span>{autoRefreshEnabled ? 'التحديث التلقائي نشط' : 'تحديث دوري'}</span>
            </button>
          </div>
        </div>
      </header>

      {/* 2. HERO SEARCH SECTION (Housely Search Hub) */}
      <section className="housely-hero">
        <div className="housely-container">
          <div className="hero-welcome">
            <div className="hero-tagline-badge">
              <Sparkles size={14} />
              <span>البحث الأول لشقق الإيجار في بنها والقليوبية</span>
            </div>
            <h2>
              اعثر على شقتك القادمة في <span>بنها</span> بدقة وذكاء
            </h2>
            <p>
              يجمع ويحلل منشورات الإيجار من فيسبوك والمنصات العامة لحظيًا، مع روابط مباشرة للبوستات الأصلية وأسعار وتفاصيل موثقة.
            </p>
          </div>

          {/* Floating Search Card */}
          <div className="housely-search-card">
            {/* Category Tabs */}
            <div className="search-tabs-row" role="tablist">
              <button
                type="button"
                className={`search-tab-pill ${categoryTab === 'all' ? 'active' : ''}`}
                onClick={() => setCategoryTab('all')}
              >
                ✨ جميع العقارات
              </button>
              <button
                type="button"
                className={`search-tab-pill ${categoryTab === 'rent' ? 'active' : ''}`}
                onClick={() => setCategoryTab('rent')}
              >
                🏠 شقق للإيجار
              </button>
              <button
                type="button"
                className={`search-tab-pill ${categoryTab === 'furnished' ? 'active' : ''}`}
                onClick={() => setCategoryTab('furnished')}
              >
                🛋️ شقق مفروشة
              </button>
              <button
                type="button"
                className={`search-tab-pill ${categoryTab === 'students' ? 'active' : ''}`}
                onClick={() => setCategoryTab('students')}
              >
                🎓 سكن طلبة والجامعة
              </button>
              <button
                type="button"
                className={`search-tab-pill ${categoryTab === 'commercial' ? 'active' : ''}`}
                onClick={() => setCategoryTab('commercial')}
              >
                💼 إداري وعيادات
              </button>
            </div>

            {/* Main Controls Grid */}
            <div className="search-controls-grid">
              <div className="search-input-group">
                <label>
                  <MapPin size={14} />
                  <span>المدينة والنطاق</span>
                </label>
                <div className="search-field-wrapper">
                  <span className="search-field-icon">
                    <Compass size={17} />
                  </span>
                  <input
                    type="text"
                    className="search-field-input"
                    value={area}
                    onChange={(e) => setArea(e.target.value)}
                    placeholder="بنها، القليوبية..."
                    list="housely-cities"
                  />
                  <datalist id="housely-cities">
                    <option value="بنها" />
                    <option value="طوخ" />
                    <option value="قليوب" />
                    <option value="شبرا الخيمة" />
                    <option value="العبور" />
                  </datalist>
                </div>
              </div>

              <div className="search-input-group">
                <label>
                  <SlidersHorizontal size={14} />
                  <span>الحي والمنطقة الفرعية</span>
                </label>
                <div className="search-field-wrapper">
                  <span className="search-field-icon">
                    <MapPin size={17} />
                  </span>
                  <select
                    className="search-field-select"
                    value={subAreaFilter}
                    onChange={(e) => setSubAreaFilter(e.target.value)}
                  >
                    <option value="">جميع أحياء {area}</option>
                    {BANHA_NEIGHBORHOODS.filter((n) => n.id).map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="search-input-group">
                <label>
                  <Bed size={14} />
                  <span>عدد الغرف</span>
                </label>
                <div className="search-field-wrapper">
                  <span className="search-field-icon">
                    <Layers size={17} />
                  </span>
                  <select
                    className="search-field-select"
                    value={roomsFilter}
                    onChange={(e) => setRoomsFilter(e.target.value)}
                  >
                    <option value="">أي عدد غرف</option>
                    <option value="1">غرفة واحدة / ستوديو</option>
                    <option value="2">غرفتان (2)</option>
                    <option value="3">3 غرف</option>
                    <option value="4">4 غرف فأكثر</option>
                  </select>
                </div>
              </div>

              <div className="search-input-group">
                <label>
                  <Armchair size={14} />
                  <span>حالة الفرش</span>
                </label>
                <div className="search-field-wrapper">
                  <span className="search-field-icon">
                    <Armchair size={17} />
                  </span>
                  <select
                    className="search-field-select"
                    value={furnishingFilter}
                    onChange={(e) => setFurnishingFilter(e.target.value)}
                  >
                    <option value="">الكل (مفروش أو فاضي)</option>
                    <option value="مفروش">مفروش فقط</option>
                    <option value="غير مفروش">غير مفروش (فاضي)</option>
                    <option value="قانون جديد">قانون جديد</option>
                  </select>
                </div>
              </div>

              <button
                type="button"
                className="search-action-btn"
                disabled={searchStatus === 'searching'}
                onClick={() =>
                  handleStartSearch(
                    area,
                    governorate,
                    includeNewBanha,
                    keywords,
                    timePreset,
                    timePreset === 'custom' ? customStart : null,
                    timePreset === 'custom' ? customEnd : null
                  )
                }
              >
                {searchStatus === 'searching' ? (
                  <>
                    <RefreshCw size={18} className="spin-icon" />
                    <span>جاري البحث...</span>
                  </>
                ) : (
                  <>
                    <Search size={18} />
                    <span>بحث عن شقق</span>
                  </>
                )}
              </button>
            </div>

            {/* Quick Banha Neighborhood Chips */}
            <div className="neighborhoods-section">
              <div className="neighborhoods-header">
                <span>
                  <Compass size={15} />
                  <span>تصفية سريعة بأشهر أحياء بنها:</span>
                </span>
                <label
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    color: 'var(--text-muted)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={includeNewBanha}
                    onChange={(e) => setIncludeNewBanha(e.target.checked)}
                  />
                  <span>تضمين «بنها الجديدة»</span>
                </label>
              </div>

              <div className="neighborhood-chips-list">
                {BANHA_NEIGHBORHOODS.map((item) => (
                  <button
                    key={item.id || 'all'}
                    type="button"
                    className={`neighborhood-chip ${subAreaFilter === item.id ? 'active' : ''}`}
                    onClick={() => setSubAreaFilter(item.id)}
                  >
                    <span>{item.icon}</span>
                    <span>{item.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Time Window Selector Pills */}
            <div className="time-segment-row">
              <span className="time-segment-label">
                <Clock size={14} style={{ display: 'inline', verticalAlign: 'middle' }} /> فترة النشر (بتوقيت مصر):
              </span>
              <button
                type="button"
                className={`time-pill-btn ${timePreset === '24h' ? 'active' : ''}`}
                onClick={() => handleQuickRegenerateLinks('24h')}
              >
                ⚡ آخر 24 ساعة
              </button>
              <button
                type="button"
                className={`time-pill-btn ${timePreset === '2d' ? 'active' : ''}`}
                onClick={() => handleQuickRegenerateLinks('2d')}
              >
                📅 آخر يومين
              </button>
              <button
                type="button"
                className={`time-pill-btn ${timePreset === '4d' ? 'active' : ''}`}
                onClick={() => handleQuickRegenerateLinks('4d')}
              >
                ⏱️ آخر 4 أيام (الافتراضي)
              </button>
              <button
                type="button"
                className={`time-pill-btn ${timePreset === 'custom' ? 'active' : ''}`}
                onClick={() => handleQuickRegenerateLinks('custom')}
              >
                ⚙️ فترة مخصصة
              </button>

              <button
                type="button"
                className="time-pill-btn"
                style={{ marginInlineStart: 'auto' }}
                onClick={() => setShowFiltersTray((prev) => !prev)}
              >
                <SlidersHorizontal size={14} />
                <span>{showFiltersTray ? 'إخفاء فلاتر الأسعار والكلمات' : 'فلاتر الأسعار المتقدمة'}</span>
              </button>
            </div>

            {/* Custom Time Range Picker */}
            {timePreset === 'custom' && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '1rem',
                  background: 'var(--bg-subtle)',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  marginBlockStart: '1rem',
                  border: '1px dashed var(--brand-primary)',
                }}
              >
                <div className="search-input-group">
                  <label>من تاريخ ووقت (Africa/Cairo)</label>
                  <input
                    type="datetime-local"
                    className="search-field-input"
                    value={customStart}
                    onChange={(e) => setCustomStart(e.target.value)}
                  />
                </div>
                <div className="search-input-group">
                  <label>إلى تاريخ ووقت (Africa/Cairo)</label>
                  <input
                    type="datetime-local"
                    className="search-field-input"
                    value={customEnd}
                    onChange={(e) => setCustomEnd(e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* Advanced Filters Tray (Price range & Editable Keywords) */}
            {showFiltersTray && (
              <div
                style={{
                  marginBlockStart: '1.25rem',
                  paddingBlockStart: '1.25rem',
                  borderBlockStart: '1px solid var(--border-color)',
                }}
              >
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                    gap: '1rem',
                    marginBlockEnd: '1rem',
                  }}
                >
                  <div className="search-input-group">
                    <label>الحد الأدنى للسعر (جنيه / شهر)</label>
                    <input
                      type="number"
                      className="search-field-input"
                      placeholder="مثال: 2000"
                      value={minPriceFilter}
                      onChange={(e) => setMinPriceFilter(e.target.value)}
                    />
                  </div>
                  <div className="search-input-group">
                    <label>الحد الأقصى للسعر (جنيه / شهر)</label>
                    <input
                      type="number"
                      className="search-field-input"
                      placeholder="مثال: 7000"
                      value={maxPriceFilter}
                      onChange={(e) => setMaxPriceFilter(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBlockEnd: '0.5rem',
                    }}
                  >
                    <label style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                      🏷️ عبارات البحث المعتمدة ({keywords.length} عبارة):
                    </label>
                    <button
                      type="button"
                      className="time-pill-btn"
                      onClick={() => setKeywords(config?.default_keywords || FALLBACK_DEFAULT_KEYWORDS)}
                    >
                      استعادة الافتراضية
                    </button>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '0.45rem',
                      background: 'var(--bg-subtle)',
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-md)',
                      marginBlockEnd: '0.75rem',
                    }}
                  >
                    {keywords.map((kw) => (
                      <span
                        key={kw}
                        style={{
                          background: '#fff',
                          border: '1px solid var(--border-color)',
                          padding: '0.2rem 0.65rem',
                          borderRadius: '999px',
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                        }}
                      >
                        <span>{kw}</span>
                        <button
                          type="button"
                          style={{
                            border: 'none',
                            background: 'transparent',
                            color: 'var(--rose-600)',
                            cursor: 'pointer',
                            fontWeight: 800,
                          }}
                          onClick={() => handleRemoveKeyword(kw)}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>

                  <form onSubmit={handleAddKeyword} style={{ display: 'flex', gap: '0.5rem' }}>
                    <input
                      type="text"
                      className="search-field-input"
                      style={{ maxInlineSize: '360px' }}
                      placeholder="أضف عبارة بحث جديدة (مثال: شقة الفلل بنها)..."
                      value={newKeywordInput}
                      onChange={(e) => setNewKeywordInput(e.target.value)}
                    />
                    <button type="submit" className="nav-btn primary">
                      + إضافة عبارة
                    </button>
                  </form>
                </div>
              </div>
            )}
          </div>

          {/* Error Banner */}
          {errorBanner && (
            <div
              style={{
                background: 'var(--bg-rose-soft)',
                border: '1px solid #fecdd3',
                color: 'var(--rose-600)',
                padding: '1rem 1.25rem',
                borderRadius: 'var(--radius-md)',
                marginBlockEnd: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontWeight: 700,
              }}
              role="alert"
            >
              <AlertCircle size={20} />
              <span>{errorBanner}</span>
            </div>
          )}

          {/* 3. METRICS OVERVIEW (Housely Stats Cards) */}
          <div className="stats-overview-grid">
            <div className="stat-metric-card">
              <div className="stat-metric-icon blue">
                <Search size={22} />
              </div>
              <div className="stat-metric-info">
                <div className="stat-num">{totalFetched}</div>
                <div className="stat-label">إجمالي المفحوص</div>
                <div className="stat-sub">من المصادر العامة</div>
              </div>
            </div>

            <div className="stat-metric-card">
              <div className="stat-metric-icon emerald">
                <CheckCircle2 size={22} />
              </div>
              <div className="stat-metric-info">
                <div className="stat-num">{totalAcceptedVerified}</div>
                <div className="stat-label">منشورات حديثة مؤكدة</div>
                <div className="stat-sub">خلال الفترة المحددة</div>
              </div>
            </div>

            <div className="stat-metric-card">
              <div className="stat-metric-icon amber">
                <Clock size={22} />
              </div>
              <div className="stat-metric-info">
                <div className="stat-num">{totalUnverifiedDate}</div>
                <div className="stat-label">تاريخ غير مؤكد</div>
                <div className="stat-sub">في قسم منفصل للشفافية</div>
              </div>
            </div>

            <div className="stat-metric-card">
              <div className="stat-metric-icon rose">
                <AlertCircle size={22} />
              </div>
              <div className="stat-metric-info">
                <div className="stat-num">{totalExcludedAll}</div>
                <div className="stat-label">مستبعدة بدقة</div>
                <div className="stat-sub">
                  قديم: {totalExcludedOld} | غير مطابق: {totalExcludedIrrelevant} | مكرر: {totalExcludedDuplicates}
                </div>
              </div>
            </div>
          </div>

          {/* 4. FEED HEADER & VIEW TOOLBAR */}
          <div className="feed-header-toolbar">
            <div className="feed-title-block">
              <h3>
                <Building2 size={22} color="var(--brand-primary)" />
                <span>عقارات الإيجار المتاحة في بنها ({filteredVerifiedPosts.length + filteredUnverifiedPosts.length})</span>
              </h3>
              <p>
                حالة البحث: <strong>{statusMessage}</strong>
              </p>
            </div>

            <div className="feed-view-toggles">
              <button
                type="button"
                className={`view-toggle-btn ${viewMode === 'cards' ? 'active' : ''}`}
                onClick={() => setViewMode('cards')}
              >
                <LayoutGrid size={16} />
                <span>بطاقات العقارات</span>
              </button>
              <button
                type="button"
                className={`view-toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
                onClick={() => setViewMode('table')}
              >
                <TableProperties size={16} />
                <span>جدول المقارنة</span>
              </button>
            </div>
          </div>

          {/* 5. VERIFIED RECENT POSTS SECTION */}
          {filteredVerifiedPosts.length > 0 && (
            <div style={{ marginBlockEnd: '2.5rem' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.65rem',
                  marginBlockEnd: '1.25rem',
                }}
              >
                <div
                  style={{
                    inlineSize: '12px',
                    blockSize: '12px',
                    borderRadius: '50%',
                    background: 'var(--emerald-500)',
                    boxShadow: '0 0 10px rgba(16, 185, 129, 0.6)',
                  }}
                />
                <h4 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--brand-dark)' }}>
                  منشورات حديثة مؤكدة تاريخ النشر ({filteredVerifiedPosts.length})
                </h4>
                <span
                  style={{
                    fontSize: '0.8rem',
                    background: 'var(--bg-emerald-soft)',
                    color: 'var(--emerald-700)',
                    padding: '0.2rem 0.65rem',
                    borderRadius: 'var(--radius-pill)',
                    fontWeight: 700,
                  }}
                >
                  مرتبة من الأحدث إلى الأقدم بتوقيت مصر
                </span>
              </div>

              {viewMode === 'cards' ? (
                <div className="properties-grid">
                  {filteredVerifiedPosts.map((post) => (
                    <HouselyPropertyCard
                      key={post.id}
                      post={post}
                      isFavorite={favoriteIds.includes(post.id)}
                      onToggleFavorite={() => toggleFavorite(post.id)}
                      onOpenDetails={() => setSelectedPostForModal(post)}
                      copiedId={copiedId}
                      onCopy={copyToClipboard}
                    />
                  ))}
                </div>
              ) : (
                <PostsTableView
                  posts={filteredVerifiedPosts}
                  favoriteIds={favoriteIds}
                  onToggleFavorite={toggleFavorite}
                  onOpenDetails={setSelectedPostForModal}
                  copiedId={copiedId}
                  onCopy={copyToClipboard}
                />
              )}
            </div>
          )}

          {/* 6. UNVERIFIED DATE SECTION (Clear Transparency Section) */}
          <div style={{ marginBlockEnd: '3rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.65rem',
                marginBlockEnd: '1.25rem',
              }}
            >
              <div
                style={{
                  inlineSize: '12px',
                  blockSize: '12px',
                  borderRadius: '50%',
                  background: 'var(--amber-500)',
                  boxShadow: '0 0 10px rgba(245, 158, 11, 0.5)',
                }}
              />
              <h4 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#92400e' }}>
                تاريخ النشر غير مؤكد ({filteredUnverifiedPosts.length})
              </h4>
              <span
                style={{
                  fontSize: '0.8rem',
                  background: 'var(--bg-amber-soft)',
                  color: '#92400e',
                  padding: '0.2rem 0.65rem',
                  borderRadius: 'var(--radius-pill)',
                  fontWeight: 700,
                }}
              >
                تطابق شروط الإيجار في بنها لكن تعذّر التحقق من تاريخ نشرها من المصدر
              </span>
            </div>

            {filteredUnverifiedPosts.length === 0 ? (
              <div
                style={{
                  background: 'var(--bg-surface)',
                  padding: '2.5rem',
                  borderRadius: 'var(--radius-lg)',
                  textAlign: 'center',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-muted)',
                }}
              >
                لا توجد منشورات في هذا القسم حاليًا.
              </div>
            ) : viewMode === 'cards' ? (
              <div className="properties-grid">
                {filteredUnverifiedPosts.map((post) => (
                  <HouselyPropertyCard
                    key={post.id}
                    post={post}
                    isFavorite={favoriteIds.includes(post.id)}
                    onToggleFavorite={() => toggleFavorite(post.id)}
                    onOpenDetails={() => setSelectedPostForModal(post)}
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                ))}
              </div>
            ) : (
              <PostsTableView
                posts={filteredUnverifiedPosts}
                favoriteIds={favoriteIds}
                onToggleFavorite={toggleFavorite}
                onOpenDetails={setSelectedPostForModal}
                copiedId={copiedId}
                onCopy={copyToClipboard}
              />
            )}
          </div>

          {/* 7. FACEBOOK DIRECT SEARCH LINKS SECTION (Housely Cards Grid) */}
          <section className="fb-section-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--brand-dark)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Compass size={22} color="#1877f2" />
                  <span>روابط البحث المباشرة في فيسبوك والجروبات العامة ({fbLinks.length} رابط جاهز)</span>
                </h3>
                <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginBlockStart: '0.25rem' }}>
                  تتيح لك تصفح أحدث منشورات الجروبات العامة في {area} مباشرة داخل تطبيق فيسبوك بمتصفحك دون الحاجة لتسجيل كلمة مرورك.
                </p>
              </div>

              <div className="fb-category-pills">
                <button
                  type="button"
                  className={`fb-cat-btn ${fbCategoryFilter === 'all' ? 'active' : ''}`}
                  onClick={() => setFbCategoryFilter('all')}
                >
                  الكل ({fbLinks.length})
                </button>
                <button
                  type="button"
                  className={`fb-cat-btn ${fbCategoryFilter === 'recent_posts' ? 'active' : ''}`}
                  onClick={() => setFbCategoryFilter('recent_posts')}
                >
                  منشورات حديثة بالأحدث
                </button>
                <button
                  type="button"
                  className={`fb-cat-btn ${fbCategoryFilter === 'public_groups' ? 'active' : ''}`}
                  onClick={() => setFbCategoryFilter('public_groups')}
                >
                  الجروبات العامة
                </button>
                <button
                  type="button"
                  className={`fb-cat-btn ${fbCategoryFilter === 'sub_area' ? 'active' : ''}`}
                  onClick={() => setFbCategoryFilter('sub_area')}
                >
                  أحياء {area} الفرعية
                </button>
              </div>
            </div>

            <div className="fb-links-grid-housely">
              {filteredFbLinks.map((item, idx) => {
                const copyKey = `fblink_${idx}`;
                return (
                  <div key={copyKey} className="fb-tile-card">
                    <div>
                      <div className="fb-tile-title">{item.title}</div>
                      <div className="fb-tile-desc">{item.description}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', marginBlockStart: '0.5rem' }}>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="action-btn-primary"
                        style={{ fontSize: '0.82rem', padding: '0.45rem 0.85rem' }}
                      >
                        <span>فتح في فيسبوك</span>
                        <ExternalLink size={14} />
                      </a>
                      <button
                        type="button"
                        className="action-btn-secondary"
                        style={{ fontSize: '0.82rem', padding: '0.45rem 0.85rem' }}
                        onClick={() => copyToClipboard(item.url, copyKey)}
                      >
                        {copiedId === copyKey ? <Check size={14} color="var(--emerald-600)" /> : <Copy size={14} />}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      </section>

      {/* 8. PROPERTY DETAILS MODAL (Housely View Sheet) */}
      {selectedPostForModal && (
        <div className="modal-backdrop" onClick={() => setSelectedPostForModal(null)}>
          <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <Building2 size={22} color="var(--brand-primary)" />
                <span>تفاصيل إعلان الشقة في بنها</span>
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setSelectedPostForModal(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {/* Header Price & Location */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  paddingBlockEnd: '1rem',
                  borderBlockEnd: '1px solid var(--border-color)',
                }}
              >
                <div>
                  <h4 style={{ fontSize: '1.25rem', fontWeight: 900, color: 'var(--brand-dark)' }}>
                    شقة للإيجار {selectedPostForModal.sub_area ? `— ${selectedPostForModal.sub_area}` : `في ${selectedPostForModal.area_mentioned || 'بنها'}`}
                  </h4>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.88rem', marginBlockStart: '0.25rem' }}>
                    <MapPin size={15} color="var(--brand-primary)" />
                    <span>
                      {selectedPostForModal.area_mentioned}
                      {selectedPostForModal.sub_area ? `، ${selectedPostForModal.sub_area}` : ''}
                    </span>
                  </div>
                </div>

                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: '1.8rem', fontWeight: 900, color: 'var(--brand-primary)', fontFamily: 'var(--font-num)', lineHeight: 1 }}>
                    {selectedPostForModal.price_egp
                      ? `${selectedPostForModal.price_egp.toLocaleString('ar-EG')} ج.م`
                      : 'السعر غير مذكور'}
                  </div>
                  {selectedPostForModal.price_egp && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>شهريًا</div>
                  )}
                </div>
              </div>

              {/* Specs Grid */}
              <div className="modal-specs-grid">
                <div className="modal-spec-box">
                  <Bed size={22} className="icon" />
                  <div className="val">{selectedPostForModal.rooms_count ? `${selectedPostForModal.rooms_count} غرف` : 'غير محدد'}</div>
                  <div className="lbl">عدد الغرف</div>
                </div>
                <div className="modal-spec-box">
                  <Bath size={22} className="icon" />
                  <div className="val">{selectedPostForModal.bathrooms_count ? `${selectedPostForModal.bathrooms_count} حمام` : 'غير محدد'}</div>
                  <div className="lbl">دورات المياه</div>
                </div>
                <div className="modal-spec-box">
                  <Maximize2 size={22} className="icon" />
                  <div className="val">{selectedPostForModal.area_sqm ? `${selectedPostForModal.area_sqm} م²` : 'غير محدد'}</div>
                  <div className="lbl">المساحة الإجمالية</div>
                </div>
                <div className="modal-spec-box">
                  <Armchair size={22} className="icon" />
                  <div className="val">{selectedPostForModal.furnishing_status || 'غير مذكور'}</div>
                  <div className="lbl">حالة الفرش</div>
                </div>
              </div>

              {/* Original Post Text */}
              <div>
                <label style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-secondary)', display: 'block', marginBlockEnd: '0.45rem' }}>
                  📄 نص المنشور الأصلي الكامل:
                </label>
                <div
                  style={{
                    background: 'var(--bg-subtle)',
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    whiteSpace: 'pre-line',
                    fontSize: '0.94rem',
                    lineHeight: 1.6,
                    borderInlineStart: '4px solid var(--brand-primary)',
                  }}
                >
                  {selectedPostForModal.original_text}
                </div>
              </div>

              {/* Verification & Metadata */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '0.75rem',
                  fontSize: '0.84rem',
                  color: 'var(--text-muted)',
                }}
              >
                <div>
                  <strong>تاريخ النشر الأصلي: </strong>
                  <span>
                    {selectedPostForModal.published_at
                      ? formatCairoDateTime(selectedPostForModal.published_at)
                      : selectedPostForModal.published_at_raw || 'غير مؤكد'}
                  </span>
                </div>
                <div>
                  <strong>المصدر: </strong>
                  <span>{selectedPostForModal.source_name}</span>
                  {selectedPostForModal.group_or_page_name ? ` (${selectedPostForModal.group_or_page_name})` : ''}
                </div>
              </div>

              {/* Contact Card */}
              {selectedPostForModal.contact_info && (
                <div className="modal-contact-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 800, color: 'var(--brand-dark)' }}>
                    <Phone size={18} color="var(--emerald-600)" />
                    <span>معلومات التواصل المعلنة: {selectedPostForModal.contact_info}</span>
                  </div>
                  <div className="contact-actions-row">
                    <a
                      href={`tel:${selectedPostForModal.contact_info.replace(/[^0-9+]/g, '')}`}
                      className="contact-btn phone"
                    >
                      <Phone size={16} />
                      <span>اتصال هاتفي</span>
                    </a>
                    <a
                      href={`https://wa.me/2${selectedPostForModal.contact_info.replace(/[^0-9]/g, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="contact-btn whatsapp"
                    >
                      <MessageCircle size={16} />
                      <span>مراسلة واتساب</span>
                    </a>
                  </div>
                </div>
              )}

              {/* Direct Link Action */}
              <div style={{ display: 'flex', gap: '0.75rem', marginBlockStart: '0.5rem' }}>
                {selectedPostForModal.post_url ? (
                  <a
                    href={selectedPostForModal.post_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="action-btn-primary"
                    style={{ padding: '0.75rem' }}
                  >
                    <span>فتح البوست الأصلي على فيسبوك</span>
                    <ExternalLink size={16} />
                  </a>
                ) : selectedPostForModal.raw_discovered_url ? (
                  <a
                    href={selectedPostForModal.raw_discovered_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="action-btn-primary"
                    style={{ padding: '0.75rem' }}
                  >
                    <span>فتح البوست داخل الجروب العام</span>
                    <ExternalLink size={16} />
                  </a>
                ) : null}

                <button
                  type="button"
                  className="action-btn-secondary"
                  style={{ padding: '0.75rem 1.25rem' }}
                  onClick={() =>
                    copyToClipboard(
                      selectedPostForModal.post_url || selectedPostForModal.raw_discovered_url || '',
                      `modal_copy_${selectedPostForModal.id}`
                    )
                  }
                >
                  {copiedId === `modal_copy_${selectedPostForModal.id}` ? (
                    <>
                      <Check size={16} color="var(--emerald-600)" />
                      <span>تم النسخ</span>
                    </>
                  ) : (
                    <>
                      <Copy size={16} />
                      <span>نسخ الرابط</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 9. FAVORITES DRAWER MODAL */}
      {showFavoritesModal && (
        <div className="modal-backdrop" onClick={() => setShowFavoritesModal(false)}>
          <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <Heart size={22} color="var(--rose-600)" fill="var(--rose-600)" />
                <span>العقارات المحفوظة في المفضلة ({favoritePosts.length})</span>
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowFavoritesModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {favoritePosts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                  <Heart size={42} color="#cbd5e1" style={{ margin: '0 auto 0.75rem' }} />
                  <p style={{ fontWeight: 700, marginBlockEnd: '0.25rem' }}>لا توجد عقارات محفوظة بعد.</p>
                  <p style={{ fontSize: '0.85rem' }}>اضغط على أيقونة القلب في أي بطاقة عقار لحفظها والرجوع إليها بسهولة.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                  {favoritePosts.map((fav) => (
                    <div
                      key={fav.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.85rem 1rem',
                        background: 'var(--bg-subtle)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-color)',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 800, color: 'var(--brand-dark)' }}>
                          {fav.sub_area ? `شقة في ${fav.sub_area}` : `شقة في ${fav.area_mentioned || 'بنها'}`}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--emerald-600)', fontWeight: 800 }}>
                          {fav.price_egp ? `${fav.price_egp.toLocaleString('ar-EG')} ج.م / شهر` : 'السعر غير محدد'}
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                          type="button"
                          className="nav-btn primary"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem' }}
                          onClick={() => {
                            setSelectedPostForModal(fav);
                            setShowFavoritesModal(false);
                          }}
                        >
                          <Eye size={14} />
                          <span>عرض</span>
                        </button>
                        <button
                          type="button"
                          className="nav-btn"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem', color: 'var(--rose-600)' }}
                          onClick={() => toggleFavorite(fav.id)}
                        >
                          إزالة
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 10. IMPORT POST MODAL (Authorized User Input) */}
      {showImportPanel && (
        <div className="modal-backdrop" onClick={() => setShowImportPanel(false)}>
          <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <Plus size={22} color="var(--brand-primary)" />
                <span>استيراد منشور شقة عام من فيسبوك</span>
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowImportPanel(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleUserImportSubmit} className="modal-body">
              <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                يمكنك نسخ نص أي منشور تشاهده أثناء تصفحك لجروبات فيسبوك العامة ولصقه هنا ليقوم محرك التحليل باستخراج السعر والغرف والمساحة والمنطقة الفرعية وإضافتها فوريًا لقاعدة بياناتك.
              </p>

              <div className="search-input-group">
                <label>نص المنشور الأصلي (مطلوب) *</label>
                <textarea
                  rows={4}
                  className="search-field-input"
                  style={{ resize: 'vertical' }}
                  required
                  placeholder="مثال: شقة للإيجار في بنها منطقة الفلل 3 غرف وصالة مساحة 130م الدور الثالث الإيجار 4500 للتواصل 01012345678"
                  value={importText}
                  onChange={(e) => setImportText(e.target.value)}
                />
              </div>

              <div className="search-input-group">
                <label>رابط المنشور الأصلي في فيسبوك (اختياري)</label>
                <input
                  type="url"
                  className="search-field-input"
                  placeholder="https://www.facebook.com/groups/.../posts/..."
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="search-input-group">
                  <label>تاريخ النشر كما ظهر (اختياري)</label>
                  <input
                    type="text"
                    className="search-field-input"
                    placeholder="مثال: منذ ساعتين"
                    value={importDateText}
                    onChange={(e) => setImportDateText(e.target.value)}
                  />
                </div>
                <div className="search-input-group">
                  <label>اسم الجروب أو الصفحة (اختياري)</label>
                  <input
                    type="text"
                    className="search-field-input"
                    placeholder="مثال: عقارات بنها"
                    value={importGroupName}
                    onChange={(e) => setImportGroupName(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="search-action-btn"
                style={{ width: '100%', marginBlockStart: '0.5rem' }}
                disabled={isImporting}
              >
                {isImporting ? (
                  <>
                    <RefreshCw size={18} className="spin-icon" />
                    <span>جاري تحليل المنشور...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={18} />
                    <span>تحليل المنشور وإضافته للنتائج</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------
// HOUSELY PROPERTY CARD COMPONENT
// ----------------------------------------------------
interface PropertyCardProps {
  post: RentalPost;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  onOpenDetails: () => void;
  copiedId: string | null;
  onCopy: (text: string, key: string) => void;
}

function HouselyPropertyCard({
  post,
  isFavorite,
  onToggleFavorite,
  onOpenDetails,
  copiedId,
  onCopy,
}: PropertyCardProps) {
  const isVerifiedDate = post.date_verification_status === 'verified_in_range';
  const hasDirectPostUrl = Boolean(post.url_verified && post.post_url);
  const hasInGroupLocator = Boolean(
    !hasDirectPostUrl && post.raw_discovered_url && post.raw_discovered_url.includes('/search/?q=')
  );
  const shareableUrl = post.post_url || post.raw_discovered_url || post.group_or_page_url || '';

  return (
    <article className="housely-card">
      <div>
        {/* Top Visual Banner */}
        <div className={`card-visual-banner ${!isVerifiedDate ? 'unverified-banner' : ''}`}>
          <div className="banner-top-row">
            <div className="banner-tags">
              {isVerifiedDate ? (
                <span className="banner-pill verified">
                  <CheckCircle2 size={12} />
                  <span>تاريخ مؤكد</span>
                </span>
              ) : (
                <span className="banner-pill unverified">
                  <Clock size={12} />
                  <span>تاريخ غير مؤكد</span>
                </span>
              )}

              {hasDirectPostUrl && (
                <span className="banner-pill direct-link">
                  <span>🔗 بوست مباشر</span>
                </span>
              )}

              {post.possible_duplicate_of_id && (
                <span className="banner-pill duplicate">
                  <span>قد يكون مكررًا</span>
                </span>
              )}
            </div>

            <button
              type="button"
              className={`card-favorite-btn ${isFavorite ? 'favorited' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggleFavorite();
              }}
              title={isFavorite ? 'إزالة من المفضلة' : 'حفظ في المفضلة'}
            >
              <Heart size={16} fill={isFavorite ? '#e11d48' : 'none'} />
            </button>
          </div>

          <div className="banner-price-row">
            <div className="banner-price-tag">
              <span className="amount">
                {post.price_egp ? post.price_egp.toLocaleString('ar-EG') : 'غير مذكور'}
              </span>
              <span className="period">{post.price_egp ? 'ج.م / شهر' : ''}</span>
            </div>

            <div className="banner-area-pill">
              <MapPin size={12} />
              <span>{post.sub_area || post.area_mentioned || 'بنها'}</span>
            </div>
          </div>
        </div>

        {/* Card Body */}
        <div className="card-body">
          <div className="card-title-row">
            <h5 className="card-title">
              شقة للإيجار {post.sub_area ? `في ${post.sub_area}` : `بمدينة ${post.area_mentioned || 'بنها'}`}
            </h5>
          </div>

          {/* Specs Bar with Icons */}
          <div className="card-features-bar">
            <span className="feature-spec-pill">
              <Bed size={15} color="var(--brand-primary)" />
              <span>{post.rooms_count ? `${post.rooms_count} غرف` : 'غير محدد'}</span>
            </span>

            <span className="spec-dot" />

            <span className="feature-spec-pill">
              <Bath size={15} color="var(--brand-primary)" />
              <span>{post.bathrooms_count ? `${post.bathrooms_count} حمام` : 'غير محدد'}</span>
            </span>

            <span className="spec-dot" />

            <span className="feature-spec-pill">
              <Maximize2 size={15} color="var(--brand-primary)" />
              <span>{post.area_sqm ? `${post.area_sqm} م²` : 'غير محدد'}</span>
            </span>

            {post.furnishing_status && (
              <>
                <span className="spec-dot" />
                <span className="feature-spec-pill">
                  <Armchair size={15} color="var(--emerald-600)" />
                  <span>{post.furnishing_status}</span>
                </span>
              </>
            )}
          </div>

          {/* Text Excerpt */}
          <p className="card-snippet">{post.original_text}</p>

          {/* Publisher & Meta Row */}
          <div className="card-publisher-meta">
            <div className="publisher-info">
              <div className="publisher-avatar">
                {post.group_or_page_name ? post.group_or_page_name.charAt(0) : 'ف'}
              </div>
              <span>{post.group_or_page_name || post.source_name}</span>
            </div>

            <div className="time-badge">
              {post.published_at_raw || (post.published_at ? formatCairoDateTime(post.published_at) : 'تاريخ غير مؤكد')}
            </div>
          </div>
        </div>
      </div>

      {/* Card Action Footer */}
      <div className="card-actions-footer">
        {hasDirectPostUrl && post.post_url ? (
          <a
            href={post.post_url}
            target="_blank"
            rel="noopener noreferrer"
            className="action-btn-primary"
          >
            <span>فتح البوست المباشر</span>
            <ExternalLink size={14} />
          </a>
        ) : hasInGroupLocator && post.raw_discovered_url ? (
          <a
            href={post.raw_discovered_url}
            target="_blank"
            rel="noopener noreferrer"
            className="action-btn-primary"
          >
            <span>البوست داخل الجروب</span>
            <ExternalLink size={14} />
          </a>
        ) : post.group_or_page_url ? (
          <a
            href={post.group_or_page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="action-btn-primary"
          >
            <span>فتح الجروب العام</span>
            <ExternalLink size={14} />
          </a>
        ) : null}

        <button
          type="button"
          className="action-btn-secondary"
          onClick={onOpenDetails}
          title="معاينة تفاصيل الإعلان والتواصل"
        >
          <Eye size={16} />
        </button>

        {shareableUrl && (
          <button
            type="button"
            className="action-btn-secondary"
            onClick={() => onCopy(shareableUrl, `card_copy_${post.id}`)}
            title="نسخ رابط الإعلان"
          >
            {copiedId === `card_copy_${post.id}` ? (
              <Check size={16} color="var(--emerald-600)" />
            ) : (
              <Copy size={16} />
            )}
          </button>
        )}
      </div>
    </article>
  );
}

// ----------------------------------------------------
// POSTS TABLE VIEW COMPONENT
// ----------------------------------------------------
function PostsTableView({
  posts,
  favoriteIds,
  onToggleFavorite,
  onOpenDetails,
  copiedId,
  onCopy,
}: {
  posts: RentalPost[];
  favoriteIds: string[];
  onToggleFavorite: (id: string) => void;
  onOpenDetails: (post: RentalPost) => void;
  copiedId: string | null;
  onCopy: (text: string, key: string) => void;
}) {
  return (
    <div className="table-responsive">
      <table className="housely-table">
        <thead>
          <tr>
            <th>حفظ</th>
            <th>العقار والنص</th>
            <th>المنطقة / الحي</th>
            <th>السعر الشهري</th>
            <th>المواصفات</th>
            <th>تاريخ النشر الأصلي</th>
            <th>المصدر</th>
            <th>الإجراءات</th>
          </tr>
        </thead>
        <tbody>
          {posts.map((post) => {
            const hasDirectPostUrl = Boolean(post.url_verified && post.post_url);
            const hasInGroupLocator = Boolean(
              !hasDirectPostUrl && post.raw_discovered_url && post.raw_discovered_url.includes('/search/?q=')
            );
            const shareableUrl = post.post_url || post.raw_discovered_url || post.group_or_page_url || '';
            const isFav = favoriteIds.includes(post.id);

            return (
              <tr key={post.id}>
                <td>
                  <button
                    type="button"
                    style={{
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      color: isFav ? 'var(--rose-600)' : 'var(--text-subtle)',
                    }}
                    onClick={() => onToggleFavorite(post.id)}
                  >
                    <Heart size={18} fill={isFav ? '#e11d48' : 'none'} />
                  </button>
                </td>
                <td style={{ maxInlineSize: '360px' }}>
                  <div style={{ fontWeight: 700, marginBlockEnd: '0.25rem', color: 'var(--brand-dark)' }}>
                    {post.sub_area ? `شقة في ${post.sub_area}` : `شقة في ${post.area_mentioned || 'بنها'}`}
                  </div>
                  <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {post.original_text}
                  </div>
                </td>
                <td>
                  <strong style={{ color: 'var(--brand-primary)' }}>{post.area_mentioned || 'بنها'}</strong>
                  {post.sub_area && <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{post.sub_area}</div>}
                </td>
                <td>
                  <span style={{ fontWeight: 800, color: 'var(--emerald-600)', fontFamily: 'var(--font-num)' }}>
                    {post.price_egp ? `${post.price_egp.toLocaleString('ar-EG')} ج.م` : 'غير مذكور'}
                  </span>
                </td>
                <td>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    <div>غرف: {post.rooms_count ?? '—'}</div>
                    <div>مساحة: {post.area_sqm ? `${post.area_sqm} م²` : '—'}</div>
                    <div>فرش: {post.furnishing_status || '—'}</div>
                  </div>
                </td>
                <td>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    {post.published_at_raw || (post.published_at ? formatCairoDateTime(post.published_at) : 'غير مؤكد')}
                  </div>
                </td>
                <td>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                    {post.group_or_page_name || post.source_name}
                  </div>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <button
                      type="button"
                      className="action-btn-secondary"
                      style={{ padding: '0.4rem 0.65rem' }}
                      onClick={() => onOpenDetails(post)}
                      title="عرض التفاصيل"
                    >
                      <Eye size={14} />
                    </button>

                    {hasDirectPostUrl && post.post_url ? (
                      <a
                        href={post.post_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="action-btn-primary"
                        style={{ padding: '0.4rem 0.65rem', fontSize: '0.8rem' }}
                      >
                        <ExternalLink size={14} />
                      </a>
                    ) : hasInGroupLocator && post.raw_discovered_url ? (
                      <a
                        href={post.raw_discovered_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="action-btn-primary"
                        style={{ padding: '0.4rem 0.65rem', fontSize: '0.8rem' }}
                      >
                        <ExternalLink size={14} />
                      </a>
                    ) : null}

                    {shareableUrl && (
                      <button
                        type="button"
                        className="action-btn-secondary"
                        style={{ padding: '0.4rem 0.65rem' }}
                        onClick={() => onCopy(shareableUrl, `tbl_copy_${post.id}`)}
                        title="نسخ الرابط"
                      >
                        {copiedId === `tbl_copy_${post.id}` ? (
                          <Check size={14} color="var(--emerald-600)" />
                        ) : (
                          <Copy size={14} />
                        )}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
