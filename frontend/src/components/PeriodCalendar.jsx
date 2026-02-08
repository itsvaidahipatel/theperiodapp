import { useState, useEffect, useRef, useMemo } from 'react'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'
import { format, startOfMonth, endOfMonth, addMonths, subMonths, addYears, subYears, startOfDay, isSameDay, addDays, differenceInDays } from 'date-fns'
import { getPhaseMap, logPeriod, getPeriodLogs, getCurrentPhase } from '../utils/api'
import { AlertCircle, Info } from 'lucide-react'

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
const PHASE_COLORS = {
  // ACTUAL/LOGGED dates - Vibrant, solid colors
  Period: '#F8BBD9',      // Soft pastel pink (matches period-pink theme)
  Follicular: '#FEF3C7',   // Soft pastel yellow/cream
  Ovulation: '#B8E6E6',    // Soft pastel teal/cyan
  Luteal: '#E1BEE7',       // Soft pastel lavender (matches period-lavender theme)
  Logged: '#E91E63',       // Vibrant pink for logged periods (darker, more solid)
  Default: '#F3F4F6'       // Soft gray for no data
}

// PREDICTED dates - Muted, lighter versions
const PREDICTED_PHASE_COLORS = {
  Period: '#FCE4EC',       // Very light pink for predicted periods
  Follicular: '#FFF9E6',   // Very light yellow for predicted follicular
  Ovulation: '#E0F7FA',   // Very light teal for predicted ovulation
  Luteal: '#F3E5F5',       // Very light lavender for predicted luteal
  Default: '#F5F5F5'       // Very light gray for predicted no data
}

const PeriodCalendar = ({ onPeriodLogged }) => {
  const [selectedDate, setSelectedDate] = useState(null)
  const [phaseMap, setPhaseMap] = useState({})
  const [periodLogs, setPeriodLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeStartDate, setActiveStartDate] = useState(new Date())
  const [showLogButton, setShowLogButton] = useState(false)
  const [logging, setLogging] = useState(false)
  const [error, setError] = useState(null)
  const [todayPhase, setTodayPhase] = useState(null) // Today's phase information
  const isInitialLoadRef = useRef(true) // Ref to track initial load
  const isPrefetchingRef = useRef(false) // Track if prefetching is in progress
  const prefetchedMonthsRef = useRef(new Set()) // Track which months have been prefetched

  // FAST MAP-BASED LOOKUPS (inspired by reference code)
  // Pre-calculate phase info map for O(1) lookups
  const phaseInfoMap = useMemo(() => {
    const map = new Map()
    Object.entries(phaseMap).forEach(([dateStr, phaseData]) => {
      // Handle both object format and direct phase string
      if (phaseData) {
        const phase = typeof phaseData === 'string' ? phaseData : phaseData.phase
        if (phase) {
          map.set(dateStr, {
            phase: phase,
            phaseDayId: typeof phaseData === 'object' ? (phaseData.phase_day_id || null) : null,
            fertilityProb: typeof phaseData === 'object' ? (phaseData.fertility_prob || 0) : 0,
            isPredicted: typeof phaseData === 'object' ? (phaseData.is_predicted !== false) : true
          })
        }
      }
    })
    console.log(`📊 PhaseInfoMap updated: ${map.size} dates with phase data`)
    return map
  }, [phaseMap])

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

  // Fetch phase map - INSTANT: 3 months past + current + 3 months future (7 months total)
  useEffect(() => {
    const fetchPhaseMap = async (forceRefresh = false, isInitial = false) => {
      try {
        // Only show loading on initial load
        if (isInitial && isInitialLoadRef.current) {
          setLoading(true)
          isInitialLoadRef.current = false
        }
        
        let startDate, endDate
        
        if (isInitial) {
          // INITIAL LOAD: Fetch 3 months past + current + 3 months future (7 months) INSTANTLY
          const today = new Date()
          const threeMonthsPast = subMonths(today, 3)
          const threeMonthsFuture = addMonths(today, 3)
          startDate = format(startOfMonth(threeMonthsPast), 'yyyy-MM-dd')
          endDate = format(endOfMonth(threeMonthsFuture), 'yyyy-MM-dd')
          console.log('🚀 INITIAL LOAD: Fetching 7 months instantly (3 past + current + 3 future)')
        } else {
          // MONTH NAVIGATION: Only fetch current visible month + adjacent months
          const prevMonth = subMonths(activeStartDate, 1)
          const nextMonth = addMonths(activeStartDate, 1)
          startDate = format(startOfMonth(prevMonth), 'yyyy-MM-dd')
          endDate = format(endOfMonth(nextMonth), 'yyyy-MM-dd')
        }
        
        // Check if we already have data for this range to avoid unnecessary API calls
        // Skip check if forceRefresh is true
        if (!forceRefresh && !isInitial) {
          const monthKey = format(activeStartDate, 'yyyy-MM')
          const hasDataForMonth = Object.keys(phaseMap).some(date => {
            try {
              const dateObj = new Date(date)
              return format(dateObj, 'yyyy-MM') === monthKey
            } catch {
              return false
            }
          })
          
          // Only fetch if we don't have data for this month
          if (hasDataForMonth) {
            return
          }
        }
        
        // For future months, show loading but don't block - let it generate in background
        let response
        try {
          response = await getPhaseMap(startDate, endDate, forceRefresh)
        } catch (err) {
          // Handle timeout gracefully - show message but don't break calendar
          if (err.message?.includes('timeout') || err.message?.includes('Timeout')) {
            console.warn(`⚠️ Timeout fetching month ${format(activeStartDate, 'MMMM yyyy')}:`, err.message)
            // Only show error for non-initial loads (initial load should have longer timeout)
            if (!isInitial) {
              setError('Predictions for this month are being generated. Please wait a moment and try again.')
            } else {
              // For initial load, just log - don't show error (it's still loading)
              console.log('⏳ Initial load taking longer than expected, continuing...')
            }
            // Don't return - continue to finally block to set loading to false
            // But skip processing response
            response = null
          } else {
            throw err // Re-throw other errors
          }
        }
        
        // Only process response if we have one (not timed out)
        if (!response) {
          // For initial load timeout, keep loading state (will be set in finally)
          // For navigation timeout, clear loading
          if (!isInitial) {
            setLoading(false)
          }
          return
        }
        
        if (response?.phase_map && Array.isArray(response.phase_map)) {
          const map = {}
          response.phase_map.forEach((item) => {
            if (item.date && item.phase) {
              map[item.date] = {
                phase: item.phase,
                phase_day_id: item.phase_day_id || null,
                fertility_prob: item.fertility_prob || 0
              }
            }
          })
          // Merge with existing map instead of replacing
          setPhaseMap(prevMap => {
            const merged = { ...prevMap, ...map }
            console.log(`✅ Phase map updated: ${Object.keys(merged).length} total dates, ${Object.keys(map).length} new dates for ${format(activeStartDate, 'MMMM yyyy')}`)
            // Log phase distribution for debugging
            const phaseCounts = {}
            Object.values(merged).forEach(item => {
              const p = (typeof item === 'object' && item.phase) ? item.phase : 'Unknown'
              phaseCounts[p] = (phaseCounts[p] || 0) + 1
            })
            console.log(`   Phase distribution:`, phaseCounts)
            
            // Verify phase data structure
            const sampleDates = Object.keys(map).slice(0, 3)
            sampleDates.forEach(dateStr => {
              const data = map[dateStr]
              console.log(`   Sample date ${dateStr}:`, data)
            })
            
            // Dispatch calendar update event for cycle history
            window.dispatchEvent(new CustomEvent('calendarUpdated'))
            
            return merged
          })
        } else {
          console.warn('⚠️ No phase map data received from API')
          console.warn('Response:', response)
        }
      } catch (err) {
        console.error('Failed to fetch phase map:', err)
        // Don't clear phaseMap on error - keep existing data visible
        setError(err.message || 'Failed to load calendar predictions')
      } finally {
        setLoading(false)
      }
    }

    // Initial load: Fetch 7 months instantly
    fetchPhaseMap(false, true)
    
    // Listen for periodLogged event to force refresh
    const handlePeriodLogged = () => {
      // Force refresh immediately - backend generates 7 months synchronously
      // This ensures calendar shows accurate predictions right away
      console.log('🔄 Period logged - refreshing 7 months with accurate calculations')
      fetchPhaseMap(true, true) // Refresh 7 months with force recalculation
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
    }
  }, []) // Only run on mount - don't refetch on activeStartDate change
  
  // Separate effect for month navigation - only fetch missing months
  useEffect(() => {
    const fetchMissingMonth = async () => {
      // Skip if initial load hasn't completed
      if (isInitialLoadRef.current) return
      
      const monthKey = format(activeStartDate, 'yyyy-MM')
      const hasDataForMonth = Object.keys(phaseMap).some(date => {
        try {
          const dateObj = new Date(date)
          return format(dateObj, 'yyyy-MM') === monthKey
        } catch {
          return false
        }
      })
      
      if (!hasDataForMonth) {
        // Fetch only the missing month + adjacent months for context
        const prevMonth = subMonths(activeStartDate, 1)
        const nextMonth = addMonths(activeStartDate, 1)
        const startDate = format(startOfMonth(prevMonth), 'yyyy-MM-dd')
        const endDate = format(endOfMonth(nextMonth), 'yyyy-MM-dd')
        
        try {
          const response = await getPhaseMap(startDate, endDate, false)
          if (response?.phase_map && Array.isArray(response.phase_map)) {
            const map = {}
            response.phase_map.forEach((item) => {
              if (item.date && item.phase) {
                map[item.date] = {
                  phase: item.phase,
                  phase_day_id: item.phase_day_id || null,
                  fertility_prob: item.fertility_prob || 0
                }
              }
            })
            setPhaseMap(prevMap => ({ ...prevMap, ...map }))
            console.log(`✅ Fetched missing month: ${monthKey}`)
          }
        } catch (err) {
          console.error('Failed to fetch missing month:', err)
        }
      }
    }
    
    fetchMissingMonth()
  }, [activeStartDate])

  // Background prefetching: Load remaining months, cycle stats, and cycle history in PARALLEL
  useEffect(() => {
    // Only start prefetching after initial load is complete
    if (isInitialLoadRef.current || loading) return
    
    console.log('🔄 Starting PARALLEL background prefetch: months + cycle stats + cycle history...')

    const prefetchAllInParallel = async () => {
      if (isPrefetchingRef.current) return
      isPrefetchingRef.current = true

      try {
        // PARALLEL TASK 1: Prefetch remaining calendar months
        const prefetchMonths = async () => {
          try {
            const today = new Date()
            const monthsToPrefetch = []
            
            // Generate list of months to prefetch: 1 year past to 2 years future
            // SKIP the 7 months already loaded (3 past + current + 3 future)
            for (let i = -12; i <= 24; i++) {
              const monthDate = addMonths(today, i)
              const monthKey = format(monthDate, 'yyyy-MM')
              
              // Skip the 7 months already loaded in initial fetch (3 past + current + 3 future)
              if (i >= -3 && i <= 3) continue
              
              // Skip if already prefetched or currently visible
              if (prefetchedMonthsRef.current.has(monthKey)) continue
              if (format(activeStartDate, 'yyyy-MM') === monthKey) continue
              
              monthsToPrefetch.push({
                date: monthDate,
                key: monthKey,
                startDate: format(startOfMonth(monthDate), 'yyyy-MM-dd'),
                endDate: format(endOfMonth(monthDate), 'yyyy-MM-dd')
              })
            }

            // Prefetch months in batches
            const batchSize = 5
            for (let i = 0; i < monthsToPrefetch.length; i += batchSize) {
              const batch = monthsToPrefetch.slice(i, i + batchSize)
              
              await Promise.all(
                batch.map(async ({ date, key, startDate, endDate }) => {
                  try {
                    // Check again if we have data
                    const monthKeyCheck = key.substring(0, 7)
                    const hasData = Object.keys(phaseMap).some(d => {
                      try {
                        return d.startsWith(monthKeyCheck)
                      } catch {
                        return false
                      }
                    })
                    if (hasData) {
                      prefetchedMonthsRef.current.add(key)
                      return
                    }

                    const response = await getPhaseMap(startDate, endDate)
                    if (response?.phase_map && Array.isArray(response.phase_map)) {
                      const map = {}
                      response.phase_map.forEach((item) => {
                        if (item.date && item.phase) {
                          map[item.date] = {
                            phase: item.phase,
                            phase_day_id: item.phase_day_id || null,
                            fertility_prob: item.fertility_prob || 0
                          }
                        }
                      })
                      
                      // Merge with existing map
                      setPhaseMap(prevMap => ({ ...prevMap, ...map }))
                      prefetchedMonthsRef.current.add(key)
                      
                      console.log(`✅ Prefetched month: ${key} (${Object.keys(map).length} dates)`)
                      
                      // Dispatch calendar update event for cycle history
                      window.dispatchEvent(new CustomEvent('calendarUpdated'))
                    }
                  } catch (err) {
                    console.error(`Failed to prefetch month ${key}:`, err)
                  }
                })
              )
              
              // Small delay between batches
              if (i + batchSize < monthsToPrefetch.length) {
                await new Promise(resolve => setTimeout(resolve, 200))
              }
            }
            
            console.log('✅ Background month prefetching complete')
          } catch (err) {
            console.error('Error in month prefetching:', err)
          }
        }

        // PARALLEL TASK 2: Prefetch cycle stats
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

        // PARALLEL TASK 3: Prefetch cycle history
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

        // Run all three tasks in PARALLEL
        await Promise.all([
          prefetchMonths(),
          prefetchCycleStats(),
          prefetchCycleHistory()
        ])
        
        console.log('✅ All parallel background tasks complete (months + stats + history)')
      } catch (err) {
        console.error('Error in parallel prefetching:', err)
      } finally {
        isPrefetchingRef.current = false
      }
    }

    // Start parallel prefetching after initial load completes
    const timeoutId = setTimeout(() => {
      prefetchAllInParallel()
    }, 500) // Start quickly after initial load

    return () => clearTimeout(timeoutId)
  }, [loading, activeStartDate, phaseMap])

  // Note: Cycle history prefetching is now handled in the parallel prefetch effect above
  // This ensures it runs in parallel with month prefetching for better performance

  // Get today's phase from phaseMap (already loaded) - much faster than API call
  useEffect(() => {
    const updateTodayPhase = () => {
      const today = format(new Date(), 'yyyy-MM-dd')
      const phaseInfo = getPhaseInfo(today)
      
      if (phaseInfo?.phase) {
        setTodayPhase({
          phase: phaseInfo.phase,
          phaseDayId: phaseInfo.phaseDayId || null
        })
      } else {
        // Fallback: Try API call only if phaseMap doesn't have today's data
        const fetchTodayPhase = async () => {
          try {
            // Add timeout to prevent hanging
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
            // Set a default so it doesn't show "Loading..." forever
            setTodayPhase({
              phase: 'Unknown',
              phaseDayId: null
            })
          }
        }
        fetchTodayPhase()
      }
    }

    // Update when phaseMap changes
    updateTodayPhase()
    
    // Refresh today's phase when period is logged
    const handlePeriodLogged = () => {
      updateTodayPhase()
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
    }
  }, [phaseMap, phaseInfoMap]) // Depend on phaseMap so it updates when calendar loads

  // Fetch period logs
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const logs = await getPeriodLogs()
        setPeriodLogs(logs || [])
      } catch (err) {
        console.error('Failed to fetch period logs:', err)
      }
    }

    fetchLogs()
    
    // Refresh logs and phase map when period is logged (listen for custom event)
    const handlePeriodLogged = async () => {
      // Refresh logs
      fetchLogs()
      
      // Clear phase map cache to force refresh
      setPhaseMap({})
      prefetchedMonthsRef.current.clear()
      
      // Wait a bit for backend to process, then refresh phase map
      setTimeout(async () => {
        const startDate = format(startOfMonth(activeStartDate), 'yyyy-MM-dd')
        const endDate = format(endOfMonth(addMonths(activeStartDate, 1)), 'yyyy-MM-dd')
        try {
          const response = await getPhaseMap(startDate, endDate, true) // Force recalculation
          if (response?.phase_map) {
            const map = {}
            response.phase_map.forEach((item) => {
              map[item.date] = item
            })
            // Merge with existing map
            setPhaseMap(prevMap => ({ ...prevMap, ...map }))
          }
        } catch (err) {
          console.error('Failed to refresh phase map after period logged:', err)
        }
      }, 2000) // Wait 2 seconds for backend to process
    }
    window.addEventListener('periodLogged', handlePeriodLogged)
    
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
    }
  }, [activeStartDate])

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
      await logPeriod({ date: dateStr })
      
      // Refresh logs immediately
      const logs = await getPeriodLogs()
      setPeriodLogs(logs || [])
      
      // Dispatch event to notify other components
      window.dispatchEvent(new CustomEvent('periodLogged'))
      
      // Dispatch calendar update event for cycle history
      window.dispatchEvent(new CustomEvent('calendarUpdated'))
      
      // Clear selection
      setSelectedDate(null)
      setShowLogButton(false)
      
      // Clear phase map cache to force refresh
      setPhaseMap({})
      prefetchedMonthsRef.current.clear()
      
      // Refresh IMMEDIATELY - backend generates predictions synchronously now
      const refreshPhaseMap = async () => {
        const startDate = format(startOfMonth(activeStartDate), 'yyyy-MM-dd')
        const endDate = format(endOfMonth(addMonths(activeStartDate, 1)), 'yyyy-MM-dd')
        try {
          // Force recalculation to get fresh predictions
          const response = await getPhaseMap(startDate, endDate, true)
          if (response?.phase_map && Array.isArray(response.phase_map)) {
            const map = {}
            response.phase_map.forEach((item) => {
              if (item.date && item.phase) {
                map[item.date] = {
                  phase: item.phase,
                  phase_day_id: item.phase_day_id || null,
                  fertility_prob: item.fertility_prob || 0
                }
              }
            })
            // Merge with existing map
            setPhaseMap(prevMap => {
              const merged = { ...prevMap, ...map }
              console.log(`✅ Calendar refreshed: ${Object.keys(map).length} new dates, ${Object.keys(merged).length} total`)
              
              // Dispatch calendar update event for cycle history
              window.dispatchEvent(new CustomEvent('calendarUpdated'))
              
              return merged
            })
          } else {
            console.warn('⚠️ No phase map data in response:', response)
          }
        } catch (err) {
          console.error('Failed to refresh phase map:', err)
        }
      }
      
      // Refresh immediately (backend generates predictions synchronously)
      refreshPhaseMap()
      
      if (onPeriodLogged) {
        onPeriodLogged()
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to log period')
    } finally {
      setLogging(false)
    }
  }

  const getPhaseColor = (phase, isLogged = false) => {
    if (!phase) return isLogged ? PHASE_COLORS.Default : PREDICTED_PHASE_COLORS.Default
    // Use vibrant colors for logged dates, muted colors for predicted
    return isLogged 
      ? (PHASE_COLORS[phase] || PHASE_COLORS.Default)
      : (PREDICTED_PHASE_COLORS[phase] || PREDICTED_PHASE_COLORS.Default)
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
      const dateStr = format(date, 'yyyy-MM-dd')
      // FAST LOOKUP: Use Map for O(1) access instead of object property access
      const phaseInfo = getPhaseInfo(dateStr)
      const isLogged = isDateLogged(dateStr)
      const isSelected = selectedDate && format(selectedDate, 'yyyy-MM-dd') === dateStr
      const today = format(new Date(), 'yyyy-MM-dd')
      const isToday = dateStr === today
      
      // Determine phase and color (fast lookup from Map)
      let phase = phaseInfo?.phase || null
      let phaseDayId = phaseInfo?.phaseDayId || null
      const fertilityProb = phaseInfo?.fertilityProb || 0
      const isPredicted = phaseInfo?.isPredicted !== false
      
      // FALLBACK: If Map lookup fails, try direct phaseMap lookup
      if (!phase) {
        const directPhaseData = phaseMap[dateStr]
        if (directPhaseData) {
          phase = typeof directPhaseData === 'string' ? directPhaseData : directPhaseData.phase
          phaseDayId = typeof directPhaseData === 'object' ? (directPhaseData.phase_day_id || null) : null
        }
      }
      
      // If logged but no phase data, assume Period phase
      if (isLogged && !phase) {
        phase = 'Period'
        phaseDayId = 'p1'
      }
      
      // Debug logging for missing phases
      if (!phase && !isLogged) {
        // Only log occasionally to avoid spam
        if (Math.random() < 0.01) { // 1% chance
          console.log(`⚠️ No phase data for date ${dateStr}, phaseMap has ${Object.keys(phaseMap).length} dates`)
        }
      }
      
      // ALWAYS show a color - use vibrant for logged, muted for predicted
      // This ensures the calendar always has visual feedback
      const backgroundColor = isLogged 
        ? PHASE_COLORS.Logged  // Vibrant pink for actual logged periods
        : phase 
          ? getPhaseColor(phase, false)  // Muted colors for predicted dates
          : PREDICTED_PHASE_COLORS.Default  // Light gray for dates without predictions
      
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
              border: isSelected 
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
              opacity: isLogged ? 1 : isPredicted ? 0.7 : 0.85,  // Lower opacity for predicted
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
      
      // Proactively prefetch adjacent months when user navigates
      const prefetchAdjacentMonths = async () => {
        const monthsToPrefetch = [
          subMonths(newActiveStartDate, 1), // Previous month
          addMonths(newActiveStartDate, 2), // Next month (current + 1 is already visible)
        ]
        
        monthsToPrefetch.forEach(async (monthDate) => {
          const monthKey = format(monthDate, 'yyyy-MM')
          
          // Skip if already prefetched
          if (prefetchedMonthsRef.current.has(monthKey)) return
          
          try {
            const startDate = format(startOfMonth(monthDate), 'yyyy-MM-dd')
            const endDate = format(endOfMonth(monthDate), 'yyyy-MM-dd')
            
            const response = await getPhaseMap(startDate, endDate)
            if (response?.phase_map) {
              const map = {}
              response.phase_map.forEach((item) => {
                map[item.date] = item
              })
              
              setPhaseMap(prevMap => ({ ...prevMap, ...map }))
              prefetchedMonthsRef.current.add(monthKey)
              console.log(`✅ Proactively prefetched adjacent month: ${monthKey}`)
            }
          } catch (err) {
            console.error(`Failed to prefetch adjacent month ${monthKey}:`, err)
          }
        })
      }
      
      // Prefetch adjacent months after a short delay
      setTimeout(prefetchAdjacentMonths, 300)
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

  return (
    <div className="period-calendar-container">
      <div className="mb-6">
        <h3 className="text-2xl font-bold text-gray-800 mb-2">Cycle Calendar</h3>
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

              <button
                onClick={handleLogPeriod}
                disabled={logging || isDateLogged(format(selectedDate, 'yyyy-MM-dd'))}
                className="w-full bg-gradient-to-r from-period-pink to-period-purple text-white px-4 py-3 rounded-lg font-semibold hover:opacity-90 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {logging ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Logging...</span>
                  </>
                ) : isDateLogged(format(selectedDate, 'yyyy-MM-dd')) ? (
                  'Already Logged'
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
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Period, opacity: 0.7 }}
                  />
                  <span className="text-xs font-medium text-gray-600">Predicted Period</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border border-dashed border-gray-300 shadow-sm"
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Follicular, opacity: 0.7 }}
                  />
                  <span className="text-xs font-medium text-gray-600">Predicted Follicular</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border border-dashed border-gray-300 shadow-sm"
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Ovulation, opacity: 0.7 }}
                  />
                  <span className="text-xs font-medium text-gray-600">Predicted Ovulation</span>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50">
                  <div
                    className="w-5 h-5 rounded-lg border border-dashed border-gray-300 shadow-sm"
                    style={{ backgroundColor: PREDICTED_PHASE_COLORS.Luteal, opacity: 0.7 }}
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
