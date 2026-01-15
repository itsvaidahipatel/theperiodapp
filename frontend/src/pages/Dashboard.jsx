import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'
import { format, startOfMonth, endOfMonth, addMonths, subMonths } from 'date-fns'
import { getTimeBasedGreeting, getTimeBasedMessage } from '../utils/greetings'
import { getPhaseColorClass, getPhaseDescription, getPhaseEmoji, getPhaseColor } from '../utils/phaseHelpers'
import { logout, logPeriod, getPhaseMap } from '../utils/api'
import { useDataContext } from '../context/DataContext'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import PeriodLogModal from '../components/PeriodLogModal'
import LoadingSpinner from '../components/LoadingSpinner'
import { useTranslation } from '../utils/translations'
import { User, LogOut, MessageCircle, Calendar as CalendarIcon, Activity, Apple, Dumbbell, Plus, Home, ClipboardCheck, Droplet } from 'lucide-react'

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
  const { dashboardData, loading, refreshData } = useDataContext()
  const [user, setUser] = useState(null)
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [activeStartDate, setActiveStartDate] = useState(new Date())
  const [error, setError] = useState(null)
  const [cycleStats, setCycleStats] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [calendarPhaseMap, setCalendarPhaseMap] = useState({})
  const [loadingCalendar, setLoadingCalendar] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const isFetchingRef = useRef(false)
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
  
  // Extract data from context
  const currentPhase = dashboardData?.currentPhase || null
  const phaseMap = dashboardData?.phaseMap || {}
  const periodLogs = dashboardData?.periodLogs || []
  
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

  // Fetch phase map when active month changes
  useEffect(() => {
    let abortController = new AbortController()
    
    const fetchPhaseMapForMonth = async () => {
      if (!user) return
      
      // Prevent concurrent requests using ref
      if (isFetchingRef.current) {
        console.log('Phase map fetch already in progress, skipping...')
        return
      }
      
      // Check if we already have data for this month
      const startDate = format(startOfMonth(activeStartDate), 'yyyy-MM-dd')
      const endDate = format(endOfMonth(activeStartDate), 'yyyy-MM-dd')
      const monthKey = format(activeStartDate, 'yyyy-MM')
      
      // Check if we have data for this month in calendarPhaseMap
      const hasDataForMonth = Object.keys(calendarPhaseMap).some(date => {
        const dateMonth = date.substring(0, 7) // Get YYYY-MM
        return dateMonth === monthKey
      })
      
      if (hasDataForMonth && Object.keys(calendarPhaseMap).length > 0) {
        console.log('Already have phase map data for', monthKey, ', skipping fetch')
        return
      }
      
      isFetchingRef.current = true
      setLoadingCalendar(true)
      try {
        // Get start and end of the active month only (not 3 months to reduce load)
        console.log('Fetching phase map from', startDate, 'to', endDate)
        
        // Add timeout to prevent infinite loading
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Request timeout after 30 seconds')), 30000)
        )
        
        const response = await Promise.race([
          getPhaseMap(startDate, endDate),
          timeoutPromise
        ])
        console.log('Phase map API response:', JSON.stringify(response, null, 2))
        console.log('Response phase_map:', response?.phase_map)
        console.log('Response phase_map length:', response?.phase_map?.length || 0)
        if (response?.phase_map && response.phase_map.length > 0) {
          console.log('First 3 items:', response.phase_map.slice(0, 3))
        }
        console.log('Context phaseMap keys:', phaseMap ? Object.keys(phaseMap).length : 0)
        
        const map = {}
        
        if (response && response.phase_map && Array.isArray(response.phase_map)) {
          console.log('Processing phase_map array with', response.phase_map.length, 'items')
          response.phase_map.forEach((item, index) => {
            // Ensure date is in correct format
            let dateKey = item.date
            if (dateKey && typeof dateKey === 'string') {
              // If date includes time, extract just the date part
              if (dateKey.includes('T')) {
                dateKey = dateKey.split('T')[0]
              }
              
              // Derive phase from phase_day_id if phase field is missing
              if (!item.phase && item.phase_day_id) {
                const phaseDayId = item.phase_day_id.toLowerCase()
                const firstChar = phaseDayId.charAt(0)
                if (firstChar === 'p') {
                  item.phase = 'Period'
                } else if (firstChar === 'f') {
                  item.phase = 'Follicular'
                } else if (firstChar === 'o') {
                  item.phase = 'Ovulation'
                } else if (firstChar === 'l') {
                  item.phase = 'Luteal'
                }
              }
              
              // Debug first few items
              if (index < 3) {
                console.log(`  Item ${index}: date=${dateKey}, phase=${item.phase}, phase_day_id=${item.phase_day_id}`)
              }
              
              map[dateKey] = item
            } else {
              console.warn('  Item', index, 'has invalid date:', item)
            }
          })
          console.log('Final map has', Object.keys(map).length, 'dates')
        } else {
          console.warn('Response phase_map is not an array:', response?.phase_map)
        }
        
        // If map is still empty, try using context phaseMap
        if (Object.keys(map).length === 0 && phaseMap && Object.keys(phaseMap).length > 0) {
          console.log('Using context phaseMap as fallback')
          Object.keys(phaseMap).forEach(dateKey => {
            const item = phaseMap[dateKey]
            // Derive phase from phase_day_id if needed
            if (!item.phase && item.phase_day_id) {
              const phaseDayId = item.phase_day_id.toLowerCase()
              const firstChar = phaseDayId.charAt(0)
              if (firstChar === 'p') {
                item.phase = 'Period'
              } else if (firstChar === 'f') {
                item.phase = 'Follicular'
              } else if (firstChar === 'o') {
                item.phase = 'Ovulation'
              } else if (firstChar === 'l') {
                item.phase = 'Luteal'
              }
            }
            map[dateKey] = item
          })
        }
        
        setCalendarPhaseMap(map)
        console.log('✅ Calendar phase map loaded:', Object.keys(map).length, 'dates')
        if (Object.keys(map).length > 0) {
          const sampleDates = Object.keys(map).slice(0, 3)
          sampleDates.forEach(date => {
            console.log(`  ${date}: phase="${map[date].phase}", phase_day_id="${map[date].phase_day_id}"`)
          })
        } else {
          if (!hasLastPeriodDate) {
            console.warn('⚠️ No phase data available. User needs to set last_period_date.')
            console.warn('💡 Solution: Log a period using the "Log Period" button to set your last period date.')
          } else {
            console.warn('⚠️ No phase data available. Backend calculation may have failed.')
            console.warn('💡 Check backend terminal for errors. Make sure backend server is running and has been restarted.')
            console.warn('💡 User has last_period_date:', user?.last_period_date, 'cycle_length:', user?.cycle_length)
          }
        }
      } catch (error) {
        console.error('Failed to fetch phase map for calendar:', error)
        setError(error.message || 'Failed to load calendar data')
        // Fallback to context phaseMap if available
        if (phaseMap && Object.keys(phaseMap).length > 0) {
          console.log('Using context phaseMap as fallback')
          setCalendarPhaseMap(phaseMap)
        } else {
          // Set empty map to stop loading
          setCalendarPhaseMap({})
        }
      } finally {
        setLoadingCalendar(false)
        isFetchingRef.current = false
      }
    }

    fetchPhaseMapForMonth()
    
    // Cleanup: abort request if component unmounts or dependencies change
    return () => {
      abortController.abort()
    }
    // Only depend on activeStartDate and user, NOT phaseMap to prevent infinite loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStartDate, user])

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
        height: '4rem',
        minHeight: '4rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'visible',
        padding: '0.75rem',
        margin: '0.25rem'
      }
    }
    return {}
  }

  const tileContent = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      // Try calendarPhaseMap first (from fetchPhaseMapForMonth), then fallback to context phaseMap
      let phaseData = calendarPhaseMap[dateStr] || phaseMap[dateStr]
      const dayNumber = date.getDate()
      const today = new Date()
      const isToday = format(date, 'yyyy-MM-dd') === format(today, 'yyyy-MM-dd')
      
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
      
      // Determine circle color - ALWAYS show a color, even if no data
      let circleColor = '#D1D5DB' // Default grey
      if (phaseData && phaseData.phase) {
        circleColor = getPhaseCircleColor(phaseData.phase)
        // Debug for first few dates and today
        if (isToday || dayNumber <= 5) {
          console.log(`📅 Date ${dateStr} (day ${dayNumber}): phase=${phaseData.phase}, phase_day_id=${phaseData.phase_day_id}, color=${circleColor}`)
        }
      } else {
        // Debug when no phase data for first few dates
        if (isToday || dayNumber <= 5) {
          console.log(`⚠️ Date ${dateStr} (day ${dayNumber}): No phaseData. calendarPhaseMap=${Object.keys(calendarPhaseMap).length} dates, phaseMap=${Object.keys(phaseMap).length} dates`)
        }
      }
      
      // Use filled circle with white border for better visibility
      // Force inline styles to ensure colors are applied
      // Mobile-optimized: smaller circles on mobile
      const circleSize = (isMobile === true) ? '2rem' : '2.75rem'
      const borderWidth = (isMobile === true) ? '2px' : '3px'
      const circleStyle = {
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: circleSize,
        height: 'auto',
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
        paddingBottom: (isMobile === true) ? '0.25rem' : '0.35rem'
      }
      
      const phaseDayId = phaseData?.phase_day_id || ''
      
      return (
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

        {/* D. Current Phase Card - Mobile Optimized */}
        {currentPhase && currentPhase.phase ? (
          <div 
            className="mb-4 sm:mb-6 rounded-lg shadow-lg p-4 sm:p-6 border-2"
            style={{
              backgroundColor: `${getPhaseColor(currentPhase.phase)}20`,
              borderColor: getPhaseColor(currentPhase.phase)
            }}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 sm:gap-3">
                  <PhaseIcon phase={currentPhase.phase} size={isMobile ? 36 : 48} />
                  <div>
                    <h3 className="text-lg sm:text-xl lg:text-2xl font-bold text-gray-800 capitalize">
                      {t('dashboard.currentPhase')}: {t(`phase.${currentPhase.phase.toLowerCase()}`)}
                    </h3>
                    {(currentPhase.phase_day_id || currentPhase.id) && (
                      <p className="text-sm sm:text-base text-gray-600">{t('dashboard.day')} {currentPhase.phase_day_id || currentPhase.id}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="mb-4 sm:mb-6 bg-white rounded-lg shadow-lg p-4 sm:p-6 border-2 border-gray-200">
            <div className="text-center py-6 sm:py-8">
              <p className="text-sm sm:text-base text-gray-600 mb-2">No cycle data available yet.</p>
              <p className="text-xs sm:text-sm text-gray-500 mb-4 px-2">
                {periodLogs.length >= 1 
                  ? "Cycle predictions are being generated. Please wait a moment and refresh, or check if RAPIDAPI_KEY is configured in your backend."
                  : "Please log your period dates to generate cycle predictions."}
              </p>
              {periodLogs.length >= 1 && (
                <button
                  onClick={() => window.location.reload()}
                  className="bg-period-pink text-white px-4 py-2 rounded-lg font-semibold hover:bg-opacity-90 transition min-h-[44px]"
                >
                  Refresh Page
                </button>
              )}
            </div>
          </div>
        )}

        {/* E. Calendar Section - Mobile First: Stack on mobile, side-by-side on desktop */}
        <div className="flex flex-col lg:grid lg:grid-cols-2 gap-4 sm:gap-6 lg:gap-8 mb-6 sm:mb-8">
          {/* Left Side: Calendar - Full width on mobile */}
          <div className="bg-white rounded-xl shadow-lg p-3 sm:p-4 lg:p-6 border border-gray-100 order-1">
            <div className="mb-4 sm:mb-6">
              <h3 className="text-lg sm:text-xl lg:text-2xl font-bold text-gray-800 mb-1 flex items-center gap-2">
                <CalendarIcon className="h-5 w-5 sm:h-6 sm:w-6 text-period-pink" />
                {t('dashboard.cycleCalendar')}
              </h3>
              <p className="text-xs sm:text-sm text-gray-500">{t('dashboard.calendarDescription')}</p>
            </div>
            
            {loadingCalendar && Object.keys(calendarPhaseMap).length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-period-pink"></div>
              </div>
            ) : (
              <div className="calendar-wrapper">
                <Calendar
                  onChange={setSelectedDate}
                  value={selectedDate}
                  onActiveStartDateChange={onActiveStartDateChange}
                  activeStartDate={activeStartDate}
                  tileClassName={tileClassName}
                  tileContent={tileContent}
                  tileStyle={tileStyle}
                  prev2Label={null}
                  next2Label={null}
                  className="w-full custom-calendar"
                  formatShortWeekday={(locale, date) => {
                    const weekdays = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
                    return weekdays[date.getDay()]
                  }}
                />
              </div>
            )}
            
            {/* Legend - Mobile Optimized */}
            <div className="mt-4 sm:mt-6 pt-4 sm:pt-6 border-t border-gray-200">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 sm:mb-3">{t('dashboard.legend')}</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-5 h-5 rounded-full border-2 border-white flex-shrink-0" 
                    style={{ backgroundColor: '#F8BBD9' }}
                  ></div>
                  <span className="text-xs font-medium text-gray-700">{t('phase.period')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div 
                    className="w-5 h-5 rounded-full border-2 border-white flex-shrink-0" 
                    style={{ backgroundColor: '#4ECDC4' }}
                  ></div>
                  <span className="text-xs font-medium text-gray-700">{t('phase.follicular')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div 
                    className="w-5 h-5 rounded-full border-2 border-white flex-shrink-0" 
                    style={{ backgroundColor: '#FFB74D' }}
                  ></div>
                  <span className="text-xs font-medium text-gray-700">{t('phase.ovulation')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div 
                    className="w-5 h-5 rounded-full border-2 border-white flex-shrink-0" 
                    style={{ backgroundColor: '#BA68C8' }}
                  ></div>
                  <span className="text-xs font-medium text-gray-700">{t('phase.luteal')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div 
                    className="w-5 h-5 rounded-full border-2 flex-shrink-0" 
                    style={{ borderColor: '#D1D5DB', backgroundColor: '#D1D5DB15' }}
                  ></div>
                  <span className="text-xs font-medium text-gray-500">{t('dashboard.noPhaseData')}</span>
                </div>
              </div>
            </div>
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

            {/* Cycle Statistics Card - Mobile Optimized */}
            {cycleStats && (
              <div className="bg-white rounded-lg shadow-lg p-4 sm:p-6">
                <h3 className="text-lg sm:text-xl font-bold mb-3 sm:mb-4 flex items-center gap-2">
                  <CalendarIcon className="h-4 w-4 sm:h-5 sm:w-5 text-period-pink" />
                  {t('dashboard.cycleStatistics')}
                </h3>
                
                {/* Current Phase Badge - Mobile Compact */}
                {cycleStats.currentPhase && (
                  <div className="mb-3 sm:mb-4 p-2 sm:p-3 rounded-lg bg-gradient-to-r from-period-pink/10 to-period-purple/10 border border-period-pink/20">
                    <div className="flex items-center justify-between">
                      <span className="text-xs sm:text-sm text-gray-600">{t('dashboard.currentPhase')}:</span>
                      <span className="font-bold text-sm sm:text-base text-period-pink capitalize">{cycleStats.currentPhase}</span>
                    </div>
                    {cycleStats.phaseDayId && (
                      <div className="text-xs text-gray-500 mt-1">Day {cycleStats.phaseDayId}</div>
                    )}
                  </div>
                )}
                
                <div className="space-y-2 sm:space-y-3 mb-3 sm:mb-4">
                  {/* Basic Cycle Info - Mobile Optimized */}
                  <div className="grid grid-cols-2 gap-2 sm:gap-3 pb-2 sm:pb-3 border-b border-gray-200">
                    <div>
                      <div className="text-xs text-gray-500 mb-1">{t('dashboard.cycleLength')}</div>
                      <div className="font-semibold text-base sm:text-lg">{cycleStats.cycleLength} {t('dashboard.days')}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 mb-1">{t('dashboard.avgPeriodLength') || 'Avg Period'}</div>
                      <div className="font-semibold text-base sm:text-lg">{cycleStats.avgPeriodLength} {t('dashboard.days')}</div>
                    </div>
                  </div>
                  
                  {/* Cycle Progress */}
                  <div className="pb-3 border-b border-gray-200">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm text-gray-600">{t('dashboard.daysSincePeriod')}:</span>
                      <span className="font-semibold">
                        {cycleStats.daysSince !== null && cycleStats.daysSince !== undefined 
                          ? `${cycleStats.daysSince} ${t('dashboard.days')}` 
                          : '—'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">{t('dashboard.daysUntilNext')}:</span>
                      <span className="font-semibold text-period-pink">
                        {cycleStats.daysUntil !== null && cycleStats.daysUntil !== undefined 
                          ? `${cycleStats.daysUntil} ${t('dashboard.days')}` 
                          : '—'}
                      </span>
                    </div>
                    {/* Progress bar */}
                    {cycleStats.daysSince !== null && cycleStats.daysSince !== undefined && (
                      <div className="mt-3 w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-gradient-to-r from-period-pink to-period-purple h-2 rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, (cycleStats.daysSince / cycleStats.cycleLength) * 100)}%` }}
                        ></div>
                      </div>
                    )}
                  </div>
                  
                  {/* Advanced Stats */}
                  {cycleStats.cyclesTracked > 0 && (
                    <div className="space-y-2 pt-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">{t('dashboard.cyclesTracked') || 'Cycles Tracked'}:</span>
                        <span className="font-semibold">{cycleStats.cyclesTracked}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">{t('dashboard.cycleRegularity') || 'Regularity'}:</span>
                        <span className={`font-semibold ${
                          cycleStats.cycleRegularity === 'Very Regular' ? 'text-green-600' :
                          cycleStats.cycleRegularity === 'Regular' ? 'text-blue-600' :
                          cycleStats.cycleRegularity === 'Somewhat Irregular' ? 'text-yellow-600' :
                          'text-orange-600'
                        }`}>
                          {cycleStats.cycleRegularity}
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {/* Predicted Ovulation */}
                  {cycleStats.predictedOvulationDate && (
                    <div className="pt-2 border-t border-gray-200">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">{t('dashboard.predictedOvulation') || 'Predicted Ovulation'}:</span>
                        <span className="font-semibold text-period-purple">
                          {cycleStats.predictedOvulationDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </span>
                      </div>
                      {(() => {
                        const today = new Date()
                        today.setHours(0, 0, 0, 0)
                        const ovDate = new Date(cycleStats.predictedOvulationDate)
                        ovDate.setHours(0, 0, 0, 0)
                        const daysUntilOv = Math.floor((ovDate - today) / (1000 * 60 * 60 * 24))
                        if (daysUntilOv >= 0 && daysUntilOv <= 7) {
                          return (
                            <div className="text-xs text-period-purple mt-1">
                              {daysUntilOv === 0 ? 'Today' : daysUntilOv === 1 ? 'Tomorrow' : `In ${daysUntilOv} days`}
                            </div>
                          )
                        }
                        return null
                      })()}
                    </div>
                  )}
                </div>
                
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="w-full flex items-center justify-center gap-2 bg-period-pink text-white px-4 py-3 sm:py-2 rounded-lg font-semibold hover:bg-opacity-90 transition shadow-lg min-h-[44px] text-sm sm:text-base"
                >
                  <Plus className="h-5 w-5" />
                  <span>{t('dashboard.logPeriod')}</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* F. Three Main Feature Cards - Mobile Optimized */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 lg:gap-6 mb-4 sm:mb-6">
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
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleLogPeriod}
        selectedDate={format(selectedDate, 'yyyy-MM-dd')}
      />
    </div>
  )
}

export default Dashboard
