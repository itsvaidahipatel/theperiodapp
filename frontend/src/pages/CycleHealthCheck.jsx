import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from '../utils/translations'
import { getCycleHealthCheck } from '../utils/api'
import { AlertCircle, CheckCircle, AlertTriangle, ArrowLeft, Calendar, Activity, TrendingUp } from 'lucide-react'
import SafetyDisclaimer from '../components/SafetyDisclaimer'

const CycleHealthCheck = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [healthData, setHealthData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchHealthCheck = async () => {
      try {
        setLoading(true)
        const data = await getCycleHealthCheck()
        setHealthData(data)
      } catch (err) {
        console.error('Failed to fetch cycle health check:', err)
        setError(err.message || 'Failed to load cycle health check')
      } finally {
        setLoading(false)
      }
    }

    fetchHealthCheck()
  }, [])

  const getRiskColor = (riskLevel) => {
    switch (riskLevel) {
      case 'high':
        return 'text-red-600 bg-red-50 border-red-200'
      case 'medium':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200'
      case 'low':
        return 'text-green-600 bg-green-50 border-green-200'
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'high':
        return <AlertCircle className="h-5 w-5 text-red-600" />
      case 'medium':
        return <AlertTriangle className="h-5 w-5 text-yellow-600" />
      case 'low':
        return <AlertCircle className="h-5 w-5 text-blue-600" />
      default:
        return <AlertCircle className="h-5 w-5 text-gray-600" />
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-period-pink"></div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => navigate('/dashboard')}
            className="mb-6 flex items-center gap-2 text-period-pink hover:opacity-80"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('common.back') || 'Back to Dashboard'}
          </button>
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center gap-3 text-red-600 mb-4">
              <AlertCircle className="h-6 w-6" />
              <h2 className="text-xl font-bold">Error</h2>
            </div>
            <p className="text-gray-700">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  // Always show data if available, even if insufficient for full analysis
  const showCurrentCycleStats = healthData?.current_cycle_stats
  const hasTimeline = healthData?.cycle_timeline && healthData.cycle_timeline.length > 0

  // If no data at all, show message
  if (!healthData || (!healthData.current_cycle_stats && !hasTimeline)) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => navigate('/dashboard')}
            className="mb-6 flex items-center gap-2 text-period-pink hover:opacity-80"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('common.back') || 'Back to Dashboard'}
          </button>
          
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <div className="flex items-center gap-3 text-period-pink mb-4">
              <Calendar className="h-6 w-6" />
              <h1 className="text-2xl font-bold">{t('healthCheck.title') || 'Cycle Health Check'}</h1>
            </div>
            
            <div className="bg-blue-50 border-l-4 border-blue-400 p-4 rounded">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-blue-800 font-semibold mb-1">{t('healthCheck.insufficientData') || 'Insufficient Data'}</p>
                  <p className="text-blue-700">{healthData?.message || 'No period data available. Please log at least one period to see your cycle information.'}</p>
                </div>
              </div>
            </div>
          </div>

          <SafetyDisclaimer />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <button
          onClick={() => navigate('/dashboard')}
          className="mb-6 flex items-center gap-2 text-period-pink hover:opacity-80"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('common.back') || 'Back to Dashboard'}
        </button>

        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center gap-3 text-period-pink mb-4">
            <Calendar className="h-6 w-6" />
            <h1 className="text-2xl font-bold">{t('healthCheck.title') || 'Cycle Health Check'}</h1>
          </div>
          <p className="text-gray-600 mb-4">
            {t('healthCheck.subtitle') || 'Analysis of your last 7 cycles for potential abnormalities'}
          </p>
          
          {/* Risk Level Badge */}
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border ${getRiskColor(healthData.risk_level)}`}>
            {healthData.risk_level === 'low' ? (
              <CheckCircle className="h-5 w-5" />
            ) : (
              <AlertCircle className="h-5 w-5" />
            )}
            <span className="font-semibold capitalize">
              {t(`healthCheck.riskLevel.${healthData.risk_level}`) || `${healthData.risk_level} Risk`}
            </span>
          </div>
        </div>

        {/* Cycle Timeline - Visual Dot Representation (Display First) */}
        {healthData.cycle_timeline && healthData.cycle_timeline.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Calendar className="h-6 w-6 text-period-pink" />
                {t('healthCheck.cycleTimeline') || 'Cycle Timeline'}
              </h2>
            </div>
            
            {/* Color Legend */}
            <div className="flex flex-wrap items-center gap-4 mb-6 p-3 bg-gray-50 rounded-lg text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <span className="text-gray-700">{t('healthCheck.legend.period') || 'Period'}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-teal-400"></div>
                <span className="text-gray-700">{t('healthCheck.legend.fertile') || 'Fertile Window'}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-gray-300"></div>
                <span className="text-gray-700">{t('healthCheck.legend.other') || 'Other Phases'}</span>
              </div>
            </div>
            
            <div className="space-y-5">
              {healthData.cycle_timeline.map((cycle, index) => {
                const startDate = new Date(cycle.start_date)
                const endDate = new Date(cycle.end_date)
                const isCurrent = cycle.is_current
                
                // Format date range
                const dateRange = isCurrent
                  ? `Started ${startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
                  : `${startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
                
                // Get daily phases for visual representation
                const dailyPhases = cycle.daily_phases || []
                
                // Function to get dot color based on phase
                const getDotColor = (phase) => {
                  switch (phase?.toLowerCase()) {
                    case 'period':
                    case 'menstrual':
                      return 'bg-red-500' // Red for period
                    case 'ovulation':
                      return 'bg-teal-400' // Teal for ovulation/fertile
                    case 'follicular':
                    case 'luteal':
                    default:
                      return 'bg-gray-300' // Light grey for other phases
                  }
                }
                
                return (
                  <div
                    key={index}
                    className={`border rounded-lg p-4 transition-shadow ${
                      isCurrent 
                        ? 'border-period-pink bg-pink-50/30 shadow-sm' 
                        : 'border-gray-200 bg-white hover:shadow-md'
                    }`}
                  >
                    {/* Cycle Header */}
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="font-bold text-gray-900 text-base">
                          {isCurrent 
                            ? `${t('healthCheck.currentCycle') || 'Current cycle'}: ${cycle.cycle_length} ${t('common.days') || 'days'}`
                            : `${cycle.cycle_length} ${t('common.days') || 'days'}`
                          }
                        </div>
                        <div className="text-sm text-gray-500 mt-1">
                          {dateRange}
                        </div>
                      </div>
                      {!isCurrent && (
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          cycle.status === 'normal'
                            ? 'bg-green-100 text-green-700'
                            : cycle.status === 'short'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          {cycle.status === 'normal' ? (t('healthCheck.normal') || 'Normal') :
                           cycle.status === 'short' ? (t('healthCheck.short') || 'Short') :
                           (t('healthCheck.long') || 'Long')}
                        </span>
                      )}
                    </div>
                    
                    {/* Visual Dot Representation */}
                    {dailyPhases.length > 0 ? (
                      <div className="flex flex-wrap gap-1 items-center">
                        {dailyPhases.map((day, dayIndex) => (
                          <div
                            key={dayIndex}
                            className={`w-2.5 h-2.5 rounded-full ${getDotColor(day.phase)} transition-opacity hover:opacity-80`}
                            title={`Day ${day.day}: ${day.phase} (${day.date})`}
                          />
                        ))}
                      </div>
                    ) : (
                      // Fallback: Generate dots based on cycle length and estimated phases
                      <div className="flex flex-wrap gap-1 items-center">
                        {Array.from({ length: cycle.cycle_length }).map((_, dayIndex) => {
                          const day = dayIndex + 1
                          // Estimate phase based on day number
                          let phase = 'Follicular'
                          if (day <= 5) {
                            phase = 'Period' // First 5 days = period
                          } else if (day >= cycle.cycle_length - 14 && day <= cycle.cycle_length - 12) {
                            phase = 'Ovulation' // Estimated ovulation window
                          } else if (day > cycle.cycle_length - 14) {
                            phase = 'Luteal' // Last 14 days = luteal
                          }
                          
                          return (
                            <div
                              key={dayIndex}
                              className={`w-2.5 h-2.5 rounded-full ${getDotColor(phase)} transition-opacity hover:opacity-80`}
                              title={`Day ${day}: ${phase}`}
                            />
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Current Cycle Stats - Enhanced with all Dashboard stats */}
        {healthData.current_cycle_stats && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Activity className="h-5 w-5 text-period-pink" />
              {t('healthCheck.currentCycleStats') || 'Current Cycle Statistics'}
            </h2>
            
            {/* Current Phase Badge */}
            {healthData.current_phase && (
              <div className="mb-4 p-4 rounded-lg bg-gradient-to-r from-period-pink/10 to-period-purple/10 border border-period-pink/20">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{t('healthCheck.currentPhase') || 'Current Phase'}:</span>
                  <span className="font-bold text-lg text-period-pink capitalize">{healthData.current_phase.phase}</span>
                </div>
                {healthData.current_phase.phase_day_id && (
                  <div className="text-sm text-gray-500 mt-1">Day {healthData.current_phase.phase_day_id}</div>
                )}
              </div>
            )}
            
            {/* Basic Cycle Info - Enhanced Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
              <div className="bg-gradient-to-br from-pink-50 to-purple-50 p-4 rounded-lg">
                <div className="text-xs text-gray-600 mb-1">{t('healthCheck.cycleLength') || 'Cycle Length'}</div>
                <div className="font-bold text-xl text-period-pink">{healthData.current_cycle_stats.cycle_length} {t('common.days') || 'days'}</div>
              </div>
              {healthData.current_cycle_stats.period_length && (
                <div className="bg-gradient-to-br from-blue-50 to-cyan-50 p-4 rounded-lg">
                  <div className="text-xs text-gray-600 mb-1">{t('healthCheck.periodLength') || 'Period Length'}</div>
                  <div className="font-bold text-xl text-blue-600">{healthData.current_cycle_stats.period_length} {t('common.days') || 'days'}</div>
                </div>
              )}
              {healthData.current_cycle_stats.last_period_date && (
                <div className="bg-gradient-to-br from-purple-50 to-pink-50 p-4 rounded-lg">
                  <div className="text-xs text-gray-600 mb-1">{t('healthCheck.lastPeriodDate') || 'Last Period'}</div>
                  <div className="font-bold text-lg text-period-pink">
                    {new Date(healthData.current_cycle_stats.last_period_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </div>
                </div>
              )}
            </div>
            
            {/* Cycle Progress - Enhanced */}
            <div className="mb-4 pb-4 border-b border-gray-200">
              <div className="grid grid-cols-2 gap-4 mb-4">
                {healthData.current_cycle_stats.days_since_period !== null && healthData.current_cycle_stats.days_since_period !== undefined && (
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <div className="text-xs text-gray-500 mb-1">{t('healthCheck.daysSincePeriod') || 'Days Since Period'}</div>
                    <div className="font-bold text-xl">
                      {healthData.current_cycle_stats.days_since_period} {t('common.days') || 'days'}
                    </div>
                  </div>
                )}
                {healthData.current_cycle_stats.days_until_next_period !== null && healthData.current_cycle_stats.days_until_next_period !== undefined && (
                  <div className="bg-pink-50 p-4 rounded-lg">
                    <div className="text-xs text-gray-500 mb-1">{t('healthCheck.daysUntilNext') || 'Days Until Next'}</div>
                    <div className="font-bold text-xl text-period-pink">
                      {healthData.current_cycle_stats.days_until_next_period > 0 
                        ? `${healthData.current_cycle_stats.days_until_next_period} ${t('common.days') || 'days'}`
                        : t('healthCheck.overdue') || 'Overdue'}
                    </div>
                  </div>
                )}
              </div>
              {/* Enhanced Progress bar */}
              {healthData.current_cycle_stats.days_since_period !== null && healthData.current_cycle_stats.days_since_period !== undefined && healthData.current_cycle_stats.cycle_length && (
                <div className="relative">
                  <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                    <div 
                      className="bg-gradient-to-r from-period-pink via-period-purple to-period-pink h-3 rounded-full transition-all duration-500 shadow-sm"
                      style={{ width: `${Math.min(100, (healthData.current_cycle_stats.days_since_period / healthData.current_cycle_stats.cycle_length) * 100)}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>Day 1</span>
                    <span className="font-semibold text-period-pink">Day {healthData.current_cycle_stats.days_since_period}</span>
                    <span>Day {healthData.current_cycle_stats.cycle_length}</span>
                  </div>
                </div>
              )}
            </div>
            
            {/* Additional Stats */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {healthData.current_cycle_stats.estimated_next_period && (
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-1">{t('healthCheck.estimatedNext') || 'Estimated Next Period'}</div>
                  <div className="text-lg font-bold text-period-purple">
                    {new Date(healthData.current_cycle_stats.estimated_next_period).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </div>
                </div>
              )}
              {healthData.predicted_ovulation_date && (
                <div className="bg-purple-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-1">{t('healthCheck.predictedOvulation') || 'Predicted Ovulation'}</div>
                  <div className="text-lg font-bold text-period-purple">
                    {new Date(healthData.predicted_ovulation_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </div>
                  {(() => {
                    const today = new Date()
                    today.setHours(0, 0, 0, 0)
                    const ovDate = new Date(healthData.predicted_ovulation_date)
                    ovDate.setHours(0, 0, 0, 0)
                    const daysUntilOv = Math.floor((ovDate - today) / (1000 * 60 * 60 * 24))
                    if (daysUntilOv >= 0 && daysUntilOv <= 5) {
                      return (
                        <div className="text-xs text-period-purple mt-1">
                          {daysUntilOv === 0 ? 'Today' : `In ${daysUntilOv} ${t('common.days') || 'days'}`}
                        </div>
                      )
                    }
                    return null
                  })()}
                </div>
              )}
              {healthData.cycles_tracked && (
                <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-1">{t('healthCheck.cyclesTracked') || 'Cycles Tracked'}</div>
                  <div className="font-bold text-xl text-green-600">{healthData.cycles_tracked}</div>
                </div>
              )}
              {healthData.cycle_regularity && (
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-1">{t('healthCheck.cycleRegularity') || 'Regularity'}</div>
                  <div className={`font-bold text-lg ${
                    healthData.cycle_regularity === 'Very Regular' ? 'text-green-600' :
                    healthData.cycle_regularity === 'Regular' ? 'text-blue-600' :
                    healthData.cycle_regularity === 'Somewhat Irregular' ? 'text-yellow-600' :
                    'text-orange-600'
                  }`}>
                    {healthData.cycle_regularity}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Cycle Statistics */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5 text-period-pink" />
            {t('healthCheck.cycleStatistics') || 'Cycle Statistics (Last 7 Cycles)'}
          </h2>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">{t('healthCheck.cyclesAnalyzed') || 'Cycles Analyzed'}</div>
              <div className="text-2xl font-bold text-period-pink">{healthData.cycles_analyzed}</div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">{t('healthCheck.averageLength') || 'Average Length'}</div>
              <div className="text-2xl font-bold">{healthData.cycle_statistics.average_cycle_length} {t('common.days') || 'days'}</div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">{t('healthCheck.shortestCycle') || 'Shortest'}</div>
              <div className="text-2xl font-bold">{healthData.cycle_statistics.min_cycle_length} {t('common.days') || 'days'}</div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">{t('healthCheck.longestCycle') || 'Longest'}</div>
              <div className="text-2xl font-bold">{healthData.cycle_statistics.max_cycle_length} {t('common.days') || 'days'}</div>
            </div>
          </div>


          {/* Cycle Details Table */}
          <div className="overflow-x-auto">
            <h3 className="text-lg font-semibold mb-3">{t('healthCheck.last7Cycles') || 'Last 7 Cycles Details'}</h3>
            <table className="w-full">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">{t('healthCheck.cycle') || 'Cycle'}</th>
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">{t('healthCheck.length') || 'Length (days)'}</th>
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">{t('healthCheck.status') || 'Status'}</th>
                </tr>
              </thead>
              <tbody>
                {healthData.cycle_data.map((cycle, index) => (
                  <tr key={index} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold">{cycle.cycle_number}</td>
                    <td className="px-4 py-3">{cycle.cycle_length} {t('common.days') || 'days'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        cycle.status === 'normal' ? 'bg-green-100 text-green-700' :
                        cycle.status === 'short' ? 'bg-red-100 text-red-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {cycle.status === 'normal' ? (t('healthCheck.normal') || 'Normal') :
                         cycle.status === 'short' ? (t('healthCheck.short') || 'Short') :
                         (t('healthCheck.long') || 'Long')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Insufficient Data Warning (if applicable) */}
        {!healthData.has_sufficient_data && (
          <div className="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-lg mb-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-blue-800 font-semibold mb-1">{t('healthCheck.insufficientData') || 'Limited Data'}</p>
                <p className="text-blue-700">
                  {healthData.message || 'You have logged 1 period. Log at least 2 periods to get cycle length analysis and abnormality detection.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Abnormalities */}
        {healthData.has_sufficient_data && healthData.abnormalities && healthData.abnormalities.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-600" />
              {t('healthCheck.abnormalities') || 'Abnormalities Detected'}
            </h2>
            
            <div className="space-y-4">
              {healthData.abnormalities.map((abnormality, index) => (
                <div
                  key={index}
                  className={`border-l-4 p-4 rounded ${
                    abnormality.severity === 'high' ? 'border-red-500 bg-red-50' :
                    abnormality.severity === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                    'border-blue-500 bg-blue-50'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {getSeverityIcon(abnormality.severity)}
                    <div className="flex-1">
                      <h3 className="font-bold text-lg mb-2">{abnormality.title}</h3>
                      <p className="text-gray-700 mb-2">{abnormality.description}</p>
                      {abnormality.cycles_affected && (
                        <p className="text-sm text-gray-600 mb-2">
                          <strong>{t('healthCheck.affectedCycles') || 'Affected Cycles'}:</strong>{' '}
                          {abnormality.cycles_affected.join(', ')} {t('common.days') || 'days'}
                        </p>
                      )}
                      <p className="text-sm font-semibold text-gray-800 mt-2">
                        {t('healthCheck.medicalConcern') || 'Medical Concern'}: {abnormality.medical_concern}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No Abnormalities */}
        {healthData.has_sufficient_data && (!healthData.abnormalities || healthData.abnormalities.length === 0) && (
          <div className="bg-green-50 border-l-4 border-green-400 p-6 rounded-lg mb-6">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-6 w-6 text-green-600" />
              <div>
                <h3 className="font-bold text-green-800 mb-2">
                  {t('healthCheck.noAbnormalities') || 'No Abnormalities Detected'}
                </h3>
                <p className="text-green-700">
                  {t('healthCheck.normalCycles') || 'Your cycles appear to be within normal ranges. Continue tracking for ongoing monitoring.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Recommendations */}
        {healthData.recommendations && healthData.recommendations.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-period-pink" />
              {t('healthCheck.recommendations') || 'Recommendations'}
            </h2>
            <ul className="space-y-3">
              {healthData.recommendations.map((rec, index) => (
                <li key={index} className="flex items-start gap-3">
                  <span className="text-period-pink font-bold mt-1">•</span>
                  <span className="text-gray-700">{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Medical Disclaimer */}
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

export default CycleHealthCheck
