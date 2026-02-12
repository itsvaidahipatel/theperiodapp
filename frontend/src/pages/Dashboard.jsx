import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'
import { format, startOfMonth, endOfMonth, addMonths, subMonths } from 'date-fns'
import { getTimeBasedGreeting, getTimeBasedMessage } from '../utils/greetings'
import { getPhaseColorClass, getPhaseDescription, getPhaseEmoji, getPhaseColor } from '../utils/phaseHelpers'
import { logout, logPeriod, getPeriodEpisodes } from '../utils/api'
import { useDataContext } from '../context/DataContext'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import PeriodLogModal from '../components/PeriodLogModal'
import LoadingSpinner from '../components/LoadingSpinner'
import PeriodCalendar from '../components/PeriodCalendar'
import { useTranslation } from '../utils/translations'
import { useViewMode } from '../context/ViewModeContext'
import { User, LogOut, MessageCircle, Calendar as CalendarIcon, Activity, Apple, Dumbbell, Plus, Home, ClipboardCheck, Droplet, Smartphone, Monitor } from 'lucide-react'

// Phase Icon Component - matches the design from the image
const PhaseIcon = ({ phase, size = 40 }) => {
  const iconSize = size
  
  switch (phase) {
    case 'Period':
    case 'Menstrual':
      // Teardrop with waves (reddish-pink)
      return (
        <div className="relative flex items-center justify-center" style={{ width: iconSize, height: iconSize }}>
          <svg width={iconSize} height={iconSize} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Teardrop shape - main body */}
            <path d="M20 6C20 6 10 13 10 22C10 29.731 16.269 36 24 36C31.731 36 38 29.731 38 22C38 13 28 6 20 6Z" fill="#F8BBD9" stroke="white" strokeWidth="2"/>
            {/* Inner teardrop (blood drop) */}
            <path d="M20 10C20 10 14 15 14 21C14 25.9706 18.0294 30 23 30C27.9706 30 32 25.9706 32 21C32 15 26 10 20 10Z" fill="white" fillOpacity="0.7"/>
            {/* Waves below */}
            <path d="M8 30Q10 28 12 30T16 30" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round"/>
            <path d="M24 30Q26 28 28 30T32 30" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round"/>
            <path d="M8 34Q10 32 12 34T16 34" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round"/>
            <path d="M24 34Q26 32 28 34T32 34" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round"/>
          </svg>
        </div>
      )
    case 'Follicular':
      // Tulip flower (mint green) - clean and elegant
      return (
        <div className="relative flex items-center justify-center" style={{ width: iconSize, height: iconSize }}>
          <svg width={iconSize} height={iconSize} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Stem - straight stem */}
            <line x1="20" y1="23" x2="20" y2="35" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
            
            {/* Left leaf - elegant curved leaf */}
            <path d="M20 26C18 28.5 16 28 15.5 26.5C15 25 16.5 24 18.5 24.5C19.5 25 19.8 26 20 26Z" 
                  fill="white" fillOpacity="0.5" stroke="white" strokeWidth="2" strokeLinejoin="round"/>
            
            {/* Right leaf - elegant curved leaf */}
            <path d="M20 26C22 28.5 24 28 24.5 26.5C25 25 23.5 24 21.5 24.5C20.5 25 20.2 26 20 26Z" 
                  fill="white" fillOpacity="0.5" stroke="white" strokeWidth="2" strokeLinejoin="round"/>
            
            {/* Tulip flower - simple and elegant cup shape */}
            {/* Main flower - classic tulip cup */}
            <path d="M12 9C12 9 14 8 16 9C18 10 19 11.5 20 13C21 11.5 22 10 24 9C26 8 28 9 28 9C28 13 26 17 20 21C14 17 12 13 12 9Z" 
                  fill="#B2DFDB" stroke="white" strokeWidth="2.5" strokeLinejoin="round"/>
            
            {/* Left petal detail */}
            <path d="M12 9C12 11 13 13 14.5 14.5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.7"/>
            
            {/* Right petal detail */}
            <path d="M28 9C28 11 27 13 25.5 14.5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.7"/>
            
            {/* Center petal highlight for depth */}
            <path d="M18 12C18 12 19 13 20 14C21 13 22 12 22 12" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" opacity="0.6"/>
          </svg>
        </div>
      )
    case 'Ovulation':
      // Sun with rays (orange/peach)
      return (
        <div className="relative flex items-center justify-center" style={{ width: iconSize, height: iconSize }}>
          <svg width={iconSize} height={iconSize} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Sun rays - dashed lines */}
            <line x1="20" y1="4" x2="20" y2="9" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            <line x1="20" y1="31" x2="20" y2="36" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            <line x1="4" y1="20" x2="9" y2="20" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            <line x1="31" y1="20" x2="36" y2="20" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            <line x1="8.464" y1="8.464" x2="12.121" y2="12.121" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            <line x1="27.879" y1="27.879" x2="31.536" y2="31.536" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            <line x1="8.464" y1="31.536" x2="12.121" y2="27.879" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            <line x1="27.879" y1="12.121" x2="31.536" y2="8.464" stroke="white" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 2"/>
            {/* Sun center circle */}
            <circle cx="20" cy="20" r="7" fill="#FFB74D" stroke="white" strokeWidth="2"/>
            <circle cx="20" cy="20" r="4" fill="white" fillOpacity="0.3"/>
          </svg>
        </div>
      )
    case 'Luteal':
      // Cloud with moon (lavender/purple)
      return (
        <div className="relative flex items-center justify-center" style={{ width: iconSize, height: iconSize }}>
          <svg width={iconSize} height={iconSize} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Cloud shape */}
            <ellipse cx="20" cy="24" rx="12" ry="8" fill="#E1BEE7" stroke="white" strokeWidth="2"/>
            <ellipse cx="14" cy="24" rx="6" ry="7" fill="#E1BEE7" stroke="white" strokeWidth="2"/>
            <ellipse cx="26" cy="24" rx="6" ry="7" fill="#E1BEE7" stroke="white" strokeWidth="2"/>
            <ellipse cx="20" cy="18" rx="9" ry="7" fill="#E1BEE7" stroke="white" strokeWidth="2"/>
            {/* Moon crescent inside cloud upper right */}
            <path d="M27 12C28.6569 12 30 10.6569 30 9C30 7.34315 28.6569 6 27 6C25.3431 6 24 7.34315 24 9C24 10.6569 25.3431 12 27 12Z" fill="white" stroke="white" strokeWidth="1.5"/>
            <circle cx="28.5" cy="9.5" r="2.5" fill="#E1BEE7"/>
          </svg>
        </div>
      )
    default:
      return <Droplet size={iconSize} className="text-period-pink" />
  }
}

const Dashboard = () => {
  const { t } = useTranslation()
  const { dashboardData, loading, refreshData, updatePhaseMap } = useDataContext()
  const { viewMode, isMobileView, isWebView, getResponsiveClass, toggleViewMode } = useViewMode()
  const [user, setUser] = useState(null)

  const getViewModeIcon = () => {
    if (viewMode === 'mobile') return Smartphone
    return Monitor // Web view
  }

  const getViewModeLabel = () => {
    if (viewMode === 'mobile') return 'Mobile View'
    return 'Web View'
  }

  const ViewModeIcon = getViewModeIcon()
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [activeStartDate, setActiveStartDate] = useState(new Date())
  const [error, setError] = useState(null)
  const [cycleStats, setCycleStats] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [periodEpisodes, setPeriodEpisodes] = useState([])
  const [isMobile, setIsMobile] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  
  // Detect mobile screen size
  useEffect(() => {
    if (typeof window === 'undefined') return
    
    const checkMobile = () => {
      if (typeof window !== 'undefined' && window.innerWidth) {
        setIsMobile(window.innerWidth < 640)
      }
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('resize', checkMobile)
      }
    }
  }, [])
  
  // Extract data from context (phase map is ONLY fetched by PeriodCalendar; Dashboard only reads it here)
  const currentPhase = dashboardData?.currentPhase || null
  const phaseMap = dashboardData?.phaseMap || {}
  const periodLogs = dashboardData?.periodLogs || []
  
  // Get today's phase from phaseMap (same as PeriodCalendar) - ensures consistency
  const [todayPhase, setTodayPhase] = useState(null)
  
  useEffect(() => {
    const updateTodayPhase = () => {
      const today = format(new Date(), 'yyyy-MM-dd')
      const phaseData = phaseMap[today]
      
      if (phaseData) {
        const phase = typeof phaseData === 'string' ? phaseData : phaseData.phase
        const phaseDayId = typeof phaseData === 'object' ? (phaseData.phase_day_id || null) : null
        
        if (phase) {
          setTodayPhase({
            phase: phase,
            phaseDayId: phaseDayId
          })
          return
        }
      }
      
      // Fallback to currentPhase from context if phaseMap doesn't have today
      if (currentPhase?.phase) {
        setTodayPhase({
          phase: currentPhase.phase,
          phaseDayId: currentPhase.phase_day_id || currentPhase.id || null
        })
      } else {
        setTodayPhase(null)
      }
    }
    
    updateTodayPhase()
  }, [phaseMap, currentPhase])
  
  // Check if user has last_period_date
  const hasLastPeriodDate = user?.last_period_date

  // Memoize period logs and current phase to prevent infinite loops
  const periodLogsRef = useRef([])
  const currentPhaseRef = useRef(null)
  const lastCalculationRef = useRef('')
  const dataVersionRef = useRef(0)
  
  // Create stable string representations for comparison
  const periodLogsKey = useRef('')
  const currentPhaseKey = useRef('')
  
  // Update refs when data actually changes (using string comparison to avoid object reference issues)
  useEffect(() => {
    const logsKey = JSON.stringify(periodLogs?.map(log => ({ date: log?.date, flow: log?.flow })) || [])
    const phaseKey = JSON.stringify({ phase: currentPhase?.phase, phase_day_id: currentPhase?.phase_day_id } || {})
    
    const logsChanged = periodLogsKey.current !== logsKey
    const phaseChanged = currentPhaseKey.current !== phaseKey
    
    if (logsChanged || phaseChanged) {
      periodLogsRef.current = periodLogs
      currentPhaseRef.current = currentPhase
      periodLogsKey.current = logsKey
      currentPhaseKey.current = phaseKey
      // Reset calculation key to force recalculation
      lastCalculationRef.current = ''
      dataVersionRef.current += 1
    }
  }, [periodLogs, currentPhase])

  // Track user data to avoid unnecessary updates
  const userDataRef = useRef(null)
  const isCalculatingRef = useRef(false)
  
  useEffect(() => {
    // Prevent concurrent calculations
    if (isCalculatingRef.current) {
      return
    }
    
    try {
      const userData = localStorage.getItem('user')
      if (userData) {
        const parsedUser = JSON.parse(userData)
        // Only update user if data actually changed
        const userKey = JSON.stringify({ 
          id: parsedUser?.id, 
          last_period_date: parsedUser?.last_period_date, 
          cycle_length: parsedUser?.cycle_length 
        })
        if (userDataRef.current !== userKey) {
          setUser(parsedUser)
          userDataRef.current = userKey
        }
        
        // Calculate enhanced cycle stats from user data and period logs
        if (parsedUser?.last_period_date) {
          // Create a unique key for this calculation to prevent duplicate calculations
          // Include dataVersion to trigger recalculation when periodLogs/currentPhase change
          const logsLength = periodLogsRef.current?.length || 0
          const phaseName = currentPhaseRef.current?.phase || 'none'
          const calculationKey = `${parsedUser.last_period_date}-${parsedUser.cycle_length || 28}-${logsLength}-${phaseName}-${dataVersionRef.current}`
          
          // Skip if we already calculated for this exact state
          if (lastCalculationRef.current === calculationKey) {
            return
          }
          
          lastCalculationRef.current = calculationKey
          isCalculatingRef.current = true
          try {
            const today = new Date()
            today.setHours(0, 0, 0, 0)
            
            // Check if last_period_date exists
            let daysSince = null
            let daysUntil = null
            
            if (parsedUser.last_period_date) {
              const lastPeriod = new Date(parsedUser.last_period_date)
              
              // Validate date
              if (isNaN(lastPeriod.getTime())) {
                console.warn('Invalid date in user data')
                return
              }
              
              lastPeriod.setHours(0, 0, 0, 0)
              const cycleLength = parsedUser.cycle_length || 28
              
              // Calculate days since last period start date
              // If today is the last period date, daysSince = 0
              // If today is the day after, daysSince = 1, etc.
              daysSince = Math.max(0, Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24)))
              
              // Calculate next period start date
              // Start with last period + cycle length
              let nextPeriodDate = new Date(lastPeriod)
              nextPeriodDate.setDate(nextPeriodDate.getDate() + cycleLength)
              
              // If the next period date has passed or is today, move to the following cycle
              while (nextPeriodDate <= today) {
                nextPeriodDate.setDate(nextPeriodDate.getDate() + cycleLength)
              }
              
              // Calculate days until next period (always positive)
              daysUntil = Math.floor((nextPeriodDate - today) / (1000 * 60 * 60 * 24))
            }
            
            const cycleLength = parsedUser.cycle_length || 28
            
            // Calculate additional statistics from period logs (use ref to avoid dependency issues)
            const logsToUse = periodLogsRef.current || []
            const phaseToUse = currentPhaseRef.current
            
            let avgPeriodLength = 5 // default
            let cyclesTracked = 0
            let cycleRegularity = 'Regular'
            let predictedOvulationDate = null
            let lutealEstimate = 14
            
            if (logsToUse && logsToUse.length > 0) {
              try {
                // Calculate average period length
                const periodLengths = []
                logsToUse.forEach((log, index) => {
                  if (index < logsToUse.length - 1 && log?.date && logsToUse[index + 1]?.date) {
                    try {
                      const currentDate = new Date(log.date)
                      const nextDate = new Date(logsToUse[index + 1].date)
                      if (!isNaN(currentDate.getTime()) && !isNaN(nextDate.getTime())) {
                        const diff = Math.floor((currentDate - nextDate) / (1000 * 60 * 60 * 24))
                        if (diff > 0 && diff < 45) { // Valid cycle length
                          periodLengths.push(diff)
                        }
                      }
                    } catch (dateError) {
                      console.warn('Error parsing date in period log:', dateError)
                    }
                  }
                })
                
                if (periodLengths.length > 0) {
                  cyclesTracked = periodLengths.length
                  const avgCycleLength = periodLengths.reduce((a, b) => a + b, 0) / periodLengths.length
                  
                  // Calculate cycle regularity
                  const cycleVariance = periodLengths.reduce((sum, len) => sum + Math.pow(len - avgCycleLength, 2), 0) / periodLengths.length
                  const cycleStdDev = Math.sqrt(cycleVariance)
                  
                  if (cycleStdDev < 2) {
                    cycleRegularity = 'Very Regular'
                  } else if (cycleStdDev < 4) {
                    cycleRegularity = 'Regular'
                  } else if (cycleStdDev < 7) {
                    cycleRegularity = 'Somewhat Irregular'
                  } else {
                    cycleRegularity = 'Irregular'
                  }
                }
                
                // Calculate average period length (count consecutive period days)
                const periodDays = []
                logsToUse.forEach(log => {
                  if (log?.flow && log.flow !== 'none' && log?.date) {
                    periodDays.push(log.date)
                  }
                })
                
                // Group consecutive days
                if (periodDays.length > 0) {
                  try {
                    let currentPeriod = []
                    let periods = []
                    periodDays.sort().forEach((date, index) => {
                      try {
                        if (index === 0) {
                          currentPeriod = [date]
                        } else {
                          const prevDate = new Date(periodDays[index - 1])
                          const currDate = new Date(date)
                          if (!isNaN(prevDate.getTime()) && !isNaN(currDate.getTime())) {
                            const diff = Math.floor((currDate - prevDate) / (1000 * 60 * 60 * 24))
                            if (diff === 1) {
                              currentPeriod.push(date)
                            } else {
                              periods.push(currentPeriod)
                              currentPeriod = [date]
                            }
                          }
                        }
                      } catch (dateError) {
                        console.warn('Error processing period date:', dateError)
                      }
                    })
                    if (currentPeriod.length > 0) {
                      periods.push(currentPeriod)
                    }
                    
                    if (periods.length > 0) {
                      const periodLengths = periods.map(p => p.length)
                      avgPeriodLength = Math.round(periodLengths.reduce((a, b) => a + b, 0) / periodLengths.length)
                    }
                  } catch (periodError) {
                    console.warn('Error calculating period lengths:', periodError)
                  }
                }
                
                // Calculate predicted ovulation date (cycle_length - luteal_mean)
                // Estimate luteal phase (typically 14 days, but can vary)
                if (parsedUser.last_period_date) {
                  try {
                    const lastPeriod = new Date(parsedUser.last_period_date)
                    lutealEstimate = 14 // Default, could be improved with actual data
                    const ovulationOffset = cycleLength - lutealEstimate
                    const nextOvulation = new Date(lastPeriod)
                    if (!isNaN(nextOvulation.getTime())) {
                      nextOvulation.setDate(nextOvulation.getDate() + ovulationOffset)
                      predictedOvulationDate = nextOvulation
                    }
                  } catch (ovulationError) {
                    console.warn('Error calculating ovulation date:', ovulationError)
                  }
                }
              } catch (statsCalcError) {
                console.warn('Error in cycle stats calculation:', statsCalcError)
              }
            }
            
            // Set cycle stats after all calculations
            setCycleStats({
              cycleLength,
              daysSince: daysSince, // Days since last period start date (always >= 0)
              daysUntil: daysUntil, // Days until next period start date (always positive)
              avgPeriodLength,
              cyclesTracked,
              cycleRegularity,
              predictedOvulationDate,
              lutealEstimate,
              currentPhase: phaseToUse?.phase || null,
              phaseDayId: phaseToUse?.phase_day_id || null
            })
          } catch (statsError) {
            console.error('Error calculating cycle stats:', statsError)
            // Set basic stats even if calculation fails
            try {
              const fallbackCycleLength = parsedUser?.cycle_length || 28
              // Only set daysSince and daysUntil if last_period_date exists
              let fallbackDaysSince = null
              let fallbackDaysUntil = null
              
              if (parsedUser?.last_period_date) {
                const lastPeriod = new Date(parsedUser.last_period_date)
                const today = new Date()
                today.setHours(0, 0, 0, 0)
                lastPeriod.setHours(0, 0, 0, 0)
                
                if (!isNaN(lastPeriod.getTime())) {
                  fallbackDaysSince = Math.max(0, Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24)))
                  
                  let nextPeriodDate = new Date(lastPeriod)
                  nextPeriodDate.setDate(nextPeriodDate.getDate() + fallbackCycleLength)
                  while (nextPeriodDate <= today) {
                    nextPeriodDate.setDate(nextPeriodDate.getDate() + fallbackCycleLength)
                  }
                  fallbackDaysUntil = Math.floor((nextPeriodDate - today) / (1000 * 60 * 60 * 24))
                }
              }
              
              setCycleStats({
                cycleLength: fallbackCycleLength,
                daysSince: fallbackDaysSince,
                daysUntil: fallbackDaysUntil,
                avgPeriodLength: 5,
                cyclesTracked: 0,
                cycleRegularity: 'Regular',
                predictedOvulationDate: null,
                lutealEstimate: 14,
                currentPhase: phaseToUse?.phase || null,
                phaseDayId: phaseToUse?.phase_day_id || null
              })
            } catch (fallbackError) {
              console.error('Error setting fallback stats:', fallbackError)
            }
          }
          isCalculatingRef.current = false
        }
      } else {
        navigate('/login')
      }
    } catch (error) {
      console.error('Error in Dashboard useEffect:', error)
      isCalculatingRef.current = false
      // Don't crash the app, just log the error
    }
    // Only depend on navigate - use refs for periodLogs and currentPhase to prevent loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate])

  // Throttle: don't fire fetch more than once every 2 seconds (stops API spam)
  const lastFetchRef = useRef(0)
  const FETCH_THROTTLE_MS = 2000

  // Fetch period episodes for bleeding range visualization
  useEffect(() => {
    const fetchPeriodEpisodes = async () => {
      if (!user) return
      const now = Date.now()
      if (now - lastFetchRef.current < FETCH_THROTTLE_MS) return
      lastFetchRef.current = now
      try {
        const episodes = await getPeriodEpisodes()
        setPeriodEpisodes(episodes || [])
      } catch (error) {
        console.error('Failed to fetch period episodes:', error)
        setPeriodEpisodes([])
      }
    }
    fetchPeriodEpisodes()
    const handlePeriodLogged = () => {
      setTimeout(() => {
        fetchPeriodEpisodes()
      }, 2000)
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
    }
  }, [user])

  const handleLogout = async () => {
    try {
      await logout()
      sessionStorage.clear()
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      navigate('/login')
    } catch (error) {
      sessionStorage.clear()
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
        const cycleLength = result.user?.cycle_length || 28
        let daysSince = null
        let daysUntil = null
        
        if (result.user?.last_period_date) {
          const lastPeriod = new Date(result.user.last_period_date)
          const today = new Date()
          today.setHours(0, 0, 0, 0)
          lastPeriod.setHours(0, 0, 0, 0)
          
          // Calculate days since last period start date
          daysSince = Math.max(0, Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24)))
          
          // Calculate next period start date
          let nextPeriodDate = new Date(lastPeriod)
          nextPeriodDate.setDate(nextPeriodDate.getDate() + cycleLength)
          
          // If the next period date has passed or is today, move to the following cycle
          while (nextPeriodDate <= today) {
            nextPeriodDate.setDate(nextPeriodDate.getDate() + cycleLength)
          }
          
          // Calculate days until next period (always positive)
          daysUntil = Math.floor((nextPeriodDate - today) / (1000 * 60 * 60 * 24))
        }
        
        setCycleStats({
          cycleLength,
          daysSince: daysSince, // Days since last period start date (null if no last_period_date)
          daysUntil: daysUntil  // Days until next period start date (null if no last_period_date)
        })
      }
      
      // Dispatch event to clear cache and refresh all data
      window.dispatchEvent(new CustomEvent('periodLogged'))
      window.dispatchEvent(new CustomEvent('calendarUpdated'))
      
      // Refresh period episodes
      try {
        const episodes = await getPeriodEpisodes()
        setPeriodEpisodes(episodes || [])
      } catch (error) {
        console.error('Failed to refresh period episodes:', error)
      }
      
      // Clear calendar phase map so entire timeline refreshes (PeriodCalendar refetches on periodLogged)
      updatePhaseMap({})
      setIsModalOpen(false)
    } catch (error) {
      console.error('Failed to log period:', error)
      throw error
    }
  }

  // Check if a date is in predicted bleeding range
  const isInBleedingRange = (dateStr) => {
    if (!periodEpisodes || periodEpisodes.length === 0) return false
    
    const date = new Date(dateStr)
    date.setHours(0, 0, 0, 0)
    
    for (const episode of periodEpisodes) {
      const startDate = new Date(episode.start_date)
      startDate.setHours(0, 0, 0, 0)
      const endDate = new Date(episode.predicted_end_date)
      endDate.setHours(0, 0, 0, 0)
      
      if (date >= startDate && date <= endDate) {
        return true
      }
    }
    
    return false
  }

  const handleLogPeriodClick = (date) => {
    setSelectedDate(date)
    setIsModalOpen(true)
  }

  // Get phase color for circle - using vibrant, visible colors
  const getPhaseCircleColor = (phase) => {
    const colors = {
      'Period': '#F8BBD9',      // Pink
      'Menstrual': '#F8BBD9',   // Pink
      'Follicular': '#4ECDC4',  // Brighter Teal
      'Ovulation': '#FFB74D',   // Brighter Orange/Yellow
      'Luteal': '#BA68C8'       // Brighter Purple
    }
    return colors[phase] || '#D1D5DB' // Grey for unknown
  }

  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      return 'relative'
    }
    return null
  }

  const tileStyle = ({ date, view }) => {
    if (view === 'month') {
      return {
        position: 'relative',
        height: '5.5rem', // Increased from 4rem to accommodate button below
        minHeight: '5.5rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-start',
        overflow: 'visible',
        padding: '0.5rem',
        paddingTop: '0.75rem',
        paddingBottom: '0.25rem',
        margin: '0.25rem'
      }
    }
    return {}
  }

  const tileContent = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      let phaseData = phaseMap[dateStr]
      const dayNumber = date.getDate()
      const today = new Date()
      const isToday = format(date, 'yyyy-MM-dd') === format(today, 'yyyy-MM-dd')
      
      // Check if date is in predicted bleeding range
      const isBleeding = isInBleedingRange(dateStr)
      
      // Check if this date is already logged as a period start
      const isLoggedPeriod = periodLogs.some(log => log.date === dateStr)
      
      // If this is a logged period but no phase data, create phase data for it
      if (isLoggedPeriod && !phaseData) {
        phaseData = {
          phase: 'Period',
          phase_day_id: 'p1',
          is_logged: true
        }
      }
      
      // If phaseData exists but no phase field, derive it from phase_day_id
      if (phaseData && !phaseData.phase && phaseData.phase_day_id) {
        const phaseDayId = phaseData.phase_day_id.toLowerCase()
        const firstChar = phaseDayId.charAt(0)
        if (firstChar === 'p') {
          phaseData.phase = 'Period'
        } else if (firstChar === 'f') {
          phaseData.phase = 'Follicular'
        } else if (firstChar === 'o') {
          phaseData.phase = 'Ovulation'
        } else if (firstChar === 'l') {
          phaseData.phase = 'Luteal'
        }
      }
      
      // Determine circle color - prioritize phase data, then logged periods, then bleeding range
      let circleColor = '#D1D5DB' // Default grey
      if (phaseData && phaseData.phase) {
        // Use phase data if available (this includes predictions)
        circleColor = getPhaseCircleColor(phaseData.phase)
      } else if (isLoggedPeriod) {
        // Fallback: show Period color for logged periods
        circleColor = getPhaseCircleColor('Period')
      } else if (isBleeding) {
        // If in bleeding range but no phase data, show Period color
        circleColor = getPhaseCircleColor('Period')
      }
      
      // Debug logging for current month dates (only log first few to avoid spam)
      // Reuse currentMonth and currentYear declared earlier
      if (isToday || (dayNumber <= 3 && date.getMonth() === currentMonth && date.getFullYear() === currentYear)) {
        console.log(`📅 Date ${dateStr}: phaseData=${phaseData ? 'yes' : 'no'}, phase=${phaseData?.phase || 'none'}, phase_day_id=${phaseData?.phase_day_id || 'none'}, color=${circleColor}, isLogged=${isLoggedPeriod}, isBleeding=${isBleeding}, phaseMap has ${Object.keys(phaseMap).length} dates`)
      }
      
      // Use filled circle with white border for better visibility
      // Force inline styles to ensure colors are applied
      // Mobile-optimized: smaller circles on mobile
      const circleSize = (isMobile === true) ? '2rem' : '2.75rem'
      const borderWidth = (isMobile === true) ? '2px' : '3px'
      const circleStyle = {
        position: 'relative',
        width: circleSize,
        height: circleSize,
        minHeight: circleSize,
        borderRadius: '50%',
        backgroundColor: circleColor,
        border: `${borderWidth} solid white`,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        pointerEvents: 'none',
        boxShadow: isToday ? `0 0 0 ${borderWidth} ${circleColor}80` : '0 2px 4px rgba(0,0,0,0.15)',
        padding: (isMobile === true) ? '0.15rem' : '0.25rem',
        paddingTop: (isMobile === true) ? '0.25rem' : '0.35rem',
        paddingBottom: (isMobile === true) ? '0.25rem' : '0.35rem',
        flexShrink: 0
      }
      
      const phaseDayId = phaseData?.phase_day_id || ''
      
      // ⚠️ MEDICAL ACCURACY: Show fertile window indicator even in Follicular phase
      // Fertile window is 5-6 days (sperm survival + ovulation + egg viability)
      // Days with high fertility_prob should be visually marked even if phase is "Follicular"
      const fertilityProb = phaseData?.fertility_prob
      const isFertileDay = fertilityProb != null && fertilityProb >= 0.3  // Threshold for visual indicator
      const showFertileIndicator = Boolean(isFertileDay && phaseData?.phase !== 'Ovulation' && phaseData?.phase !== 'Period')
      
      return (
        <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start' }}>
          {/* Bleeding range overlay (red shading) */}
          {isBleeding && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(248, 187, 217, 0.3)', // Light pink overlay
                borderRadius: '4px',
                zIndex: 1,
                pointerEvents: 'none'
              }}
            />
          )}
          
          {/* Phase circle - positioned at top */}
          <div style={circleStyle}>
          <span 
            style={{
              fontSize: (isMobile === true) ? '0.75rem' : '0.875rem',
              fontWeight: '700',
              color: 'white',
              zIndex: 1001,
              textShadow: '0 1px 2px rgba(0,0,0,0.3)',
              lineHeight: '1',
              marginBottom: phaseDayId ? ((isMobile === true) ? '0.05rem' : '0.1rem') : '0'
            }}
          >
            {dayNumber}
          </span>
          {phaseDayId && (
            <span 
              style={{
                fontSize: (isMobile === true) ? '0.5rem' : '0.625rem',
                fontWeight: '600',
                color: 'white',
                zIndex: 1001,
                textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                lineHeight: '1',
                opacity: 0.95
              }}
            >
              {phaseDayId}
            </span>
          )}
          {/* Fertile window indicator: Show small dot for fertile days in Follicular phase */}
          {showFertileIndicator && (
            <span 
              style={{
                position: 'absolute',
                top: '2px',
                right: '2px',
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: '#FFB74D',
                border: '1px solid white',
                zIndex: 1002,
                boxShadow: '0 1px 2px rgba(0,0,0,0.2)'
              }}
              title={fertilityProb != null ? `Fertile window (${Math.round(fertilityProb * 100)}% probability)` : 'Fertile window'}
            />
          )}
          </div>
          
          {/* Log Period Button - positioned below the date circle */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleLogPeriodClick(date)
            }}
            className="w-5 h-5 sm:w-6 sm:h-6 bg-period-pink hover:bg-period-purple text-white rounded-full flex items-center justify-center shadow-md hover:shadow-lg transition-all z-50 mt-0.5"
            title="Log period start"
            style={{
              fontSize: '0.625rem',
              lineHeight: '1',
              padding: '0',
              position: 'relative',
              flexShrink: 0
            }}
          >
            <Plus className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
          </button>
        </div>
      )
    }
    return null
  }

  const onActiveStartDateChange = ({ activeStartDate }) => {
    setActiveStartDate(activeStartDate)
  }

  if (loading) {
    return <LoadingSpinner message="Loading dashboard..." />
  }

  if (!user) {
    return null
  }

  const phase = currentPhase?.phase || 'Period'

  return (
    <div className="min-h-screen bg-gray-50 pb-20 sm:pb-8">
      {/* A. Top Navigation Bar - Sticky (Mobile: Compact) */}
      <nav className="sticky top-0 z-50 bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8">
          <div className="flex justify-between items-center h-14 sm:h-16">
            <h1 className="text-lg sm:text-2xl font-bold text-period-pink truncate">{t('nav.periodGPT')}</h1>
            <div className="flex items-center gap-2 sm:gap-4">
              {/* View Mode Toggle Button */}
              <button
                onClick={toggleViewMode}
                className="flex items-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition min-h-[44px] border border-gray-200 bg-white"
                title={getViewModeLabel()}
              >
                <ViewModeIcon className="h-5 w-5 flex-shrink-0" />
                <span className="hidden sm:inline text-sm font-medium">{getViewModeLabel()}</span>
              </button>
              
              <button
                onClick={() => navigate('/profile')}
                className="flex items-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition min-h-[44px]"
              >
                <User className="h-5 w-5" />
                <span className="hidden sm:inline">{t('nav.profile')}</span>
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition min-h-[44px]"
              >
                <LogOut className="h-5 w-5" />
                <span className="hidden sm:inline">{t('nav.logout')}</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8 py-4 sm:py-6 lg:py-8">
        {/* B. Welcome Section - Mobile Optimized */}
        <div className="mb-4 sm:mb-6">
          <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-gray-800 mb-1 sm:mb-2">
            {getTimeBasedGreeting()}, {user.name}!
          </h2>
        </div>

        {/* C. Error Display */}
        {error && (
          <div className="mb-6 bg-red-50 border-l-4 border-red-400 p-4 rounded">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* D. Current Phase Card - Mobile Optimized - Matches PeriodCalendar format */}
        {todayPhase && todayPhase.phase && (
          <div 
            className="mb-4 sm:mb-6 rounded-lg shadow-lg p-4 sm:p-6 border-2"
            style={{
              backgroundColor: `${getPhaseColor(todayPhase.phase)}20`,
              borderColor: getPhaseColor(todayPhase.phase)
            }}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 sm:gap-3">
                  <PhaseIcon phase={todayPhase.phase} size={isMobile ? 36 : 48} />
                  <div>
                    <h3 className="text-lg sm:text-xl lg:text-2xl font-bold text-gray-800 capitalize">
                      Today's Phase: {todayPhase.phase}{todayPhase.phaseDayId ? ` (${todayPhase.phaseDayId})` : ''}
                    </h3>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* E. Calendar Section - Mobile First: Stack on mobile, side-by-side on desktop */}
        <div className={`flex ${isMobileView ? 'flex-col' : 'grid grid-cols-2'} gap-4 sm:gap-6 lg:gap-8 mb-6 sm:mb-8`}>
          {/* Left Side: Calendar - Full width on mobile - New Format */}
          <div className="bg-white rounded-xl shadow-lg p-3 sm:p-4 lg:p-6 border border-gray-100 order-1">
            <PeriodCalendar
              onPeriodLogged={async () => {
                await refreshData()
                window.dispatchEvent(new CustomEvent('periodLogged'))
              }}
            />
          </div>

          {/* Right Side: AI & Cycle Stats - Mobile: Show before calendar */}
          <div className="space-y-3 sm:space-y-4 order-2 lg:order-2">
            {/* AI Assistant Card - Mobile Optimized */}
            <div className="bg-white rounded-lg shadow-lg p-4 sm:p-6">
              <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
                <MessageCircle className="h-5 w-5 sm:h-6 sm:w-6 text-period-purple" />
                <h3 className="text-lg sm:text-xl font-bold text-gray-800">{t('dashboard.aiAssistant')}</h3>
              </div>
              <p className="text-sm sm:text-base text-gray-600 mb-3 sm:mb-4">
                {t('dashboard.aiDescription')}
              </p>
              <button
                onClick={() => navigate('/chat')}
                className="w-full bg-period-purple text-white py-3 sm:py-2 rounded-lg font-semibold hover:bg-opacity-90 transition min-h-[44px] text-sm sm:text-base"
              >
                {t('dashboard.startChat')}
              </button>
            </div>

            {/* Self-Tests Card - Mobile Optimized */}
            <div className="bg-white rounded-lg shadow-lg p-4 sm:p-6">
              <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
                <ClipboardCheck className="h-5 w-5 sm:h-6 sm:w-6 text-period-pink flex-shrink-0" />
                <h3 className="text-lg sm:text-xl font-bold text-gray-800">{t('dashboard.selftests')}</h3>
              </div>
              <p className="text-sm sm:text-base text-gray-600 mb-3 sm:mb-4">
                {t('dashboard.selftestsDesc')}
              </p>
              <button
                onClick={() => navigate('/selftests')}
                className="w-full bg-period-pink text-white py-3 sm:py-2 rounded-lg font-semibold hover:bg-opacity-90 transition min-h-[44px] text-sm sm:text-base"
              >
                Take Self Tests
              </button>
            </div>

            {/* Cycle Statistics Button - Navigate to full statistics page */}
            <div className="bg-white rounded-lg shadow-lg p-4 sm:p-6">
              <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
                <Activity className="h-5 w-5 sm:h-6 sm:w-6 text-period-pink" />
                <h3 className="text-lg sm:text-xl font-bold text-gray-800">{t('dashboard.cycleStatistics') || 'Cycle Statistics'}</h3>
              </div>
              <p className="text-sm sm:text-base text-gray-600 mb-3 sm:mb-4">
                {t('dashboard.cycleStatisticsDesc') || 'View detailed cycle statistics and complete history'}
              </p>
              <button
                onClick={() => navigate('/cycle-statistics')}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-period-pink to-period-purple text-white px-4 py-3 rounded-lg font-semibold hover:opacity-90 transition-all shadow-md hover:shadow-lg min-h-[44px] text-sm sm:text-base"
              >
                <Activity className="h-5 w-5" />
                <span>View Statistics & History</span>
              </button>
            </div>
          </div>
        </div>

        {/* F. Three Main Feature Cards - Mobile Optimized */}
        <div className={`grid ${isMobileView ? 'grid-cols-1' : 'grid-cols-3'} gap-3 sm:gap-4 lg:gap-6 mb-4 sm:mb-6`}>
          <button
            onClick={() => navigate('/hormones')}
            className="bg-white rounded-lg shadow-lg p-4 sm:p-6 hover:shadow-xl transition text-left min-h-[44px] active:scale-95"
          >
            <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
              <Activity className="h-6 w-6 sm:h-8 sm:w-8 text-period-pink flex-shrink-0" />
              <h3 className="text-lg sm:text-xl font-bold text-gray-800">{t('dashboard.hormones')}</h3>
            </div>
            <p className="text-sm sm:text-base text-gray-600">
              {t('dashboard.hormonesDesc')}
            </p>
          </button>

          <button
            onClick={() => navigate('/nutrition')}
            className="bg-white rounded-lg shadow-lg p-4 sm:p-6 hover:shadow-xl transition text-left min-h-[44px] active:scale-95"
          >
            <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
              <Apple className="h-6 w-6 sm:h-8 sm:w-8 text-period-purple flex-shrink-0" />
              <h3 className="text-lg sm:text-xl font-bold text-gray-800">{t('dashboard.nutrition')}</h3>
            </div>
            <p className="text-sm sm:text-base text-gray-600">
              {t('dashboard.nutritionDesc')}
            </p>
          </button>

          <button
            onClick={() => navigate('/exercise')}
            className="bg-white rounded-lg shadow-lg p-4 sm:p-6 hover:shadow-xl transition text-left min-h-[44px] active:scale-95"
          >
            <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
              <Dumbbell className="h-6 w-6 sm:h-8 sm:w-8 text-period-lavender flex-shrink-0" />
              <h3 className="text-lg sm:text-xl font-bold text-gray-800">{t('dashboard.exercise')}</h3>
            </div>
            <p className="text-sm sm:text-base text-gray-600">
              {t('dashboard.exerciseDesc')}
            </p>
          </button>
        </div>

        {/* About the App Button - Mobile Optimized */}
        <div className="mb-6 sm:mb-8 flex justify-center">
          <button
            onClick={() => navigate('/about')}
            className="bg-white rounded-lg shadow-lg px-6 sm:px-8 py-3 sm:py-4 hover:shadow-xl transition text-center border-2 border-period-pink hover:bg-period-pink hover:text-white min-h-[44px] w-full sm:w-auto active:scale-95"
          >
            <h3 className="text-base sm:text-lg font-bold text-gray-800">{t('about.title')}</h3>
          </button>
        </div>

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>

      {/* Mobile Bottom Navigation Bar */}
      {location && (
        <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-50 sm:hidden">
          <div className="flex justify-around items-center h-16">
            <button
              onClick={() => navigate('/dashboard')}
              className={`flex flex-col items-center justify-center gap-1 px-4 py-2 rounded-lg transition ${
                location?.pathname === '/dashboard' ? 'text-period-pink' : 'text-gray-600'
              }`}
            >
              <Home className="h-5 w-5" />
              <span className="text-xs font-medium">Home</span>
            </button>
            <button
              onClick={() => navigate('/chat')}
              className={`flex flex-col items-center justify-center gap-1 px-4 py-2 rounded-lg transition ${
                location?.pathname === '/chat' ? 'text-period-pink' : 'text-gray-600'
              }`}
            >
              <MessageCircle className="h-5 w-5" />
              <span className="text-xs font-medium">Chat</span>
            </button>
            <button
              onClick={() => navigate('/profile')}
              className={`flex flex-col items-center justify-center gap-1 px-4 py-2 rounded-lg transition ${
                location?.pathname === '/profile' ? 'text-period-pink' : 'text-gray-600'
              }`}
            >
              <User className="h-5 w-5" />
              <span className="text-xs font-medium">Profile</span>
            </button>
          </div>
        </nav>
      )}

      {/* Period Log Modal */}
      <PeriodLogModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false)
          setIsLoggingEnd(false)
        }}
        onSuccess={handleLogPeriod}
        selectedDate={selectedDate ? format(selectedDate, 'yyyy-MM-dd') : undefined}
        isLoggingEnd={false}
      />
    </div>
  )
}

export default Dashboard
