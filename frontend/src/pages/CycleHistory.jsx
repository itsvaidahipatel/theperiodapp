import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Calendar, Info } from 'lucide-react'
import Navbar from '../components/Navbar'
import { useDataContext } from '../context/DataContext'
import { useCycleContext } from '../context/CycleContext'
import { format, parseISO, differenceInDays, addDays } from 'date-fns'

// Pastel color scheme matching app theme (source of truth for 4-phase system)
const PHASE_COLORS = {
  Period: '#F8BBD9',
  Follicular: '#FEF3C7',
  Ovulation: '#B8E6E6',
  Luteal: '#E1BEE7',
}

const PHASE_KEYS = ['Period', 'Follicular', 'Ovulation', 'Luteal']

// Normalize backend phase (any casing) to PHASE_COLORS key
const normalizePhaseKey = (phase) => {
  if (!phase || typeof phase !== 'string') return null
  const lower = phase.trim().toLowerCase()
  return PHASE_KEYS.find((k) => k.toLowerCase() === lower) || null
}

// Map phase_day_id (p1, f1, o1, l1) to phase name (for getPhaseDates and display)
const phaseDayIdToPhase = (phaseDayId) => {
  if (!phaseDayId || typeof phaseDayId !== 'string') return 'Follicular'
  const first = (phaseDayId[0] || '').toLowerCase()
  if (first === 'p') return 'Period'
  if (first === 'f') return 'Follicular'
  if (first === 'o') return 'Ovulation'
  if (first === 'l') return 'Luteal'
  return 'Follicular'
}

// Very light fallback for dots with no phase data
const FALLBACK_DOT_COLOR = '#F5F0F8'
const DOT_SIZE_PX = 10

// cycle.cycleData = current cycle (dashboard); cycle.cycle_data_json = past cycles (DB)
const renderCycleDots = (cycle) => {
  const cycleData = cycle.cycleData || cycle.cycle_data_json
  if (!cycleData || cycleData.length === 0) {
    return Array.from({ length: Math.min(cycle.length || 28, 35) }, (_, i) => (
      <div
        key={i}
        role="img"
        aria-hidden
        style={{
          width: DOT_SIZE_PX,
          height: DOT_SIZE_PX,
          minWidth: DOT_SIZE_PX,
          minHeight: DOT_SIZE_PX,
          borderRadius: '50%',
          backgroundColor: FALLBACK_DOT_COLOR,
          border: '1.5px dashed rgba(0,0,0,0.4)',
          opacity: 1,
          flexShrink: 0,
        }}
        title="Loading"
      />
    ))
  }

  return cycleData.map((dot, idx) => {
    const phaseKey = dot.phase ? dot.phase.trim() : 'Period'
    const normalizedKey = normalizePhaseKey(phaseKey) || (dot.phase_day_id ? phaseDayIdToPhase(dot.phase_day_id) : 'Period')
    const backgroundColor = PHASE_COLORS[normalizedKey] || PHASE_COLORS.Period || FALLBACK_DOT_COLOR
    const isPredicted = dot.is_predicted === true || dot.isPredicted === true
    const isVirtual = dot.is_virtual === true || dot.isVirtual === true
    const isPredictedOrVirtual = isPredicted || isVirtual
    const borderStyle = isPredictedOrVirtual ? '1.5px dashed rgba(0, 0, 0, 0.4)' : '1.5px solid white'
    const label = isVirtual ? ' (Virtual)' : isPredicted ? ' (Predicted)' : ' (Actual)'

    console.log('Rendering dot:', dot.date, 'Phase:', dot.phase, 'Predicted:', dot.is_predicted)

    return (
      <div
        key={dot.date || idx}
        role="img"
        aria-hidden
        style={{
          width: DOT_SIZE_PX,
          height: DOT_SIZE_PX,
          minWidth: DOT_SIZE_PX,
          minHeight: DOT_SIZE_PX,
          borderRadius: '50%',
          backgroundColor,
          border: borderStyle,
          opacity: 1,
          boxShadow: !isPredictedOrVirtual ? '0 1px 2px rgba(0,0,0,0.12)' : 'none',
          flexShrink: 0,
        }}
        className="transition-transform hover:scale-125"
        title={`${dot.date || ''}: ${normalizedKey}${label}`}
      />
    )
  })
}

// Phase start dates from backend cycleData
const getPhaseDates = (cycle) => {
  const cycleData = cycle.cycleData || cycle.cycle_data_json
  if (!cycleData || cycleData.length === 0) return []

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const firstByPhase = {}
  for (const entry of cycleData) {
    const phase = entry.phase || phaseDayIdToPhase(entry.phase_day_id)
    if (!firstByPhase[phase]) {
      const d = entry.date ? (typeof entry.date === 'string' ? parseISO(entry.date) : new Date(entry.date)) : null
      if (d) firstByPhase[phase] = { date: d, predicted: entry.is_predicted === true || d > today }
    }
  }

  return [
    { label: 'Period', date: firstByPhase.Period?.date, predicted: firstByPhase.Period?.predicted ?? false },
    { label: 'Follicular', date: firstByPhase.Follicular?.date, predicted: firstByPhase.Follicular?.predicted ?? false },
    { label: 'Ovulation', date: firstByPhase.Ovulation?.date, predicted: firstByPhase.Ovulation?.predicted ?? false },
    { label: 'Luteal', date: firstByPhase.Luteal?.date, predicted: firstByPhase.Luteal?.predicted ?? false },
  ].filter((p) => p.date)
}

// Slice phaseMap into array of { date, phase, phase_day_id, is_predicted, is_virtual } for a date range
const slicePhaseMapForRange = (phaseMap, startDate, endDate, today, allActual = false) => {
  const out = []
  let current = startDate
  while (current <= endDate) {
    const dateKey = format(current, 'yyyy-MM-dd')
    const entry = phaseMap[dateKey]
    if (entry) {
      const isPredicted = allActual ? false : (current > today)
      const entryIsPredicted = typeof entry === 'object' ? (entry.is_predicted ?? entry.isPredicted) : undefined
      const entryIsVirtual = typeof entry === 'object' ? (entry.is_virtual ?? entry.isVirtual) : undefined
      out.push({
        date: dateKey,
        phase: typeof entry === 'string' ? entry : entry.phase,
        phase_day_id: typeof entry === 'object' ? entry.phase_day_id : null,
        is_predicted: entryIsPredicted !== undefined ? entryIsPredicted : isPredicted,
        is_virtual: entryIsVirtual === true,
      })
    }
    current = addDays(current, 1)
  }
  return out
}

const CycleHistoryPage = () => {
  const navigate = useNavigate()
  const { dashboardData } = useDataContext()
  const { phaseMap: cyclePhaseMap, allCycles, periodLogs, isDataReady, getHistorySlices } = useCycleContext()
  const phaseMap = dashboardData?.phaseMap && Object.keys(dashboardData.phaseMap).length > 0 ? dashboardData.phaseMap : cyclePhaseMap

  const periodStarts = useMemo(() => {
    if (!periodLogs || periodLogs.length === 0) return []
    const starts = []
    const seen = new Set()
    for (const log of periodLogs) {
      const dateStr = (log.startDate || log.date || '').toString().slice(0, 10)
      if (dateStr.length === 10 && !seen.has(dateStr)) {
        seen.add(dateStr)
        starts.push(dateStr)
      }
    }
    return starts.sort()
  }, [periodLogs])

  const todayStr = new Date().toISOString().slice(0, 10)
  const today = parseISO(todayStr)

  // Cycles with phase data: from CycleContext (already loaded by Dashboard = instant render)
  const { cycles, stats } = useMemo(() => {
    const list = getHistorySlices()
    const hasPhaseMap = Object.keys(phaseMap).length > 0

    if (list.length > 0) {
      // list already has cycleData from getHistorySlices; sort and use for stats
      const sorted = [...list].sort((a, b) => (b.cycleNumber ?? 0) - (a.cycleNumber ?? 0))
      const validCycles = sorted.filter(c => !c.isCurrent && c.length >= 21 && c.length <= 45)
      const cycleLengths = validCycles.map(c => c.length)
      const avgCycleLength = cycleLengths.length > 0 ? cycleLengths.reduce((a, b) => a + b, 0) / cycleLengths.length : 28

      let avgPeriodLength = 5
      if (hasPhaseMap) {
        const periodLengths = []
        let curStart = null, curDays = 0
        for (const dateKey of Object.keys(phaseMap).sort()) {
          const entry = phaseMap[dateKey]
          const phase = typeof entry === 'string' ? entry : entry?.phase
          const isPred = typeof entry === 'object' ? (entry.is_predicted ?? false) : false
          if (phase === 'Period' && !isPred) {
            if (!curStart) { curStart = dateKey; curDays = 1; } else curDays++
          } else if (curStart) {
            periodLengths.push(curDays)
            curStart = null
            curDays = 0
          }
        }
        if (curStart) periodLengths.push(curDays)
        avgPeriodLength = periodLengths.length > 0 ? periodLengths.reduce((a, b) => a + b, 0) / periodLengths.length : 5
      }

      let cycleRegularity = 'unknown'
      if (cycleLengths.length >= 2) {
        const mean = avgCycleLength
        const variance = cycleLengths.reduce((s, len) => s + Math.pow(len - mean, 2), 0) / (cycleLengths.length - 1)
        const cv = (Math.sqrt(variance) / mean) * 100
        if (cv < 8) cycleRegularity = 'very_regular'
        else if (cv < 15) cycleRegularity = 'regular'
        else if (cv < 25) cycleRegularity = 'somewhat_irregular'
        else cycleRegularity = 'irregular'
      }

      const lastPeriodDate = periodStarts.length > 0 ? periodStarts[periodStarts.length - 1] : null
      const daysSinceLastPeriod = lastPeriodDate ? differenceInDays(today, parseISO(lastPeriodDate)) : null

      const statsObj = {
        totalCycles: validCycles.length,
        averageCycleLength: avgCycleLength,
        averagePeriodLength: avgPeriodLength,
        cycleRegularity,
        daysSinceLastPeriod,
        cycleLengths: cycleLengths.slice(-6),
        anomalies: sorted.filter(c => c.isAnomaly).length,
        insights: [],
        confidence: null,
      }
      return { cycles: sorted, stats: statsObj }
    }

    // Fallback: build from periodStarts when getHistorySlices() returned empty
    let fallbackList = []
    if (periodStarts.length > 0) {
      for (let i = 0; i < periodStarts.length - 1; i++) {
        const startStr = periodStarts[i]
        const endStr = periodStarts[i + 1]
        const startDate = parseISO(startStr)
        const endDate = parseISO(endStr)
        const length = differenceInDays(endDate, startDate)
        const slice = hasPhaseMap ? slicePhaseMapForRange(phaseMap, startDate, addDays(endDate, -1), today, true) : null
        fallbackList.push({
          cycleNumber: periodStarts.length - i - 1,
          startDate: startStr,
          endDate: endStr,
          length,
          isCurrent: false,
          isAnomaly: length < 21 || length > 45,
          cycleData: slice?.length ? slice : null,
          cycle_data_json: slice?.length ? slice : null,
        })
      }
      const lastStartStr = periodStarts[periodStarts.length - 1]
      const lastStartDate = parseISO(lastStartStr)
      const currentLength = differenceInDays(today, lastStartDate)
      const liveSlice = hasPhaseMap ? slicePhaseMapForRange(phaseMap, lastStartDate, addDays(lastStartDate, 45), today, false) : null
      fallbackList.push({
        cycleNumber: 0,
        startDate: lastStartStr,
        endDate: null,
        length: currentLength,
        isCurrent: true,
        isAnomaly: false,
        cycleData: liveSlice?.length ? liveSlice : null,
      })
    }
    const finalList = fallbackList.length > 0 ? fallbackList : list

    const validCycles = finalList.filter(c => !c.isCurrent && c.length >= 21 && c.length <= 45)
    const cycleLengths = validCycles.map(c => c.length)
    const avgCycleLength = cycleLengths.length > 0 ? cycleLengths.reduce((a, b) => a + b, 0) / cycleLengths.length : 28

    let avgPeriodLength = 5
    if (hasPhaseMap) {
      const periodLengths = []
      let curStart = null, curDays = 0
      for (const dateKey of Object.keys(phaseMap).sort()) {
        const entry = phaseMap[dateKey]
        const phase = typeof entry === 'string' ? entry : entry?.phase
        const isPred = typeof entry === 'object' ? (entry.is_predicted ?? false) : false
        if (phase === 'Period' && !isPred) {
          if (!curStart) { curStart = dateKey; curDays = 1; } else curDays++
        } else if (curStart) {
          periodLengths.push(curDays)
          curStart = null
          curDays = 0
        }
      }
      if (curStart) periodLengths.push(curDays)
      avgPeriodLength = periodLengths.length > 0 ? periodLengths.reduce((a, b) => a + b, 0) / periodLengths.length : 5
    }

    let cycleRegularity = 'unknown'
    if (cycleLengths.length >= 2) {
      const mean = avgCycleLength
      const variance = cycleLengths.reduce((s, len) => s + Math.pow(len - mean, 2), 0) / (cycleLengths.length - 1)
      const cv = (Math.sqrt(variance) / mean) * 100
      if (cv < 8) cycleRegularity = 'very_regular'
      else if (cv < 15) cycleRegularity = 'regular'
      else if (cv < 25) cycleRegularity = 'somewhat_irregular'
      else cycleRegularity = 'irregular'
    }

    const lastPeriodDate = periodStarts.length > 0 ? periodStarts[periodStarts.length - 1] : null
    const daysSinceLastPeriod = lastPeriodDate ? differenceInDays(today, parseISO(lastPeriodDate)) : null

    const statsObj = {
      totalCycles: validCycles.length,
      averageCycleLength: avgCycleLength,
      averagePeriodLength: avgPeriodLength,
      cycleRegularity,
      daysSinceLastPeriod,
      cycleLengths: cycleLengths.slice(-6),
      anomalies: finalList.filter(c => c.isAnomaly).length,
      insights: [],
      confidence: null,
    }

    return { cycles: finalList, stats: statsObj }
  }, [periodStarts, phaseMap, getHistorySlices, todayStr])

  const loading = !isDataReady
  const avgPeriodLength = stats?.averagePeriodLength ?? 5
  const avgCycleLength = stats?.averageCycleLength ?? 28

  // Format dates as "Feb 10 – Mar 12, 2025" or "Started Feb 10, 2025" for current
  const formatDateRange = (startDate, endDate, isCurrent) => {
    try {
      const start = typeof startDate === 'string' ? parseISO(startDate) : new Date(startDate)
      const end = endDate ? (typeof endDate === 'string' ? parseISO(endDate) : new Date(endDate)) : null
      
      const startFormatted = format(start, 'MMM d, yyyy')
      
      if (isCurrent) {
        return `Started ${startFormatted}`
      }
      
      if (end) {
        const endFormatted = format(end, 'MMM d, yyyy')
        return `${startFormatted} – ${endFormatted}`
      }
      
      return startFormatted
    } catch (err) {
      return startDate
    }
  }

  // Current Status: day-in-cycle + phase from phaseMap (source of truth)
  const currentCycle = cycles.find((c) => c.isCurrent)
  const todayEntry = currentCycle?.cycleData?.find((e) => (e.date || '').slice(0, 10) === todayStr) || phaseMap[todayStr]
  const dayInCycle = stats?.daysSinceLastPeriod != null ? stats.daysSinceLastPeriod + 1 : null
  const currentPhase = todayEntry
    ? (typeof todayEntry === 'string' ? todayEntry : (todayEntry.phase || phaseDayIdToPhase(todayEntry.phase_day_id)))
    : null

  const getRegularityLabel = (r) => ({ very_regular: 'Very Regular', regular: 'Regular', somewhat_irregular: 'Somewhat Irregular', irregular: 'Irregular', unknown: 'Unknown' }[r] || r)

  const RegularityBar = ({ regularity }) => {
    const levels = ['very_regular', 'regular', 'somewhat_irregular', 'irregular']
    const idx = levels.indexOf(regularity)
    const colors = ['bg-emerald-500', 'bg-green-400', 'bg-amber-500', 'bg-red-500']
    return (
      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-xs text-gray-600 mb-0.5">
          <span>Regularity</span>
          <span className="font-medium">{getRegularityLabel(regularity)}</span>
        </div>
        <div className="flex h-2 rounded-full overflow-hidden bg-gray-200">
          {levels.map((level, i) => (
            <div
              key={level}
              className={`flex-1 transition-colors ${colors[i]} ${idx === i ? 'ring-2 ring-gray-800 ring-offset-1' : 'opacity-50'}`}
              title={getRegularityLabel(level)}
            />
          ))}
        </div>
      </div>
    )
  }

  const ConfidenceSignal = ({ conf }) => {
    if (!conf) return null
    const level = (conf.level || '').toLowerCase()
    const bars = level === 'high' ? 3 : level === 'medium' ? 2 : 1
    const tooltip = `${conf.percentage}% – ${conf.level} Confidence. ${conf.reason || ''}`
    return (
      <div className="group relative inline-flex items-end gap-0.5 h-5" title={tooltip}>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className={`w-1.5 rounded-sm transition-all ${
              i <= bars ? (bars === 3 ? 'bg-green-500' : bars === 2 ? 'bg-amber-500' : 'bg-red-500') : 'bg-gray-200'
            }`}
            style={{ height: `${i * 5}px` }}
          />
        ))}
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 px-2 py-1.5 bg-gray-800 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap max-w-xs text-center z-10">
          {tooltip}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Header */}
        <div className="mb-6 sm:mb-8">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-gray-600 hover:text-period-pink transition mb-4"
          >
            <ArrowLeft className="h-5 w-5" />
            <span className="text-sm font-medium">Back to Dashboard</span>
          </button>
          <div className="flex items-center gap-3 mb-2">
            <Calendar className="h-8 w-8 text-period-pink" />
            <h1 className="text-3xl sm:text-4xl font-bold text-gray-800">Cycle History</h1>
          </div>
        </div>

        {/* Hero: 3 Info Cards + Confidence Signal */}
        {!loading && (cycles.length > 0 || stats) && (
          <div className="mb-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
              <div className="bg-white rounded-xl border-2 border-gray-100 p-5 shadow-md">
                <p className="text-sm font-medium text-gray-500 mb-1">Current Status</p>
                {(dayInCycle != null || currentPhase) ? (
                  <>
                    {dayInCycle != null && <p className="text-3xl sm:text-4xl font-bold text-period-pink">Day {dayInCycle}</p>}
                    {currentPhase && <p className="text-lg font-semibold text-gray-700">{currentPhase}</p>}
                  </>
                ) : (
                  <p className="text-lg text-gray-500">No period logged</p>
                )}
              </div>
              <div className="bg-white rounded-xl border-2 border-gray-100 p-5 shadow-md">
                <p className="text-sm font-medium text-gray-500 mb-1">Average Cycle</p>
                <p className="text-3xl sm:text-4xl font-bold text-period-pink">{avgCycleLength.toFixed(0)} days</p>
              </div>
              <div className="bg-white rounded-xl border-2 border-gray-100 p-5 shadow-md">
                <p className="text-sm font-medium text-gray-500 mb-1">Average Period</p>
                <p className="text-3xl sm:text-4xl font-bold text-period-pink">{avgPeriodLength.toFixed(0)} days</p>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
              {stats?.confidence && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <span>Confidence</span>
                  <ConfidenceSignal conf={stats.confidence} />
                </div>
              )}
              {stats?.cycleRegularity && stats.cycleRegularity !== 'unknown' && (
                <div className="flex-1 min-w-0 max-w-xs">
                  <RegularityBar regularity={stats.cycleRegularity} />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Legend: 4-phase system + Actual vs Predicted */}
        {!loading && cycles.length > 0 && (
          <div className="mb-6 p-4 bg-white rounded-xl border border-gray-100 shadow-sm">
            <p className="text-sm font-semibold text-gray-700 mb-3">Legend</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border border-white/50 shadow-sm" style={{ backgroundColor: PHASE_COLORS.Period }} />
                <span className="text-sm text-gray-600">Period</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border border-white/50 shadow-sm" style={{ backgroundColor: PHASE_COLORS.Follicular }} />
                <span className="text-sm text-gray-600">Follicular</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border border-white/50 shadow-sm" style={{ backgroundColor: PHASE_COLORS.Ovulation }} />
                <span className="text-sm text-gray-600">Ovulation</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border border-white/50 shadow-sm" style={{ backgroundColor: PHASE_COLORS.Luteal }} />
                <span className="text-sm text-gray-600">Luteal</span>
              </div>
              <span className="text-gray-300">|</span>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border border-white/50 shadow-sm" style={{ backgroundColor: PHASE_COLORS.Period }} />
                <span className="text-sm text-gray-600">Actual</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PHASE_COLORS.Period, border: '2px dashed rgba(0, 0, 0, 0.3)', opacity: 1.0 }} />
                <span className="text-sm text-gray-600">Predicted</span>
              </div>
            </div>
          </div>
        )}

        {/* Quick Tips (Insights) */}
        {stats?.insights?.length > 0 && (
          <div className="mb-6 p-4 sm:p-5 bg-blue-50 rounded-xl border border-blue-100 flex gap-3">
            <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-blue-900 mb-2">Quick Tips</p>
              <ul className="space-y-1 text-sm text-blue-800">
                {stats.insights.map((insight, i) => (
                  <li key={i}>{insight}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Cycles List */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-period-pink"></div>
          </div>
        ) : cycles.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl shadow-lg">
            <Calendar className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600 text-lg font-semibold mb-2">No cycle history available</p>
            <p className="text-gray-500 text-sm">Log at least 2 periods to see cycle history</p>
          </div>
        ) : (
          <div className="space-y-4">
            {cycles.map((cycle, index) => (
              <div
                key={index}
                className={`rounded-xl p-4 sm:p-5 transition-all shadow-md ${
                  cycle.isCurrent
                    ? 'bg-gradient-to-br from-pink-50 to-purple-50 border-2 border-period-pink/40 ring-2 ring-period-pink/20'
                    : 'bg-white border-2 border-gray-100 hover:border-period-pink/30 hover:shadow-lg'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
                  <p className="text-base sm:text-lg font-semibold text-gray-800">
                    {formatDateRange(cycle.startDate, cycle.endDate, cycle.isCurrent)}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {cycle.status === 'late' && (
                      <span className="px-2.5 py-1 bg-amber-500/90 text-white text-xs font-semibold rounded-lg">
                        Late {cycle.daysLate != null ? `${cycle.daysLate}d` : ''}
                      </span>
                    )}
                    {cycle.isAnomaly && (
                      <span className="px-2.5 py-1 text-white text-xs font-semibold rounded-lg" style={{ backgroundColor: 'rgb(255, 127, 80)' }}>
                        Irregular
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 items-center p-3 bg-gray-50 rounded-lg">
                  {renderCycleDots(cycle)}
                </div>
                <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-600">
                  {getPhaseDates(cycle).map(({ label, date, predicted }) => (
                    <span key={label}>
                      <span className="font-semibold text-gray-700">{label}:</span> {predicted ? '–' : (date ? format(date, 'MMM d') : '–')}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default CycleHistoryPage
