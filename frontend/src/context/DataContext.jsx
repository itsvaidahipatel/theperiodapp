import { createContext, useContext, useState, useEffect, useCallback } from 'react'
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

  // Check if we need to refetch (date changed or cache invalid)
  const checkAndLoadData = useCallback(async (forceRefresh = false) => {
    try {
      setLoading(true)
      setError(null)

      // Load dashboard data first (always fetch, no cache)
      // Add timeout to prevent hanging
      const dashboardPromise = loadDashboardData()
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Dashboard data loading timeout after 30 seconds')), 30000)
      )
      
      const dashboard = await Promise.race([dashboardPromise, timeoutPromise])
      setDashboardData(dashboard)
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

  // Allow PeriodCalendar (or any consumer) to update phase map so Dashboard can show todayPhase
  const updatePhaseMap = useCallback((phaseMap) => {
    setDashboardData(prev => (prev ? { ...prev, phaseMap: phaseMap || {} } : { phaseMap: phaseMap || {} }))
  }, [])

  const value = {
    dashboardData,
    wellnessData,
    loading,
    loadingWellness,
    error,
    refreshData,
    updatePhaseMap
  }

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

