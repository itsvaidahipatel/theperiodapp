/**
 * Data caching utility for PeriodCycle.AI
 * Caches dashboard, hormones, nutrition, and exercises data
 * Cache key: {date}_{phase_day_id}_{language}
 */

const CACHE_PREFIX = 'period_gpt_cache_'
const CACHE_DATE_KEY = 'period_gpt_cache_date'
const CACHE_EXPIRY_HOURS = 24 // Cache expires after 24 hours

/**
 * Generate cache key for a specific date's data
 * Cache is date-specific - only valid for the date it was cached
 */
const getCacheKey = (date, phaseDayId, language) => {
  return `${CACHE_PREFIX}${date}_${phaseDayId}_${language}`
}

/**
 * Get today's date in YYYY-MM-DD format
 */
const getTodayDate = () => {
  return new Date().toISOString().split('T')[0]
}

/**
 * Check if cache is valid (same date and not expired)
 */
const isCacheValid = (cachedDate) => {
  if (!cachedDate) return false
  
  const today = getTodayDate()
  if (cachedDate !== today) return false
  
  // Check if cache is not too old (within 24 hours)
  const cacheTime = localStorage.getItem(`${CACHE_PREFIX}timestamp`)
  if (cacheTime) {
    const cacheAge = Date.now() - parseInt(cacheTime)
    const maxAge = CACHE_EXPIRY_HOURS * 60 * 60 * 1000 // 24 hours in ms
    if (cacheAge > maxAge) return false
  }
  
  return true
}

/**
 * Get cached data for a specific date
 * Cache is date-specific - only returns data for the requested date
 */
export const getCachedData = (phaseDayId, language, date = null) => {
  try {
    const targetDate = date || getTodayDate()
    const cachedDate = localStorage.getItem(CACHE_DATE_KEY)
    
    // Check if cache is for the target date and valid
    if (cachedDate !== targetDate || !isCacheValid(cachedDate)) {
      return null
    }
    
    const cacheKey = getCacheKey(targetDate, phaseDayId, language)
    const cached = localStorage.getItem(cacheKey)
    
    if (cached) {
      return JSON.parse(cached)
    }
    
    return null
  } catch (error) {
    console.error('Error reading cache:', error)
    return null
  }
}

/**
 * Save data to cache for a specific date
 * Cache is date-specific - only valid for the date it was saved
 */
export const setCachedData = (phaseDayId, language, data, date = null) => {
  try {
    const targetDate = date || getTodayDate()
    const cacheKey = getCacheKey(targetDate, phaseDayId, language)
    
    // Only cache if we have actual data (not null or empty structures)
    if (!data || (data.hormones === null && data.nutrition === null && data.exercises === null)) {
      console.log('Skipping cache - no data to cache')
      return
    }
    
    localStorage.setItem(CACHE_DATE_KEY, targetDate)
    localStorage.setItem(cacheKey, JSON.stringify(data))
    localStorage.setItem(`${CACHE_PREFIX}timestamp`, Date.now().toString())
    
    console.log('Data cached successfully for date:', targetDate, cacheKey)
  } catch (error) {
    console.error('Error saving cache:', error)
    // If storage is full, try to clear old cache
    if (error.name === 'QuotaExceededError') {
      clearOldCache()
    }
  }
}

/**
 * Clear old cache entries
 */
const clearOldCache = () => {
  try {
    const keys = Object.keys(localStorage)
    keys.forEach(key => {
      if (key.startsWith(CACHE_PREFIX) && key !== `${CACHE_PREFIX}timestamp`) {
        localStorage.removeItem(key)
      }
    })
    localStorage.removeItem(CACHE_DATE_KEY)
  } catch (error) {
    console.error('Error clearing old cache:', error)
  }
}

/**
 * Clear all cache (called when period is logged or language changes)
 */
export const clearCache = () => {
  try {
    clearOldCache()
    localStorage.removeItem(`${CACHE_PREFIX}timestamp`)
    console.log('Cache cleared')
  } catch (error) {
    console.error('Error clearing cache:', error)
  }
}

/**
 * Check if we need to refetch data
 * Returns true if:
 * - No cache exists
 * - Cache is for a different date
 * - Cache is expired
 */
export const shouldRefetch = (phaseDayId, language) => {
  const cached = getCachedData(phaseDayId, language)
  return cached === null
}

/**
 * Get cache info for debugging
 */
export const getCacheInfo = () => {
  const cachedDate = localStorage.getItem(CACHE_DATE_KEY)
  const timestamp = localStorage.getItem(`${CACHE_PREFIX}timestamp`)
  
  return {
    cachedDate,
    timestamp: timestamp ? new Date(parseInt(timestamp)).toISOString() : null,
    isValid: isCacheValid(cachedDate)
  }
}

