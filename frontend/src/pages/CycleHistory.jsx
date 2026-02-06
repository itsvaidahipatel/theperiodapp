import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Calendar } from 'lucide-react'
import Navbar from '../components/Navbar'
import { getCycleStats } from '../utils/api'
import { format, parseISO, addDays } from 'date-fns'

// Pastel color scheme matching app theme
const PHASE_COLORS = {
  Period: '#F8BBD9',      // Soft pastel pink
  Follicular: '#FEF3C7',  // Soft pastel yellow/cream
  Ovulation: '#B8E6E6',   // Soft pastel teal/cyan
  Luteal: '#E1BEE7',      // Soft pastel lavender
}

const CycleHistoryPage = () => {
  const navigate = useNavigate()
  const [cycles, setCycles] = useState([])
  const [loading, setLoading] = useState(true)
  const [avgPeriodLength, setAvgPeriodLength] = useState(5)
  const [avgCycleLength, setAvgCycleLength] = useState(28)
  const [isPrefetching, setIsPrefetching] = useState(false)

  // Fetch cycles function - reusable
  const fetchCycles = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)
      const stats = await getCycleStats()
      console.log('📊 Cycle stats received:', { 
        allCyclesCount: stats.allCycles?.length || 0,
        allCycles: stats.allCycles,
        totalCycles: stats.totalCycles,
        stats: stats
      })
      
      // Debug: Check if allCycles is empty
      if (!stats.allCycles || stats.allCycles.length === 0) {
        console.warn('⚠️ No cycles in allCycles array. Stats:', {
          totalCycles: stats.totalCycles,
          lastPeriodDate: stats.lastPeriodDate,
          averageCycleLength: stats.averageCycleLength
        })
      }
      
      setCycles(stats.allCycles || [])
      setAvgPeriodLength(stats.averagePeriodLength || 5)
      setAvgCycleLength(stats.averageCycleLength || 28)
    } catch (err) {
      console.error('Failed to fetch cycle history:', err)
      console.error('Error details:', err.response?.data || err.message)
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  useEffect(() => {
    // Initial fetch
    fetchCycles()

    // Refresh when period is logged
    const handlePeriodLogged = () => {
      console.log('🔄 Period logged - refreshing cycle history')
      fetchCycles()
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    
    // Listen for prefetched cycle history data
    const handleCycleHistoryPrefetched = (event) => {
      const stats = event.detail
      if (stats?.allCycles) {
        console.log('✅ Using prefetched cycle history data')
        setCycles(stats.allCycles)
        setAvgPeriodLength(stats.averagePeriodLength || 5)
        setAvgCycleLength(stats.averageCycleLength || 28)
        setLoading(false)
      }
    }
    window.addEventListener('cycleHistoryPrefetched', handleCycleHistoryPrefetched)
    
    // Refresh when page becomes visible (user switches back to tab)
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        console.log('🔄 Page visible - refreshing cycle history')
        fetchCycles(false) // Don't show loading spinner on visibility change
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    
    // Refresh when window gains focus (user clicks back to tab)
    const handleFocus = () => {
      console.log('🔄 Window focused - refreshing cycle history')
      fetchCycles(false) // Don't show loading spinner on focus
    }
    window.addEventListener('focus', handleFocus)
    
    // Listen for calendar phase map updates (when calendar data changes)
    const handleCalendarUpdate = () => {
      console.log('🔄 Calendar updated - refreshing cycle history')
      // Small delay to let backend process
      setTimeout(() => {
        fetchCycles(false)
      }, 1000)
    }
    window.addEventListener('calendarUpdated', handleCalendarUpdate)
    
    // Polling fallback: Check for updates every 30 seconds if page is visible
    const pollInterval = setInterval(() => {
      if (!document.hidden) {
        console.log('🔄 Polling cycle history for updates')
        fetchCycles(false)
      }
    }, 30000) // Every 30 seconds
    
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
      window.removeEventListener('cycleHistoryPrefetched', handleCycleHistoryPrefetched)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
      window.removeEventListener('calendarUpdated', handleCalendarUpdate)
      clearInterval(pollInterval)
    }
  }, [])

  // Prefetch cycle history data in background after initial load
  useEffect(() => {
    if (loading || isPrefetching) return

    const prefetchCycleHistory = async () => {
      setIsPrefetching(true)
      try {
        // Prefetch cycle stats to ensure data is ready
        const stats = await getCycleStats()
        if (stats?.allCycles) {
          setCycles(stats.allCycles)
          setAvgPeriodLength(stats.averagePeriodLength || 5)
          setAvgCycleLength(stats.averageCycleLength || 28)
          console.log('✅ Cycle history prefetched')
        }
      } catch (err) {
        console.error('Error prefetching cycle history:', err)
      } finally {
        setIsPrefetching(false)
      }
    }

    // Prefetch after initial load completes
    const timeoutId = setTimeout(() => {
      prefetchCycleHistory()
    }, 500)

    return () => clearTimeout(timeoutId)
  }, [loading])

  const calculatePhaseForDay = (dayInCycle, cycleLength, periodLength) => {
    // Period phase: days 1 to periodLength
    if (dayInCycle <= periodLength) {
      return { phase: 'Period', color: PHASE_COLORS.Period }
    }
    
    // Calculate ovulation day (cycle_length - 14, minimum day 8)
    const ovulationDay = Math.max(8, cycleLength - 14)
    const fertileStart = ovulationDay - 5
    const fertileEnd = ovulationDay
    
    // Fertile window: 5 days before ovulation to ovulation day
    if (dayInCycle >= fertileStart && dayInCycle <= fertileEnd) {
      return { phase: 'Ovulation', color: PHASE_COLORS.Ovulation }
    }
    
    // Luteal phase: after ovulation until next period
    if (dayInCycle > ovulationDay) {
      return { phase: 'Luteal', color: PHASE_COLORS.Luteal }
    }
    
    // Follicular phase: after period, before fertile window
    return { phase: 'Follicular', color: PHASE_COLORS.Follicular }
  }

  const renderCycleDots = (cycle) => {
    const cycleLength = cycle.length
    const periodLength = Math.min(Math.round(avgPeriodLength), Math.max(2, cycleLength - 10))
    const dots = []
    
    // For current cycle, show up to today or estimated cycle length
    const maxDays = cycle.isCurrent 
      ? Math.min(cycleLength + 7, Math.max(cycleLength, 28))
      : cycleLength
    
    // Calculate ovulation day
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
          <p className="text-gray-600 text-sm sm:text-base">
            View all your menstrual cycles with phase visualization
          </p>
        </div>

        {/* Legend */}
        <div className="mb-6 p-4 sm:p-5 bg-gradient-to-br from-pink-50 to-purple-50 rounded-xl border border-pink-100">
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
          <div className="space-y-4 sm:space-y-6">
            {cycles.map((cycle, index) => (
              <div
                key={index}
                className="bg-white rounded-xl border-2 border-gray-100 p-5 sm:p-6 hover:border-period-pink/30 transition-all shadow-md hover:shadow-lg"
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
                <p className="text-2xl font-bold text-period-pink">{avgCycleLength.toFixed(1)} days</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Average Period</p>
                <p className="text-2xl font-bold text-period-pink">{avgPeriodLength.toFixed(1)} days</p>
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
  )
}

export default CycleHistoryPage
