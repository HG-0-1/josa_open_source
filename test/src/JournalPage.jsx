import { useCallback, useEffect, useState } from 'react';

const moods = [
  { value: 'قلق', icon: '😟' },
  { value: 'حزن', icon: '😔' },
  { value: 'غضب', icon: '😠' },
  { value: 'فرح', icon: '😊' },
  { value: 'هدوء', icon: '😌' },
  { value: 'توتر', icon: '😣' },
];
const triggerCategories = ['دراسة', 'شغل', 'عائلة', 'علاقات', 'صحة', 'نوم', 'غير ذلك'];

async function journalApi(path, { method = 'GET', body, csrfToken } = {}) {
  const response = await fetch(`/api/${path}`, {
    method,
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'تعذر إكمال الطلب. حاول مرة أخرى.');
  }
  return data;
}

function dateLabel(value) {
  try {
    return new Date(value).toLocaleString('ar-JO', {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return value;
  }
}

function CountChart({ title, rows, emptyLabel }) {
  const maxCount = Math.max(1, ...rows.map(row => row.count));
  const populated = rows.some(row => row.count > 0);
  return <section className="journal-card" aria-label={title}>
    <h3 className="journal-section-title">{title}</h3>
    {!populated ? <p className="journal-muted">{emptyLabel}</p> : <div className="journal-chart-list" role="img" aria-label={title}>
      {rows.filter(row => row.count > 0).map(row => <div className="journal-chart-row" key={row.label}>
        <span className="journal-chart-label">{row.label}</span>
        <div className="journal-bar-track"><span style={{ width: `${Math.max(8, (row.count / maxCount) * 100)}%` }} /></div>
        <span className="journal-chart-count">{row.count}</span>
      </div>)}
    </div>}
  </section>;
}

function IntensityChart({ points }) {
  if (!points.length) return <section className="journal-card">
    <h3 className="journal-section-title">شدة الشعور المسجّلة ذاتياً</h3>
    <p className="journal-muted">ستظهر هنا تغيّرات الشدة بعد تسجيل يومياتك.</p>
  </section>;

  const width = 720;
  const height = 210;
  const paddingX = 28;
  const paddingY = 24;
  const chartPoints = points.map((point, index) => {
    const x = points.length === 1
      ? width / 2
      : paddingX + (index / (points.length - 1)) * (width - paddingX * 2);
    const y = height - paddingY - ((point.intensity - 1) / 4) * (height - paddingY * 2);
    return { ...point, x, y };
  });
  const linePoints = chartPoints.map(point => `${point.x},${point.y}`).join(' ');
  return <section className="journal-card">
    <h3 className="journal-section-title">شدة الشعور المسجّلة ذاتياً</h3>
    <p className="journal-muted">من 1 إلى 5، بحسب تقييمك أنت.</p>
    <svg className="journal-intensity-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`شدة الشعور المسجّلة ذاتياً: ${points.map(point => point.intensity).join('، ')}`}>
      <title>تغيّر شدة الشعور التي سجلتها بنفسك</title>
      {[1, 2, 3, 4, 5].map(level => {
        const y = height - paddingY - ((level - 1) / 4) * (height - paddingY * 2);
        return <g key={level}>
          <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} className="journal-chart-gridline" />
          <text x="8" y={y + 5} className="journal-chart-axis">{level}</text>
        </g>;
      })}
      {points.length > 1 && <polyline points={linePoints} className="journal-chart-line" />}
      {chartPoints.map((point, index) => <circle key={`${point.date}-${index}`} cx={point.x} cy={point.y} r="6" className="journal-chart-dot">
        <title>{`${point.date}: ${point.mood}، الشدة ${point.intensity} من 5`}</title>
      </circle>)}
    </svg>
    <p className="journal-chart-footnote">هذا وصف لتقييمك الذاتي، وليس مقياساً للصحة النفسية.</p>
  </section>;
}

export default function JournalPage() {
  const [user, setUser] = useState(null);
  const [csrfToken, setCsrfToken] = useState('');
  const [authLoading, setAuthLoading] = useState(true);
  const [authMode, setAuthMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [authError, setAuthError] = useState('');

  const [mood, setMood] = useState('');
  const [intensity, setIntensity] = useState(3);
  const [triggerCategory, setTriggerCategory] = useState('');
  const [triggerNote, setTriggerNote] = useState('');
  const [journalText, setJournalText] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  const [entries, setEntries] = useState([]);
  const [hasMoreEntries, setHasMoreEntries] = useState(false);
  const [loadingMoreEntries, setLoadingMoreEntries] = useState(false);
  const [insights, setInsights] = useState(null);
  const [days, setDays] = useState(7);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState('');
  const [aiConsent, setAiConsent] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState('');
  const [aiReflection, setAiReflection] = useState(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    let active = true;
    journalApi('auth/me').then(data => {
      if (!active) return;
      setUser(data.authenticated ? data.user : null);
      setCsrfToken(data.csrf_token || '');
    }).catch(error => {
      if (active) setAuthError(error.message);
    }).finally(() => {
      if (active) setAuthLoading(false);
    });
    return () => { active = false; };
  }, []);

  const refreshDashboard = useCallback(async () => {
    if (!user) return;
    setDashboardLoading(true);
    setDashboardError('');
    try {
      const [entryData, insightData] = await Promise.all([
        journalApi('journal/entries?limit=100&offset=0'),
        journalApi(`journal/insights?days=${days}`),
      ]);
      setEntries(entryData.entries);
      setHasMoreEntries(entryData.entries.length === entryData.limit);
      setInsights(insightData);
    } catch (error) {
      setDashboardError(error.message);
    } finally {
      setDashboardLoading(false);
    }
  }, [days, user]);

  async function loadMoreEntries() {
    if (loadingMoreEntries || !hasMoreEntries) return;
    setLoadingMoreEntries(true);
    setDashboardError('');
    try {
      const data = await journalApi(`journal/entries?limit=100&offset=${entries.length}`);
      setEntries(current => [...current, ...data.entries]);
      setHasMoreEntries(data.entries.length === data.limit);
    } catch (error) {
      setDashboardError(error.message);
    } finally {
      setLoadingMoreEntries(false);
    }
  }

  useEffect(() => {
    refreshDashboard();
  }, [refreshDashboard]);

  async function submitAuth(event) {
    event.preventDefault();
    setAuthError('');
    if (authMode === 'register' && password !== passwordConfirm) {
      setAuthError('تأكد أن كلمتي المرور متطابقتان.');
      return;
    }
    setAuthLoading(true);
    try {
      const data = await journalApi(`auth/${authMode === 'register' ? 'register' : 'login'}`, {
        method: 'POST',
        body: { email, password },
      });
      setUser(data.user);
      setCsrfToken(data.csrf_token);
      setPassword('');
      setPasswordConfirm('');
    } catch (error) {
      setAuthError(error.message);
    } finally {
      setAuthLoading(false);
    }
  }

  async function logout() {
    setAuthError('');
    try {
      await journalApi('auth/logout', { method: 'POST', body: {}, csrfToken });
      setUser(null);
      setCsrfToken('');
      setEntries([]);
      setHasMoreEntries(false);
      setInsights(null);
      setAiReflection(null);
      setAiConsent(false);
    } catch (error) {
      setAuthError(error.message);
    }
  }

  async function saveEntry(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setSaveMessage('');
    setDashboardError('');
    try {
      await journalApi('journal/entries', {
        method: 'POST',
        csrfToken,
        body: {
          mood,
          intensity,
          trigger_category: triggerCategory,
          trigger_note: triggerNote,
          journal_text: journalText,
        },
      });
      setMood('');
      setIntensity(3);
      setTriggerCategory('');
      setTriggerNote('');
      setJournalText('');
      setSaveMessage('انحفظت يوميتك. شكراً إنك خصصت وقت لنفسك.');
      await refreshDashboard();
    } catch (error) {
      setDashboardError(error.message);
    } finally {
      setSaving(false);
    }
  }

  async function deleteEntry(entry) {
    if (!window.confirm('متأكد إنك بدك تحذف هاليومية؟')) return;
    setDashboardError('');
    try {
      await journalApi(`journal/entries/${entry.id}`, { method: 'DELETE', csrfToken, body: {} });
      await refreshDashboard();
    } catch (error) {
      setDashboardError(error.message);
    }
  }

  async function askForReflection() {
    if (!aiConsent || aiLoading || !insights?.sufficient_data) return;
    setAiLoading(true);
    setAiError('');
    setAiReflection(null);
    try {
      const data = await journalApi('journal/ai-insights', {
        method: 'POST',
        csrfToken,
        body: { consent: true, days },
      });
      setAiReflection(data);
    } catch (error) {
      setAiError(error.message);
    } finally {
      setAiLoading(false);
    }
  }

  async function deleteAccount(event) {
    event.preventDefault();
    setDeleteError('');
    setDeleteLoading(true);
    try {
      await journalApi('auth/account', {
        method: 'DELETE',
        csrfToken,
        body: { password: deletePassword },
      });
      setUser(null);
      setCsrfToken('');
      setEntries([]);
      setHasMoreEntries(false);
      setInsights(null);
      setDeleteOpen(false);
      setPassword('');
      setDeletePassword('');
    } catch (error) {
      setDeleteError(error.message);
    } finally {
      setDeleteLoading(false);
    }
  }

  if (authLoading) return <section className="app-view journal-shell" aria-live="polite">
    <div className="journal-card journal-loading">عم نتحقق من جلسة الدخول…</div>
  </section>;

  if (!user) return <section className="app-view journal-shell">
    <div className="journal-auth-card">
      <span className="journal-eyebrow">مساحة خاصة في مُتَنَفَّس</span>
      <h1 className="journal-title">يومياتي ومشاعري</h1>
      <p className="journal-subtitle">سجّل دخولك حتى تتابع يومياتك الخاصة.</p>
      <div className="journal-auth-tabs" role="group" aria-label="نوع الحساب">
        <button type="button" aria-pressed={authMode === 'login'} onClick={() => { setAuthMode('login'); setAuthError(''); }}>تسجيل الدخول</button>
        <button type="button" aria-pressed={authMode === 'register'} onClick={() => { setAuthMode('register'); setAuthError(''); }}>إنشاء حساب</button>
      </div>
      <form className="journal-form" onSubmit={submitAuth}>
        <label className="journal-field">
          <span>البريد الإلكتروني</span>
          <input type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} dir="ltr" />
        </label>
        <label className="journal-field">
          <span>كلمة المرور</span>
          <input type="password" autoComplete={authMode === 'register' ? 'new-password' : 'current-password'} required minLength={authMode === 'register' ? 10 : 1} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} dir="ltr" />
          {authMode === 'register' && <small>استخدم 10 أحرف على الأقل.</small>}
        </label>
        {authMode === 'register' && <label className="journal-field">
          <span>تأكيد كلمة المرور</span>
          <input type="password" autoComplete="new-password" required minLength={10} maxLength={128} value={passwordConfirm} onChange={event => setPasswordConfirm(event.target.value)} dir="ltr" />
        </label>}
        {authError && <p className="journal-error" role="alert">{authError}</p>}
        <button className="journal-primary-button" type="submit" disabled={authLoading} aria-busy={authLoading}>
          {authLoading ? 'لحظة…' : authMode === 'register' ? 'إنشاء حساب خاص' : 'تسجيل الدخول'}
        </button>
      </form>
      <p className="journal-privacy-note">يتم حفظ يومياتك في قاعدة بيانات الخادم. لا تُرسل ملاحظاتك إلى أي نموذج ذكاء اصطناعي.</p>
    </div>
  </section>;

  const moodRows = insights?.mood_counts || [];
  const triggerRows = insights?.trigger_counts || [];
  const enoughForAi = (insights?.total_entries || 0) >= 5;

  return <section className="app-view journal-shell" dir="rtl">
    <div className="journal-dashboard-heading">
      <div>
        <span className="journal-eyebrow">مساحة خاصة إلك</span>
        <h1 className="journal-title">يومياتي ومشاعري</h1>
        <p className="journal-subtitle">مساحة خاصة تسجّل فيها مشاعرك، وتلاحظ الأنماط اللي بتتكرر في يومك.</p>
      </div>
      <div className="journal-account-actions">
        <span className="journal-account-email" dir="ltr">{user.email}</span>
        <button type="button" className="journal-secondary-button" onClick={logout}>تسجيل الخروج</button>
      </div>
    </div>

    {authError && <p className="journal-error" role="alert">{authError}</p>}
    {dashboardError && <p className="journal-error" role="alert">{dashboardError}</p>}

    <div className="journal-privacy-banner">
      <i className="fa-solid fa-lock" aria-hidden="true"></i>
      <p>يومياتك خاصة بحسابك. ما بنرسل نصوصها لموديل الذكاء الاصطناعي؛ والتأمل الآلي الاختياري يستخدم أعداداً وفئات فقط بعد موافقتك.</p>
    </div>

    <section className="journal-card journal-checkin">
      <div className="journal-section-heading">
        <div>
          <span className="journal-step-mark">تسجيل جديد</span>
          <h2 className="journal-section-title">كيف كان شعورك اليوم؟</h2>
        </div>
        <span className="journal-soft-icon" aria-hidden="true">🌱</span>
      </div>
      <form className="journal-form" onSubmit={saveEntry}>
        <fieldset className="journal-fieldset">
          <legend>اختار الشعور الأقرب إلك</legend>
          <div className="journal-mood-grid">
            {moods.map(option => <button type="button" key={option.value} aria-pressed={mood === option.value} onClick={() => setMood(option.value)} className={`journal-mood-option ${mood === option.value ? 'is-selected' : ''}`}>
              <span aria-hidden="true">{option.icon}</span><span>{option.value}</span>
            </button>)}
          </div>
        </fieldset>

        <fieldset className="journal-fieldset">
          <legend>قديش كان الشعور قوي؟ <span className="journal-muted">(من 1 إلى 5)</span></legend>
          <div className="journal-intensity-options" role="group" aria-label="شدة الشعور من 1 إلى 5">
            {[1, 2, 3, 4, 5].map(level => <button type="button" key={level} aria-pressed={intensity === level} onClick={() => setIntensity(level)} className={`journal-intensity-option ${intensity === level ? 'is-selected' : ''}`}>{level}</button>)}
          </div>
        </fieldset>

        <label className="journal-field">
          <span>شو ممكن يكون مرتبط بهالشعور؟</span>
          <select required value={triggerCategory} onChange={event => setTriggerCategory(event.target.value)}>
            <option value="">اختار فئة</option>
            {triggerCategories.map(category => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label className="journal-field">
          <span>ملاحظة قصيرة <span className="journal-muted">(اختياري)</span></span>
          <input maxLength={500} value={triggerNote} onChange={event => setTriggerNote(event.target.value)} placeholder="إذا بتحب، اكتب شي عن اللي أثر عليك…" />
        </label>
        <label className="journal-field">
          <span>اكتب أكثر عن يومك <span className="journal-muted">(اختياري)</span></span>
          <textarea rows={4} maxLength={5000} value={journalText} onChange={event => setJournalText(event.target.value)} placeholder="اكتب لنفسك، على راحتك…" />
        </label>
        {saveMessage && <p className="journal-success" role="status">{saveMessage}</p>}
        <button type="submit" className="journal-primary-button journal-save-button" disabled={!mood || !triggerCategory || saving} aria-busy={saving}>
          {saving ? 'عم نحفظ يوميتك…' : 'احفظ يوميتي'}
        </button>
      </form>
    </section>

    <section className="journal-section-block">
      <div className="journal-section-heading">
        <div>
          <span className="journal-step-mark">تسجيلاتك</span>
          <h2 className="journal-section-title">يومياتي الأخيرة</h2>
        </div>
        <span className="journal-entry-count">{entries.length} تسجيل</span>
      </div>
      {dashboardLoading && <p className="journal-muted" role="status">عم نحمّل يومياتك…</p>}
      {!dashboardLoading && entries.length === 0 && <div className="journal-empty-state">
        <span aria-hidden="true">📖</span>
        <h3>هاي أول صفحة بيومياتك</h3>
        <p>لما تسجل شعورك، رح تلاقيه هون وتقدر تتابع ملاحظاتك مع الوقت.</p>
      </div>}
      <div className="journal-entry-list">
        {entries.map(entry => <article className="journal-entry-card" key={entry.id}>
          <div className="journal-entry-topline">
            <div className="journal-entry-mood"><span aria-hidden="true">{moods.find(option => option.value === entry.mood)?.icon || '📝'}</span><strong>{entry.mood}</strong></div>
            <time dateTime={entry.created_at}>{dateLabel(entry.created_at)}</time>
          </div>
          <div className="journal-entry-meta">
            <span>الشدة: {entry.intensity} من 5</span>
            <span>الفئة: {entry.trigger_category}</span>
          </div>
          {entry.trigger_note && <p className="journal-entry-note">{entry.trigger_note}</p>}
          {entry.journal_text && <p className="journal-entry-text">{entry.journal_text}</p>}
          <button type="button" className="journal-delete-entry" onClick={() => deleteEntry(entry)}>حذف اليومية</button>
        </article>)}
      </div>
      {hasMoreEntries && <button type="button" className="journal-secondary-button journal-load-more" onClick={loadMoreEntries} disabled={loadingMoreEntries} aria-busy={loadingMoreEntries}>
        {loadingMoreEntries ? 'عم نحمل تسجيلات أقدم…' : 'تحميل تسجيلات أقدم'}
      </button>}
    </section>

    <section className="journal-section-block">
      <div className="journal-section-heading journal-analytics-heading">
        <div>
          <span className="journal-step-mark">من تسجيلاتك فقط</span>
          <h2 className="journal-section-title">نظرة على مشاعرك</h2>
        </div>
        <div className="journal-filter" role="group" aria-label="الفترة الزمنية للتحليل">
          {[7, 30].map(period => <button type="button" key={period} aria-pressed={days === period} onClick={() => { setDays(period); setAiReflection(null); setAiConsent(false); }} className={days === period ? 'is-selected' : ''}>{period} يوم</button>)}
        </div>
      </div>
      <p className="journal-muted">هاي ملخصات لما سجلته، وما بتحدد سبب شعورك.</p>
      {insights && <div className="journal-chart-grid">
        <CountChart title="تكرار المشاعر" rows={moodRows} emptyLabel="ما في تسجيلات بهاي الفترة لسه." />
        <CountChart title="الفئات اللي اخترتها" rows={triggerRows} emptyLabel="ما في فئات مسجلة بهاي الفترة لسه." />
        <IntensityChart points={insights.intensity_trend} />
      </div>}
    </section>

    <section className="journal-card journal-patterns">
      <span className="journal-step-mark">ملاحظات من تسجيلاتك</span>
      <h2 className="journal-section-title">أنماط ممكن تلاحظها</h2>
      <p className="journal-muted">التكرار أو التزامن بين فئة وشعور ما بيثبت إن واحد سبب الثاني.</p>
      {!insights?.sufficient_data && <p className="journal-pattern-note">لسه بدنا تسجيلات أكثر حتى نلاحظ نمط واضح</p>}
      {insights?.sufficient_data && <ul className="journal-pattern-list">
        {insights.pattern_notes.map((note, index) => <li key={index}>{note}</li>)}
      </ul>}
    </section>

    <section className="journal-card journal-ai-card">
      <span className="journal-step-mark">اختياري وبموافقتك</span>
      <h2 className="journal-section-title">تأمل بمساعدة الذكاء الاصطناعي</h2>
      <p className="journal-muted">إذا وافقت، رح نرسل أعداد المشاعر وفئات المحفزات للفترة المختارة إلى Ollama المحلي فقط، بدون الملاحظات أو نص يومياتك.</p>
      {insights && !enoughForAi && <p className="journal-pattern-note">لسه بدنا تسجيلات أكثر حتى نلاحظ نمط واضح (5 تسجيلات على الأقل).</p>}
      <label className="journal-consent">
        <input type="checkbox" checked={aiConsent} onChange={event => setAiConsent(event.target.checked)} />
        <span>أوافق على إرسال ملخص الأعداد والفئات فقط للحصول على تأمل اختياري.</span>
      </label>
      <button type="button" className="journal-primary-button" onClick={askForReflection} disabled={!aiConsent || !enoughForAi || aiLoading} aria-busy={aiLoading}>
        {aiLoading ? 'عم نراجع الملخص…' : 'ساعدني أفهم نمط يومي'}
      </button>
      {aiError && <p className="journal-error" role="alert">{aiError}</p>}
      {aiReflection && <div className="journal-reflection" aria-live="polite">
        <div className="journal-reflection-grid">
          <article className="journal-reflection-card">
            <span className="journal-reflection-icon" aria-hidden="true"><i className="fa-solid fa-lightbulb"></i></span>
            <h3>شو لاحظنا؟</h3>
            <p>{aiReflection.pattern}</p>
          </article>
          <article className="journal-reflection-card">
            <span className="journal-reflection-icon" aria-hidden="true"><i className="fa-solid fa-book-open"></i></span>
            <h3>شو بتقول يومياتك؟</h3>
            <p>{aiReflection.evidence}</p>
            <small>ملاحظة مبنية على التسجيلات اللي أضفتها.</small>
          </article>
          <article className="journal-reflection-card journal-reflection-suggestion">
            <span className="journal-reflection-icon" aria-hidden="true"><i className="fa-solid fa-seedling"></i></span>
            <h3>شو ممكن تجرّب؟</h3>
            <p>{aiReflection.suggestion}</p>
            <small>اقتراح اختياري، خذ منه اللي بناسبك.</small>
          </article>
        </div>
        <p className="journal-reflection-note">هذا تأمل غير سريري، والتزامن بين المشاعر والفئات ما يثبت إن واحد سبب الثاني.</p>
      </div>}
    </section>

    <section className="journal-delete-account">
      <div>
        <h2>حذف الحساب والبيانات</h2>
        <p>تقدر تحذف حسابك وكل اليوميات والجلسات المرتبطة فيه نهائياً.</p>
      </div>
      {!deleteOpen ? <button type="button" className="journal-danger-button" onClick={() => setDeleteOpen(true)}>حذف حسابي وكل يومياتي</button> : <form className="journal-delete-form" onSubmit={deleteAccount}>
        <label className="journal-field"><span>أكد الحذف بكلمة المرور</span><input type="password" autoComplete="current-password" required value={deletePassword} onChange={event => setDeletePassword(event.target.value)} dir="ltr" /></label>
        {deleteError && <p className="journal-error" role="alert">{deleteError}</p>}
        <div className="journal-inline-actions">
          <button type="submit" className="journal-danger-button" disabled={deleteLoading} aria-busy={deleteLoading}>{deleteLoading ? 'عم نحذف…' : 'أكد حذف الحساب'}</button>
          <button type="button" className="journal-secondary-button" onClick={() => { setDeleteOpen(false); setDeletePassword(''); setDeleteError(''); }}>إلغاء</button>
        </div>
      </form>}
    </section>
  </section>;
}
