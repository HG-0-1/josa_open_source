import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const ROUTE_VIEW = { '/': 'hero', '/cbt': 'cbt', '/panic': 'panic', '/support': 'support' };
const VIEW_ROUTE = { hero: '/', cbt: '/cbt', panic: '/panic', support: '/support' };
const API_ROOT = '/api';

const SAFETY_PATTERN = /(انتحار|أنتحر|بدي\s+أنتحر|بدي\s+أموت|ما\s+بدي\s+أعيش|انهي\s+حياتي|إنهاء\s+حياتي|إيذاء\s+(النفس|نفسي)|أؤذي\s+نفسي|أجرح\s+نفسي|أقتل\s+نفسي|أفكر\s+ب(إيذاء|قتل)\s+نفسي|مش\s+آمن|مو\s+آمن|غير\s+آمن|خطر\s+مباشر)/i;

const thoughts = [
  { label: 'إحباط الإنجاز والعمل', text: 'أشعر بتشتت وإحباط شديد ولا أستطيع إنجاز المهام المطلوبة مني' },
  { label: 'خوف وفقدان السيطرة', text: 'خائف جداً من فقدان السيطرة والقلق يتزايد بشكل لا أستطيعه' },
];

const groundingTexts = {
  5: 'انظر حولك واسمح لعينيك بتحديد 5 أشياء واضحة في الغرفة وركز في ألوانها وملمسها البصري.',
  4: 'لاحظ 4 أشياء يمكنك لمسها حولك الآن (ملابسك، السطح الخشبي، أو يديك).',
  3: 'ركز وانتبه إلى 3 أصوات خفيفة في المحيط من حولك.',
  2: 'لاحظ رائحتين في الهواء حولك الآن.',
  1: 'خذ رشفة ماء دافئة أو لاحظ الطعم في فمك لترسيخ شعور التواجد الحاضر.',
};

const groundingSenses = [
  { value: 5, icon: 'fa-eye', label: '5 تراها' },
  { value: 4, icon: 'fa-hand', label: '4 تلمسها' },
  { value: 3, icon: 'fa-ear-listen', label: '3 تسمعها' },
  { value: 2, icon: 'fa-wind', label: '2 تشمها' },
  { value: 1, icon: 'fa-mug-hot', label: '1 تتذوقها' },
];

const breathPhases = {
  in: { label: 'شهيق عميق...', seconds: 4, scale: 1 },
  hold: { label: 'حبس النفس بهدوء...', seconds: 4, scale: 1.25 },
  out: { label: 'زفير بطيء ومريح...', seconds: 6, scale: 0.85 },
};

async function requestApi(path, body) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`${API_ROOT}/${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = data?.detail || data?.message || data?.error;
      const message = Array.isArray(detail)
        ? detail.map(issue => (Array.isArray(issue.loc) ? issue.loc.slice(1).join('.') : '')).filter(Boolean).join('، ') || 'قيمة غير صالحة'
        : typeof detail === 'string' ? detail : null;
      throw new Error(message || `تعذّر تنفيذ الطلب (${response.status}).`);
    }
    if (!data || typeof data !== 'object') throw new Error('وصل رد غير صالح من الخادم.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('انتهت مهلة الاتصال بالخادم. حاول مرة أخرى.');
    if (error instanceof TypeError) throw new Error('تعذّر الاتصال بالخادم. تأكد من تشغيل FastAPI على المنفذ 8000 ثم أعد المحاولة.');
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const view = ROUTE_VIEW[location.pathname] || 'hero';

  const [toast, setToast] = useState('');
  const requestId = useRef(0);

  const [thought, setThought] = useState('');
  const [cbtStage, setCbtStage] = useState('input');
  const [cbtResult, setCbtResult] = useState(null);
  const [cbtLoading, setCbtLoading] = useState(false);
  const [emergencyMessage, setEmergencyMessage] = useState('');

  const [breathing, setBreathing] = useState({ phase: 'in', count: 4 });
  const [breathingRunning, setBreathingRunning] = useState(true);
  const [groundingStep, setGroundingStep] = useState(5);
  const [groundingReply, setGroundingReply] = useState('');
  const [groundingCompleted, setGroundingCompleted] = useState(false);
  const groundingRequests = useRef(new Set());

  function notify(message) {
    setToast(message);
    window.setTimeout(() => setToast(''), 3200);
  }

  function navigateTo(nextView) {
    navigate(VIEW_ROUTE[nextView]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  useEffect(() => () => {
    requestId.current += 1;
  }, []);

  useEffect(() => {
    if (!breathingRunning) return undefined;
    const timer = window.setInterval(() => {
      setBreathing(current => {
        if (current.count > 1) return { ...current, count: current.count - 1 };
        if (current.phase === 'in') return { phase: 'hold', count: breathPhases.hold.seconds };
        if (current.phase === 'hold') return { phase: 'out', count: breathPhases.out.seconds };
        return { phase: 'in', count: breathPhases.in.seconds };
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [breathingRunning]);

  useEffect(() => {
    if (view !== 'panic') return;
    groundingRequests.current.clear();
    setGroundingStep(5);
    setGroundingReply('');
    setGroundingCompleted(false);
  }, [view]);

  function resetCbt() {
    requestId.current += 1;
    setThought('');
    setCbtStage('input');
    setCbtResult(null);
    setCbtLoading(false);
  }

  async function analyzeThought() {
    const cleaned = thought.trim();
    if (!cleaned || cbtLoading) return;
    const id = ++requestId.current;
    setCbtLoading(true);
    setCbtResult(null);

    if (SAFETY_PATTERN.test(cleaned)) {
      const message = 'سلامتك الآن هي الأولوية. لن نرسل هذه العبارة إلى نموذج إعادة الصياغة. تواصل مع شخص تثق به أو مع جهة مساندة الآن.';
      setEmergencyMessage(message);
      setCbtLoading(false);
      navigateTo('support');
      return;
    }

    try {
      const data = await requestApi('reframe', { text: cleaned });
      if (id !== requestId.current) return;
      if (data.emergency) {
        setEmergencyMessage(data.message || 'سلامتك الآن هي الأولوية. تواصل مع شخص تثق به أو مع جهة مساندة الآن.');
        navigateTo('support');
        return;
      }
      setCbtResult(data);
      setCbtStage('distortion');
    } catch (error) {
      notify(error.message || 'تعذّر الاتصال بالخادم. حاول مرة أخرى.');
    } finally {
      if (id === requestId.current) setCbtLoading(false);
    }
  }

  function buildAlternative() {
    setCbtStage('result');
  }

  async function chooseGrounding(step) {
    const requestStep = 6 - step;
    if (groundingCompleted || groundingRequests.current.has(requestStep)) return;
    groundingRequests.current.add(requestStep);
    setGroundingStep(step);
    try {
      const data = await requestApi('panic', { step: requestStep, text: `الخطوة ${requestStep}` });
      if (data.emergency) {
        setEmergencyMessage(data.message || data.reply || 'سلامتك الآن هي الأولوية. تواصل مع شخص تثق به أو مع جهة مساندة الآن.');
        navigateTo('support');
        return;
      }
      const reply = data.reply || data.message;
      if (reply) {
        setGroundingReply(reply);
      }
      if (data.completed === true) setGroundingCompleted(true);
    } catch {
      groundingRequests.current.delete(requestStep);
      // Keep the built-in grounding guidance when the local service is unavailable.
    }
  }

  function confirmEmergencyCall(number) {
    if (window.confirm(`هل تود إجراء الاتصال المباشر برقم الطوارئ ${number} الآن؟`)) {
      window.location.href = `tel:${number}`;
    }
  }

  const ring = breathPhases[breathing.phase];

  return <div className="min-h-screen flex flex-col justify-between selection:bg-moss-200 selection:text-moss-900 pb-24 md:pb-0">
    <header className="sticky top-0 z-40 bg-sand/90 backdrop-blur-md border-b border-moss-100/80 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          <button onClick={() => navigateTo('hero')} className="flex items-center gap-3 cursor-pointer group text-right">
            <span className="w-11 h-11 rounded-2xl bg-moss-700 text-sand flex items-center justify-center font-bold text-xl shadow-soft group-hover:scale-105 transition-transform">مـ</span>
            <span className="block">
              <span className="text-xl font-extrabold text-moss-900 block leading-tight">مُتَنَفَّس</span>
              <span className="text-[11px] text-moss-500 font-medium">مساعد التوازن النفسي التفاعلي</span>
            </span>
          </button>

          <nav className="hidden md:flex items-center gap-1 bg-sandLight p-1.5 rounded-full border border-moss-100/80" aria-label="التنقل الرئيسي">
            {[
              { id: 'hero', label: 'الرئيسية' },
              { id: 'cbt', label: 'مُخطط الأفكار (CBT)' },
              { id: 'panic', label: 'غرفة الهلع والتنفس' },
              { id: 'support', label: 'شبكة الدعم الطارئ' },
            ].map(item => <button key={item.id} onClick={() => navigateTo(item.id)} aria-current={view === item.id ? 'page' : undefined} className={`px-5 py-2 rounded-full text-xs font-bold transition-all ${view === item.id ? 'text-moss-900 bg-sand shadow-sm' : 'text-moss-700 hover:text-moss-900'}`}>{item.label}</button>)}
          </nav>

          <button onClick={() => navigateTo('panic')} className="bg-terracotta-500 hover:bg-terracotta-600 text-white px-5 py-2.5 rounded-full text-xs font-bold shadow-soft flex items-center gap-2 transition-all hover:scale-105">
            <span className="w-2 h-2 rounded-full bg-white animate-ping"/>
            <i className="fa-solid fa-wind text-xs" aria-hidden="true"></i>
            <span>طوارئ الهلع SOS</span>
          </button>
        </div>
      </div>

      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-sandLight/95 backdrop-blur-lg border-t border-moss-100 flex items-center justify-around py-3 px-2">
        {[
          { id: 'hero', icon: 'fa-house', label: 'الرئيسية', tone: 'text-moss-800' },
          { id: 'cbt', icon: 'fa-diagram-project', label: 'المخطط', tone: 'text-moss-800' },
          { id: 'panic', icon: 'fa-lungs', label: 'التنفس', tone: 'text-terracotta-600' },
          { id: 'support', icon: 'fa-phone-volume', label: 'الدعم', tone: 'text-moss-800' },
        ].map(item => <button key={item.id} onClick={() => navigateTo(item.id)} className={`flex flex-col items-center ${item.tone} text-[11px] font-bold`}>
          <i className={`fa-solid ${item.icon} mb-1 text-sm`} aria-hidden="true"></i> {item.label}
        </button>)}
      </div>
    </header>

    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-grow w-full relative">
      {view === 'hero' && <section className="app-view space-y-16">
        <div className="bg-gradient-to-br from-sandLight via-sand to-moss-50 rounded-3xl p-8 sm:p-14 border border-moss-100 shadow-soft relative overflow-hidden">
          <div className="max-w-2xl space-y-6 text-right relative z-10">
            <div className="inline-flex items-center gap-2 bg-moss-100 text-moss-900 text-xs font-bold px-4 py-1.5 rounded-full border border-moss-200">
              <i className="fa-solid fa-seedling text-moss-700" aria-hidden="true"></i>
              <span>مساحة شخصية هادئة للتفكر والاستعادة</span>
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-moss-900 leading-tight">تنَفَّس بعمق، <br/><span className="text-moss-700">وأعد ترتيب أفكارك.</span></h1>
            <p className="text-sm sm:text-base text-moss-700 leading-relaxed font-medium">تجربة إنسانية مصممة لمساعدتك على تفكيك المشاعر المعقدة، مواجهة نوبات الهلع والقلق، واستعادة التوازن من خلال أدوات المعالجة المعرفية التفاعلية.</p>
            <div className="flex flex-wrap items-center gap-4 pt-2">
              <button onClick={() => navigateTo('cbt')} className="bg-moss-700 hover:bg-moss-900 text-sand font-bold px-7 py-3.5 rounded-2xl shadow-soft transition-all flex items-center gap-3 text-sm"><span>افتح مخطط الأفكار الذهني</span><i className="fa-solid fa-arrow-left" aria-hidden="true"></i></button>
              <button onClick={() => navigateTo('panic')} className="bg-sandLight hover:bg-white text-moss-900 border border-moss-200 font-bold px-6 py-3.5 rounded-2xl transition-all flex items-center gap-2 text-sm"><i className="fa-solid fa-lungs text-terracotta-500" aria-hidden="true"></i><span>تمرين التنفس الفوري</span></button>
            </div>
          </div>
          <div className="absolute -left-12 -bottom-12 opacity-10 pointer-events-none text-moss-900"><i className="fa-solid fa-brain text-[280px]" aria-hidden="true"></i></div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <button onClick={() => navigateTo('cbt')} className="text-right bg-sandLight p-8 rounded-3xl border border-moss-100 shadow-soft hover:shadow-floating hover:-translate-y-1 transition-all cursor-pointer space-y-4">
            <span className="w-12 h-12 rounded-2xl bg-moss-100 text-moss-700 flex items-center justify-center text-xl"><i className="fa-solid fa-diagram-project" aria-hidden="true"></i></span>
            <h3 className="text-xl font-bold text-moss-900">مُخطط الأفكار التفاعلي</h3>
            <p className="text-xs text-moss-700 leading-relaxed">خريطة تفاعلية لتفكيك الأفكار المزعجة بصرياً، استخراج الأوهام المعرفية، وبناء بدائل واقعية بخطوات واضحة.</p>
            <span className="text-xs font-bold text-moss-700 flex items-center gap-2"><span>خوض التجربة</span><i className="fa-solid fa-arrow-left" aria-hidden="true"></i></span>
          </button>
          <button onClick={() => navigateTo('panic')} className="text-right bg-sandLight p-8 rounded-3xl border border-moss-100 shadow-soft hover:shadow-floating hover:-translate-y-1 transition-all cursor-pointer space-y-4">
            <span className="w-12 h-12 rounded-2xl bg-terracotta-100 text-terracotta-500 flex items-center justify-center text-xl"><i className="fa-solid fa-wave-square" aria-hidden="true"></i></span>
            <h3 className="text-xl font-bold text-moss-900">موجة التنفس والتهدئة</h3>
            <p className="text-xs text-moss-700 leading-relaxed">موجة بصرية حية تنقبض وتنبسط بإيقاع علمي مهدئ، مقترنة بتقنية عدّ الحواس الخمس للارتباط السريع بالواقع.</p>
            <span className="text-xs font-bold text-terracotta-600 flex items-center gap-2"><span>التنفس الآن</span><i className="fa-solid fa-arrow-left" aria-hidden="true"></i></span>
          </button>
          <button onClick={() => navigateTo('support')} className="text-right bg-sandLight p-8 rounded-3xl border border-moss-100 shadow-soft hover:shadow-floating hover:-translate-y-1 transition-all cursor-pointer space-y-4">
            <span className="w-12 h-12 rounded-2xl bg-sage/20 text-moss-800 flex items-center justify-center text-xl"><i className="fa-solid fa-shield-heart" aria-hidden="true"></i></span>
            <h3 className="text-xl font-bold text-moss-900">شبكة الدعم والمساندة</h3>
            <p className="text-xs text-moss-700 leading-relaxed">دليل موثوق ومباشر للاتصال بخطوط الدعم النفسي المجانية والطوارئ في الأردن عند حاجتك للتحدث مع أخصائي.</p>
            <span className="text-xs font-bold text-moss-700 flex items-center gap-2"><span>عرض الأرقام</span><i className="fa-solid fa-arrow-left" aria-hidden="true"></i></span>
          </button>
        </div>
      </section>}

      {view === 'cbt' && <section className="app-view space-y-8">
        <div className="bg-sandLight rounded-3xl p-6 sm:p-10 border border-moss-100 shadow-soft space-y-8">
          <div className="flex items-center justify-between gap-3 border-b border-moss-100 pb-6">
            <div>
              <span className="text-xs font-bold text-moss-600 uppercase tracking-wider block mb-1">CBT Mind Mapping</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-moss-900">مُخطط الأفكار المعرفي التفاعلي</h2>
            </div>
            <button onClick={resetCbt} className="text-xs font-bold text-moss-700 hover:text-moss-900 bg-sand px-4 py-2 rounded-xl transition-all whitespace-nowrap"><i className="fa-solid fa-rotate-right ml-1" aria-hidden="true"></i> إعادة بدء المخطط</button>
          </div>

          <div className="relative bg-sand border-2 border-dashed border-moss-200 rounded-3xl p-6 sm:p-10 min-h-[420px] flex flex-col justify-between overflow-hidden">
            {cbtStage === 'input' && <div className="space-y-4 max-w-xl mx-auto text-center">
              <div className="inline-block bg-moss-700 text-sand text-xs font-bold px-3 py-1 rounded-full">الخطوة 1: الفكرة التلقائية المزعجة</div>
              <h3 className="text-lg font-bold text-moss-900">ما هي الفكرة التي تضغط عليك حالياً؟</h3>
              <div className="relative">
                <textarea value={thought} onChange={event => setThought(event.target.value)} rows="3" placeholder="اكتب فكرتك هنا (مثال: أشعر أنني سأفشل في المقابلة القادمة ولن أجد فرصة عمل...)" className="w-full bg-sandLight border-2 border-moss-200 rounded-2xl p-4 text-sm text-moss-900 focus:outline-none focus:border-moss-700 transition-all resize-none shadow-sm"/>
              </div>
              <div className="flex flex-wrap justify-center gap-2 pt-2">
                {thoughts.map(preset => <button key={preset.label} onClick={() => setThought(preset.text)} className="text-[11px] font-bold bg-sandLight border border-moss-200 text-moss-800 px-3 py-1.5 rounded-full hover:bg-moss-100 transition-all">{preset.label}</button>)}
              </div>
              <button onClick={analyzeThought} disabled={!thought.trim() || cbtLoading} className="bg-moss-700 hover:bg-moss-900 disabled:opacity-50 disabled:cursor-not-allowed text-sand font-bold px-8 py-3.5 rounded-2xl shadow-soft text-sm transition-all">
                {cbtLoading ? <><i className="fa-solid fa-circle-notch fa-spin ml-2" aria-hidden="true"></i> نحلل الفكرة…</> : <>تحليل واستخراج التشوه المعرفي <i className="fa-solid fa-arrow-left mr-2" aria-hidden="true"></i></>}
              </button>
            </div>}

            {cbtStage === 'distortion' && cbtResult && <div className="space-y-6 max-w-2xl mx-auto text-right">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-terracotta-500 text-white flex items-center justify-center text-xs font-bold">2</div>
                <h4 className="font-bold text-moss-900 text-base">التشوه المعرفي المكتشف في فكرتك:</h4>
              </div>
              <div className="bg-terracotta-100/60 border border-terracotta-500/30 p-5 rounded-2xl space-y-2">
                <h5 className="font-bold text-terracotta-600 text-sm">{cbtResult.distortion}</h5>
                <p className="text-xs text-moss-800 leading-relaxed">{cbtResult.explanation || 'يمكننا فحص الفكرة بهدوء ومن دون أحكام.'}</p>
              </div>
              <button onClick={buildAlternative} className="w-full bg-moss-700 hover:bg-moss-900 text-sand font-bold py-3.5 rounded-2xl shadow-soft text-sm transition-all text-center">بناء المنظور البديل المتوازن <i className="fa-solid fa-wand-magic-sparkles mr-2" aria-hidden="true"></i></button>
            </div>}

            {cbtStage === 'result' && cbtResult && <div className="space-y-6 max-w-2xl mx-auto text-right">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-moss-700 text-white flex items-center justify-center text-xs font-bold">3</div>
                <h4 className="font-bold text-moss-900 text-base">الصياغة البديلة والمتوازنة:</h4>
              </div>
              <div className="bg-moss-50 border border-moss-200 p-6 rounded-2xl space-y-3">
                <p className="text-sm font-semibold text-moss-900 leading-relaxed">{cbtResult.reframed_thought}</p>
              </div>
              <div className="bg-sandLight border border-moss-200 p-4 rounded-2xl flex items-center gap-3">
                <i className="fa-solid fa-lightbulb text-amber-600 text-lg" aria-hidden="true"></i>
                <p className="text-xs text-moss-800 font-medium">{cbtResult.reality_check || 'الفكرة تعبّر عن شعورك الآن، لكنها لا تصف كل الحقيقة أو كل ما يمكن أن يحدث.'}</p>
              </div>
            </div>}
          </div>
        </div>
      </section>}

      {view === 'panic' && <section className="app-view space-y-8">
        <div className="bg-moss-900 text-sand rounded-3xl p-6 sm:p-12 shadow-floating relative overflow-hidden space-y-8">
          <div className="flex items-center justify-between gap-3 border-b border-moss-700 pb-6 relative z-10">
            <div>
              <span className="inline-block bg-terracotta-500/20 text-terracotta-100 text-xs font-bold px-3 py-1 rounded-full mb-2">غرفة التهدئة الفورية</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white">موجة التنفس والتهدئة الحيوية</h2>
            </div>
            <button onClick={() => navigateTo('hero')} className="text-xs font-bold text-moss-200 hover:text-white bg-moss-800 px-4 py-2 rounded-xl transition-all">إغلاق</button>
          </div>

          <div className="text-center py-6 space-y-8 relative z-10">
            <div className="relative w-64 h-64 mx-auto flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-emerald-400/40 bg-emerald-500/10 transition-transform duration-[4000ms] ease-in-out shadow-glow" style={{ transform: `scale(${ring.scale})` }}/>
              <div className="relative z-10 space-y-2">
                <div className="text-5xl font-black text-white tabular-nums">{breathing.count}</div>
                <div className="text-sm font-bold text-emerald-200">{ring.label}</div>
              </div>
            </div>

            <div className="flex justify-center gap-4">
              <button onClick={() => setBreathingRunning(running => !running)} className="bg-emerald-500 hover:bg-emerald-600 text-moss-900 font-extrabold px-8 py-3 rounded-full text-sm shadow-soft transition-all">{breathingRunning ? 'إيقاف مؤقت' : 'استئناف التنفس'}</button>
            </div>
          </div>

          <div className="mt-10 pt-8 border-t border-moss-700 space-y-6 relative z-10">
            <div className="text-center space-y-1">
              <h3 className="text-lg font-bold text-white">تقنية الارتباط بالواقع (5-4-3-2-1)</h3>
              <p className="text-xs text-moss-300">لاحظ ما حولك للرجوع للحظة الحالية واستعادة الأمان</p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {groundingSenses.map(sense => <button key={sense.value} onClick={() => chooseGrounding(sense.value)} disabled={groundingCompleted} className={`bg-moss-800/80 hover:bg-moss-700 border p-4 rounded-2xl text-center space-y-2 transition-all disabled:cursor-default disabled:opacity-60 ${groundingStep === sense.value ? 'border-emerald-400' : 'border-moss-600'}`}>
                <i className={`fa-solid ${sense.icon} text-2xl text-emerald-300`} aria-hidden="true"></i>
                <div className="text-xs font-bold">{sense.label}</div>
              </button>)}
            </div>

            <div className="bg-moss-800/60 p-4 rounded-2xl text-center">
              <p className="text-xs font-semibold text-emerald-200 leading-relaxed" role="status">{groundingCompleted ? (groundingReply || 'خلصت خطوات التمرين. خذ وقتك للراحة.') : groundingTexts[groundingStep]}</p>
            </div>
          </div>
        </div>
      </section>}

      {view === 'support' && <section className="app-view space-y-8">
        <div className="bg-sandLight rounded-3xl p-6 sm:p-10 border border-moss-100 shadow-soft space-y-8">
          <div className="border-b border-moss-100 pb-6">
            <span className="text-xs font-bold text-terracotta-600 uppercase tracking-wider block mb-1">Crisis Direct Dial Hub</span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-moss-900">شبكة الدعم والمساندة المباشرة</h2>
          </div>

          {emergencyMessage && <div role="alert" className="rounded-2xl border border-terracotta-500/40 bg-terracotta-100 p-4 text-xs leading-7 text-moss-900">
            <div className="mb-1 flex items-center gap-2 font-bold text-terracotta-600"><i className="fa-solid fa-shield-heart" aria-hidden="true"></i> الأولوية لسلامتك الآن</div>
            {emergencyMessage}
            <p className="mt-2 font-semibold">إذا كنت في خطر مباشر، اتصل بالطوارئ 911 الآن أو اطلب من شخص تثق به أن يبقى معك.</p>
          </div>}

          <p className="text-xs sm:text-sm text-moss-700 leading-relaxed">إذا كنت تمر بحالة طوارئ شديدة أو تحتاج للتحدث مع مختص نفسي مرخص فوراً، يمكنك الاتصال المباشر بالجهات الرسمية المعتمدة في الأردن:</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-moss-50 border border-moss-200 p-6 rounded-3xl space-y-4 flex flex-col justify-between">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="bg-moss-200 text-moss-900 text-[10px] font-bold px-3 py-1 rounded-full">استشارة مجانية وسرية</span>
                  <i className="fa-solid fa-headset text-moss-700 text-xl" aria-hidden="true"></i>
                </div>
                <h3 className="font-bold text-moss-900 text-lg">خط المساندة النفسية الوطني</h3>
                <p className="text-xs text-moss-700 leading-relaxed">إرشاد ومساندة نفسية مهنية مقدمة من مؤسسة نهر الأردن والجهات المعتمدة.</p>
              </div>
              <button onClick={() => confirmEmergencyCall('110')} className="w-full bg-moss-700 hover:bg-moss-900 text-sand font-bold py-3.5 rounded-2xl text-sm transition-all flex items-center justify-center gap-2"><i className="fa-solid fa-phone" aria-hidden="true"></i> الاتصال بـ 110</button>
            </div>

            <div className="bg-terracotta-100/50 border border-terracotta-500/30 p-6 rounded-3xl space-y-4 flex flex-col justify-between">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="bg-terracotta-500 text-white text-[10px] font-bold px-3 py-1 rounded-full">طوارئ 24/7</span>
                  <i className="fa-solid fa-truck-medical text-terracotta-600 text-xl" aria-hidden="true"></i>
                </div>
                <h3 className="font-bold text-moss-900 text-lg">طوارئ الدفاع المدني والإسعاف</h3>
                <p className="text-xs text-moss-700 leading-relaxed">للحالات الحادة والتدخل الطبي العاجل المتاح على مدار الساعة.</p>
              </div>
              <button onClick={() => confirmEmergencyCall('911')} className="w-full bg-terracotta-500 hover:bg-terracotta-600 text-white font-bold py-3.5 rounded-2xl text-sm transition-all flex items-center justify-center gap-2"><i className="fa-solid fa-phone" aria-hidden="true"></i> الاتصال بـ 911</button>
            </div>
          </div>
        </div>
      </section>}

      {toast && <div role="status" className="fixed bottom-40 left-1/2 z-50 -translate-x-1/2 rounded-full bg-moss-900 px-5 py-3 text-xs text-sand shadow-xl">{toast}</div>}
    </main>

    <footer className="bg-sandLight border-t border-moss-100 py-6 text-center text-xs text-moss-700">
      <p>مُتَنَفَّس © 2026 • منصة داعمة للتأمل والاتزان الذاتي ولا تغني عن الاستشارة الطبية المباشرة</p>
    </footer>
  </div>;
}
