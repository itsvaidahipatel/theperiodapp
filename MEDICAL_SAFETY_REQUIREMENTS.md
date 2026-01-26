# Medical Safety & Liability Requirements

## Overview

PeriodCycle.AI provides cycle predictions and fertility information. To ensure medical safety and legal compliance, the following requirements must be implemented and maintained.

---

## 1. UI Disclaimers

### Required Disclaimers

**1. Contraception Warning:**
- **Text**: "⚠️ NOT FOR CONTRACEPTION: This app is NOT a contraceptive method. Do NOT rely on fertility predictions for birth control. Use FDA-approved contraceptive methods if you wish to prevent pregnancy."
- **Location**: Must be visible on all pages showing fertility/ovulation data
- **Implementation**: `SafetyDisclaimer` component (already implemented)

**2. Diagnosis Warning:**
- **Text**: "⚠️ NOT FOR DIAGNOSIS: This app does NOT diagnose medical conditions. Cycle predictions are estimates based on patterns and should not be used to diagnose or treat health conditions. Consult a healthcare professional for diagnosis."
- **Location**: Must be visible on all pages showing cycle predictions
- **Implementation**: `SafetyDisclaimer` component (already implemented)

**3. General Medical Disclaimer:**
- **Text**: "Disclaimer: This information is for educational purposes only and should not replace professional medical advice. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition."
- **Location**: All pages
- **Implementation**: `SafetyDisclaimer` component (already implemented)

### Display Requirements

- **Visibility**: Disclaimers must be visible without scrolling on key pages (Dashboard, Calendar, Chat)
- **Persistence**: Disclaimers should appear on every page that shows medical/health information
- **Multilingual**: All disclaimers must be translated (English, Hindi, Gujarati)

---

## 2. Confidence-Based Data Suppression

### Backend Implementation

**Fertility Probability Suppression:**
- **Threshold**: `MIN_CONFIDENCE_FOR_FERTILITY = 0.5`
- **Rule**: Only return `fertility_prob` if `confidence >= 0.5`
- **Rationale**: Low-confidence predictions may be inaccurate and should not be shown to users

**Implementation Location**: `backend/routes/cycles.py`
- Line ~361: RapidAPI data formatting
- Line ~427: Fallback calculation formatting

**Code Pattern:**
```python
MIN_CONFIDENCE_FOR_FERTILITY = 0.5
confidence = item.get("confidence", 0.0)
if "fertility_prob" in item and confidence >= MIN_CONFIDENCE_FOR_FERTILITY:
    formatted_entry["fertility_prob"] = item["fertility_prob"]
# If confidence is low, do NOT include fertility_prob (suppressed for safety)
```

### Confidence Levels

| Source | Confidence | Fertility Data Shown? |
|--------|-----------|----------------------|
| RapidAPI cycle_phases | 0.9 | ✅ Yes |
| Adjusted (RapidAPI + manual) | 0.7 | ✅ Yes |
| Fallback (local calculation) | 0.4 | ❌ No (suppressed) |

**Rationale**: Fallback calculations have lower confidence (0.4) and should not show fertility probabilities to avoid misleading users.

---

## 3. Medical Language Requirements

### Required Wording

**Always Use:**
- ✅ "Estimated" (not "Actual")
- ✅ "Predicted" (not "Confirmed")
- ✅ "Likely" (not "Definite")
- ✅ "Probable" (not "Certain")

**Never Use:**
- ❌ "Actual ovulation date"
- ❌ "Confirmed fertile window"
- ❌ "Definite cycle phase"
- ❌ "Guaranteed prediction"

### Implementation

**Backend API Responses:**
- `predicted_ovulation_date_label`: "Estimated ovulation date" (not "Ovulation date")
- All phase labels should use "Estimated" or "Predicted" prefix where appropriate

**Frontend Display:**
- Use translation keys: `safety.estimated`, `safety.predicted`, `safety.likely`
- Example: "Estimated ovulation: [date]" instead of "Ovulation: [date]"

---

## 4. Data Suppression Rules

### When to Suppress Data

**1. Low Confidence Predictions:**
- Suppress `fertility_prob` when `confidence < 0.5`
- Suppress detailed uncertainty metrics when `confidence < 0.4`

**2. Missing Data:**
- If user has < 3 cycles logged, suppress fertility probabilities
- If cycle variance is very high (irregular cycles), consider suppressing or warning

**3. Anovulatory Cycles:**
- If system detects likely anovulatory cycle, suppress ovulation predictions
- Show warning: "Cycle pattern suggests possible anovulatory cycle. Consult healthcare professional."

### Frontend Handling

**When `fertility_prob` is Missing:**
- Do NOT show fertility probability indicator
- Do NOT show "High/Low Fertility" labels
- Show: "Fertility data unavailable - insufficient cycle data"

---

## 5. Legal & Ethical Considerations

### Liability Protection

**1. Clear Disclaimers:**
- Users must acknowledge that predictions are estimates
- Users must understand app is NOT for contraception
- Users must understand app is NOT for diagnosis

**2. Data Accuracy:**
- Suppress low-confidence data to prevent reliance on inaccurate predictions
- Use appropriate medical language to set expectations

**3. User Education:**
- Encourage consultation with healthcare professionals
- Provide links to medical resources where appropriate

### Ethical Requirements

**1. Informed Consent:**
- Users should understand limitations of predictions
- Users should know when to consult healthcare professionals

**2. Privacy:**
- Health data must be protected (already implemented via RLS)
- Users should understand data usage

**3. Accuracy:**
- System should not overstate prediction accuracy
- Uncertainty should be clearly communicated

---

## 6. Implementation Checklist

### Backend ✅

- [x] Confidence-based fertility_prob suppression
- [x] Medical language in API responses ("Estimated ovulation date")
- [x] Confidence threshold: 0.5 for fertility data
- [x] Documentation of suppression logic

### Frontend ✅

- [x] SafetyDisclaimer component with contraception warning
- [x] SafetyDisclaimer component with diagnosis warning
- [x] SafetyDisclaimer component with general medical disclaimer
- [x] Multilingual translations (English, Hindi, Gujarati)
- [x] Display on all relevant pages

### Documentation ✅

- [x] Medical safety requirements documented
- [x] Confidence thresholds documented
- [x] Suppression rules documented
- [x] Language requirements documented

### Testing Required

- [ ] Test fertility_prob suppression when confidence < 0.5
- [ ] Test disclaimer visibility on all pages
- [ ] Test multilingual disclaimer display
- [ ] Test frontend handling of missing fertility_prob
- [ ] Verify "Estimated"/"Predicted" wording in UI

---

## 7. Ongoing Maintenance

### Regular Reviews

**Quarterly:**
- Review disclaimer wording for clarity
- Verify confidence thresholds are appropriate
- Check for any new medical/legal requirements

**After Major Updates:**
- Verify disclaimers still appear correctly
- Test confidence-based suppression still works
- Review medical language usage

### User Feedback

- Monitor user questions about contraception/diagnosis
- Track if users misunderstand predictions
- Adjust disclaimers if needed based on feedback

---

## 8. Key Files

**Backend:**
- `backend/routes/cycles.py` - Confidence-based suppression logic
- `backend/cycle_utils.py` - Prediction confidence calculation

**Frontend:**
- `frontend/src/components/SafetyDisclaimer.jsx` - Disclaimer component
- `frontend/src/utils/translations.js` - Multilingual disclaimer text

**Documentation:**
- `COMPLETE_SYSTEM_DOCUMENTATION.md` - System documentation
- `MEDICAL_SAFETY_REQUIREMENTS.md` - This file

---

## 9. Compliance Notes

**FDA/Medical Device Regulations:**
- This app is NOT a medical device
- Predictions are for informational/educational purposes only
- No claims of medical diagnosis or treatment

**International Considerations:**
- Disclaimers must be in user's preferred language
- Local regulations may require additional disclaimers
- Consult legal counsel for jurisdiction-specific requirements

---

## 10. Emergency Contacts

**If Medical Issues Arise:**
- Users should contact healthcare professionals immediately
- App should NOT delay seeking medical care
- App should NOT replace emergency medical services

**Support:**
- Provide clear path to healthcare professional consultation
- Do NOT provide medical advice through support channels
- Direct users to appropriate medical resources

---

**Last Updated:** 2025-11-16  
**Status:** Implemented and documented  
**Next Review:** Quarterly or after major updates
