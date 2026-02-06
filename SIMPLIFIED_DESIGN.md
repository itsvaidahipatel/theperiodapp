# Simplified Design: One Log = One Cycle Start

## Core Design Principle

**One log = one cycle start (period start only, no end/duration)**

This is simpler and medically valid. Doctors track LMP (Last Menstrual Period) - the start date, not the duration.

## What This Eliminates

- ❌ Consecutive bleeding grouping
- ❌ Period end logic
- ❌ Spotting vs bleeding confusion
- ❌ "Forgot to stop period" issues
- ❌ Period length tracking

## What We Keep

- ✅ Cycle start detection
- ✅ Cycle length accuracy (gap between starts)
- ✅ Late logging handling
- ✅ Irregular cycle handling
- ✅ Future log support (is_confirmed=false)

## Core Truth

**PeriodStartLog = cycle start date**

Everything else (cycle length, ovulation, predictions) is derived.

## Database Schema

```sql
CREATE TABLE period_start_logs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    start_date DATE NOT NULL,
    is_confirmed BOOLEAN DEFAULT TRUE,  -- false for future/predicted logs
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(user_id, start_date)
);
```

## Cycle Calculation

**Cycle definition:**
- Cycle.start = PeriodStartLog[n].start_date
- Cycle.length = PeriodStartLog[n+1].start_date - PeriodStartLog[n].start_date

**Only valid cycles (15-60 days) are included in averages:**
- < 15 days: Outlier (excluded from averages, likely mistake)
- 15-60 days: Valid (included in averages)
- > 60 days: Irregular (excluded from averages, gap/skipped month)

## Edge Cases Handled

### A. Normal Logging
User logs: Jan 10
- System: Cycle start = Jan 10
- No cycle length yet (needs previous start)

### B. Late Logs (Past Date)
User logs on Jan 20: "My period started Jan 5"
- Insert Jan 5
- Sort all starts
- Recompute cycle lengths
- Example: Dec 7, Jan 5 → cycle length = 29 days

### C. Future Logs
User logs: Feb 2 (future)
- Store as: is_confirmed = false
- Does NOT affect cycle averages yet
- If date passes or user confirms → becomes real
- If conflicting log appears → auto-delete prediction

### D. Two Logs in Same Month
Example: Jan 3, Jan 29
- Allowed
- Cycle length = 26 days
- Month irrelevant

### E. Very Short Cycles (Fake/Mistake)
Example: Jan 10, Jan 13 (3 days)
- Still store it
- Mark cycle length < 15 days as outlier
- Exclude from prediction averages
- Do NOT delete automatically

### F. Duplicate Logs
User logs: Jan 10, Jan 10
- Prevent duplicate date (UNIQUE constraint)
- OR keep latest and overwrite
- Never create two cycles on same date

### G. User Deletes a Log
When a log is deleted:
- Remove it
- Re-sort
- Recompute all cycle lengths
- Nothing else needed

### H. Gaps (Skipped Months)
Example: Jan 5, May 20 (135 days)
- Store it
- Flag as irregular (> 60 days)
- Reduce prediction weight
- Exclude from averages

## Prediction Model

Since we only track starts:

**Cycle length average = Average of last N valid cycle gaps**

Where valid: 15 ≤ cycleLength ≤ 60

**Ovulation estimate:**
- ovulation ≈ nextPeriod - 14

Still medically acceptable (industry standard).

## Why This Design is Good

Compared to Flo:

| Aspect | Flo | This App |
|--------|-----|----------|
| Logging complexity | High | Low |
| User confusion | Medium | Very low |
| Medical validity | High | High |
| Edge cases | Many | Fewer |
| Debuggability | Hard | Clean |

Doctors often ask: "When was your last period start?"
Not: "How many days exactly did it last?"

## Golden Rule

**Never attach meaning to a log beyond "cycle start"**

Everything else is derived.
