/**
 * Data loader utility
 * Loads all required data (dashboard, hormones, nutrition, exercises) in sequence
 */

import { 
  getCurrentPhase, 
  getPhaseMap, 
  getPeriodLogs,
  getHormonesData,
  getNutritionData,
  getExerciseData
} from './api'
import { getUserLanguage } from './userPreferences'
import { getCachedData, setCachedData, shouldRefetch, clearCache } from './dataCache'

/**
 * Load dashboard data
 */
export const loadDashboardData = async () => {
  try {
    // Get current phase first
    const currentPhase = await getCurrentPhase().catch(() => null)
    
    // Get phase map for calendar (3 months: previous, current, next)
    let phaseMap = {}
    try {
      const today = new Date()
      const startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      const endDate = new Date(today.getFullYear(), today.getMonth() + 2, 0)
      
      const startDateStr = startDate.toISOString().split('T')[0]
      const endDateStr = endDate.toISOString().split('T')[0]
      
      const phaseMapResponse = await getPhaseMap(startDateStr, endDateStr)
      if (phaseMapResponse?.phase_map) {
        phaseMapResponse.phase_map.forEach((item) => {
          phaseMap[item.date] = item
        })
      }
    } catch (mapError) {
      console.log('No phase map data available yet:', mapError)
    }
    
    // Get period logs
    const periodLogs = await getPeriodLogs().catch(() => [])
    
    return {
      currentPhase,
      phaseMap,
      periodLogs
    }
  } catch (error) {
    console.error('Error loading dashboard data:', error)
    return {
      currentPhase: null,
      phaseMap: {},
      periodLogs: []
    }
  }
}

/**
 * Load all wellness data (hormones, nutrition, exercises) for a phase-day ID
 */
export const loadWellnessData = async (phaseDayId = null, language = null) => {
  const lang = language || getUserLanguage()
  
  // Check cache first
  if (phaseDayId) {
    const cached = getCachedData(phaseDayId, lang)
    if (cached) {
      console.log('Using cached wellness data')
      return cached
    }
  }
  
  try {
    // Load all data in parallel
    const [hormones, nutrition, exercises] = await Promise.all([
      getHormonesData(phaseDayId).catch((err) => {
        console.error('Error fetching hormones:', err)
        return { today: null, history: [], phase_day_id: phaseDayId }
      }),
      getNutritionData(phaseDayId, lang, null).catch((err) => {
        console.error('Error fetching nutrition:', err)
        return { recipes: [] }
      }),
      getExerciseData(phaseDayId, lang, null).catch((err) => {
        console.error('Error fetching exercises:', err)
        return { exercises: [] }
      })
    ])
    
    // Normalize hormones data structure
    let normalizedHormones = hormones
    // If hormones doesn't have 'today' field but has the data directly, wrap it
    if (hormones && !hormones.today && !hormones.history && !hormones.message) {
      normalizedHormones = {
        today: hormones,
        history: [],
        phase_day_id: hormones.phase_day_id || phaseDayId
      }
    }
    // If hormones has a message (no data), ensure it has the right structure
    if (hormones && hormones.message && !hormones.today) {
      normalizedHormones = {
        today: null,
        history: [],
        phase_day_id: hormones.phase_day_id || phaseDayId,
        message: hormones.message
      }
    }
    
    const wellnessData = {
      hormones: normalizedHormones,
      nutrition,
      exercises,
      phaseDayId: phaseDayId || normalizedHormones?.phase_day_id || hormones?.phase_day_id,
      language: lang,
      timestamp: Date.now()
    }
    
    // Cache the data
    if (wellnessData.phaseDayId) {
      setCachedData(wellnessData.phaseDayId, lang, wellnessData)
    }
    
    return wellnessData
  } catch (error) {
    console.error('Error loading wellness data:', error)
    return {
      hormones: { today: null, history: [] },
      nutrition: { recipes: [] },
      exercises: { exercises: [] },
      phaseDayId,
      language: lang
    }
  }
}

/**
 * Load all data (dashboard + wellness) in sequence
 * Dashboard loads first, then wellness data loads in background
 */
export const loadAllData = async (onDashboardLoaded = null, onWellnessLoaded = null) => {
  // Load dashboard data first (for immediate display)
  const dashboardData = await loadDashboardData()
  
  if (onDashboardLoaded) {
    onDashboardLoaded(dashboardData)
  }
  
  // Get phase-day ID from dashboard data
  const phaseDayId = dashboardData.currentPhase?.phase_day_id || 
                     dashboardData.currentPhase?.id || 
                     null
  
  // Load wellness data in background
  if (phaseDayId) {
    const wellnessData = await loadWellnessData(phaseDayId)
    
    if (onWellnessLoaded) {
      onWellnessLoaded(wellnessData)
    }
    
    return {
      dashboard: dashboardData,
      wellness: wellnessData
    }
  }
  
  return {
    dashboard: dashboardData,
    wellness: null
  }
}

/**
 * Get cached wellness data if available
 */
export const getCachedWellnessData = (phaseDayId = null) => {
  if (!phaseDayId) return null
  
  const language = getUserLanguage()
  return getCachedData(phaseDayId, language)
}

/**
 * Clear cache and refetch (called when period is logged or language changes)
 */
export const refreshAllData = async (onDashboardLoaded = null, onWellnessLoaded = null) => {
  clearCache()
  return loadAllData(onDashboardLoaded, onWellnessLoaded)
}

