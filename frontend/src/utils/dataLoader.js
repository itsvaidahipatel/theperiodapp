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
    // Get current phase first (with timeout)
    const currentPhasePromise = getCurrentPhase().catch(() => null)
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Timeout')), 15000)
    )
    const currentPhase = await Promise.race([currentPhasePromise, timeoutPromise]).catch(() => null)
    
    // Get phase map for calendar (3 months: previous, current, next)
    let phaseMap = {}
    try {
      const today = new Date()
      const startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      const endDate = new Date(today.getFullYear(), today.getMonth() + 2, 0)
      
      const startDateStr = startDate.toISOString().split('T')[0]
      const endDateStr = endDate.toISOString().split('T')[0]
      
      // Add timeout to prevent hanging
      const phaseMapPromise = getPhaseMap(startDateStr, endDateStr)
      const phaseMapTimeout = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Phase map timeout')), 30000)
      )
      const phaseMapResponse = await Promise.race([phaseMapPromise, phaseMapTimeout]).catch((err) => {
        console.warn('Phase map request timed out or failed:', err)
        return { phase_map: [] }
      })
      console.log('📅 Phase map response in dataLoader:', {
        hasPhaseMap: !!phaseMapResponse?.phase_map,
        length: phaseMapResponse?.phase_map?.length || 0,
        first3: phaseMapResponse?.phase_map?.slice(0, 3) || []
      })
      if (phaseMapResponse?.phase_map && Array.isArray(phaseMapResponse.phase_map)) {
        phaseMapResponse.phase_map.forEach((item) => {
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
            
            phaseMap[dateKey] = item
          }
        })
        console.log('✅ Processed phase map with', Object.keys(phaseMap).length, 'dates')
      } else {
        console.warn('⚠️ Phase map response is not valid:', phaseMapResponse)
      }
    } catch (mapError) {
      console.log('No phase map data available yet:', mapError)
    }
    
    // Get period logs (with timeout)
    const periodLogsPromise = getPeriodLogs().catch(() => null)
    const periodLogsTimeout = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Period logs timeout')), 10000)
    )
    const periodLogs = await Promise.race([periodLogsPromise, periodLogsTimeout]).catch(() => null)
    
    return {
      currentPhase: currentPhase || null,
      phaseMap: Object.keys(phaseMap).length > 0 ? phaseMap : null,
      periodLogs: periodLogs || null
    }
  } catch (error) {
    console.error('Error loading dashboard data:', error)
    return null
  }
}

/**
 * Load all wellness data (hormones, nutrition, exercises) for a phase-day ID
 * Now preloads all categories/cuisines for exercises and nutrition
 */
export const loadWellnessData = async (phaseDayId = null, language = null, preloadAll = true) => {
  const lang = language || getUserLanguage()
  
  // Check cache first
  if (phaseDayId && !preloadAll) {
    const cached = getCachedData(phaseDayId, lang)
    if (cached) {
      console.log('Using cached wellness data')
      return cached
    }
  }
  
  try {
    // Load hormones (no categories)
    const hormonesPromise = getHormonesData(phaseDayId).catch((err) => {
      console.error('Error fetching hormones:', err)
      return null
    })
    
    // Get user preferences
    let favoriteCuisine = 'international'
    let favoriteExercise = 'mind'
    
    try {
      const userData = localStorage.getItem('user')
      if (userData) {
        const user = JSON.parse(userData)
        const rawCuisine = user.favorite_cuisine || 'international'
        // Normalize to standard cuisine names (handles legacy values)
        const normalized = rawCuisine.toLowerCase()
        if (normalized === 'gujarati' || normalized.includes('gujarati') || normalized.includes('kathiya')) {
          favoriteCuisine = 'gujarati'
        } else {
          favoriteCuisine = rawCuisine
        }
        const fav = user.favorite_exercise || ''
        // Map to database category
        if (fav === 'Yoga' || fav === 'Mind' || fav === 'Stretching') favoriteExercise = 'mind'
        else if (fav === 'Cardio') favoriteExercise = 'cardio'
        else if (fav === 'Strength') favoriteExercise = 'strength'
      }
    } catch {}
    
    // All cuisines and categories
    const allCuisines = ['international', 'south_indian', 'north_indian', 'gujarati']
    const allCategories = ['mind', 'cardio', 'strength']
    
    // Load favorite first (always load favorite for immediate display)
    console.log(`📥 Loading wellness data for phaseDayId: ${phaseDayId}, language: ${lang}`)
    console.log(`📥 Favorite cuisine: ${favoriteCuisine}, Favorite exercise: ${favoriteExercise}`)
    
    const [hormones, nutrition, exercises] = await Promise.all([
      hormonesPromise,
      getNutritionData(phaseDayId, lang, favoriteCuisine)
        .then(data => {
          console.log(`✅ Nutrition API response for ${favoriteCuisine}:`, data)
          return data
        })
        .catch((err) => {
          console.error('❌ Error fetching nutrition:', err)
          return null
        }),
      getExerciseData(phaseDayId, lang, favoriteExercise)
        .then(data => {
          console.log(`✅ Exercise API response for ${favoriteExercise}:`, data)
          return data
        })
        .catch((err) => {
          console.error('❌ Error fetching exercises:', err)
          return null
        })
    ])
    
    console.log(`📦 Loaded wellness data:`, {
      hormones: hormones ? 'has data' : 'null',
      nutrition: nutrition ? (nutrition.recipes ? `${nutrition.recipes.length} recipes` : 'no recipes') : 'null',
      exercises: exercises ? (exercises.exercises ? `${exercises.exercises.length} exercises` : 'no exercises') : 'null'
    })
    
    // If preloadAll is true, start background loading of all other categories/cuisines
    if (preloadAll) {
      // Load all others in background (don't wait)
      const otherNutritionPromises = allCuisines
        .filter(c => c !== favoriteCuisine)
        .map(cuisine => 
          getNutritionData(phaseDayId, lang, cuisine)
            .then(data => ({ type: 'nutrition', cuisine, data }))
            .catch(() => ({ type: 'nutrition', cuisine, data: null }))
        )
      
      const otherExercisePromises = allCategories
        .filter(c => c !== favoriteExercise)
        .map(category => 
          getExerciseData(phaseDayId, lang, category)
            .then(data => ({ type: 'exercise', category, data }))
            .catch(() => ({ type: 'exercise', category, data: null }))
        )
      
      // Load all others in parallel (background, don't block)
      Promise.all([...otherNutritionPromises, ...otherExercisePromises])
        .then((results) => {
          console.log('✅ Background preloading completed for all categories/cuisines')
        })
        .catch((err) => {
          console.error('Error in background preloading:', err)
        })
    }
    
    // Normalize hormones data structure - only if we have actual data
    let normalizedHormones = null
    if (hormones) {
      // If hormones doesn't have 'today' field but has the data directly, wrap it
      if (!hormones.today && !hormones.history && !hormones.message) {
        normalizedHormones = {
          today: hormones,
          phase_day_id: hormones.phase_day_id || phaseDayId
        }
      } else if (hormones.message && !hormones.today) {
        // If hormones has a message (no data), preserve the message
        normalizedHormones = {
          message: hormones.message,
          phase_day_id: hormones.phase_day_id || phaseDayId
        }
      } else {
        normalizedHormones = hormones
      }
    }
    
    // Normalize nutrition and exercises - convert empty arrays to null
    let normalizedNutrition = null
    if (nutrition && nutrition.recipes) {
      if (Array.isArray(nutrition.recipes) && nutrition.recipes.length > 0) {
        normalizedNutrition = nutrition
      } else {
        // Empty array or no recipes - set to null
        normalizedNutrition = null
      }
    }
    
    let normalizedExercises = null
    if (exercises && exercises.exercises) {
      if (Array.isArray(exercises.exercises) && exercises.exercises.length > 0) {
        normalizedExercises = exercises
      } else {
        // Empty array or no exercises - set to null
        normalizedExercises = null
      }
    }
    
    const wellnessData = {
      hormones: normalizedHormones,
      nutrition: normalizedNutrition,  // null if no recipes, or {recipes: [...], wholefoods: []} if has recipes
      exercises: normalizedExercises,   // null if no exercises, or {exercises: [...]} if has exercises
      phaseDayId: phaseDayId || normalizedHormones?.phase_day_id || hormones?.phase_day_id,
      language: lang,
      timestamp: Date.now()
    }
    
    console.log(`💾 Final wellnessData structure:`, {
      hasHormones: !!wellnessData.hormones,
      hasNutrition: !!wellnessData.nutrition,
      nutritionRecipes: wellnessData.nutrition?.recipes?.length || 0,
      hasExercises: !!wellnessData.exercises,
      exerciseCount: wellnessData.exercises?.exercises?.length || 0,
      phaseDayId: wellnessData.phaseDayId
    })
    
    // Cache the data only if we have a phaseDayId
    if (wellnessData.phaseDayId) {
      setCachedData(wellnessData.phaseDayId, lang, wellnessData)
      console.log(`✅ Cached wellness data for phaseDayId: ${wellnessData.phaseDayId}`)
    } else {
      console.warn(`⚠️ Cannot cache wellness data - no phaseDayId`)
    }
    
    return wellnessData
  } catch (error) {
    console.error('Error loading wellness data:', error)
    return null
  }
}

/**
 * Preload all wellness data for all categories/cuisines
 * Called after dashboard loads to preload everything in background
 */
export const preloadAllWellnessData = async (phaseDayId = null, language = null) => {
  if (!phaseDayId) return
  
  const lang = language || getUserLanguage()
  console.log('🔄 Starting background preload of all wellness data...')
  
  try {
    // Get user preferences
    let favoriteCuisine = 'international'
    let favoriteExercise = 'mind'
    
    try {
      const userData = localStorage.getItem('user')
      if (userData) {
        const user = JSON.parse(userData)
        const rawCuisine = user.favorite_cuisine || 'international'
        // Normalize to standard cuisine names (handles legacy values)
        const normalized = rawCuisine.toLowerCase()
        if (normalized === 'gujarati' || normalized.includes('gujarati') || normalized.includes('kathiya')) {
          favoriteCuisine = 'gujarati'
        } else {
          favoriteCuisine = rawCuisine
        }
        const fav = user.favorite_exercise || ''
        if (fav === 'Yoga' || fav === 'Mind' || fav === 'Stretching') favoriteExercise = 'mind'
        else if (fav === 'Cardio') favoriteExercise = 'cardio'
        else if (fav === 'Strength') favoriteExercise = 'strength'
      }
    } catch {}
    
    const allCuisines = ['international', 'south_indian', 'north_indian', 'gujarati']
    const allCategories = ['mind', 'cardio', 'strength']
    
    // Load all in parallel (background, don't block)
    const promises = []
    
    // All nutrition cuisines
    allCuisines.forEach(cuisine => {
      promises.push(
        getNutritionData(phaseDayId, lang, cuisine)
          .then(data => ({ type: 'nutrition', cuisine, data }))
          .catch(err => {
            console.error(`Error preloading nutrition for ${cuisine}:`, err)
            return { type: 'nutrition', cuisine, data: null }
          })
      )
    })
    
    // All exercise categories
    allCategories.forEach(category => {
      promises.push(
        getExerciseData(phaseDayId, lang, category)
          .then(data => ({ type: 'exercise', category, data }))
          .catch(err => {
            console.error(`Error preloading exercises for ${category}:`, err)
            return { type: 'exercise', category, data: null }
          })
      )
    })
    
    // Execute all in background
    Promise.all(promises)
      .then((results) => {
        console.log('✅ Background preloading completed:', results.length, 'items')
        // Update cache with all preloaded data
        const cached = getCachedData(phaseDayId, lang)
        if (cached) {
          // Merge preloaded data into cache (only store non-null data)
          const nutritionByCuisine = {}
          const exercisesByCategory = {}
          
          results.forEach(result => {
            if (result.type === 'nutrition' && result.data) {
              nutritionByCuisine[result.cuisine] = result.data
            } else if (result.type === 'exercise' && result.data) {
              exercisesByCategory[result.category] = result.data
            }
          })
          
          // Update cache with all preloaded data
          const updatedCache = {
            ...cached,
            nutritionByCuisine,
            exercisesByCategory,
            allPreloaded: true,
            preloadTimestamp: Date.now()
          }
          
          setCachedData(phaseDayId, lang, updatedCache)
        }
      })
      .catch((err) => {
        console.error('Error in background preloading:', err)
      })
  } catch (error) {
    console.error('Error starting background preload:', error)
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
 * Get preloaded nutrition data for a specific cuisine
 */
export const getPreloadedNutritionData = (phaseDayId = null, cuisine = null) => {
  if (!phaseDayId || !cuisine) return null
  
  const language = getUserLanguage()
  const cached = getCachedData(phaseDayId, language)
  
  if (cached && cached.nutritionByCuisine && cached.nutritionByCuisine[cuisine]) {
    return cached.nutritionByCuisine[cuisine]
  }
  
  return null
}

/**
 * Get preloaded exercise data for a specific category
 */
export const getPreloadedExerciseData = (phaseDayId = null, category = null) => {
  if (!phaseDayId || !category) return null
  
  const language = getUserLanguage()
  const cached = getCachedData(phaseDayId, language)
  
  if (cached && cached.exercisesByCategory && cached.exercisesByCategory[category]) {
    return cached.exercisesByCategory[category]
  }
  
  return null
}

/**
 * Clear cache and refetch (called when period is logged or language changes)
 */
export const refreshAllData = async (onDashboardLoaded = null, onWellnessLoaded = null) => {
  clearCache()
  return loadAllData(onDashboardLoaded, onWellnessLoaded)
}

