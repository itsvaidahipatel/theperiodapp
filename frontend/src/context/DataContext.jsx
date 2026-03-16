import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { loadDashboardData, loadWellnessData, getCachedWellnessData, refreshAllData, preloadAllWellnessData } from '../utils/dataLoader'
import { shouldRefetch, clearCache } from '../utils/dataCache'
import { getUserLanguage } from '../utils/userPreferences'

const DataContext = createContext()

export const useDataContext = () => {
  const context = useContext(DataContext)
  if (!context) {
    throw new Error('useDataContext must be used within DataProvider')
  }
  return context
}

export const DataProvider = ({ children }) => {
  const [dashboardData, setDashboardData] = useState(null)
  const [wellnessData, setWellnessData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingWellness, setLoadingWellness] = useState(false)
  const [error, setError] = useState(null)
  const [lastLoadDate, setLastLoadDate] = useState(() => {
    // Get last load date from localStorage
    try {
      return localStorage.getItem('period_gpt_last_load_date')
    } catch {
      return null
    }
  })
  const isFetchingRef = useRef(false)
  const lastFetchRef = useRef(0)
  const lastPhaseMapFetchedAtRef = useRef(0)
  const FETCH_THROTTLE_MS = 2000

  const PHASE_MAP_MAX_AGE_MS = 5 * 60 * 1000 // 5 minutes

  // Check if we need to refetch (date changed or cache invalid)
  const checkAndLoadData = useCallback(async (forceRefresh = false) => {
    if (isFetchingRef.current) {
      console.log('⏳ Dashboard data fetch already in progress, skipping')
      return
    }
    const now = Date.now()
    if (now - lastFetchRef.current < FETCH_THROTTLE_MS) {
      console.log('⏳ Dashboard data fetch throttled (2000ms), skipping')
      return
    }
    // If phaseMap was fetched less than 5 minutes ago, don't fetch again on remount
    if (!forceRefresh && lastPhaseMapFetchedAtRef.current > 0 && (now - lastPhaseMapFetchedAtRef.current) < PHASE_MAP_MAX_AGE_MS) {
      setLoading(false)
      return
    }
    lastFetchRef.current = now
    isFetchingRef.current = true
    try {
      setLoading(true)
      setError(null)

      // Load dashboard data first (always fetch unless phase map is fresh)
      // Add timeout to prevent hanging
      const dashboardPromise = loadDashboardData(forceRefresh)
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Dashboard data loading timeout after 30 seconds')), 30000)
      )
      
      const dashboard = await Promise.race([dashboardPromise, timeoutPromise])
      const data = dashboard || {}
      // Phase map comes from CycleContext (single /cycles/phase-map call). Only key from phase_map if we have data; otherwise keep existing phaseMap
      const dataArray = data.phase_map || []
      let keyedMap = {}
      dataArray.forEach(item => {
        const d = item?.date
        if (!d) return
        const dateKey = typeof d === 'string' ? d.slice(0, 10) : (d.toISOString?.()?.slice(0, 10) || String(d).slice(0, 10))
        if (dateKey.length === 10) keyedMap[dateKey] = item
      })
      if (keyedMap && Object.keys(keyedMap).length > 0) lastPhaseMapFetchedAtRef.current = Date.now()
      setDashboardData(prev => {
        const next = { ...(prev || {}), ...data, phaseMapFetchedAt: lastPhaseMapFetchedAtRef.current }
        next.phaseMap = (keyedMap && Object.keys(keyedMap).length > 0) ? keyedMap : (prev?.phaseMap || {})
        return next
      })
      setLoading(false)

      // Get phase-day ID from dashboard
      const phaseDayId = dashboard?.currentPhase?.phase_day_id || 
                         dashboard?.currentPhase?.id

      if (phaseDayId) {
        const language = getUserLanguage()
        const needsRefetch = forceRefresh || shouldRefetch(phaseDayId, language)

        if (needsRefetch) {
          setLoadingWellness(true)
          console.log(`🔄 Loading wellness data (needsRefetch=true) for phaseDayId: ${phaseDayId}`)
          // Load wellness data with favorite category first (for immediate display)
          const wellness = await loadWellnessData(phaseDayId, language, false)
          console.log(`📊 Wellness data loaded:`, wellness ? {
            hasHormones: !!wellness.hormones,
            hasNutrition: !!wellness.nutrition,
            nutritionRecipes: wellness.nutrition?.recipes?.length || 0,
            hasExercises: !!wellness.exercises,
            exerciseCount: wellness.exercises?.exercises?.length || 0
          } : 'null')
          setWellnessData(wellness || null)
          setLoadingWellness(false)
          
          // Start background preloading of all categories/cuisines (only if we have data)
          if (wellness) {
            console.log('🚀 Starting background preload of all wellness data...')
            preloadAllWellnessData(phaseDayId, language)
          }
        } else {
          // Use cached data
          const cached = getCachedWellnessData(phaseDayId)
          if (cached) {
            console.log('Using cached wellness data')
            setWellnessData(cached)
            setLoadingWellness(false)
            
            // If cache doesn't have all preloaded data, preload in background
            if (!cached.allPreloaded) {
              console.log('🚀 Cache missing preloaded data, starting background preload...')
              preloadAllWellnessData(phaseDayId, language)
            }
          } else {
            // Cache miss, load fresh
            setLoadingWellness(true)
            console.log(`🔄 Loading wellness data (cache miss) for phaseDayId: ${phaseDayId}`)
            const wellness = await loadWellnessData(phaseDayId, language, false)
            console.log(`📊 Wellness data loaded (cache miss):`, wellness ? {
              hasHormones: !!wellness.hormones,
              hasNutrition: !!wellness.nutrition,
              nutritionRecipes: wellness.nutrition?.recipes?.length || 0,
              hasExercises: !!wellness.exercises,
              exerciseCount: wellness.exercises?.exercises?.length || 0
            } : 'null')
            setWellnessData(wellness || null)
            setLoadingWellness(false)
            
            // Start background preloading of all categories/cuisines (only if we have data)
            if (wellness) {
              console.log('🚀 Starting background preload of all wellness data...')
              preloadAllWellnessData(phaseDayId, language)
            }
          }
        }
      } else {
        setLoadingWellness(false)
      }

      const today = new Date().toISOString().split('T')[0]
      setLastLoadDate(today)
      localStorage.setItem('period_gpt_last_load_date', today)
    } catch (err) {
      console.error('Error loading data:', err)
      setError(err.message || 'Failed to load data')
      // Always set loading to false, even on error
      setLoading(false)
      setLoadingWellness(false)
      // Set empty data structure to prevent rendering issues
      setDashboardData(prev => prev || { currentPhase: null, phaseMap: null, periodLogs: null })
    } finally {
      isFetchingRef.current = false
    }
  }, []) // Empty deps - stable function

  // Load data on mount and check date change
  useEffect(() => {
    let isMounted = true
    let interval = null
    
    const loadInitialData = async () => {
      if (!isMounted) return
      
      // Only load data if user is authenticated
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.log('No auth token, skipping data load')
        // Safety: clear any lingering session data when auth is missing/expired
        try {
          sessionStorage.clear()
        } catch {
          // ignore
        }
        setLoading(false)
        return
      }
      
      const today = new Date().toISOString().split('T')[0]
      
      // Check if date changed
      if (lastLoadDate && lastLoadDate !== today) {
        console.log('Date changed, forcing refresh')
        await checkAndLoadData(true) // Force refresh if date changed
      } else {
        await checkAndLoadData(false)
      }
    }
    
    loadInitialData()
    
    // Set up interval to check for date change every minute
    interval = setInterval(() => {
      if (!isMounted) return
      
      // CRITICAL: Check for auth token before making any API calls
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.log('No auth token, skipping interval data check')
        return
      }
      
      const currentDate = new Date().toISOString().split('T')[0]
      const storedLastLoadDate = localStorage.getItem('period_gpt_last_load_date')
      if (storedLastLoadDate && storedLastLoadDate !== currentDate) {
        console.log('Date changed (detected via interval), forcing refresh')
        checkAndLoadData(true)
      }
    }, 60000) // Check every minute
    
    return () => {
      isMounted = false
      if (interval) clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount - checkAndLoadData is stable (useCallback with empty deps)

  // Listen for auth success (login/register) - reset phase map so dashboard gets fresh data
  useEffect(() => {
    const handleAuthSuccess = () => {
      let userId = null
      try {
        const raw = localStorage.getItem('user')
        if (raw) {
          const parsed = JSON.parse(raw)
          userId = parsed?.id || null
        }
      } catch {
        // ignore JSON errors
      }
      console.log(`DEBUG: Initializing DataContext for User ${userId || '(unknown)'}`)
      setDashboardData(prev => (prev ? { ...prev, phaseMap: {} } : null))
    }
    window.addEventListener('authSuccess', handleAuthSuccess)
    return () => window.removeEventListener('authSuccess', handleAuthSuccess)
  }, [])

  // Listen for period log events (clear cache and reload)
  useEffect(() => {
    const handlePeriodLogged = () => {
      // CRITICAL: Check for auth token before making any API calls
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.log('No auth token, skipping period logged event handler')
        return
      }
      
      console.log('Period logged, clearing cache and refreshing all data...')
      clearCache()
      checkAndLoadData(true)
    }

    window.addEventListener('periodLogged', handlePeriodLogged)
    return () => {
      window.removeEventListener('periodLogged', handlePeriodLogged)
    }
  }, [checkAndLoadData])

  // Listen for calendar reset/refresh so phase map stays in sync (single source of truth)
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    const handleResetAllCycles = () => {
      setDashboardData(prev => (prev ? { ...prev, phaseMap: {} } : null))
    }
    const handleResetLastPeriod = () => { checkAndLoadData(true) }
    const handleCalendarRefresh = () => { checkAndLoadData(true) }
    window.addEventListener('resetAllCycles', handleResetAllCycles)
    window.addEventListener('resetLastPeriod', handleResetLastPeriod)
    window.addEventListener('calendarRefresh', handleCalendarRefresh)
    return () => {
      window.removeEventListener('resetAllCycles', handleResetAllCycles)
      window.removeEventListener('resetLastPeriod', handleResetLastPeriod)
      window.removeEventListener('calendarRefresh', handleCalendarRefresh)
    }
  }, [checkAndLoadData])

  // Listen for language changes (clear cache and reload)
  useEffect(() => {
    const handleLanguageChange = () => {
      // CRITICAL: Check for auth token before making any API calls
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.log('No auth token, skipping language changed event handler')
        return
      }
      
      console.log('Language changed, clearing cache and refreshing all data...')
      clearCache()
      checkAndLoadData(true)
    }

    window.addEventListener('languageChanged', handleLanguageChange)
    return () => {
      window.removeEventListener('languageChanged', handleLanguageChange)
    }
  }, [checkAndLoadData])

  // Manual refresh function
  const refreshData = useCallback(() => {
    clearCache()
    checkAndLoadData(true)
  }, [checkAndLoadData])

  // Allow CycleContext (or any consumer) to update phase map so Dashboard/CycleHistory can use it
  const updatePhaseMap = useCallback((phaseMap) => {
    lastPhaseMapFetchedAtRef.current = Date.now()
    setDashboardData(prev => (prev ? { ...prev, phaseMap: phaseMap || {}, phaseMapFetchedAt: lastPhaseMapFetchedAtRef.current } : { phaseMap: phaseMap || {}, phaseMapFetchedAt: lastPhaseMapFetchedAtRef.current }))
  }, [])

  // Store allCycles from prefetch so CycleHistory can use cycle_data_json for past cycles without calling /periods/stats
  const updateCycleHistoryData = useCallback((stats) => {
    if (!stats?.allCycles) return
    setDashboardData(prev => (prev ? { ...prev, allCycles: stats.allCycles, cycleStats: stats } : { allCycles: stats.allCycles, cycleStats: stats }))
  }, [])

  // Ensure calendar always gets a keyed phaseMap: use phaseMap when present, else derive from phase_map array.
  // Fixes race where dashboardData.phaseMap was empty when PeriodCalendar first read context.
  const effectiveDashboardData = useMemo(() => {
    if (!dashboardData) return null
    const pm = dashboardData.phaseMap
    if (pm && typeof pm === 'object' && Object.keys(pm).length > 0) return dashboardData
    const arr = dashboardData.phase_map
    if (Array.isArray(arr) && arr.length > 0) {
      const keyed = {}
      arr.forEach(item => {
        const d = item?.date
        if (!d) return
        const dateKey = typeof d === 'string' ? d.slice(0, 10) : (d.toISOString?.()?.slice(0, 10) || String(d).slice(0, 10))
        if (dateKey.length === 10) keyed[dateKey] = item
      })
      return { ...dashboardData, phaseMap: keyed }
    }
    return dashboardData
  }, [dashboardData])

  const value = {
    dashboardData: effectiveDashboardData,
    wellnessData,
    loading,
    loadingWellness,
    error,
    refreshData,
    updatePhaseMap,
    updateCycleHistoryData
  }

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

