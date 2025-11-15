import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'
import { format } from 'date-fns'
import { getTimeBasedGreeting, getTimeBasedMessage } from '../utils/greetings'
import { getPhaseColorClass, getPhaseDescription, getPhaseEmoji, getPhaseTips, getPhaseColor } from '../utils/phaseHelpers'
import { getCurrentPhase, getPhaseMap, getPeriodLogs, logout, logPeriod, predictCycles } from '../utils/api'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import PeriodLogModal from '../components/PeriodLogModal'
import { User, LogOut, MessageCircle, Calendar as CalendarIcon, Activity, Apple, Dumbbell, Plus } from 'lucide-react'

const Dashboard = () => {
  const [user, setUser] = useState(null)
  const [currentPhase, setCurrentPhase] = useState(null)
  const [phaseMap, setPhaseMap] = useState({})
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [cycleStats, setCycleStats] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [periodLogs, setPeriodLogs] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      setUser(JSON.parse(userData))
    } else {
      navigate('/login')
    }
  }, [navigate])

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch current phase (this might fail if no cycle data exists, which is okay)
        try {
          const phase = await getCurrentPhase()
          // Only set if we got actual phase data (not just a message)
          if (phase && phase.phase) {
            setCurrentPhase(phase)
          } else {
            setCurrentPhase(null)
          }
        } catch (phaseError) {
          console.log('No phase data available yet:', phaseError)
          // This is okay - user might not have cycle predictions yet
          setCurrentPhase(null)
        }

        // Fetch phase map for calendar (this might also fail, which is okay)
        try {
          const today = new Date()
          const startDate = format(new Date(today.getFullYear(), today.getMonth() - 1, 1), 'yyyy-MM-dd')
          const endDate = format(new Date(today.getFullYear(), today.getMonth() + 2, 0), 'yyyy-MM-dd')
          
          const phaseMapResponse = await getPhaseMap(startDate, endDate)
          const map = {}
          if (phaseMapResponse.phase_map) {
            phaseMapResponse.phase_map.forEach((item) => {
              map[item.date] = item
            })
          }
          setPhaseMap(map)
        } catch (mapError) {
          console.log('No phase map data available yet:', mapError)
          // This is okay - user might not have cycle predictions yet
          setPhaseMap({})
        }

        // Fetch period logs
        try {
          const logs = await getPeriodLogs()
          setPeriodLogs(logs)
        } catch (logError) {
          console.log('No period logs available:', logError)
        }

        // Calculate cycle stats (this should always work if user has last_period_date)
        if (user?.last_period_date) {
          try {
            const lastPeriod = new Date(user.last_period_date)
            const today = new Date()
            const daysSince = Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24))
            const cycleLength = user.cycle_length || 28
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
      } catch (err) {
        console.error('Failed to fetch data:', err)
        // Only show error if it's a critical failure
        if (err.message && !err.message.includes('No phase data')) {
          setError('Failed to load some dashboard data. Some features may not be available.')
        }
      } finally {
        setLoading(false)
      }
    }

    if (user) {
      fetchData()
    }
  }, [user])

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
      }
      
      // Refresh all data
      const logs = await getPeriodLogs()
      setPeriodLogs(logs)
      
      // Wait a bit for backend to generate predictions (if applicable)
      // Then retry fetching phase data with exponential backoff
      const refreshPhaseData = async (retries = 5, initialDelay = 3000) => {
        for (let i = 0; i < retries; i++) {
          const delay = initialDelay * (i + 1) // 3s, 6s, 9s, 12s, 15s
          console.log(`Waiting ${delay}ms before attempt ${i + 1}/${retries} to fetch phase data...`)
          await new Promise(resolve => setTimeout(resolve, delay))
          
          try {
            console.log(`Attempt ${i + 1}: Fetching current phase...`)
            const phase = await getCurrentPhase()
            console.log(`Attempt ${i + 1}: Got phase response:`, phase)
            
            // Only set if we got actual phase data (not just a message)
            if (phase && phase.phase) {
              console.log(`✅ Success! Got phase data:`, phase.phase)
              setCurrentPhase(phase)
              
              // Also refresh phase map if we got phase data
              try {
                const today = new Date()
                const startDate = format(new Date(today.getFullYear(), today.getMonth() - 1, 1), 'yyyy-MM-dd')
                const endDate = format(new Date(today.getFullYear(), today.getMonth() + 2, 0), 'yyyy-MM-dd')
                console.log(`Fetching phase map from ${startDate} to ${endDate}...`)
                const phaseMapResponse = await getPhaseMap(startDate, endDate)
                console.log(`Got phase map response:`, phaseMapResponse)
                const map = {}
                if (phaseMapResponse.phase_map && phaseMapResponse.phase_map.length > 0) {
                  phaseMapResponse.phase_map.forEach((item) => {
                    map[item.date] = item
                  })
                  console.log(`✅ Loaded ${phaseMapResponse.phase_map.length} phase mappings`)
                } else {
                  console.log(`⚠️ Phase map is empty`)
                }
                setPhaseMap(map)
              } catch (mapError) {
                console.error('Error fetching phase map:', mapError)
              }
              
              return // Success, exit retry loop
            } else {
              console.log(`Attempt ${i + 1}: No phase data yet (phase is null or missing)`)
            }
          } catch (phaseError) {
            console.error(`Attempt ${i + 1} failed:`, phaseError)
            if (i === retries - 1) {
              console.error('❌ No phase data available after all retries')
            }
          }
        }
      }
      
      // Start refreshing phase data in background
      refreshPhaseData()
      
      // Refresh phase map immediately (might be empty, that's okay)
      try {
        const today = new Date()
        const startDate = format(new Date(today.getFullYear(), today.getMonth() - 1, 1), 'yyyy-MM-dd')
        const endDate = format(new Date(today.getFullYear(), today.getMonth() + 2, 0), 'yyyy-MM-dd')
        const phaseMapResponse = await getPhaseMap(startDate, endDate)
        const map = {}
        if (phaseMapResponse.phase_map) {
          phaseMapResponse.phase_map.forEach((item) => {
            map[item.date] = item
          })
        }
        setPhaseMap(map)
      } catch (mapError) {
        console.log('No phase map yet:', mapError)
      }
      
      // Refresh cycle stats
      const updatedUserData = result.user || user
      if (updatedUserData?.last_period_date) {
        const lastPeriod = new Date(updatedUserData.last_period_date)
        const today = new Date()
        const daysSince = Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24))
        const cycleLength = updatedUserData.cycle_length || 28
        const daysUntil = cycleLength - daysSince
        
        setCycleStats({
          cycleLength,
          daysSince: daysSince >= 0 ? daysSince : 0,
          daysUntil: daysUntil > 0 ? daysUntil : cycleLength + daysUntil
        })
      }
      
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
  const tips = getPhaseTips(phase)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* A. Top Navigation Bar - Sticky */}
      <nav className="sticky top-0 z-50 bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <h1 className="text-2xl font-bold text-period-pink">Period GPT</h1>
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/profile')}
                className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition"
              >
                <User className="h-5 w-5" />
                <span className="hidden sm:inline">Profile</span>
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition"
              >
                <LogOut className="h-5 w-5" />
                <span className="hidden sm:inline">Logout</span>
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
          <p className="text-lg text-gray-600">
            {getTimeBasedMessage(phase)}
          </p>
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
                    <h3 className="text-2xl font-bold text-gray-800 capitalize">{currentPhase.phase} Phase</h3>
                    {(currentPhase.phase_day_id || currentPhase.id) && (
                      <p className="text-gray-600">Day {currentPhase.phase_day_id || currentPhase.id}</p>
                    )}
                  </div>
                </div>
                <p className="text-gray-700 text-lg">{getPhaseDescription(currentPhase.phase)}</p>
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
                <span className="text-sm">Period</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-follicular"></div>
                <span className="text-sm">Follicular</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-ovulation"></div>
                <span className="text-sm">Ovulation</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-luteal"></div>
                <span className="text-sm">Luteal</span>
              </div>
            </div>
          </div>

          {/* Right Side: AI & Cycle Stats */}
          <div className="space-y-4">
            {/* AI Assistant Card */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="flex items-center gap-3 mb-3">
                <MessageCircle className="h-6 w-6 text-period-purple" />
                <h3 className="text-xl font-bold">AI Assistant</h3>
              </div>
              <p className="text-gray-600 mb-4">
                Get personalized health advice and cycle insights from our AI assistant.
              </p>
              <button
                onClick={() => navigate('/chat')}
                className="w-full bg-period-purple text-white py-2 rounded-lg font-semibold hover:bg-opacity-90 transition"
              >
                Start Chat
              </button>
            </div>

            {/* Cycle Statistics Card */}
            {cycleStats && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-xl font-bold mb-4">Cycle Statistics</h3>
                <div className="space-y-3 mb-4">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Cycle Length:</span>
                    <span className="font-semibold">{cycleStats.cycleLength} days</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Days Since Period:</span>
                    <span className="font-semibold">{cycleStats.daysSince} days</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Days Until Next:</span>
                    <span className="font-semibold">{cycleStats.daysUntil} days</span>
                  </div>
                </div>
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="w-full flex items-center justify-center gap-2 bg-period-pink text-white px-4 py-2 rounded-lg font-semibold hover:bg-opacity-90 transition shadow-lg"
                >
                  <Plus className="h-5 w-5" />
                  <span>Log Period</span>
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
              <h3 className="text-xl font-bold">Hormones</h3>
            </div>
            <p className="text-gray-600">
              Track your hormone levels and understand your cycle better.
            </p>
          </button>

          <button
            onClick={() => navigate('/nutrition')}
            className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition text-left"
          >
            <div className="flex items-center gap-3 mb-3">
              <Apple className="h-8 w-8 text-period-purple" />
              <h3 className="text-xl font-bold">Nutrition</h3>
            </div>
            <p className="text-gray-600">
              Get personalized nutrition recommendations for your cycle phase.
            </p>
          </button>

          <button
            onClick={() => navigate('/exercise')}
            className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition text-left"
          >
            <div className="flex items-center gap-3 mb-3">
              <Dumbbell className="h-8 w-8 text-period-lavender" />
              <h3 className="text-xl font-bold">Exercise</h3>
            </div>
            <p className="text-gray-600">
              Find the best exercises for your current cycle phase.
            </p>
          </button>
        </div>

        {/* G. Tips Section */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <h3 className="text-xl font-bold mb-4">Today's Tips</h3>
          <div className="grid md:grid-cols-2 gap-4">
            {tips.map((tip, index) => (
              <div key={index} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <span className="text-period-pink font-bold">{index + 1}.</span>
                <p className="text-gray-700">{tip}</p>
              </div>
            ))}
          </div>
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
