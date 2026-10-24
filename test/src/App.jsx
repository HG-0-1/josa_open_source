import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, Eraser, Headphones, Mic, Pause, Play, Scale, ShieldAlert, ShieldCheck, Siren, Sparkles, Volume2, X, Phone } from 'lucide-react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import LandingPage from './LandingPage.jsx';

const ROUTE_TABS = { '/cbt': 'cbt', '/panic': 'sos', '/support': 'support' };
const TAB_ROUTES = { cbt: '/cbt', sos: '/panic', support: '/support' };

const demos = [
  { icon: '💻', title: 'سيناريو إحباط البرمجة', text: 'حاسس حالي غبي وما رح أفهم البرمجة بحياتي لأن الكود ما اشتغل اليوم' },
  { icon: '💼', title: 'سيناريو رفض المقابلة', text: 'أنا فاشل، رسبت بمقابلة العمل ومستحيل ألاقي وظيفة بحياتي' },
  { icon: '🛡️', title: 'سيناريو صمام الأمان الطارئ', emergency: true, text: 'أفكر بإيذاء نفسي ولا أشعر أنني بأمان الآن' },
];
const senses = [
  { icon: '👀', n: 5, title: 'أشياء تراها' }, { icon: '✋', n: 4, title: 'أشياء تلمسها' },
  { icon: '👂', n: 3, title: 'أصوات تسمعها' }, { icon: '🌿', n: 2, title: 'رائحة تشمها' },
  { icon: '💧', n: 1, title: 'شيء يمنحك أمانًا' },
];
const mockResults = [
  { distortion: 'التفكير الكارثي', explanation: 'تحويل تعثر واحد إلى توقّع أن كل شيء سيفشل.', reality_check: 'تعطّل الكود اليوم موقف مؤقت، ولا يثبت أنك غير قادر على التعلّم. الأخطاء جزء طبيعي من البرمجة.', reframed_thought: 'واجهتني عقبة اليوم، لكنها لا تحدد قدرتي. أستطيع أن أتعلم من الخطأ وأجرب خطوة صغيرة جديدة.' },
  { distortion: 'وسم الذات والتعميم', explanation: 'حكم واسع على نفسك انطلاقًا من تجربة واحدة.', reality_check: 'نتيجة مقابلة واحدة لا تختصر مهاراتك ولا تحدد فرصك القادمة. كل مقابلة تجربة مختلفة.', reframed_thought: 'لم تكن هذه المقابلة كما تمنيت، لكن ذلك لا يجعلني فاشلًا. أستطيع التعلّم والاستعداد للفرصة التالية.' },
];

async function fetchReframeAPI(text) {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/reframe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
    if (!response.ok) throw new Error('Local API unavailable');
    return await response.json();
  } catch {
    await new Promise(resolve => setTimeout(resolve, 600));
    if (/إيذاء|انتحار|أقتل|مش آمن|غير آمن/.test(text)) return { emergency: true, message: 'سلامتك الآن هي الأولوية. إذا كنت في خطر مباشر، اتصل بالطوارئ أو اطلب من شخص تثق به أن يبقى معك.' };
    return mockResults[/مقابلة|وظيف|فاشل/.test(text) ? 1 : 0];
  }
}

async function fetchPanicAPI(step, text) {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/panic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ step, text }) });
    if (!response.ok) throw new Error('Local API unavailable');
    return await response.json();
  } catch {
    await new Promise(resolve => setTimeout(resolve, 600));
    const sense = senses[Math.min(step, senses.length - 1)];
    return { reply: `أحسنت. خذ وقتك، والآن لاحظ ${sense.n} ${sense.title} بهدوء.` };
  }
}

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = ROUTE_TABS[location.pathname];
  const workspaceOpen = Boolean(activeTab);
  const [thoughtText, setThoughtText] = useState('');
  const [uiState, setUiState] = useState('idle');
  const [result, setResult] = useState(null);
  const [breathingPhase, setBreathingPhase] = useState(0);
  const [seconds, setSeconds] = useState(4);
  const [breathingOn, setBreathingOn] = useState(true);
  const [groundingStep, setGroundingStep] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [isPanicRecording, setIsPanicRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voiceReply, setVoiceReply] = useState('أنا معك، إنت بأمان. خذ نفس عميق مع الدائرة. شو الأشياء اللي شايفها حوليك؟');
  const [toast, setToast] = useState('');
  const speech = useRef(null);
  const panicSpeech = useRef(null);
  const request = useRef(0);
  const lengths = [4, 7, 8];
  const phases = ['شهيق بهدوء', 'احبس النفس', 'زفير طويل'];

  useEffect(() => {
    if (!breathingOn) return undefined;
    const timer = setInterval(() => setSeconds(current => {
      if (current > 1) return current - 1;
      setBreathingPhase(phase => (phase + 1) % 3);
      return lengths[(breathingPhase + 1) % 3];
    }), 1000);
    return () => clearInterval(timer);
  }, [breathingOn, breathingPhase]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [location.pathname]);

  useEffect(() => () => {
    request.current += 1;
    window.speechSynthesis?.cancel();
    speech.current?.stop();
    panicSpeech.current?.stop();
  }, []);

  function announce(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ar-SA'; utterance.rate = 0.9;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }

  function notify(text) {
    setToast(text);
    window.setTimeout(() => setToast(''), 3000);
  }

  async function reframe(text = thoughtText) {
    const cleaned = text.trim();
    if (!cleaned) return;
    const id = ++request.current;
    window.speechSynthesis?.cancel(); setIsSpeaking(false); setResult(null); setUiState('loading');
    const data = await fetchReframeAPI(cleaned);
    if (id !== request.current) return;
    setResult(data); setUiState(data.emergency ? 'triage' : 'result');
    if (data.emergency) navigate(TAB_ROUTES.support);
  }

  function startMic(target) {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) { notify('الإملاء الصوتي غير متاح في هذا المتصفح. يمكنك الكتابة بدلًا منه.'); return; }
    const recognizer = new Recognition(); recognizer.lang = 'ar-JO'; recognizer.interimResults = false;
    recognizer.onresult = event => {
      const text = event.results[0][0].transcript;
      if (target === 'panic') sendPanic(text);
      else setThoughtText(previous => previous ? `${previous} ${text}` : text);
    };
    recognizer.onerror = () => { target === 'panic' ? setIsPanicRecording(false) : setIsRecording(false); notify('تعذّر التقاط الصوت. جرّب مرة أخرى.'); };
    recognizer.onend = () => { target === 'panic' ? setIsPanicRecording(false) : setIsRecording(false); };
    if (target === 'panic') { panicSpeech.current = recognizer; setIsPanicRecording(true); }
    else { speech.current = recognizer; setIsRecording(true); }
    recognizer.start();
  }

  async function sendPanic(text = 'محاكاة الخطوة') {
    const step = groundingStep + 1;
    const data = await fetchPanicAPI(step, text);
    const reply = data.reply || 'أنا معك. خذ نفسًا هادئًا.';
    setVoiceReply(reply); setGroundingStep(current => Math.min(current + 1, 4)); announce(reply);
  }

  function chooseDemo(demo) {
    setThoughtText(demo.text);
    if (demo.emergency) {
      request.current += 1;
      setResult({ emergency: true, message: 'سلامتك الآن هي الأولوية. إذا كنت في خطر مباشر، اتصل بالطوارئ أو اطلب من شخص تثق به أن يبقى معك.' });
      setUiState('triage');
      navigate(TAB_ROUTES.support);
    } else reframe(demo.text);
  }

  function openWorkspace(tab) {
    navigate(TAB_ROUTES[tab]);
  }

  function closeWorkspace() {
    navigate('/');
    if (uiState === 'triage') setUiState('idle');
  }

  function wipeSession() {
    request.current += 1; setThoughtText(''); setResult(null); setUiState('idle'); setGroundingStep(0);
    window.speechSynthesis?.cancel(); setIsSpeaking(false); setBreathingOn(true); setBreathingPhase(0); setSeconds(4);
    notify('تم تصفير الجلسة على هذا الجهاز.');
  }

  const progress = (lengths[breathingPhase] - seconds) / lengths[breathingPhase];
  const wave = <span className="wave flex h-4 items-end gap-0.5">{[1, 2, 3, 4, 5].map(n => <i key={n} className="block w-1 rounded bg-current" style={{ height: 4 + (n % 3) * 3 }} />)}</span>;

  return <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.35 }} className="min-h-screen">
    <header className="sticky top-0 z-50 min-h-20 w-full border-b border-[#234737]/10 bg-[#FBFAF6]/90 backdrop-blur-md sm:h-20">
      <div className="mx-auto flex min-h-20 max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-2 sm:h-full sm:flex-nowrap sm:px-6 sm:py-0">
        <div className="flex items-center gap-3"><div className="w-11 h-11 rounded-2xl bg-[#DDEFEA] border border-[#0D9488]/30 text-[#0D9488] font-bold text-xl flex items-center justify-center">م</div><div><span className="text-xl font-bold text-[#123B48] block leading-tight">مُتَنَفَّس</span><span className="inline-block mt-1 text-[11px] text-[#0D9488] font-medium bg-[#DDEFEA]/70 px-2.5 py-0.5 rounded-full border border-[#0D9488]/20">ذكاء اصطناعي محلي 100% آمن</span></div></div>
        <button onClick={() => openWorkspace('sos')} className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700 shadow-sm transition hover:bg-rose-100 sm:px-4 sm:py-2.5 sm:text-sm"><span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse"/><Siren size={16}/>مسار طوارئ الهلع (SOS)</button>
      </div>
    </header>
    <main className="w-full pb-16">
      {!workspaceOpen && location.pathname !== '/' && <Navigate to="/" replace />}
      {!workspaceOpen && location.pathname === '/' && <LandingPage onOpen={openWorkspace} />}
      {false && !workspaceOpen && location.pathname === '/' && <>
      <section className="max-w-4xl mx-auto px-6 pt-12 pb-8 text-center"><div className="inline-flex items-center gap-2 bg-white border border-[#123B48]/10 px-4 py-1.5 rounded-full text-xs text-[#123B48]/80 font-medium mb-6 shadow-sm">🌿 مساحتك الرقمية الخاصة للتفريغ واستعادة التوازن</div><h1 className="text-3xl sm:text-4xl font-extrabold text-[#123B48] leading-tight mb-4">صحتك النفسية بأمان، بأدوات مفتوحة وخصوصية مطلقة</h1><p className="text-base sm:text-lg text-[#123B48]/70 max-w-2xl mx-auto leading-relaxed">منصة داعمة تجمع بين تقنيات العلاج السلوكي المعرفي (CBT) وإسعاف نوبات التوتر بالصوت والتنفس. كافة المعالجات تتم على جهازك محلياً دون إرسال بياناتك لأي جهة.</p></section>
      <section className="max-w-6xl mx-auto px-6 py-6 w-full"><div className="flex items-center justify-between mb-6"><h2 className="text-lg font-bold text-[#123B48]">الأقسام والخدمات</h2><span className="text-xs text-[#123B48]/60">اختر القسم الذي تحتاجه لبدء الجلسة</span></div><div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ServiceCard active={workspaceOpen && activeTab === 'cbt'} onClick={() => openWorkspace('cbt')} icon="💡" title="عيادة الأفكار (CBT)" description="تفكيك التشوهات المعرفية (التفكير الكارثي، التهويل، ولوم الذات) وإعادة صياغتها بطريقة موضوعية مريحة." action="دخول العيادة ←" tone="teal" />
        <ServiceCard active={workspaceOpen && activeTab === 'sos'} onClick={() => openWorkspace('sos')} icon="🫁" title="مسعف الهلع والتأريض" description="غرفة طوارئ مخصصة لتهدئة تسارع الأنفاس والنبض عبر بروتوكول 5-4-3-2-1 الصوتي وتنظيم التنفس التفاعلي." action="بدء الإسعاف الفوري ←" tone="rose" />
        <ServiceCard active={workspaceOpen && activeTab === 'support'} onClick={() => openWorkspace('support')} icon="🛡️" title="الدعم المتخصص والأمان" description="أرقام الدعم الوطني المعتمدة وخطوط المساندة المجانية في الأردن للتعامل مع الأزمات الحادة بأمان ومسؤولية." action="عرض خطوط المساندة ←" tone="deep" />
      </div></section>
      </>}

    {workspaceOpen && <motion.section key={activeTab} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="relative mx-auto w-full max-w-4xl scroll-mt-24 rounded-2xl border border-[#123B48]/10 bg-white/65 px-6 py-8 shadow-sm">
      <button onClick={closeWorkspace} className="absolute top-8 left-6 z-10 bg-[#FAF8F4] hover:bg-[#DDEFEA]/60 text-[#123B48] px-4 py-2 rounded-xl text-xs font-semibold transition inline-flex items-center gap-2">العودة إلى الرئيسية <X size={14}/></button>
      <div className="pt-10">{activeTab === 'support' ? <SupportPanel emergencyMessage={uiState === 'triage' ? result?.message : ''} /> : activeTab === 'cbt' ? <section className="space-y-6">
      <article className="space-y-5 rounded-2xl border border-[#123B48]/10 bg-white p-6 shadow-sm sm:p-8"><div className="mb-5"><div className="text-lg font-bold">عيادة إعادة صياغة الأفكار</div><p className="mt-1 text-sm leading-6 text-[#78908A]">اكتب أو تحدث بما يضغط عليك الآن ليقوم النموذج بتفكيكه بهدوء.</p></div>
        <div><textarea value={thoughtText} onChange={event => setThoughtText(event.target.value)} onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') reframe(); }} rows="5" placeholder="ما الفكرة التي تود النظر إليها من جديد؟" className="min-h-[120px] w-full resize-none rounded-2xl border border-[#123B48]/15 bg-[#FAF8F4] p-4 text-sm text-[#123B48] outline-none transition placeholder:text-[#9AAFA9] focus:border-[#0D9488] focus:ring-4 focus:ring-[#0D9488]/10"/></div>
        <div className="mt-4 flex flex-wrap items-center gap-2"><div className="text-xs text-[#123B48]/60">تجربة سريعة:</div><div className="flex flex-wrap items-center gap-2">{demos.map(demo => <button key={demo.title} onClick={() => chooseDemo(demo)} className="rounded-lg border border-[#123B48]/10 bg-[#FAF8F4] px-3 py-1.5 text-xs font-medium text-[#56736F] transition hover:border-[#0D9488]/30 hover:bg-[#DDEFEA]">{demo.icon} {demo.title}</button>)}</div></div>
        <div className="flex flex-col gap-3 sm:flex-row"><button disabled={!thoughtText.trim() || uiState === 'loading'} onClick={() => reframe()} className="flex-1 rounded-xl bg-[#0D9488] px-6 py-3.5 text-sm font-bold text-white transition hover:bg-[#123B48] disabled:opacity-45">{uiState === 'loading' ? 'نعيد ترتيب الفكرة…' : 'تفكيك الفكرة وإعادة بنائها'}</button><button type="button" onClick={() => isRecording ? speech.current?.stop() : startMic('cbt')} className="flex items-center justify-center gap-2 rounded-xl bg-[#DDEFEA]/70 px-5 py-3.5 text-sm font-semibold text-[#123B48] transition hover:bg-[#DDEFEA]">{isRecording ? <>{wave} جارٍ الاستماع</> : <><Mic size={16}/> تحدث بفكرتك</>}</button></div><p className="text-center text-[10px] text-[#9AAFA9]">تُرسل إلى الخدمة المحلية عند توفرها، وإلا تُستخدم استجابة تجريبية.</p>
      </article>

      {uiState === 'result' && result && <AnimatePresence mode="wait"><motion.article key="result" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4 rounded-2xl border border-[#123B48]/10 bg-white p-6 shadow-sm sm:p-8"><div className="rounded-2xl border border-[#E6B68A] bg-[#E6B68A]/20 p-4"><div className="text-xs font-bold text-[#9a704c]">التشوه المكتشف</div><div className="mt-2 font-bold text-[#123B48]">{result.distortion || 'تعميم الفكرة'}</div><p className="mt-1 text-xs leading-6 text-[#765639]">{result.explanation || 'يمكننا فحص الفكرة بهدوء ومن دون أحكام.'}</p></div><div className="rounded-2xl border border-[#123B48]/10 bg-[#FAF8F4] p-4"><div className="mb-2 text-xs font-bold text-[#123B48]">الحقيقة الموضوعية</div><p className="text-sm leading-7 text-[#56736F]">{result.reality_check || 'الفكرة تعبّر عن شعورك الآن، لكنها لا تصف كل الحقيقة أو كل ما يمكن أن يحدث.'}</p></div><div className="rounded-2xl border border-[#0D9488]/40 bg-[#DDEFEA]/70 p-5"><div className="text-xs font-bold text-[#0D766F]">الفكرة البديلة الصحية</div><p className="mt-3 text-lg font-semibold leading-8 text-[#123B48]">“{result.reframed_thought || result.message}”</p><button onClick={() => isSpeaking ? window.speechSynthesis.cancel() : announce(result.reframed_thought || result.message)} className="mt-4 inline-flex items-center gap-2 rounded-xl border border-[#0D9488]/20 bg-white/80 px-4 py-2 text-xs font-semibold text-[#0D766F]">{isSpeaking ? <>{wave} إيقاف الصوت</> : <><Volume2 size={16}/> استمع بصوت هادئ</>}</button></div></motion.article></AnimatePresence>}
    </section> : <section className="w-full space-y-6"><article className="relative flex min-h-[480px] flex-col items-center justify-center overflow-hidden rounded-[32px] bg-[#123B48] px-6 py-10 text-center text-white shadow-[0_24px_70px_rgba(18,59,72,.2)]"><div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_45%,rgba(13,148,136,.4),transparent_52%),radial-gradient(ellipse_at_15%_85%,rgba(221,239,234,.15),transparent_35%)]"/><div className="relative mb-2 text-xs text-[#DDEFEA]/70">تنفّس على إيقاعك</div><div className="relative grid h-64 w-64 place-items-center sm:h-72 sm:w-72"><div className={`absolute inset-0 rounded-full border border-[#DDEFEA]/25 bg-[#DDEFEA]/5 ${breathingOn ? 'orb-hold' : ''}`}/><div className={`absolute inset-7 rounded-full border border-[#DDEFEA]/35 bg-[#0D9488]/10 ${breathingOn ? 'orb-inhale' : ''}`}/><div className={`absolute inset-14 rounded-full border border-[#DDEFEA]/40 bg-[#DDEFEA]/10 ${breathingOn ? 'orb-out' : ''}`}/><div className="absolute inset-[72px] grid place-items-center rounded-full bg-gradient-to-br from-[#DDEFEA]/25 to-[#0D9488]/30 shadow-[0_0_55px_rgba(13,148,136,.28)] backdrop-blur-md"><div><div className="text-5xl font-light tabular-nums">{breathingOn ? seconds : 'Ⅱ'}</div><div className="mt-2 text-sm text-[#DDEFEA]">{breathingOn ? phases[breathingPhase] : 'توقّف مؤقت'}</div></div></div><svg className="absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 100 100" aria-label="تقدم مرحلة التنفس"><circle cx="50" cy="50" r="48" fill="none" stroke="rgba(221,239,234,.14)" strokeWidth=".8"/><circle cx="50" cy="50" r="48" fill="none" stroke="#DDEFEA" strokeWidth="1" strokeDasharray="301.6" strokeDashoffset={301.6 * (1 - (breathingOn ? progress : 0))} strokeLinecap="round" style={{ transition: 'stroke-dashoffset .8s linear' }}/></svg></div><div className="relative mt-2 text-xs text-[#DDEFEA]/65">دورة تنفّس ٤–٧–٨</div><button onClick={() => setBreathingOn(on => !on)} className="relative mt-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-2 text-xs font-semibold text-[#DDEFEA]">{breathingOn ? <><Pause size={14}/> إيقاف مؤقت</> : <><Play size={14}/> استئناف التنفّس</>}</button></article>
      <div className="flex flex-col gap-5"><article className="rounded-2xl border border-[#123B48]/10 bg-white/80 p-5 shadow-[0_14px_45px_rgba(18,59,72,.05)] sm:p-6"><div className="flex items-start justify-between"><div><div className="text-base font-bold">عد إلى حواسك</div><p className="mt-1 text-xs text-[#78908A]">لاحظ ما حولك، خطوة واحدة في كل مرة.</p></div><span className="rounded-full bg-[#DDEFEA] px-3 py-1 text-[10px] font-bold text-[#0D766F]">{groundingStep + 1} / 5</span></div><div className="mt-5 grid grid-cols-5 gap-1.5">{senses.map((sense, index) => <button key={sense.n} onClick={() => setGroundingStep(index)} className={`flex flex-col items-center gap-1 rounded-2xl border p-2 transition ${groundingStep === index ? 'border-[#0D9488]/30 bg-[#DDEFEA] text-[#0D766F]' : 'border-transparent bg-[#FAF8F4] text-[#9AAFA9] hover:border-[#123B48]/10'}`}><span className="text-lg">{sense.icon}</span><span className="text-[9px] font-bold">{sense.n} {sense.title.split(' ')[1]}</span></button>)}</div><div className="mt-4 rounded-2xl bg-[#FAF8F4] p-4"><div className="mb-2 text-[10px] font-bold text-[#0D766F]">رسالة هادئة لك</div><p className="text-sm leading-7 text-[#56736F]">{voiceReply}</p></div><div className="mt-4 flex gap-2"><button onClick={() => isPanicRecording ? panicSpeech.current?.stop() : startMic('panic')} className={`flex flex-1 items-center justify-center gap-2 rounded-2xl px-4 py-3 text-xs font-bold ${isPanicRecording ? 'bg-rose-50 text-rose-700' : 'bg-[#0D9488] text-white hover:bg-[#123B48]'}`}>{isPanicRecording ? <>{wave} أستمع إليك</> : <><Mic size={16}/> تحدث للمسعف الصوتي</>}</button><button onClick={() => sendPanic('محاكاة الخطوة')} className="rounded-2xl border border-[#123B48]/10 bg-white px-4 py-3 text-xs font-bold text-[#56736F] hover:bg-[#DDEFEA]">محاكاة</button></div><button onClick={() => setGroundingStep(step => (step + 1) % 5)} className="mt-3 w-full py-2 text-xs font-semibold text-[#0D766F]">الخطوة التالية <ArrowLeft className="ms-1 inline" size={14}/></button></article><article className="rounded-2xl border border-[#123B48]/10 bg-[#DDEFEA]/65 p-5"><div className="font-bold"><Headphones className="me-1 inline" size={16}/> تذكير لطيف</div><p className="mt-2 text-sm leading-7 text-[#56736F]">إذا كان حبس النفس غير مريح، تنفّس بطريقتك الطبيعية. أوقف التمرين متى شئت.</p></article></div>
    </section>}</div></motion.section>}

    {!workspaceOpen && <footer className="mx-auto flex max-w-6xl flex-col justify-between gap-2 px-6 border-t border-[#123B48]/10 pt-5 text-[10px] leading-5 text-[#9AAFA9] sm:flex-row"><span>مُتَنَفَّس — مساحة للتأمل وإعادة التوازن.</span><span>المحتوى داعم للتأمل الذاتي ولا يغني عن المساعدة المتخصصة.</span></footer>}
    {toast && <div role="status" className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-full bg-[#123B48] px-5 py-3 text-xs text-white shadow-xl">{toast}</div>}
  </main></motion.div>;
}

function ServiceCard({ active, onClick, icon, title, description, action, tone }) {
  const accents = {
    teal: { icon: 'bg-[#DDEFEA] text-[#0D9488]', hover: 'hover:border-[#0D9488]', action: 'text-[#0D9488]' },
    rose: { icon: 'bg-rose-50 text-rose-600', hover: 'hover:border-rose-400', action: 'text-rose-600' },
    deep: { icon: 'bg-[#FAF8F4] border border-[#123B48]/15 text-[#123B48]', hover: 'hover:border-[#123B48]/40', action: 'text-[#123B48]' },
  }[tone];
  return <motion.button type="button" onClick={onClick} whileHover={{ y: -3 }} whileTap={{ scale: 0.99 }} className={`group flex min-h-64 flex-col justify-between rounded-2xl border bg-white p-6 text-right transition ${accents.hover} ${active ? 'border-[#0D9488] ring-2 ring-[#0D9488]/15 shadow-lg' : 'border-[#123B48]/10 hover:shadow-[0_12px_32px_rgba(35,71,55,.09)]'}`}>
    <span><span className={`mb-4 flex h-12 w-12 items-center justify-center rounded-xl text-2xl ${accents.icon}`}>{icon}</span><span className="mb-2 block text-lg font-bold text-[#123B48]">{title}</span><span className="mb-5 block text-sm leading-relaxed text-[#123B48]/70">{description}</span></span>
    <span className={`inline-flex items-center gap-1 text-xs font-bold transition group-hover:-translate-x-1 ${accents.action}`}>{action}</span>
  </motion.button>;
}

function SupportPanel({ emergencyMessage }) {
  return <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="w-full rounded-2xl border border-[#123B48]/10 bg-white/90 p-5 shadow-[0_18px_55px_rgba(18,59,72,.07)] backdrop-blur-xl sm:p-8">
    <div className="flex items-start justify-between gap-4">
      <div><div className="mb-3 grid h-11 w-11 place-items-center rounded-2xl bg-[#DDEFEA]/70 text-[#123B48]"><ShieldCheck size={22}/></div><h2 className="text-2xl font-bold text-[#123B48]">الخطوط الوطنية للدعم والمساندة</h2><p className="mt-2 text-sm leading-6 text-[#123B48]/70">جهات رسمية معتمدة لتقديم المساندة النفسية والإرشادية المتخصصة في الأردن</p></div>
    </div>

    {emergencyMessage && <div role="alert" className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm leading-7 text-rose-900"><div className="mb-1 flex items-center gap-2 font-bold"><ShieldAlert size={17}/> الأولوية لسلامتك الآن</div>{emergencyMessage}<p className="mt-2 font-semibold">إذا كنت في خطر مباشر، اتصل بالطوارئ 911 الآن أو اطلب من شخص تثق به أن يبقى معك.</p></div>}

    <div className="mt-6 grid gap-3">
      <article className="group flex flex-col items-start justify-between gap-4 rounded-2xl border border-[#123B48]/10 bg-[#FAF8F4] p-5 transition hover:border-[#0D9488]/40 hover:bg-[#DDEFEA]/30 sm:flex-row sm:items-center">
        <div><h3 className="font-bold text-base text-[#123B48]">خط المساندة النفسية الوطني (مجاني)</h3><p className="mt-1 text-xs text-[#123B48]/70">استشارات وإرشاد نفسي مهني سري</p><p className="mt-2 text-[11px] leading-5 text-[#56736F]">خط مؤسسة نهر الأردن للدعم النفسي والإرشاد الأسري.</p></div>
        <a href="tel:110" aria-label="اتصل بخط المساندة 110" className="inline-flex items-center gap-2 rounded-xl border border-[#0D9488]/30 bg-[#DDEFEA]/80 px-4 py-2 font-mono text-xl font-extrabold text-[#0D9488] transition group-hover:bg-[#0D9488] group-hover:text-white"><Phone size={17}/>110</a>
      </article>
      <article className="group flex flex-col items-start justify-between gap-4 rounded-2xl border border-[#123B48]/10 bg-[#FAF8F4] p-5 transition hover:border-rose-300 hover:bg-rose-50/40 sm:flex-row sm:items-center">
        <div><h3 className="font-bold text-base text-[#123B48]">طوارئ الإسعاف والدفاع المدني</h3><p className="mt-1 text-xs text-[#123B48]/70">للحالات الطبية الطارئة والإنقاذ الفوري</p><p className="mt-2 text-[11px] leading-5 text-[#56736F]">الرقم الموحد للطوارئ في الأردن، متاح على مدار الساعة.</p></div>
        <a href="tel:911" aria-label="اتصل بالطوارئ 911" className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 font-mono text-xl font-extrabold text-rose-700 transition group-hover:bg-rose-600 group-hover:text-white"><Phone size={17}/>911</a>
      </article>
    </div>

    <div className="mt-5 flex items-start gap-3 rounded-2xl border border-[#E6B68A]/25 bg-[#E6B68A]/20 p-4 text-xs leading-6 text-[#765639]"><ShieldCheck className="mt-1 shrink-0" size={17}/><p>خط 110 مجاني وسري. رقم الطوارئ 911 متاح على مدار الساعة للحالات العاجلة؛ عند وجود خطر مباشر، اتصل به فورًا.</p></div>
    <p className="mt-4 text-[10px] leading-5 text-[#78908A]">هذه المعلومات للتوجيه الأولي ولا تغني عن الرعاية الطبية المباشرة عند الحاجة.</p>
  </motion.section>;
}

export default App;
