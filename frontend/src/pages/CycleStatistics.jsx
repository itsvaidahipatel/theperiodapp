import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Calendar, Activity, TrendingUp, AlertCircle, CheckCircle2, History } from 'lucide-react'
import Navbar from '../components/Navbar'
import { getCycleStats } from '../utils/api'
import { format, parseISO } from 'date-fns'

// Pastel color scheme matching app theme
const PHASE_COLORS = {
  Period: '#F8BBD9',      // Soft pastel pink
  Follicular: '#FEF3C7',  // Soft pastel yellow/cream
  Ovulation: '#B8E6E6',   // Soft pastel teal/cyan
  Luteal: '#E1BEE7',      // Soft pastel lavender
}

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

  const getConfidenceColor = (level) => {
    switch (level) {
      case 'High':
        return 'bg-green-100 text-green-800 border-green-300'
      case 'Medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 'Low':
        return 'bg-red-100 text-red-800 border-red-300'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  const getRegularityLabel = (regularity) => {
    const labels = {
      very_regular: 'Very Regular',
      regular: 'Regular',
      somewhat_irregular: 'Somewhat Irregular',
      irregular: 'Irregular',
      unknown: 'Unknown'
    }
    return labels[regularity] || regularity
  }

  const getRegularityColor = (regularity) => {
    switch (regularity) {
      case 'very_regular':
        return 'text-green-600'
      case 'regular':
        return 'text-green-500'
      case 'somewhat_irregular':
        return 'text-yellow-600'
      case 'irregular':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  const calculatePhaseForDay = (dayInCycle, cycleLength, periodLength) => {
    if (dayInCycle <= periodLength) {
      return { phase: 'Period', color: PHASE_COLORS.Period }
    }
    
    const ovulationDay = Math.max(8, cycleLength - 14)
    const fertileStart = ovulationDay - 5
    const fertileEnd = ovulationDay
    
    if (dayInCycle >= fertileStart && dayInCycle <= fertileEnd) {
      return { phase: 'Ovulation', color: PHASE_COLORS.Ovulation }
    }
    
    if (dayInCycle > ovulationDay) {
      return { phase: 'Luteal', color: PHASE_COLORS.Luteal }
    }
    
    return { phase: 'Follicular', color: PHASE_COLORS.Follicular }
  }

  const renderCycleDots = (cycle) => {
    const cycleLength = cycle.length
    const periodLength = Math.min(Math.round(stats?.averagePeriodLength || 5), Math.max(2, cycleLength - 10))
    const dots = []
    
    const maxDays = cycle.isCurrent 
      ? Math.min(cycleLength + 7, Math.max(cycleLength, 28))
      : cycleLength
    
    const ovulationDay = Math.max(8, cycleLength - 14)
    
    for (let day = 1; day <= maxDays; day++) {
      const phaseInfo = calculatePhaseForDay(day, cycleLength, periodLength)
      const isOvulationDay = day === ovulationDay
      const isFutureDay = cycle.isCurrent && day > cycleLength
      
      dots.push(
        <div
          key={day}
          className="w-2.5 h-2.5 rounded-full border border-white/50 shadow-sm transition-all hover:scale-125"
          style={{
            backgroundColor: isFutureDay ? '#F3F4F6' : phaseInfo.color,
            borderColor: isOvulationDay ? '#67E8F9' : 'rgba(255, 255, 255, 0.5)',
            boxShadow: isOvulationDay ? '0 0 0 1px #67E8F9' : 'none',
            opacity: isFutureDay ? 0.5 : 1
          }}
          title={isFutureDay 
            ? `Day ${day}: Future (estimated)` 
            : `Day ${day}: ${phaseInfo.phase}${isOvulationDay ? ' (Ovulation)' : ''}`}
        />
      )
    }
    
    return dots
  }

  const formatDateRange = (startDate, endDate, isCurrent) => {
    try {
      const start = typeof startDate === 'string' ? parseISO(startDate) : new Date(startDate)
      const end = endDate ? (typeof endDate === 'string' ? parseISO(endDate) : new Date(endDate)) : null
      
      const startFormatted = format(start, 'MMM d')
      
      if (isCurrent) {
        return `Started ${startFormatted}`
      }
      
      if (end) {
        const endFormatted = format(end, 'MMM d')
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

        {/* Confidence Badge */}
        {stats.confidence && (
          <div className={`mb-6 p-4 rounded-lg border-2 ${getConfidenceColor(stats.confidence.level)}`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium mb-1">Prediction Confidence</div>
                <div className="text-2xl font-bold">{stats.confidence.percentage}%</div>
                <div className="text-sm mt-1">{stats.confidence.level} Confidence</div>
              </div>
              <div className="text-right">
                <div className="text-xs opacity-75">{stats.confidence.reason}</div>
              </div>
            </div>
          </div>
        )}

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {/* Average Cycle Length */}
          <div className="bg-white rounded-lg shadow-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="h-5 w-5 text-period-pink" />
              <h3 className="font-semibold text-gray-700">Average Cycle Length</h3>
            </div>
            <div className="text-3xl font-bold text-period-pink mb-1">
              {stats.averageCycleLength?.toFixed(1) || 'N/A'} days
            </div>
            {stats.shortestCycle && stats.longestCycle && (
              <div className="text-sm text-gray-600">
                Range: {stats.shortestCycle} - {stats.longestCycle} days
              </div>
            )}
          </div>

          {/* Average Period Length */}
          <div className="bg-white rounded-lg shadow-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-5 w-5 text-period-pink" />
              <h3 className="font-semibold text-gray-700">Average Period Length</h3>
            </div>
            <div className="text-3xl font-bold text-period-pink mb-1">
              {stats.averagePeriodLength?.toFixed(1) || 'N/A'} days
              {stats.isPeriodLengthOutsideRange && (
                <span className="text-sm text-yellow-600 ml-2" title="Outside typical range (3-8 days)">
                  ⚠️
                </span>
              )}
            </div>
            {stats.shortestPeriod && stats.longestPeriod && (
              <div className="text-sm text-gray-600">
                Range: {stats.shortestPeriod} - {stats.longestPeriod} days
              </div>
            )}
            {stats.isPeriodLengthOutsideRange && (
              <div className="text-xs text-yellow-700 mt-1 italic">
                Your actual pattern ({stats.averagePeriodLength?.toFixed(1)} days) is outside the typical range (3-8 days). 
                Phase calculations use normalized value ({stats.averagePeriodLengthNormalized?.toFixed(1)} days) for medical accuracy.
              </div>
            )}
          </div>

          {/* Cycle Regularity */}
          <div className="bg-white rounded-lg shadow-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="h-5 w-5 text-period-pink" />
              <h3 className="font-semibold text-gray-700">Cycle Regularity</h3>
            </div>
            <div className={`text-2xl font-bold mb-1 ${getRegularityColor(stats.cycleRegularity)}`}>
              {getRegularityLabel(stats.cycleRegularity)}
            </div>
            <div className="text-sm text-gray-600">
              {stats.totalCycles} valid cycle{stats.totalCycles !== 1 ? 's' : ''} (21-45 days) used for statistics
            </div>
          </div>

          {/* Last Period */}
          <div className="bg-white rounded-lg shadow-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="h-5 w-5 text-period-pink" />
              <h3 className="font-semibold text-gray-700">Last Period</h3>
            </div>
            {stats.lastPeriodDate ? (
              <>
                <div className="text-lg font-bold text-gray-800 mb-1">
                  {new Date(stats.lastPeriodDate).toLocaleDateString()}
                </div>
                {stats.daysSinceLastPeriod !== null && (
                  <div className="text-sm text-gray-600">
                    {stats.daysSinceLastPeriod} day{stats.daysSinceLastPeriod !== 1 ? 's' : ''} ago
                  </div>
                )}
              </>
            ) : (
              <div className="text-gray-500">No period logged</div>
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

        {/* Insights */}
        {stats.insights && stats.insights.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-period-pink" />
              Insights
            </h3>
            <ul className="space-y-2">
              {stats.insights.map((insight, index) => (
                <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="text-period-pink mt-1">•</span>
                  <span>{insight}</span>
                </li>
              ))}
            </ul>
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

        {/* Cycle History Section */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <History className="h-6 w-6 text-period-pink" />
            <h2 className="text-2xl font-bold text-gray-800">Cycle History</h2>
          </div>

          {/* Legend */}
          <div className="mb-6 p-4 bg-gradient-to-br from-pink-50 to-purple-50 rounded-xl border border-pink-100">
            <p className="text-sm font-semibold text-gray-700 mb-3">Phase Legend</p>
            <div className="flex flex-wrap gap-4 sm:gap-6">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full border border-white shadow-sm" style={{ backgroundColor: PHASE_COLORS.Period }} />
                <span className="text-sm text-gray-700">Period</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full border border-white shadow-sm" style={{ backgroundColor: PHASE_COLORS.Follicular }} />
                <span className="text-sm text-gray-700">Follicular</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full border border-cyan-400 shadow-sm" style={{ backgroundColor: PHASE_COLORS.Ovulation }} />
                <span className="text-sm text-gray-700">Ovulation</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full border border-white shadow-sm" style={{ backgroundColor: PHASE_COLORS.Luteal }} />
                <span className="text-sm text-gray-700">Luteal</span>
              </div>
            </div>
          </div>

          {/* Cycles List */}
          {cycles.length === 0 ? (
            <div className="text-center py-16">
              <Calendar className="h-16 w-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-600 text-lg font-semibold mb-2">No cycle history available</p>
              <p className="text-gray-500 text-sm">Log at least 2 periods to see cycle history</p>
            </div>
          ) : (
            <div className="space-y-4 sm:space-y-6">
              {cycles.map((cycle, index) => (
                <div
                  key={index}
                  className="border-2 border-gray-100 p-5 sm:p-6 hover:border-period-pink/30 transition-all rounded-lg"
                >
                  {/* Cycle Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
                    <div>
                      {cycle.isCurrent ? (
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xl sm:text-2xl font-bold text-period-pink">Current cycle</span>
                          <span className="px-3 py-1 bg-period-pink/10 text-period-pink text-sm font-semibold rounded-full">
                            {cycle.length} days
                          </span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xl sm:text-2xl font-bold text-gray-800">{cycle.length} days</span>
                        </div>
                      )}
                      <p className="text-sm sm:text-base text-gray-600 mt-1">
                        {formatDateRange(cycle.startDate, cycle.endDate, cycle.isCurrent)}
                      </p>
                    </div>
                    {cycle.isAnomaly && (
                      <span className="px-3 py-1 bg-yellow-100 text-yellow-800 text-xs font-semibold rounded-full self-start sm:self-auto">
                        Anomaly
                      </span>
                    )}
                  </div>

                  {/* Cycle Dots Visualization */}
                  <div className="flex flex-wrap gap-1.5 items-center mb-4 p-3 bg-gray-50 rounded-lg">
                    {renderCycleDots(cycle)}
                  </div>

                  {/* Phase Info */}
                  <div className="pt-4 border-t border-gray-100">
                    <div className="flex flex-wrap gap-4 text-xs sm:text-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PHASE_COLORS.Period }} />
                        <span className="text-gray-600">Period</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PHASE_COLORS.Follicular }} />
                        <span className="text-gray-600">Follicular</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full border border-cyan-400" style={{ backgroundColor: PHASE_COLORS.Ovulation }} />
                        <span className="text-gray-600">Ovulation</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PHASE_COLORS.Luteal }} />
                        <span className="text-gray-600">Luteal</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Summary Stats */}
          {cycles.length > 0 && (
            <div className="mt-8 p-5 sm:p-6 bg-gradient-to-br from-pink-50 to-purple-50 rounded-xl border border-pink-100">
              <h3 className="text-lg font-bold text-gray-800 mb-4">Summary</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-gray-600">Total Cycles</p>
                  <p className="text-2xl font-bold text-period-pink">{cycles.filter(c => !c.isCurrent).length}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Average Length</p>
                  <p className="text-2xl font-bold text-period-pink">{stats.averageCycleLength?.toFixed(1) || 'N/A'} days</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Average Period</p>
                  <p className="text-2xl font-bold text-period-pink">{stats.averagePeriodLength?.toFixed(1) || 'N/A'} days</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Anomalies</p>
                  <p className="text-2xl font-bold text-yellow-600">
                    {cycles.filter(c => c.isAnomaly).length}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default CycleStatistics
