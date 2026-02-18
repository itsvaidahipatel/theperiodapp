/**
 * Data loader utility
 * Loads all required data (dashboard, hormones, nutrition, exercises) in sequence
 */

import { 
  getCurrentPhase, 
  getPeriodLogs,
  getPhaseMap,
  getHormonesData,
  getNutritionData,
  getExerciseData
} from './api'
import { getUserLanguage } from './userPreferences'
import { getCachedData, setCachedData, shouldRefetch, clearCache } from './dataCache'

/**
 * Load dashboard data (single source of truth for phase map).
 * Fetches 3 months past to 6 months future once so calendar shows colors instantly.
 * @param {boolean} forceRefresh - If true, getPhaseMap is called with force_recalculate
 */
export const loadDashboardData = async (forceRefresh = false) => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    return { currentPhase: null, phaseMap: null, periodLogs: null }
  }

  try {
    const now = new Date()
    // Request a full month range (start_date to end_date) for calendar display - at least current month
    const start = new Date(now.getFullYear(), now.getMonth() - 3, 1)
    const end = new Date(now.getFullYear(), now.getMonth() + 6 + 1, 0)
    const startDate = start.toISOString().slice(0, 10)
    let endDate = end.toISOString().slice(0, 10)
    // Ensure we never request a single day (full month required)
    if (startDate === endDate) {
      const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0)
      endDate = endOfMonth.toISOString().slice(0, 10)
    }

    const [currentPhase, periodLogs, phaseMapResponse] = await Promise.all([
      getCurrentPhase().catch(() => null),
      getPeriodLogs().catch(() => null),
      getPhaseMap(startDate, endDate, forceRefresh).catch(() => null)
    ])

    // Pass raw array to DataContext so it can save under key 'phaseMap' with consistent mapping
    const phase_map = (phaseMapResponse?.phase_map && Array.isArray(phaseMapResponse.phase_map))
      ? phaseMapResponse.phase_map
      : []

    // #region agent log
    const firstItem = phase_map[0]
    fetch('http://127.0.0.1:7242/ingest/6e7c83a7-9704-42b4-bb73-f91cceedfc17',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'dataLoader.js:loadDashboardData',message:'phase_map from API',data:{length:phase_map.length,firstDate:firstItem?.date,firstPhase:firstItem?.phase,firstPhaseDayId:firstItem?.phase_day_id},timestamp:Date.now(),hypothesisId:'A,B,D'})}).catch(()=>{});
    // #endregion

    return {
      currentPhase: currentPhase || null,
      phase_map,
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
  // CRITICAL: Check for auth token before making any protected API calls
  const token = localStorage.getItem('access_token')
  if (!token) {
    console.log('No auth token, skipping wellness data load')
    return null
  }

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
  // CRITICAL: Check for auth token before making any protected API calls
  const token = localStorage.getItem('access_token')
  if (!token) {
    console.log('No auth token, skipping wellness data preload')
    return
  }

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

