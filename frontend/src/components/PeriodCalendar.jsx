import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'
import { format, startOfMonth, endOfMonth, addMonths, subMonths, addYears, subYears, startOfDay, isSameDay, addDays, differenceInDays } from 'date-fns'
import { logPeriod, getCurrentPhase, getHormonesData, getNutritionData, getExerciseData } from '../utils/api'
import { AlertCircle, Info, RefreshCw } from 'lucide-react'
import { useCalendarCache } from '../context/CalendarCacheContext'
import { useDataContext } from '../context/DataContext'

// Get user from localStorage (since we don't have context here)
const getUser = () => {
  try {
    const userStr = localStorage.getItem('user')
    return userStr ? JSON.parse(userStr) : null
  } catch {
    return null
  }
}

// Color scheme: Actual dates (vibrant) vs Predicted dates (muted)
// Keys must match exact case: 'Period', 'Follicular', 'Ovulation', 'Luteal'
const PHASE_COLORS = {
  Period: '#F8BBD9',      // Soft pastel pink (matches period-pink theme)
  Follicular: '#FEF3C7',   // Soft pastel yellow/cream
  Ovulation: '#B8E6E6',   // Soft pastel teal/cyan
  Luteal: '#E1BEE7',      // Soft pastel lavender (matches period-lavender theme)
  Logged: '#E91E63',      // Vibrant pink for logged periods (darker, more solid)
  Default: '#F3F4F6'      // Soft gray for no data
}

// Normalize API phase string to exact key for PHASE_COLORS / PREDICTED_PHASE_COLORS lookup
const PHASE_KEYS = ['Period', 'Follicular', 'Ovulation', 'Luteal']
const normalizePhaseKey = (phase) => {
  if (!phase || typeof phase !== 'string') return null
  const trimmed = phase.trim()
  const lower = trimmed.toLowerCase()
  return PHASE_KEYS.find(k => k.toLowerCase() === lower) || null
}

// PREDICTED dates - Same as PHASE_COLORS but with 0.8 opacity so they are visible
const PREDICTED_PHASE_COLORS = {
  Period: '#F8BBD9CC',      // PHASE_COLORS.Period @ 0.8
  Follicular: '#FEF3C7CC',  // PHASE_COLORS.Follicular @ 0.8
  Ovulation: '#B8E6E6CC',   // PHASE_COLORS.Ovulation @ 0.8
  Luteal: '#E1BEE7CC',      // PHASE_COLORS.Luteal @ 0.8
  Logged: '#E91E63CC',      // PHASE_COLORS.Logged @ 0.8
  Default: '#F3F4F6CC'      // PHASE_COLORS.Default @ 0.8
}

const PeriodCalendar = ({ onPeriodLogged }) => {
  // Single source of truth: phase map and period logs come from DataContext (fetched once on app load)
  const { dashboardData } = useDataContext()
  const phaseMap = dashboardData?.phaseMap || {}
  const periodLogs = dashboardData?.periodLogs || []
  const contextLoading = dashboardData === undefined || dashboardData === null

  const {
    cachedWellnessData,
    updateCache,
    updateWellnessCache,
    clearCache
  } = useCalendarCache()

  const [selectedDate, setSelectedDate] = useState(null)
  const [loading, setLoading] = useState(contextLoading)

  // Sync context data to calendar cache so other consumers (Nutrition, Exercise, etc.) have it
  useEffect(() => {
    if (Object.keys(phaseMap).length > 0 || periodLogs.length > 0) {
      const t = setTimeout(() => updateCache(phaseMap, periodLogs), 0)
      return () => clearTimeout(t)
    }
  }, [phaseMap, periodLogs, updateCache])

  useEffect(() => {
    setLoading(contextLoading)
  }, [contextLoading])
  
  const [activeStartDate, setActiveStartDate] = useState(new Date())
  const [showLogButton, setShowLogButton] = useState(false)
  const [logging, setLogging] = useState(false)
  const [error, setError] = useState(null)
  const [todayPhase, setTodayPhase] = useState(null)
  const isPrefetchingRef = useRef(false)
  const lastGetCurrentPhaseDateRef = useRef(null) // Prevent infinite getCurrentPhase loop

  // Build Map from dashboardData.phaseMap (keyed by date) for O(1) lookups; only when phaseMap changes
  const phaseMapRef = dashboardData?.phaseMap
  const phaseInfoMap = useMemo(() => {
    const map = new Map()
    const source = phaseMapRef || {}
    Object.entries(source).forEach(([dateStr, phaseData]) => {
      if (!phaseData) return
      let phase = typeof phaseData === 'string' ? phaseData : (phaseData.phase && phaseData.phase.trim ? phaseData.phase.trim() : phaseData.phase)
      if (!phase && phaseData.phase_day_id) {
        const pid = String(phaseData.phase_day_id).toLowerCase()
        const first = pid.charAt(0)
        if (first === 'p') phase = 'Period'
        else if (first === 'f') phase = 'Follicular'
        else if (first === 'o') phase = 'Ovulation'
        else if (first === 'l') phase = 'Luteal'
      }
      if (phase) {
        map.set(dateStr, {
          phase: phase,
          phaseDayId: typeof phaseData === 'object' ? (phaseData.phase_day_id || null) : null,
          fertilityProb: typeof phaseData === 'object' ? (phaseData.fertility_prob || 0) : 0,
          isPredicted: typeof phaseData === 'object' ? (phaseData.is_predicted !== false) : true
        })
      }
    })
    console.log(`📊 PhaseInfoMap updated: ${map.size} dates (from phaseMap keys: ${Object.keys(source).length})`)
    // #region agent log
    const sampleKey = map.size ? Array.from(map.keys())[0] : null
    const sampleVal = sampleKey ? map.get(sampleKey) : null
    fetch('http://127.0.0.1:7242/ingest/6e7c83a7-9704-42b4-bb73-f91cceedfc17',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'PeriodCalendar.jsx:phaseInfoMap',message:'phaseInfoMap built',data:{size:map.size,sourceKeys:Object.keys(source).length,sampleKey,samplePhase:sampleVal?.phase},timestamp:Date.now(),hypothesisId:'A,C,E'})}).catch(()=>{});
    // #endregion
    return map
  }, [phaseMapRef])

  // Pre-calculate logged dates set for O(1) lookups
  // Note: periodLogs now contains period START dates only
  // The backend automatically creates period days in user_cycle_days, 
  // so we check phaseMap for Period phase with is_predicted=false to identify logged periods
  const loggedDatesSet = useMemo(() => {
    const set = new Set()
    // Add period start dates
    periodLogs.forEach(log => {
      const dateStr = log.startDate || log.date
      if (dateStr) {
        set.add(dateStr)
      }
    })
    // Also add dates from phaseMap that are Period phase and not predicted (logged)
    Object.entries(phaseMap).forEach(([dateStr, phaseData]) => {
      const phase = typeof phaseData === 'string' ? phaseData : phaseData.phase
      const isPredicted = typeof phaseData === 'object' ? (phaseData.is_predicted !== false) : true
      if (phase === 'Period' && !isPredicted) {
        set.add(dateStr)
      }
    })
    return set
  }, [periodLogs, phaseMap])

  // Date range: 1 year past to 2 years future
  const minDate = subYears(new Date(), 1)
  const maxDate = addYears(new Date(), 2)

  // Event listeners: DataContext handles refetch/clear; we only clear local cache here
  useEffect(() => {
    const handleResetAllCycles = () => {
      clearCache()
    }
    window.addEventListener('resetAllCycles', handleResetAllCycles)
    return () => window.removeEventListener('resetAllCycles', handleResetAllCycles)
  }, [clearCache])

  // Background prefetching: Load cycle stats and cycle history
  useEffect(() => {
    if (loading) return
    
    console.log('🔄 Starting background prefetch: cycle stats + cycle history (no aggressive month prefetch)')

    const prefetchStatsAndHistory = async () => {
      if (isPrefetchingRef.current) return
      isPrefetchingRef.current = true

      try {

        // PARALLEL TASK 1: Prefetch cycle stats
        const prefetchCycleStats = async () => {
          try {
            const { getCycleStats } = await import('../utils/api')
            const stats = await getCycleStats()
            console.log('✅ Cycle stats prefetched:', { 
              totalCycles: stats.totalCycles,
              averageCycleLength: stats.averageCycleLength 
            })
            // Dispatch event with stats for components that need it
            window.dispatchEvent(new CustomEvent('cycleStatsPrefetched', { detail: stats }))
          } catch (err) {
            console.error('Error prefetching cycle stats:', err)
          }
        }

        // PARALLEL TASK 2: Prefetch cycle history
        const prefetchCycleHistory = async () => {
          try {
            const { getCycleStats } = await import('../utils/api')
            const stats = await getCycleStats()
            if (stats?.allCycles) {
              console.log(`✅ Cycle history prefetched: ${stats.allCycles.length} cycles ready`)
              // Dispatch event to notify cycle history page
              window.dispatchEvent(new CustomEvent('cycleHistoryPrefetched', { detail: stats }))
            }
          } catch (err) {
            console.error('Error prefetching cycle history:', err)
          }
        }

        // Run stats and history tasks in PARALLEL (no aggressive month prefetching)
        await Promise.all([
          prefetchCycleStats(),
          prefetchCycleHistory()
        ])
        
        console.log('✅ All parallel background tasks complete (stats + history)')
      } catch (err) {
        console.error('Error in parallel prefetching:', err)
      } finally {
        isPrefetchingRef.current = false
      }
    }

    // Start parallel prefetching after initial load completes
    const timeoutId = setTimeout(() => {
      prefetchStatsAndHistory()
    }, 500) // Start quickly after initial load

    return () => clearTimeout(timeoutId)
  }, [loading, phaseMap])

  // Note: Cycle history prefetching is now handled in the parallel prefetch effect above
  // This ensures it runs in parallel with month prefetching for better performance

  // Preload wellness data (hormones, nutrition, exercise) when calendar loads
  useEffect(() => {
    const preloadWellnessData = async () => {
      // Only preload if we have phaseMap data and today's phase_day_id
      if (Object.keys(phaseMap).length === 0) return
      
      const today = format(new Date(), 'yyyy-MM-dd')
      const todayPhaseData = phaseMap[today]
      
      if (!todayPhaseData) return
      
      const todayPhaseDayId = typeof todayPhaseData === 'object' 
        ? todayPhaseData.phase_day_id 
        : null
      
      if (!todayPhaseDayId) return
      
      // Check if we already have cached wellness data for this phase_day_id
      if (cachedWellnessData?.phaseDayId === todayPhaseDayId && 
          cachedWellnessData?.hormones && 
          cachedWellnessData?.nutrition && 
          cachedWellnessData?.exercises) {
        console.log('📦 Wellness data already cached for phase_day_id:', todayPhaseDayId)
        return
      }
      
      // Get user language for nutrition/exercise
      const user = getUser()
      const language = user?.language || 'en'
      
      console.log(`🚀 Preloading wellness data for phase_day_id: ${todayPhaseDayId} (language: ${language})`)
      
      // Fetch all wellness data in parallel (background, non-blocking)
      Promise.all([
        getHormonesData(todayPhaseDayId, 5).catch(err => {
          console.warn('⚠️ Failed to preload hormones data:', err)
          return null
        }),
        getNutritionData(todayPhaseDayId, language).catch(err => {
          console.warn('⚠️ Failed to preload nutrition data:', err)
          return null
        }),
        getExerciseData(todayPhaseDayId, language).catch(err => {
          console.warn('⚠️ Failed to preload exercise data:', err)
          return null
        })
      ]).then(([hormones, nutrition, exercises]) => {
        if (hormones || nutrition || exercises) {
          updateWellnessCache({
            hormones,
            nutrition,
            exercises,
            phaseDayId: todayPhaseDayId,
            timestamp: new Date().toISOString()
          })
          console.log('✅ Wellness data preloaded and cached')
        }
      }).catch(err => {
        console.error('❌ Error preloading wellness data:', err)
      })
    }
    
    // Preload after a short delay to not block calendar rendering
    const timeoutId = setTimeout(preloadWellnessData, 500)
    return () => clearTimeout(timeoutId)
  }, [phaseMap, cachedWellnessData?.phaseDayId, updateWellnessCache])

  // Get today's phase from phaseMap (already loaded) - avoid calling getCurrentPhase in a loop
  useEffect(() => {
    const today = format(new Date(), 'yyyy-MM-dd')
    const phaseInfo = getPhaseInfo(today)

    if (phaseInfo?.phase) {
      lastGetCurrentPhaseDateRef.current = null // Reset so periodLogged can refetch if needed
      setTodayPhase({
        phase: phaseInfo.phase,
        phaseDayId: phaseInfo.phaseDayId || null
      })
      return
    }

    // Fallback: call getCurrentPhase at most once per day when today is missing from phaseMap
    if (lastGetCurrentPhaseDateRef.current === today) return
    lastGetCurrentPhaseDateRef.current = today

    const fetchTodayPhase = async () => {
      try {
        const timeoutPromise = new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), 3000)
        )
        const phaseData = await Promise.race([
          getCurrentPhase(),
          timeoutPromise
        ])
        if (phaseData?.phase) {
          setTodayPhase({
            phase: phaseData.phase,
            phaseDayId: phaseData.phase_day_id || null
          })
        }
      } catch (err) {
        console.error('Failed to fetch today\'s phase:', err)
        setTodayPhase({ phase: 'Unknown', phaseDayId: null })
      }
    }
    fetchTodayPhase()
  }, [phaseMapRef]) // Only when phaseMap changes; getPhaseInfo from phaseInfoMap (derived from phaseMapRef)

  // Refresh today's phase when period is logged (reset ref so one refetch is allowed)
  useEffect(() => {
    const handlePeriodLogged = () => {
      lastGetCurrentPhaseDateRef.current = null
      const today = format(new Date(), 'yyyy-MM-dd')
      const phaseInfo = getPhaseInfo(today)
      if (phaseInfo?.phase) {
        setTodayPhase({ phase: phaseInfo.phase, phaseDayId: phaseInfo.phaseDayId || null })
      } else {
        getCurrentPhase().then((phaseData) => {
          if (phaseData?.phase) {
            setTodayPhase({ phase: phaseData.phase, phaseDayId: phaseData.phase_day_id || null })
          }
        }).catch(() => {})
      }
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    return () => window.removeEventListener('periodLogged', handlePeriodLogged)
  }, [])

  const handleDateClick = (date) => {
    // Prevent triggering activeStartDate change when just selecting a date
    // Only update selected date, don't change activeStartDate
    setSelectedDate(date)
    setShowLogButton(true)
    setError(null)
    
    // If the clicked date is in a different month, update activeStartDate
    // but do it without triggering loading (we'll merge the data)
    const clickedMonth = date.getMonth()
    const clickedYear = date.getFullYear()
    const currentMonth = activeStartDate.getMonth()
    const currentYear = activeStartDate.getFullYear()
    
    if (clickedMonth !== currentMonth || clickedYear !== currentYear) {
      // Update activeStartDate but don't show loading - just update silently
      const newActiveStart = new Date(clickedYear, clickedMonth, 1)
      setActiveStartDate(newActiveStart)
    }
  }

  const handleLogPeriod = async () => {
    if (!selectedDate) return

    // CRITICAL: Prevent logging periods in future dates
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const selectedDateOnly = new Date(selectedDate)
    selectedDateOnly.setHours(0, 0, 0, 0)
    
    if (selectedDateOnly > today) {
      setError('Cannot log period for future dates. Please log periods that have already occurred.')
      return
    }

    // Check if selected date falls within an existing logged period range
    const selectedDateStr = format(selectedDate, 'yyyy-MM-dd')
    const phaseInfo = getPhaseInfo(selectedDateStr)
    const phaseData = phaseMap[selectedDateStr]
    const phase = phaseInfo?.phase || (typeof phaseData === 'string' ? phaseData : phaseData?.phase)
    const isPredicted = phaseInfo?.isPredicted !== false || (typeof phaseData === 'object' ? (phaseData?.is_predicted !== false) : true)
    
    // If this date is already part of a logged period (Period phase, not predicted), prevent logging
    if (phase === 'Period' && !isPredicted) {
      setError('This date is already part of a logged period. Please log only the period start date.')
      return
    }

    try {
      setLogging(true)
      setError(null)
      
      const dateStr = format(selectedDate, 'yyyy-MM-dd')
      const user = getUser()
      const bleedingDays = user?.avg_bleeding_days != null ? Math.max(2, Math.min(8, Number(user.avg_bleeding_days))) : 5
      await logPeriod({ date: dateStr, bleeding_days: bleedingDays })
      window.dispatchEvent(new CustomEvent('periodLogged'))
      window.dispatchEvent(new CustomEvent('calendarUpdated'))
      setSelectedDate(null)
      setShowLogButton(false)
      if (onPeriodLogged) {
        onPeriodLogged()
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to log period')
    } finally {
      setLogging(false)
    }
  }

  const handleLogPeriodStart = async () => {
    if (!selectedDate) return

    // CRITICAL: Prevent logging periods in future dates
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const selectedDateOnly = new Date(selectedDate)
    selectedDateOnly.setHours(0, 0, 0, 0)
    
    if (selectedDateOnly > today) {
      setError('Cannot log period for future dates. Please log periods that have already occurred.')
      return
    }

    const selectedDateStr = format(selectedDate, 'yyyy-MM-dd')
    
    setLogging(true)
    setError(null)

    try {
      const user = getUser()
      const bleedingDays = user?.avg_bleeding_days != null ? Math.max(2, Math.min(8, Number(user.avg_bleeding_days))) : 5
      await logPeriod({ date: selectedDateStr, bleeding_days: bleedingDays })
      window.dispatchEvent(new CustomEvent('periodLogged'))
      window.dispatchEvent(new CustomEvent('calendarUpdated'))
      setSelectedDate(null)
      setShowLogButton(false)
      if (onPeriodLogged) onPeriodLogged()
    } catch (err) {
      console.error('Failed to log period start:', err)
      setError(err.response?.data?.detail || err.message || 'Failed to log period start')
    } finally {
      setLogging(false)
    }
  }

  const getPhaseColor = (phase, isLogged = false) => {
    if (!phase) return isLogged ? PHASE_COLORS.Default : PREDICTED_PHASE_COLORS.Default
    const key = normalizePhaseKey(phase)
    if (!key) return isLogged ? PHASE_COLORS.Default : PREDICTED_PHASE_COLORS.Default
    return isLogged
      ? (PHASE_COLORS[key] || PHASE_COLORS.Default)
      : (PREDICTED_PHASE_COLORS[key] || PREDICTED_PHASE_COLORS.Default)
  }

  // Fast O(1) lookup for logged dates (using Set)
  const isDateLogged = (dateStr) => {
    return loggedDatesSet.has(dateStr)
  }

  // Fast O(1) lookup for phase info (using Map)
  const getPhaseInfo = (dateStr) => {
    return phaseInfoMap.get(dateStr) || null
  }

  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      // Use both Map and direct lookup for reliability
      const phaseInfo = getPhaseInfo(dateStr)
      const phaseData = phaseMap[dateStr] || (phaseInfo ? { phase: phaseInfo.phase } : null)
      const isLogged = isDateLogged(dateStr)
      const isSelected = selectedDate && format(selectedDate, 'yyyy-MM-dd') === dateStr
      
      let classes = 'custom-calendar-day'
      if (isSelected) {
        classes += ' selected-date'
      }
      if (isLogged) {
        classes += ' logged-period'
      }
      // Add phase class for styling
      if (phaseData?.phase) {
        classes += ` phase-${phaseData.phase.toLowerCase()}`
      }
      
      return classes
    }
    return null
  }

  const tileContent = ({ date, view }) => {
    if (view === 'month') {
      // O(1) lookup: dateStr must be 'yyyy-MM-dd' to match phaseMap keys (e.g. '2026-02-09')
      const dateStr = format(date, 'yyyy-MM-dd')
      const phaseInfo = getPhaseInfo(dateStr)
      const isLogged = isDateLogged(dateStr)
      const isSelected = selectedDate && format(selectedDate, 'yyyy-MM-dd') === dateStr
      const today = format(new Date(), 'yyyy-MM-dd')
      const isToday = dateStr === today
      
      let phase = phaseInfo?.phase || null
      let phaseDayId = phaseInfo?.phaseDayId || null
      const fertilityProb = phaseInfo?.fertilityProb || 0
      const isPredicted = phaseInfo?.isPredicted !== false
      
      if (!phase) {
        const directPhaseData = phaseMap[dateStr]
        if (directPhaseData) {
          phase = typeof directPhaseData === 'string' ? directPhaseData : directPhaseData.phase
          phaseDayId = typeof directPhaseData === 'object' ? (directPhaseData.phase_day_id || null) : null
        }
      }
      
      if (isLogged && !phase) {
        phase = 'Period'
        phaseDayId = 'p1'
      }
      
      if (!phase && !isLogged && Math.random() < 0.01) {
        console.log(`⚠️ No phase for ${dateStr}, phaseMap keys: ${Object.keys(phaseMap).length}`)
      }
      
      // If phaseMap is empty, do NOT render muted/predicted colors (transparent only)
      const phaseMapHasData = Object.keys(phaseMap).length > 0
      const phaseKey = normalizePhaseKey(phase)
      const backgroundColor = !phaseMapHasData
        ? 'transparent'
        : isLogged
          ? PHASE_COLORS.Logged
          : phaseKey
            ? (PHASE_COLORS[phaseKey] || PHASE_COLORS.Default)
            : 'transparent'

      // #region agent log
      const isTodayForLog = dateStr === format(new Date(), 'yyyy-MM-dd')
      if (isTodayForLog || (phaseMapHasData && !phase && Math.random() < 0.05)) {
        fetch('http://127.0.0.1:7242/ingest/6e7c83a7-9704-42b4-bb73-f91cceedfc17',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'PeriodCalendar.jsx:tileContent',message:'tile render',data:{dateStr,phase,phaseMapHasData,backgroundColor,hasPhaseInColors:!!(phaseKey && PHASE_COLORS[phaseKey]),phaseMapKeys:Object.keys(phaseMap).length},timestamp:Date.now(),hypothesisId:'C,D,E'})}).catch(()=>{});
      }
      // #endregion

      // Fast fertility/ovulation checks using pre-calculated data
      const isFertile = fertilityProb >= 0.3 && phase !== 'Period' && phase !== 'Ovulation'
      const isOvulation = phase === 'Ovulation'
      const isPeriodDay = phase === 'Period' || isLogged
      
      return (
        <div
          className="calendar-day-content"
          style={{
            position: 'relative',
            width: '100%',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer'
          }}
        >
          {/* Background color based on phase - Pastel with better styling */}
          <div
            style={{
              position: 'absolute',
              top: '4px',
              left: '4px',
              right: '4px',
              bottom: '4px',
              backgroundColor: backgroundColor,
              borderRadius: '12px',
              border: !phaseMapHasData
                ? (isSelected ? '3px solid #E91E63' : isToday ? '2px solid #E91E63' : '1px solid rgba(0, 0, 0, 0.1)')
                : isSelected 
                  ? '3px solid #E91E63'  // Vibrant border for selected
                  : isToday 
                    ? '2px solid #E91E63'  // Vibrant border for today
                    : isLogged
                      ? '2px solid #C2185B'  // Darker border for logged dates (vibrant)
                      : isPredicted
                        ? '1px dashed rgba(0, 0, 0, 0.15)'  // Dashed border for predicted dates
                        : '1px solid rgba(255, 255, 255, 0.5)',
              boxShadow: isSelected 
                ? '0 4px 12px rgba(233, 30, 99, 0.4)' 
                : isToday 
                  ? '0 2px 8px rgba(233, 30, 99, 0.3)' 
                  : isLogged
                    ? '0 2px 6px rgba(233, 30, 99, 0.25)'  // Stronger shadow for logged
                    : isPredicted
                      ? '0 1px 2px rgba(0, 0, 0, 0.05)'  // Subtle shadow for predicted
                      : '0 1px 3px rgba(0, 0, 0, 0.1)',
              opacity: !phaseMapHasData ? 1 : (isLogged ? 1 : isPredicted ? 0.7 : 0.85),
              transition: 'all 0.2s ease'
            }}
          />
          
          {/* Day number */}
          <span
            style={{
              position: 'relative',
              zIndex: 10,
              fontSize: '1rem',
              fontWeight: isToday ? 'bold' : '600',
              color: phase === 'Period' || isLogged 
                ? '#8B1538'  // Darker pink for contrast
                : phase === 'Ovulation'
                  ? '#0C4A6E'  // Darker teal for contrast
                  : '#374151',  // Dark gray for other phases
              textShadow: 'none',
              lineHeight: '1.2'
            }}
          >
            {date.getDate()}
          </span>
          
          {/* Phase day ID */}
          {phaseDayId && (
            <span
              style={{
                position: 'relative',
                zIndex: 10,
                fontSize: '0.625rem',
                fontWeight: '600',
                color: phase === 'Period' || isLogged 
                  ? '#8B1538'  // Darker pink for contrast
                  : phase === 'Ovulation'
                    ? '#0C4A6E'  // Darker teal for contrast
                    : '#6B7280',  // Medium gray for other phases
                textShadow: 'none',
                marginTop: '2px',
                opacity: 0.8
              }}
            >
              {phaseDayId}
            </span>
          )}
          
          {/* Fertile window indicator - Pastel */}
          {isFertile && (
            <div
              style={{
                position: 'absolute',
                top: '6px',
                right: '6px',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#FCD34D',  // Soft pastel yellow
                border: '2px solid white',
                zIndex: 11,
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)'
              }}
            />
          )}
          
          {/* Ovulation indicator - Pastel */}
          {isOvulation && (
            <div
              style={{
                position: 'absolute',
                top: '6px',
                left: '6px',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#67E8F9',  // Soft pastel cyan
                border: '2px solid white',
                zIndex: 11,
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)'
              }}
            />
          )}
        </div>
      )
    }
    return null
  }

  const tileStyle = ({ date, view }) => {
    if (view === 'month') {
      return {
        height: '4rem',
        minHeight: '4rem',
        padding: '0.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }
    return {}
  }

  const onActiveStartDateChange = ({ activeStartDate: newActiveStartDate }) => {
    // Only update if the month/year actually changed to prevent unnecessary reloads
    const currentMonth = activeStartDate.getMonth()
    const currentYear = activeStartDate.getFullYear()
    const newMonth = newActiveStartDate.getMonth()
    const newYear = newActiveStartDate.getFullYear()
    
    if (currentMonth !== newMonth || currentYear !== newYear) {
      setActiveStartDate(newActiveStartDate)
    }
  }

  // Get today's phase display
  const getTodayPhaseDisplay = () => {
    if (!todayPhase) {
      return 'Loading...'
    }
    const phaseName = todayPhase.phase || 'Unknown'
    const phaseDayId = todayPhase.phaseDayId || ''
    return `${phaseName}${phaseDayId ? ` (${phaseDayId})` : ''}`
  }

  // Handle refresh button click
  const handleRefresh = () => {
    console.log('🔄 Manual calendar refresh triggered')
    window.dispatchEvent(new CustomEvent('calendarRefresh'))
  }

  return (
    <div className="period-calendar-container">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-2xl font-bold text-gray-800">Cycle Calendar</h3>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
            title="Refresh calendar data"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-sm text-gray-600">
            Today's Phase:
          </p>
          <span className="px-3 py-1 bg-gradient-to-r from-pink-50 to-purple-50 border border-pink-200 rounded-lg text-sm font-semibold text-period-pink">
            {getTodayPhaseDisplay()}
          </span>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-period-pink"></div>
        </div>
      ) : (
        <>
          <div className="calendar-wrapper mb-6 bg-white rounded-xl p-4 shadow-sm border border-gray-100">
            <Calendar
              onChange={handleDateClick}
              value={selectedDate}
              onActiveStartDateChange={onActiveStartDateChange}
              activeStartDate={activeStartDate}
              tileClassName={tileClassName}
              tileContent={tileContent}
              tileStyle={tileStyle}
              minDate={minDate}
              maxDate={maxDate}
              prev2Label={null}
              next2Label={null}
              formatDay={(locale, date) => ''}
              className="w-full custom-calendar-improved"
            />
          </div>

          {/* Selected Date Info & Log Button - Moved ABOVE legend */}
          {showLogButton && selectedDate && (
            <div className="mb-6 p-5 bg-gradient-to-br from-pink-50 to-purple-50 border-2 border-period-pink/30 rounded-xl shadow-lg">
              <div className="mb-4">
                <p className="text-sm font-semibold text-gray-600 mb-2">Selected Date:</p>
                <p className="text-xl font-bold text-period-pink">
                  {format(selectedDate, 'EEEE, MMMM d, yyyy')}
                </p>
                {isDateLogged(format(selectedDate, 'yyyy-MM-dd')) && (
                  <p className="text-sm text-gray-600 mt-2 flex items-center gap-1">
                    <span className="text-green-600">✓</span> Already logged
                  </p>
                )}
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                  <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              {/* Log Period Start only - end is auto-calculated from typical bleeding length */}
              <button
                onClick={handleLogPeriodStart}
                disabled={logging || isDateLogged(format(selectedDate, 'yyyy-MM-dd'))}
                className="w-full bg-gradient-to-r from-period-pink to-period-purple text-white px-4 py-3 rounded-lg font-semibold hover:opacity-90 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {logging ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Logging...</span>
                  </>
                ) : isDateLogged(format(selectedDate, 'yyyy-MM-dd')) ? (
                  'Period Already Logged'
                ) : (
                  'Log Period Start'
                )}
              </button>
            </div>
          )}

          {/* Legend - Actual vs Predicted */}
          <div className="mb-6 p-5 bg-gradient-to-br from-pink-50 to-purple-50 rounded-xl border border-pink-100">
            <p className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
              <span className="text-period-pink">Phase Legend</span>
            </p>
            
            {/* Actual/Logged Dates */}
            <div className="mb-4">
              <p className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">Actual Dates (Logged)</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border-2 border-gray-300 shadow-sm"
                    style={{ backgroundColor: PHASE_COLORS.Logged }}
                  />
                  <span className="text-xs font-medium text-gray-700">Logged Period</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border-2 border-gray-300 shadow-sm"
                    style={{ backgroundColor: PHASE_COLORS.Period }}
                  />
                  <span className="text-xs font-medium text-gray-700">Period</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border-2 border-gray-300 shadow-sm"
                    style={{ backgroundColor: PHASE_COLORS.Follicular }}
                  />
                  <span className="text-xs font-medium text-gray-700">Follicular</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border-2 border-gray-300 shadow-sm"
                    style={{ backgroundColor: PHASE_COLORS.Ovulation }}
                  />
                  <span className="text-xs font-medium text-gray-700">Ovulation</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border-2 border-gray-300 shadow-sm"
                    style={{ backgroundColor: PHASE_COLORS.Luteal }}
                  />
                  <span className="text-xs font-medium text-gray-700">Luteal</span>
                </div>
              </div>
            </div>
            
            {/* Predicted Dates */}
            <div>
              <p className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">Predicted Dates (Lighter)</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border border-dashed border-gray-300 shadow-sm"
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Period }}
                  />
                  <span className="text-xs font-medium text-gray-600">Predicted Period</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border border-dashed border-gray-300 shadow-sm"
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Follicular }}
                  />
                  <span className="text-xs font-medium text-gray-600">Predicted Follicular</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border border-dashed border-gray-300 shadow-sm"
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Ovulation }}
                  />
                  <span className="text-xs font-medium text-gray-600">Predicted Ovulation</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border border-dashed border-gray-300 shadow-sm"
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Luteal }}
                  />
                  <span className="text-xs font-medium text-gray-600">Predicted Luteal</span>
                </div>
              </div>
            </div>
          </div>

          {/* Medical Note - Pastel themed */}
          <div className="mb-6 p-4 bg-gradient-to-br from-blue-50 to-cyan-50 border border-blue-100 rounded-xl">
            <div className="flex items-start gap-3">
              <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-blue-700">
                <p className="font-semibold mb-2 text-blue-800">Medical Accuracy Note:</p>
                <p className="leading-relaxed">
                  Ovulation is calculated based on cycle length and luteal phase (12-16 days, usually 14).
                  Fertile window is 5 days before ovulation to ovulation day (medically accurate: sperm survival + egg viability).
                  Predictions improve with more logged cycles.
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default PeriodCalendar
