"""
Minimal i18n helpers for backend-generated user-facing strings.

Design goals:
- Backward compatible: endpoints still return the same fields (`insights`, `confidence.reason`)
- Forward compatible: also return stable keys + params for client-side localization
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# NOTE: Keep keys stable; clients may rely on them.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        # Confidence reasons
        "confidence.no_cycle_data": "No cycle data available. Log at least 3 cycles for accurate predictions.",
        "confidence.insufficient_data": "Insufficient data. Log at least 3 cycles for better predictions.",
        "confidence.log_3_cycles_count": "Log at least 3 cycles for better predictions. Currently have {cycle_count} cycle(s).",
        "confidence.high_variance": (
            "High cycle variance (irregular cycles) reduces prediction confidence. "
            "Ovulation timing is less certain. More consistent logging will improve accuracy."
        ),
        "confidence.moderate_variance_count": (
            "Cycle variance is moderate; predictions are less certain. "
            "Based on {cycle_count} cycle(s)."
        ),
        "confidence.irregular_cv": "Cycles are irregular (variance: {cv}%). More data will improve accuracy.",
        "confidence.somewhat_irregular": "Cycles are somewhat irregular. Tracking more cycles will improve accuracy.",
        "confidence.good_regularity_count": "Based on {cycle_count} cycle(s) with good regularity.",
        "confidence.unable": "Unable to calculate confidence. Please log more periods.",

        # Stats insights (Cycle Statistics)
        "insight.log_3_cycles_more": "Log at least 3 cycles for more accurate predictions and insights.",
        "insight.regularity.irregular": "Your cycles show high variability. Consider consulting a healthcare provider if this pattern continues.",
        "insight.regularity.somewhat_irregular": "Your cycles show moderate variability. Continue tracking to identify patterns.",
        "insight.regularity.regular": "Your cycles are regular. Great job tracking!",
        "insight.regularity.very_regular": "Your cycles are very regular. Excellent consistency!",
        "insight.anomalies_count": "You have {anomaly_count} cycle(s) outside the normal range (21-45 days).",
        "insight.period_short": "Your period length ({period_days} days) is shorter than typical (3-8 days). This is detected from your logged data.",
        "insight.period_long": "Your period length ({period_days} days) is longer than typical (3-8 days). This is detected from your logged data.",
        "insight.avg_cycle_short": "Your average cycle length is shorter than typical. Consider discussing with a healthcare provider.",
        "insight.avg_cycle_long": "Your average cycle length is longer than typical. Consider discussing with a healthcare provider.",
        "insight.continue_tracking": "Continue tracking your periods for personalized insights.",
    },
    # Lightweight translations (can be refined later)
    "hi": {
        "confidence.no_cycle_data": "कोई चक्र डेटा उपलब्ध नहीं है। सटीक अनुमान के लिए कम से कम 3 चक्र लॉग करें।",
        "confidence.insufficient_data": "पर्याप्त डेटा नहीं है। बेहतर अनुमान के लिए कम से कम 3 चक्र लॉग करें।",
        "confidence.log_3_cycles_count": "बेहतर अनुमान के लिए कम से कम 3 चक्र लॉग करें। अभी {cycle_count} चक्र उपलब्ध हैं।",
        "confidence.high_variance": "चक्रों में अधिक उतार-चढ़ाव है, इसलिए अनुमान की विश्वसनीयता कम है। नियमित लॉगिंग से सुधार होगा।",
        "confidence.moderate_variance_count": "चक्रों में मध्यम उतार-चढ़ाव है; अनुमान कम निश्चित हैं। {cycle_count} चक्रों के आधार पर।",
        "confidence.irregular_cv": "चक्र अनियमित हैं (वैरिएंस: {cv}%). अधिक डेटा से सटीकता बढ़ेगी।",
        "confidence.somewhat_irregular": "चक्र कुछ हद तक अनियमित हैं। अधिक चक्र ट्रैक करने से सटीकता बढ़ेगी।",
        "confidence.good_regularity_count": "{cycle_count} चक्रों के आधार पर (अच्छी नियमितता)।",
        "confidence.unable": "विश्वसनीयता की गणना नहीं हो सकी। कृपया और पीरियड लॉग करें।",

        "insight.log_3_cycles_more": "अधिक सटीक अनुमान और इनसाइट्स के लिए कम से कम 3 चक्र लॉग करें।",
        "insight.regularity.irregular": "आपके चक्रों में अधिक उतार-चढ़ाव है। यदि यह जारी रहे तो डॉक्टर से परामर्श करें।",
        "insight.regularity.somewhat_irregular": "आपके चक्रों में मध्यम उतार-चढ़ाव है। पैटर्न समझने के लिए ट्रैक करते रहें।",
        "insight.regularity.regular": "आपके चक्र नियमित हैं। बहुत अच्छा!",
        "insight.regularity.very_regular": "आपके चक्र बहुत नियमित हैं। शानदार!",
        "insight.anomalies_count": "आपके {anomaly_count} चक्र सामान्य सीमा (21-45 दिन) से बाहर हैं।",
        "insight.period_short": "आपके पीरियड की अवधि ({period_days} दिन) सामान्य (3-8 दिन) से कम है।",
        "insight.period_long": "आपके पीरियड की अवधि ({period_days} दिन) सामान्य (3-8 दिन) से अधिक है।",
        "insight.avg_cycle_short": "आपका औसत चक्र सामान्य से छोटा है। आवश्यकता हो तो डॉक्टर से बात करें।",
        "insight.avg_cycle_long": "आपका औसत चक्र सामान्य से लंबा है। आवश्यकता हो तो डॉक्टर से बात करें।",
        "insight.continue_tracking": "व्यक्तिगत इनसाइट्स के लिए अपने पीरियड्स ट्रैक करते रहें।",
    },
    "gu": {
        "confidence.no_cycle_data": "ચક્ર ડેટા ઉપલબ્ધ નથી. સચોટ અંદાજ માટે ઓછામાં ઓછા 3 ચક્ર લૉગ કરો.",
        "confidence.insufficient_data": "પર્યાપ્ત ડેટા નથી. બહેતર અંદાજ માટે ઓછામાં ઓછા 3 ચક્ર લૉગ કરો.",
        "confidence.log_3_cycles_count": "બહેતર અંદાજ માટે ઓછામાં ઓછા 3 ચક્ર લૉગ કરો. હાલ {cycle_count} ચક્ર છે.",
        "confidence.high_variance": "ચક્રોમાં વધારે ફેરફાર હોવાથી અંદાજની વિશ્વસનીયતા ઓછી છે. નિયમિત લૉગિંગથી સુધારો થશે.",
        "confidence.moderate_variance_count": "ચક્રોમાં મધ્યમ ફેરફાર છે; અંદાજ ઓછા નિશ્ચિત છે. {cycle_count} ચક્રના આધારે.",
        "confidence.irregular_cv": "ચક્ર અનિયમિત છે (વેરિઅન્સ: {cv}%). વધુ ડેટાથી સચોટતા વધશે.",
        "confidence.somewhat_irregular": "ચક્ર થોડા અનિયમિત છે. વધુ ચક્ર ટ્રૅક કરવાથી સચોટતા વધશે.",
        "confidence.good_regularity_count": "{cycle_count} ચક્રના આધારે (સારી નિયમિતતા).",
        "confidence.unable": "વિશ્વસનીયતા ગણતરી થઈ નથી. કૃપા કરીને વધુ પિરિયડ લૉગ કરો.",

        "insight.log_3_cycles_more": "વધુ સચોટ અંદાજ અને ઇન્સાઇટ્સ માટે ઓછામાં ઓછા 3 ચક્ર લૉગ કરો.",
        "insight.regularity.irregular": "તમારા ચક્રોમાં વધારે ફેરફાર છે. જો આ ચાલુ રહે તો ડૉક્ટર સાથે વાત કરો.",
        "insight.regularity.somewhat_irregular": "તમારા ચક્રોમાં મધ્યમ ફેરફાર છે. પેટર્ન જોવા ટ્રૅક ચાલુ રાખો.",
        "insight.regularity.regular": "તમારા ચક્ર નિયમિત છે. સરસ કામ!",
        "insight.regularity.very_regular": "તમારા ચક્ર ખૂબ નિયમિત છે. ઉત્તમ!",
        "insight.anomalies_count": "તમારા {anomaly_count} ચક્ર સામાન્ય શ્રેણી (21-45 દિવસ) બહાર છે.",
        "insight.period_short": "તમારા પિરિયડની લંબાઈ ({period_days} દિવસ) સામાન્ય (3-8 દિવસ) કરતાં ઓછી છે.",
        "insight.period_long": "તમારા પિરિયડની લંબાઈ ({period_days} દિવસ) સામાન્ય (3-8 દિવસ) કરતાં વધુ છે.",
        "insight.avg_cycle_short": "તમારો સરેરાશ ચક્ર સામાન્ય કરતાં ટૂંકો છે. જરૂર હોય તો ડૉક્ટર સાથે ચર્ચા કરો.",
        "insight.avg_cycle_long": "તમારો સરેરાશ ચક્ર સામાન્ય કરતાં લાંબો છે. જરૂર હોય તો ડૉક્ટર સાથે ચર્ચા કરો.",
        "insight.continue_tracking": "વ્યક્તિગત ઇન્સાઇટ્સ માટે પિરિયડ્સ ટ્રૅક કરતા રહો.",
    },
}


def _normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return "en"
    lang = str(lang).lower().strip()
    if lang.startswith("hi"):
        return "hi"
    if lang.startswith("gu"):
        return "gu"
    return "en"


def t(key: str, lang: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
    """Translate a key and format with params. Falls back to English/key."""
    l = _normalize_lang(lang)
    template = _STRINGS.get(l, {}).get(key) or _STRINGS["en"].get(key) or key
    if not params:
        return template
    try:
        return template.format(**params)
    except Exception:
        # If formatting fails, return template to avoid 500s
        return template

