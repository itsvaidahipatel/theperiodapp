import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCycleStats } from '../utils/api'
import { Activity, TrendingUp, Calendar, AlertCircle, CheckCircle2, History } from 'lucide-react'

const CycleStats = () => {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true)
        const data = await getCycleStats()
        setStats(data)
        setError(null)
      } catch (err) {
        console.error('Error fetching cycle stats:', err)
        setError(err.message || 'Failed to load cycle statistics')
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
    
    // Refresh stats when period is logged
    const handlePeriodLogged = () => {
      fetchStats()
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    
    // Listen for prefetched cycle stats
    const handleCycleStatsPrefetched = (event) => {
      const stats = event.detail
      if (stats) {
        console.log('✅ Using prefetched cycle stats')
        setStats(stats)
        setLoading(false)
      }
    }
    window.addEventListener('cycleStatsPrefetched', handleCycleStatsPrefetched)
    
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
      window.removeEventListener('cycleStatsPrefetched', handleCycleStatsPrefetched)
    }
  }, [])

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-period-pink"></div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="text-red-600 text-center py-4">
          <AlertCircle className="h-6 w-6 mx-auto mb-2" />
          <p>{error}</p>
        </div>
      </div>
    )
  }

  if (!stats) {
    return null
  }

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

  // Calculate chart data
  const cycleLengths = stats.cycleLengths || []
  const maxCycle = cycleLengths.length > 0 ? Math.max(...cycleLengths) : 1
  const minCycle = cycleLengths.length > 0 ? Math.min(...cycleLengths) : 1

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Activity className="h-6 w-6 text-period-pink" />
        Cycle Statistics
      </h2>

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
        <div className="bg-gray-50 rounded-lg p-4">
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
        <div className="bg-gray-50 rounded-lg p-4">
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
        <div className="bg-gray-50 rounded-lg p-4">
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
        <div className="bg-gray-50 rounded-lg p-4">
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
        <div className="mb-6">
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
        <div className="mt-6">
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
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center gap-2 text-yellow-800">
            <AlertCircle className="h-5 w-5" />
            <span className="font-semibold">
              {stats.anomalies} cycle{stats.anomalies !== 1 ? 's' : ''} outside normal range (21-45 days)
            </span>
          </div>
        </div>
      )}

      {/* Cycle History Button */}
      <div className="mt-6">
        <button
          onClick={() => navigate('/cycle-history')}
          className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-period-pink to-period-purple text-white px-4 py-3 rounded-lg font-semibold hover:opacity-90 transition-all shadow-md hover:shadow-lg"
        >
          <History className="h-5 w-5" />
          <span>View Cycle History</span>
        </button>
      </div>
    </div>
  )
}

export default CycleStats
