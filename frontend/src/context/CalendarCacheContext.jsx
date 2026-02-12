import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'

const CalendarCacheContext = createContext()

export const useCalendarCache = () => {
  const context = useContext(CalendarCacheContext)
  if (!context) {
    throw new Error('useCalendarCache must be used within CalendarCacheProvider')
  }
  return context
}

export const CalendarCacheProvider = ({ children }) => {
  // Cache for calendar phase data
  const [cachedPhaseMap, setCachedPhaseMap] = useState(() => {
    // Try to load from sessionStorage on mount
    try {
      const cached = sessionStorage.getItem('calendar_phase_map_cache')
      if (cached) {
        return JSON.parse(cached)
      }
    } catch (e) {
      console.error('Error loading calendar cache:', e)
    }
    return {}
  })
  
  const [cachedPeriodLogs, setCachedPeriodLogs] = useState(() => {
    try {
      const cached = sessionStorage.getItem('calendar_period_logs_cache')
      if (cached) {
        return JSON.parse(cached)
      }
    } catch (e) {
      console.error('Error loading period logs cache:', e)
    }
    return []
  })
  
  // Cache for wellness data (hormones, nutrition, exercise)
  const [cachedWellnessData, setCachedWellnessData] = useState(() => {
    try {
      const cached = sessionStorage.getItem('wellness_data_cache')
      if (cached) {
        return JSON.parse(cached)
      }
    } catch (e) {
      console.error('Error loading wellness data cache:', e)
    }
    return {
      hormones: null,
      nutrition: null,
      exercises: null,
      phaseDayId: null,
      timestamp: null
    }
  })
  
  // Track if calendar has been loaded in this session
  const [hasLoaded, setHasLoaded] = useState(() => {
    try {
      const cached = sessionStorage.getItem('calendar_phase_map_cache')
      return cached && Object.keys(JSON.parse(cached)).length > 0
    } catch {
      return false
    }
  })
  const [isLoading, setIsLoading] = useState(false)
  const [lastLoadTime, setLastLoadTime] = useState(() => {
    try {
      return sessionStorage.getItem('calendar_last_load_time')
    } catch {
      return null
    }
  })

  // Update cache and persist to sessionStorage
  const updateCache = useCallback((phaseMap, periodLogs) => {
    setCachedPhaseMap(phaseMap)
    setCachedPeriodLogs(periodLogs)
    setHasLoaded(true)
    const now = new Date().toISOString()
    setLastLoadTime(now)
    
    try {
      sessionStorage.setItem('calendar_phase_map_cache', JSON.stringify(phaseMap))
      sessionStorage.setItem('calendar_period_logs_cache', JSON.stringify(periodLogs))
      sessionStorage.setItem('calendar_last_load_time', now)
    } catch (e) {
      console.error('Error saving calendar cache:', e)
    }
  }, [])
  
  // Update wellness data cache
  const updateWellnessCache = useCallback((wellnessData) => {
    setCachedWellnessData(wellnessData)
    try {
      sessionStorage.setItem('wellness_data_cache', JSON.stringify(wellnessData))
    } catch (e) {
      console.error('Error saving wellness data cache:', e)
    }
  }, [])

  // Clear cache (when period is logged or refresh is clicked)
  const clearCache = useCallback(() => {
    setCachedPhaseMap({})
    setCachedPeriodLogs([])
    setCachedWellnessData({
      hormones: null,
      nutrition: null,
      exercises: null,
      phaseDayId: null,
      timestamp: null
    })
    setHasLoaded(false)
    setLastLoadTime(null)
    
    try {
      sessionStorage.removeItem('calendar_phase_map_cache')
      sessionStorage.removeItem('calendar_period_logs_cache')
      sessionStorage.removeItem('wellness_data_cache')
      sessionStorage.removeItem('calendar_last_load_time')
    } catch (e) {
      console.error('Error clearing calendar cache:', e)
    }
  }, [])

  // Check if calendar needs to be loaded
  const shouldLoadCalendar = useCallback(() => {
    // Load if:
    // 1. Never loaded in this session
    // 2. Cache is empty
    return !hasLoaded || Object.keys(cachedPhaseMap).length === 0
  }, [cachedPhaseMap, hasLoaded])

  // Listen for reset events and auth changes to clear cache
  useEffect(() => {
    const handleResetAllCycles = () => {
      console.log('🔄 Reset all cycles event - clearing calendar cache')
      clearCache()
    }
    
    const handleResetLastPeriod = () => {
      console.log('🔄 Reset last period event - clearing calendar cache')
      clearCache()
    }
    
    const handleAuthSuccess = () => {
      console.log('🔄 Auth success - clearing calendar phase map cache for clean slate')
      clearCache()
    }
    
    window.addEventListener('resetAllCycles', handleResetAllCycles)
    window.addEventListener('resetLastPeriod', handleResetLastPeriod)
    window.addEventListener('authSuccess', handleAuthSuccess)
    
    return () => {
      window.removeEventListener('resetAllCycles', handleResetAllCycles)
      window.removeEventListener('resetLastPeriod', handleResetLastPeriod)
      window.removeEventListener('authSuccess', handleAuthSuccess)
    }
  }, [clearCache])

  const value = {
    cachedPhaseMap,
    cachedPeriodLogs,
    cachedWellnessData,
    isLoading,
    setIsLoading,
    hasLoaded,
    lastLoadTime,
    updateCache,
    updateWellnessCache,
    clearCache,
    shouldLoadCalendar
  }

  return <CalendarCacheContext.Provider value={value}>{children}</CalendarCacheContext.Provider>
}
