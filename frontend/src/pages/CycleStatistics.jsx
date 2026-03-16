import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Calendar, Activity, AlertCircle, History, Info } from 'lucide-react'
import Navbar from '../components/Navbar'
import { getCycleStats } from '../utils/api'
import { format, parseISO } from 'date-fns'

// Pastel color scheme matching app theme (4-phase system)
const PHASE_COLORS = {
  Period: '#F8BBD9',
  Follicular: '#FEF3C7',
  Ovulation: '#B8E6E6',
  Luteal: '#E1BEE7',
}

const phaseDayIdToPhase = (phaseDayId) => {
  if (!phaseDayId || typeof phaseDayId !== 'string') return 'Follicular'
  const first = (phaseDayId[0] || '').toLowerCase()
  if (first === 'p') return 'Period'
  if (first === 'f') return 'Follicular'
  if (first === 'o') return 'Ovulation'
  if (first === 'l') return 'Luteal'
  return 'Follicular'
}

const phaseToColor = (phase) => PHASE_COLORS[phase] || PHASE_COLORS.Follicular

const CycleStatistics = () => {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [cycles, setCycles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getCycleStats()
      setStats(data)
      setCycles(data.allCycles || [])
    } catch (err) {
      console.error('Error fetching cycle stats:', err)
      setError(err.message || 'Failed to load cycle statistics')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    
    // Refresh stats when period is logged
    const handlePeriodLogged = () => {
      fetchData()
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    
    // Listen for prefetched cycle stats
    const handleCycleStatsPrefetched = (event) => {
      const statsData = event.detail
      if (statsData) {
        console.log('✅ Using prefetched cycle stats')
        setStats(statsData)
        setCycles(statsData.allCycles || [])
        setLoading(false)
      }
    }
    window.addEventListener('cycleStatsPrefetched', handleCycleStatsPrefetched)
    
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
      window.removeEventListener('cycleStatsPrefetched', handleCycleStatsPrefetched)
    }
  }, [])

  const renderCycleDots = (cycle) => {
    const cycleData = cycle.cycleData || cycle.cycle_data_json
    if (!cycleData || cycleData.length === 0) {
      return Array.from({ length: Math.min(cycle.length || 28, 35) }, (_, i) => (
        <div key={i} className="w-2.5 h-2.5 rounded-full bg-gray-200 opacity-60" title="Loading" />
      ))
    }
    return cycleData.map((entry, idx) => {
      const phase = entry.phase || phaseDayIdToPhase(entry.phase_day_id)
      const color = phaseToColor(phase)
      const isPredicted = entry.is_predicted === true
      const isOvulation = (entry.phase_day_id || '').toLowerCase().startsWith('o')
      return (
        <div
          key={entry.date || idx}
          className={`w-2.5 h-2.5 rounded-full transition-all hover:scale-125 ${isPredicted ? 'border border-dashed' : 'border border-white/50 shadow-sm'}`}
          style={{
            backgroundColor: color,
            borderColor: isOvulation ? '#67E8F9' : 'rgba(255, 255, 255, 0.5)',
            boxShadow: isOvulation ? '0 0 0 1px #67E8F9' : 'none',
            opacity: isPredicted ? 0.7 : 1,
          }}
          title={`${entry.date || ''}: ${phase}${isPredicted ? ' (Predicted)' : ' (Actual)'}`}
        />
      )
    })
  }

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

  const currentCycle = cycles.find((c) => c.isCurrent)
  const todayStr = new Date().toISOString().slice(0, 10)
  const todayEntry = currentCycle?.cycleData?.find((e) => (e.date || '').slice(0, 10) === todayStr)
  const dayInCycle = stats?.daysSinceLastPeriod != null ? stats.daysSinceLastPeriod + 1 : null
  const currentPhase = todayEntry ? (todayEntry.phase || phaseDayIdToPhase(todayEntry.phase_day_id)) : null

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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex items-center justify-center py-32">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-period-pink"></div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
          <div className="text-red-600 text-center py-8 bg-white rounded-lg shadow-lg">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p>{error}</p>
          </div>
        </div>
      </div>
    )
  }

  if (!stats) {
    return null
  }

  // Calculate chart data
  const cycleLengths = stats.cycleLengths || []
  const maxCycle = cycleLengths.length > 0 ? Math.max(...cycleLengths) : 1
  const minCycle = cycleLengths.length > 0 ? Math.min(...cycleLengths) : 1

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
            <Activity className="h-8 w-8 text-period-pink" />
            <h1 className="text-3xl sm:text-4xl font-bold text-gray-800">Cycle Statistics</h1>
          </div>
          <p className="text-gray-600 text-sm sm:text-base">
            View your cycle statistics and complete history
          </p>
        </div>

        {/* Hero: 3 Info Cards + Confidence Signal */}
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
              <p className="text-3xl sm:text-4xl font-bold text-period-pink">
                {stats.averageCycleLength?.toFixed(0) || 'N/A'} days
              </p>
            </div>
            <div className="bg-white rounded-xl border-2 border-gray-100 p-5 shadow-md">
              <p className="text-sm font-medium text-gray-500 mb-1">Average Period</p>
              <p className="text-3xl sm:text-4xl font-bold text-period-pink">
                {stats.averagePeriodLength?.toFixed(0) || 'N/A'} days
              </p>
            </div>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
            {stats.confidence && (
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <span>Confidence</span>
                <ConfidenceSignal conf={stats.confidence} />
              </div>
            )}
            {stats.cycleRegularity && stats.cycleRegularity !== 'unknown' && (
              <div className="flex-1 min-w-0 max-w-xs">
                <RegularityBar regularity={stats.cycleRegularity} />
              </div>
            )}
          </div>
        </div>

        {/* Cycle Length Chart */}
        {cycleLengths.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h3 className="font-semibold text-gray-700 mb-4">Recent Cycle Lengths</h3>
            <div className="flex items-end gap-2 h-48">
              {cycleLengths.map((length, index) => {
                const normalizedHeight = maxCycle > minCycle
                  ? ((length - minCycle) / (maxCycle - minCycle)) * 100
                  : 50
                
                return (
                  <div key={index} className="flex-1 flex flex-col items-center">
                    <div className="w-full bg-gray-200 rounded-t relative" style={{ height: `${normalizedHeight}%`, minHeight: '20px' }}>
                      <div className="absolute inset-0 bg-period-pink rounded-t flex items-center justify-center">
                        <span className="text-white text-xs font-bold">{length}</span>
                      </div>
                    </div>
                    <div className="text-xs text-gray-600 mt-2">
                      C{cycleLengths.length - index}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-2">
              <span>Most Recent</span>
              <span>Oldest</span>
            </div>
          </div>
        )}

        {/* Quick Tips (Insights) */}
        {stats.insights && stats.insights.length > 0 && (
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

        {/* Anomalies */}
        {stats.anomalies > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2 text-yellow-800">
              <AlertCircle className="h-5 w-5" />
              <span className="font-semibold">
                {stats.anomalies} cycle{stats.anomalies !== 1 ? 's' : ''} outside normal range (21-45 days)
              </span>
            </div>
          </div>
        )}

        {/* Legend: 4-phase system + Actual vs Predicted */}
        {cycles.length > 0 && (
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
                <div className="w-3 h-3 rounded-full border-2 border-dashed border-gray-400" style={{ backgroundColor: PHASE_COLORS.Period, opacity: 0.7 }} />
                <span className="text-sm text-gray-600">Predicted</span>
              </div>
            </div>
          </div>
        )}

        {/* Cycle History */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6 border-2 border-gray-100">
          <div className="flex items-center gap-3 mb-4">
            <History className="h-6 w-6 text-period-pink" />
            <h2 className="text-xl font-bold text-gray-800">Cycle History</h2>
          </div>

          {cycles.length === 0 ? (
            <div className="text-center py-12">
              <Calendar className="h-14 w-14 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-600 font-semibold mb-1">No cycle history available</p>
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
                      : 'border-2 border-gray-100 hover:border-period-pink/30 hover:shadow-lg'
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
    </div>
  )
}

export default CycleStatistics
