import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'

const CalendarCacheContext = createContext()

export const useCalendarCache = () => {
  const context = useContext(CalendarCacheContext)
  if (!context) {
    throw new Error('useCalendarCache must be used within CalendarCacheProvider')
  }
  return context
}

const getCurrentUserId = () => {
  try {
    const raw = localStorage.getItem('user')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.id || null
  } catch {
    return null
  }
}

export const CalendarCacheProvider = ({ children }) => {
  const userId = getCurrentUserId()
  const phaseKey = userId ? `calendar_phase_map_cache_${userId}` : 'calendar_phase_map_cache'
  const logsKey = userId ? `calendar_period_logs_cache_${userId}` : 'calendar_period_logs_cache'
  const lastLoadKey = userId ? `calendar_last_load_time_${userId}` : 'calendar_last_load_time'
  // Cache for calendar phase data
  const [cachedPhaseMap, setCachedPhaseMap] = useState(() => {
    // Try to load from sessionStorage on mount
    try {
      const cached = sessionStorage.getItem(phaseKey)
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
      const cached = sessionStorage.getItem(logsKey)
      if (cached) {
        return JSON.parse(cached)
      }
    } catch (e) {
      console.error('Error loading period logs cache:', e)
    }
    return []
  })
  
  // Cache for wellness data (hormones, nutrition, exercise) – user-keyed
  const [cachedWellnessData, setCachedWellnessData] = useState(() => {
    try {
      const uid = getCurrentUserId()
      const wKey = uid ? `wellness_data_cache_${uid}` : 'wellness_data_cache'
      const cached = sessionStorage.getItem(wKey)
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
      const cached = sessionStorage.getItem(phaseKey)
      return cached && Object.keys(JSON.parse(cached)).length > 0
    } catch {
      return false
    }
  })
  const [isLoading, setIsLoading] = useState(false)
  const [lastLoadTime, setLastLoadTime] = useState(() => {
    try {
      return sessionStorage.getItem(lastLoadKey)
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
      const uid = getCurrentUserId()
      const pKey = uid ? `calendar_phase_map_cache_${uid}` : 'calendar_phase_map_cache'
      const lKey = uid ? `calendar_period_logs_cache_${uid}` : 'calendar_period_logs_cache'
      const tKey = uid ? `calendar_last_load_time_${uid}` : 'calendar_last_load_time'
      sessionStorage.setItem(pKey, JSON.stringify(phaseMap))
      sessionStorage.setItem(lKey, JSON.stringify(periodLogs))
      sessionStorage.setItem(tKey, now)
    } catch (e) {
      console.error('Error saving calendar cache:', e)
    }
  }, [])
  
  // Update wellness data cache
  const updateWellnessCache = useCallback((wellnessData) => {
    setCachedWellnessData(wellnessData)
    try {
      const uid = getCurrentUserId()
      const wKey = uid ? `wellness_data_cache_${uid}` : 'wellness_data_cache'
      sessionStorage.setItem(wKey, JSON.stringify(wellnessData))
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
      const uid = getCurrentUserId()
      const pKey = uid ? `calendar_phase_map_cache_${uid}` : 'calendar_phase_map_cache'
      const lKey = uid ? `calendar_period_logs_cache_${uid}` : 'calendar_period_logs_cache'
      const tKey = uid ? `calendar_last_load_time_${uid}` : 'calendar_last_load_time'
      const wKey = uid ? `wellness_data_cache_${uid}` : 'wellness_data_cache'
      sessionStorage.removeItem(pKey)
      sessionStorage.removeItem(lKey)
      sessionStorage.removeItem(tKey)
      sessionStorage.removeItem(wKey)
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
