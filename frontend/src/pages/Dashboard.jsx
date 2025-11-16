import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'
import { format } from 'date-fns'
import { getTimeBasedGreeting, getTimeBasedMessage } from '../utils/greetings'
import { getPhaseColorClass, getPhaseDescription, getPhaseEmoji, getPhaseColor } from '../utils/phaseHelpers'
import { logout, logPeriod } from '../utils/api'
import { useDataContext } from '../context/DataContext'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import PeriodLogModal from '../components/PeriodLogModal'
import { useTranslation } from '../utils/translations'
import { User, LogOut, MessageCircle, Calendar as CalendarIcon, Activity, Apple, Dumbbell, Plus } from 'lucide-react'

const Dashboard = () => {
  const { t } = useTranslation()
  const { dashboardData, loading, refreshData } = useDataContext()
  const [user, setUser] = useState(null)
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [error, setError] = useState(null)
  const [cycleStats, setCycleStats] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const navigate = useNavigate()
  
  // Extract data from context
  const currentPhase = dashboardData?.currentPhase || null
  const phaseMap = dashboardData?.phaseMap || {}
  const periodLogs = dashboardData?.periodLogs || []

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      
      // Calculate cycle stats from user data
      if (parsedUser?.last_period_date) {
        try {
          const lastPeriod = new Date(parsedUser.last_period_date)
          const today = new Date()
          const daysSince = Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24))
          const cycleLength = parsedUser.cycle_length || 28
          const daysUntil = cycleLength - daysSince
          
          setCycleStats({
            cycleLength,
            daysSince: daysSince >= 0 ? daysSince : 0,
            daysUntil: daysUntil > 0 ? daysUntil : cycleLength + daysUntil
          })
        } catch (statsError) {
          console.log('Error calculating cycle stats:', statsError)
        }
      }
    } else {
      navigate('/login')
    }
  }, [navigate])

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login')
    } catch (error) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      navigate('/login')
    }
  }

  const handleLogPeriod = async (logData) => {
    try {
      // Log the period (backend will auto-generate predictions if enough data)
      const result = await logPeriod(logData)
      
      // Update user if returned
      if (result.user) {
        localStorage.setItem('user', JSON.stringify(result.user))
        setUser(result.user)
        
        // Update cycle stats
        if (result.user?.last_period_date) {
          const lastPeriod = new Date(result.user.last_period_date)
          const today = new Date()
          const daysSince = Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24))
          const cycleLength = result.user.cycle_length || 28
          const daysUntil = cycleLength - daysSince
          
          setCycleStats({
            cycleLength,
            daysSince: daysSince >= 0 ? daysSince : 0,
            daysUntil: daysUntil > 0 ? daysUntil : cycleLength + daysUntil
          })
        }
      }
      
      // Dispatch event to clear cache and refresh all data
      window.dispatchEvent(new CustomEvent('periodLogged'))
      
      // Wait a bit for backend to generate predictions, then refresh
      setTimeout(() => {
        refreshData()
      }, 3000) // Wait 3 seconds for backend to process
      
      setIsModalOpen(false)
    } catch (error) {
      console.error('Failed to log period:', error)
      throw error
    }
  }

  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      const phaseData = phaseMap[dateStr]
      
      if (phaseData) {
        return 'rounded-full'
      }
    }
    return null
  }

  const tileStyle = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      const phaseData = phaseMap[dateStr]
      
      if (phaseData) {
        return {
          backgroundColor: getPhaseColor(phaseData.phase),
          color: '#1f2937'
        }
      }
    }
    return {}
  }

  const tileContent = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      const phaseData = phaseMap[dateStr]
      
      if (phaseData) {
        return (
          <div className="text-xs font-semibold mt-1">
            {phaseData.phase_day_id || phaseData.phase?.charAt(0)}
          </div>
        )
      }
    }
    return null
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-period-pink mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  const phase = currentPhase?.phase || 'Period'

  return (
    <div className="min-h-screen bg-gray-50">
      {/* A. Top Navigation Bar - Sticky */}
      <nav className="sticky top-0 z-50 bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <h1 className="text-2xl font-bold text-period-pink">{t('nav.periodGPT')}</h1>
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/profile')}
                className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition"
              >
                <User className="h-5 w-5" />
                <span className="hidden sm:inline">{t('nav.profile')}</span>
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition"
              >
                <LogOut className="h-5 w-5" />
                <span className="hidden sm:inline">{t('nav.logout')}</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* B. Welcome Section */}
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-2">
            {getTimeBasedGreeting()}, {user.name}!
          </h2>
        </div>

        {/* C. Error Display */}
        {error && (
          <div className="mb-6 bg-red-50 border-l-4 border-red-400 p-4 rounded">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* D. Current Phase Card */}
        {currentPhase && currentPhase.phase ? (
          <div 
            className="mb-8 rounded-lg shadow-lg p-6 border-2"
            style={{
              backgroundColor: `${getPhaseColor(currentPhase.phase)}20`,
              borderColor: getPhaseColor(currentPhase.phase)
            }}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-4xl">{getPhaseEmoji(currentPhase.phase)}</span>
                  <div>
                    <h3 className="text-2xl font-bold text-gray-800 capitalize">{t(`phase.${currentPhase.phase.toLowerCase()}`)} {t('dashboard.currentPhase')}</h3>
                    {(currentPhase.phase_day_id || currentPhase.id) && (
                      <p className="text-gray-600">{t('dashboard.day')} {currentPhase.phase_day_id || currentPhase.id}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="mb-8 bg-white rounded-lg shadow-lg p-6 border-2 border-gray-200">
            <div className="text-center py-8">
              <p className="text-gray-600 mb-2">No cycle data available yet.</p>
              <p className="text-sm text-gray-500 mb-4">
                {periodLogs.length >= 1 
                  ? "Cycle predictions are being generated. Please wait a moment and refresh, or check if RAPIDAPI_KEY is configured in your backend."
                  : "Please log your period dates to generate cycle predictions."}
              </p>
              {periodLogs.length >= 1 && (
                <button
                  onClick={() => window.location.reload()}
                  className="bg-period-pink text-white px-4 py-2 rounded-lg font-semibold hover:bg-opacity-90 transition"
                >
                  Refresh Page
                </button>
              )}
            </div>
          </div>
        )}

        {/* E. Calendar Section - 2 Columns */}
        <div className="grid md:grid-cols-2 gap-8 mb-8">
          {/* Left Side: Calendar */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <CalendarIcon className="h-5 w-5 text-period-pink" />
              Cycle Calendar
            </h3>
            <Calendar
              onChange={setSelectedDate}
              value={selectedDate}
              tileClassName={tileClassName}
              tileContent={tileContent}
              tileStyle={tileStyle}
              className="w-full"
            />
            
            {/* Legend */}
            <div className="mt-6 flex flex-wrap gap-4 justify-center">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-menstrual"></div>
                <span className="text-sm">{t('phase.period')}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-follicular"></div>
                <span className="text-sm">{t('phase.follicular')}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-ovulation"></div>
                <span className="text-sm">{t('phase.ovulation')}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-luteal"></div>
                <span className="text-sm">{t('phase.luteal')}</span>
              </div>
            </div>
          </div>

          {/* Right Side: AI & Cycle Stats */}
          <div className="space-y-4">
            {/* AI Assistant Card */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="flex items-center gap-3 mb-3">
                <MessageCircle className="h-6 w-6 text-period-purple" />
                <h3 className="text-xl font-bold">{t('dashboard.aiAssistant')}</h3>
              </div>
              <p className="text-gray-600 mb-4">
                {t('dashboard.aiDescription')}
              </p>
              <button
                onClick={() => navigate('/chat')}
                className="w-full bg-period-purple text-white py-2 rounded-lg font-semibold hover:bg-opacity-90 transition"
              >
                {t('dashboard.startChat')}
              </button>
            </div>

            {/* Cycle Statistics Card */}
            {cycleStats && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-xl font-bold mb-4">{t('dashboard.cycleStatistics')}</h3>
                <div className="space-y-3 mb-4">
                  <div className="flex justify-between">
                    <span className="text-gray-600">{t('dashboard.cycleLength')}:</span>
                    <span className="font-semibold">{cycleStats.cycleLength} {t('dashboard.days')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">{t('dashboard.daysSincePeriod')}:</span>
                    <span className="font-semibold">{cycleStats.daysSince} {t('dashboard.days')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">{t('dashboard.daysUntilNext')}:</span>
                    <span className="font-semibold">{cycleStats.daysUntil} {t('dashboard.days')}</span>
                  </div>
                </div>
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="w-full flex items-center justify-center gap-2 bg-period-pink text-white px-4 py-2 rounded-lg font-semibold hover:bg-opacity-90 transition shadow-lg"
                >
                  <Plus className="h-5 w-5" />
                  <span>{t('dashboard.logPeriod')}</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* F. Three Main Feature Cards */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <button
            onClick={() => navigate('/hormones')}
            className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition text-left"
          >
            <div className="flex items-center gap-3 mb-3">
              <Activity className="h-8 w-8 text-period-pink" />
              <h3 className="text-xl font-bold">{t('dashboard.hormones')}</h3>
            </div>
            <p className="text-gray-600">
              {t('dashboard.hormonesDesc')}
            </p>
          </button>

          <button
            onClick={() => navigate('/nutrition')}
            className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition text-left"
          >
            <div className="flex items-center gap-3 mb-3">
              <Apple className="h-8 w-8 text-period-purple" />
              <h3 className="text-xl font-bold">{t('dashboard.nutrition')}</h3>
            </div>
            <p className="text-gray-600">
              {t('dashboard.nutritionDesc')}
            </p>
          </button>

          <button
            onClick={() => navigate('/exercise')}
            className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition text-left"
          >
            <div className="flex items-center gap-3 mb-3">
              <Dumbbell className="h-8 w-8 text-period-lavender" />
              <h3 className="text-xl font-bold">{t('dashboard.exercise')}</h3>
            </div>
            <p className="text-gray-600">
              {t('dashboard.exerciseDesc')}
            </p>
          </button>
        </div>

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>

      {/* Period Log Modal */}
      <PeriodLogModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleLogPeriod}
        selectedDate={format(selectedDate, 'yyyy-MM-dd')}
      />
    </div>
  )
}

export default Dashboard
