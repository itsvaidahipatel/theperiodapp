/**
 * Helpers for slim /cycles/phase-map rows: { date, phase_day_id } only.
 */

export function phaseDayIdToPhase(phaseDayId) {
  if (!phaseDayId || typeof phaseDayId !== 'string') return 'Follicular'
  const first = (phaseDayId[0] || '').toLowerCase()
  if (first === 'p') return 'Period'
  if (first === 'f') return 'Follicular'
  if (first === 'o') return 'Ovulation'
  if (first === 'l') return 'Luteal'
  return 'Follicular'
}

/**
 * Expand slim API rows for UI that expects phase + is_predicted when present.
 * @param {object} item - { date, phase_day_id, ... }
 * @param {string} [todayCalendarStr] - YYYY-MM-DD for defaulting is_predicted
 */
export function enrichPhaseMapItem(item, todayCalendarStr) {
  if (!item || !item.date) return item
  const dateKey = String(item.date).slice(0, 10)
  if (dateKey.length !== 10) return item
  const pid = item.phase_day_id
  const phase = item.phase || phaseDayIdToPhase(pid)
  const today = todayCalendarStr || new Date().toISOString().slice(0, 10)
  const hasExplicitPred =
    Object.prototype.hasOwnProperty.call(item, 'is_predicted') ||
    Object.prototype.hasOwnProperty.call(item, 'isPredicted')
  const rawPred = item.is_predicted ?? item.isPredicted
  const is_predicted = hasExplicitPred ? Boolean(rawPred) : dateKey > today
  return {
    ...item,
    date: dateKey,
    phase_day_id: pid,
    phase,
    is_predicted,
  }
}
