import json
import re
import requests

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

CRITICAL_SAFETY_KEYWORDS_AR = [
    "انتحار", "انتحر", "اموت", "انهي حياتي", "اقتل نفسي",
    "اوذي نفسي", "مش طايق اعيش", "بدي ارتاح من الدنيا", "ما بدي اعيش"
]

CRITICAL_SAFETY_KEYWORDS_EN = [
    "suicide", "kill myself", "end my life", "want to die",
    "self harm", "hurt myself", "better off dead"
]

DISTORTIONS_MAP = {
    "Catastrophizing": {
        "ar": "التهويل وتوقع الأسوأ",
        "en": "Catastrophizing"
    },
    "Overgeneralization": {
        "ar": "التعميم الزائد",
        "en": "Overgeneralization"
    },
    "Labeling": {
        "ar": "وسم الذات ولوم النفس",
        "en": "Labeling & Self-Blame"
    },
    "All-or-Nothing": {
        "ar": "التفكير الثنائي (كل شيء أو لا شيء)",
        "en": "All-or-Nothing Thinking"
    },
    "Mind Reading": {
        "ar": "قراءة الأفكار والقفز للاستنتاجات",
        "en": "Mind Reading / Jumping to Conclusions"
    },
    "Balanced": {
        "ar": "تفكير واقعي متزن",
        "en": "Realistic & Balanced Thinking"
    }
}

def is_arabic(text: str) -> bool:
    return bool(re.search(r'[\u0600-\u06FF]', text))

def normalize_arabic(text: str) -> str:
    """توحيد الهمزات والألف لضمان دقة صمام الأمان"""
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ؤ', 'و', text)
    return text

def clean_json_response(raw_response: str) -> str:
    cleaned = re.sub(r'^```json\s*', '', raw_response.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'^```\s*', '', cleaned, flags=re.MULTILINE)
    return cleaned.rstrip('`').strip()

def check_safety(text: str) -> dict:
    norm_text = normalize_arabic(text)
    lower_text = text.lower()

    for kw in CRITICAL_SAFETY_KEYWORDS_AR:
        if kw in norm_text:
            return {
                "triggered": True,
                "helpline": "الخط الوطني الساخن للدعم النفسي (الأردن): 110 (أو 065538801)",
                "message": "سلامتك وحياتك هي أولويتنا المطلقة. حالتك تستدعي رعاية إنسانية متخصصة، يرجى التواصل مع فريق الدعم المتخصص فوراً وبشكل مجاني وسري."
            }

    for kw in CRITICAL_SAFETY_KEYWORDS_EN:
        if kw in lower_text:
            return {
                "triggered": True,
                "helpline": "Jordan National Mental Health Helpline: 110 (or 065538801)",
                "message": "Your safety and life are our absolute priority. Please connect immediately with professional human support (free and confidential)."
            }

    return {"triggered": False}


def reframe_thought(thought_text: str) -> dict:
    safety = check_safety(thought_text)
    arabic = is_arabic(thought_text)

    if safety["triggered"]:
        return {
            "emergency": True,
            "distortion": "أزمة نفسية طارئة" if arabic else "Acute Psychological Crisis",
            "reality_check": safety["message"],
            "reframed_thought": safety["helpline"]
        }

    if arabic:
        system_prompt = """
You are a clinical CBT expert analyzing Arabic user thoughts.
Classify the thought using ONE exact key from this list for "distortion_key":
["Catastrophizing", "Overgeneralization", "Labeling", "All-or-Nothing", "Mind Reading", "Balanced"]
(Use "Balanced" ONLY if the thought is completely normal, calm, and realistic).

Provide "reality_check" and "reframed_thought" in clear, natural, grammatically correct Arabic (maximum 12 words each).

Examples:
Thought: "رسبت بكويز اليوم، مستقبلي بالجامعة تدمر وضاع كل تعبي"
Output: {"distortion_key": "Catastrophizing", "reality_check": "نتيجة اختبار قصير واحد لا تحدد مستقبلك الجامعي ولا تلغي جهدك.", "reframed_thought": "سأراجع أخطائي في هذا الاختبار وأعوض في الامتحانات القادمة."}

Thought: "الكود طلع فيه بج وقت الديمو، أنا غبي وما بنفع أكون مبرمج"
Output: {"distortion_key": "Labeling", "reality_check": "ظهور الأخطاء البرمجية أمر طبيعي يواجه كل المبرمجين يومياً.", "reframed_thought": "الخطأ البرمجي فرصة للتعلم وتحسين الكود وليس مقياساً لذكائي."}

Thought: "قدمت على وظيفة ورفضوني، ولا شركة رح تقبلني بحياتي"
Output: {"distortion_key": "Overgeneralization", "reality_check": "رفضك في شركة واحدة لا يعني رفض جميع الشركات لك.", "reframed_thought": "سأطور مهاراتي وأستمر في التقديم على الفرص المناسبة."}

Thought: "إذا ما أخذنا المركز الأول بالهاكاثون، بكون كل شغلنا فاشل"
Output: {"distortion_key": "All-or-Nothing", "reality_check": "النجاح لا يقتصر على المركز الأول؛ الخبرة وبناء المشروع مكسب حقيقي.", "reframed_thought": "فخور بما أنجزناه كفريق، وسنستفيد من هذه التجربة مهما كانت النتيجة."}

Thought: "شفت الدكتور ما ابتسم، أكيد حاط علي وبده يرسبني"
Output: {"distortion_key": "Mind Reading", "reality_check": "ملامح وجه الدكتور لا تعني وجود نية مسبقة ضدك، والدرجات تعتمد على أدائك.", "reframed_thought": "سأركز على دراستي وأدائي بدلاً من افتراض نوايا سلبية غير مؤكدة."}

Thought: "عندي امتحان بكرة وصحيت بكير ودرست الشباتر المطلوبة وبدي أراجع"
Output: {"distortion_key": "Balanced", "reality_check": "هذه فكرة صحية ومنطقية تعكس استعداداً جيداً وتنظيماً للوقت.", "reframed_thought": "استمر في مراجعتك الهادئة وثق بمجهودك واستعدادك."}

Return valid JSON ONLY:
{
  "distortion_key": "...",
  "reality_check": "...",
  "reframed_thought": "..."
}
"""
    else:
        system_prompt = """
You are a certified CBT expert.
Classify the thought using ONE exact key from this list for "distortion_key":
["Catastrophizing", "Overgeneralization", "Labeling", "All-or-Nothing", "Mind Reading", "Balanced"]
(Use "Balanced" ONLY if the thought is realistic and healthy).

Examples:
Thought: "I got critical review on my pull request, I am definitely getting fired tomorrow"
Output: {"distortion_key": "Catastrophizing", "reality_check": "Code reviews are standard technical feedback, not an indication of dismissal.", "reframed_thought": "I will address the feedback objectively to improve the codebase."}

Thought: "I made a syntax error during the interview, I am so incompetent"
Output: {"distortion_key": "Labeling", "reality_check": "A single syntax error under pressure does not define your overall engineering skill.", "reframed_thought": "Everyone makes small mistakes; I will learn from it and prepare for the next round."}

Thought: "My manager looked tired, he must be completely disappointed in my work"
Output: {"distortion_key": "Mind Reading", "reality_check": "Someone looking tired reflects their energy level, not a hidden judgment of your work.", "reframed_thought": "I will focus on my tasks and ask for direct feedback if needed."}

Thought: "I am working on my project and taking a short break to drink coffee"
Output: {"distortion_key": "Balanced", "reality_check": "Taking short breaks is a healthy routine to maintain focus and productivity.", "reframed_thought": "Enjoy your coffee break and return to your project refreshed."}

Return valid JSON ONLY:
{
  "distortion_key": "...",
  "reality_check": "...",
  "reframed_thought": "..."
}
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": f"{system_prompt}\n\nThought: \"{thought_text}\"\nOutput:",
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 200
        }
    }

    try:
        res = requests.post(OLLAMA_API_URL, json=payload, timeout=25)
        res.raise_for_status()
        raw_content = clean_json_response(res.json().get("response", "{}"))
        data = json.loads(raw_content)

        raw_key = data.get("distortion_key", "Catastrophizing")
        # مطابقة المفتاح مع القاموس المعتمد لضمان عدم ظهور أي اسم غريب
        matched_key = "Catastrophizing"
        for valid_k in DISTORTIONS_MAP:
            if valid_k.lower() in raw_key.lower():
                matched_key = valid_k
                break

        lang_code = "ar" if arabic else "en"
        distortion_label = DISTORTIONS_MAP[matched_key][lang_code]

        return {
            "emergency": False,
            "distortion": distortion_label,
            "reality_check": data.get("reality_check", "المشاعر الحالية مؤقتة ولا تمثل حقيقة مطلقة." if arabic else "Current feelings are temporary and do not reflect absolute facts."),
            "reframed_thought": data.get("reframed_thought", "سأتعامل مع هذا الموقف بهدوء وخطوة بخطوة." if arabic else "I can take this one step at a time with clarity.")
        }
    except Exception as e:
        print(f"[CBT Reframe Error]: {e}")
        return {
            "emergency": False,
            "distortion": "التهويل وتوقع الأسوأ" if arabic else "Catastrophizing",
            "reality_check": "المشاعر السلبية مؤقتة وليست حكماً نهائياً على قدراتك." if arabic else "Feelings are temporary and not permanent facts.",
            "reframed_thought": "سأركز على ما يمكنني التحكم فيه بهدوء الآن." if arabic else "I will focus on what I can control right now."
        }


def panic_grounding(step: int, user_input: str, history: list = None) -> dict:
    safety = check_safety(user_input)
    arabic = is_arabic(user_input)

    if safety["triggered"]:
        prefix = "أنا معك، تنفس بهدوء.. " if arabic else "I am right here with you, breathe.. "
        return {
            "reply": f"{prefix}{safety['message']} {safety['helpline']}",
            "next_step": step,
            "is_completed": True,
            "emergency": True
        }

    context_str = ""
    if history and isinstance(history, list) and len(history) > 0:
        recent = history[-4:]
        context_str = "\n".join([f"- {item.get('role', 'speaker')}: {item.get('content', '')}" for item in recent])

    if arabic:
        prompt = f"""
أنت مسعف نفسي صوتي هادئ جداً ولطيف ترافق شخصاً يمر بنوبة هلع (تمرين 5-4-3-2-1).
تحدث بلهجة أردنية/شامية بيضاء حنونة ومطمئنة. الحد الأقصى: 18 كلمة فقط!

السياق السابق:
{context_str if context_str else "بداية الجلسة."}

الخطوة الحالية: {step} من 3
المستخدم قال: "{user_input}"

المطلوب حسب الخطوة:
- خطوة 1: طمئنه بذكر ما رآه، واطلب منه تسمية شيئين يلمسهما بيده الآن.
- خطوة 2: شجعه، واطلب منه تسمية صوت واحد يسمعه في المكان الآن.
- خطوة 3: طمئنه أن نبضه هدأ، واطلب منه أخذ نفس عميق وبطيء مع الدائرة.

اكتب جملة الرد المهدئ فقط بدون أي مقدمات:
"""
    else:
        prompt = f"""
You are a warm, calming crisis grounding voice assistant (5-4-3-2-1 method).
Maximum length: 18 words strictly. Speak directly to the user.

Context:
{context_str if context_str else "Start of session."}

Current step: {step} of 3
User said: "{user_input}"

Guidelines:
- Step 1: Validate what they saw, then ask them to touch 2 physical textures around them.
- Step 2: Validate progress, then ask for 1 ambient sound they hear right now.
- Step 3: Affirm safety, note their slowing pulse, and instruct one deep slow breath.

Reply with the soothing sentence only:
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 70
        }
    }

    try:
        res = requests.post(OLLAMA_API_URL, json=payload, timeout=20)
        res.raise_for_status()
        reply_text = res.json().get("response", "").strip().replace('"', '').replace("'", "")
        # إزالة أي مقدمات قد يضيفها النموذج
        reply_text = re.sub(r'^(الرد|المسعف|Reply|Assistant)\s*:\s*', '', reply_text).strip()

        next_step = step + 1
        is_completed = (next_step > 3)

        return {
            "reply": reply_text,
            "next_step": next_step if not is_completed else 3,
            "is_completed": is_completed,
            "emergency": False
        }
    except Exception as e:
        print(f"[Panic Grounding Error]: {e}")
        if arabic:
            fallbacks = {
                1: "ممتاز يا بطل.. إنت بأمان وكل شي رح يمر بخير. هسا سمّيلي شغلتين بتقدر تلمسهم بإيدك حوليك؟",
                2: "برافو عليك.. ركز بهدوء، شو في صوت واحد سامعه حوليك هسا؟",
                3: "رائع جداً.. نبضك بدأ يهدأ تماماً، خد نفس عميق مع الدائرة، إنت مسيطر وبأمان."
            }
        else:
            fallbacks = {
                1: "Great job. You are completely safe. Now gently name 2 things you can feel or touch around you.",
                2: "Well done, you are grounded. Now tell me 1 ambient sound you hear right now.",
                3: "Wonderful. Your heart rate is slowing down. Take a deep, gentle breath, you are in control."
            }
        return {
            "reply": fallbacks.get(step, "أنا معك، تنفس بهدوء، إنت بأمان وكل شيء رح يمر بخير." if arabic else "I am here with you, breathe slowly and gently."),
            "next_step": step + 1 if step < 3 else 3,
            "is_completed": (step >= 3),
            "emergency": False
        }