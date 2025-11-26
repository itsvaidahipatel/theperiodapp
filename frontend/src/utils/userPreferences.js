/**
 * Global user preferences utility
 * Gets user preferences from localStorage
 */

/**
 * Get user's language preference
 */
export const getUserLanguage = () => {
  try {
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      return user.language || 'en'
    }
  } catch (error) {
    console.error('Error getting user language:', error)
  }
  return 'en' // Default to English
}

/**
 * Get user's favorite cuisine
 */
export const getFavoriteCuisine = () => {
  try {
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      const cuisine = user.favorite_cuisine || 'international'
      // Normalize to standard cuisine names (handles legacy values)
      const normalized = cuisine.toLowerCase()
      if (normalized === 'gujarati' || normalized.includes('gujarati') || normalized.includes('kathiya')) {
        return 'gujarati'
      }
      return cuisine
    }
  } catch (error) {
    console.error('Error getting favorite cuisine:', error)
  }
  return 'international' // Default
}

/**
 * Get user's favorite exercise category
 */
export const getFavoriteExercise = () => {
  try {
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      return user.favorite_exercise || ''
    }
  } catch (error) {
    console.error('Error getting favorite exercise:', error)
  }
  return '' // Default
}

/**
 * Get user's last period date
 */
export const getLastPeriodDate = () => {
  try {
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      return user.last_period_date || null
    }
  } catch (error) {
    console.error('Error getting last period date:', error)
  }
  return null
}

/**
 * Get user's cycle length
 */
export const getCycleLength = () => {
  try {
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      return user.cycle_length || 28
    }
  } catch (error) {
    console.error('Error getting cycle length:', error)
  }
  return 28 // Default
}

/**
 * Get user's name
 */
export const getUserName = () => {
  try {
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      return user.name || ''
    }
  } catch (error) {
    console.error('Error getting user name:', error)
  }
  return ''
}

/**
 * Get localized text from a multilingual object
 * @param {object|string} data - The multilingual data object or plain string
 * @param {string} language - The language code (en, hi, gu) - optional, uses user's language if not provided
 * @returns {string|null} - The localized text or null
 */
export const getLocalizedText = (data, language = null) => {
  if (!data) return null
  
  // If it's already a string, return it
  if (typeof data === 'string') return data
  
  // If it's not an object, return null
  if (typeof data !== 'object') return null
  
  // Use provided language or get from user
  const lang = language || getUserLanguage()
  
  // Check for the selected language first
  if (data[lang]) return data[lang]
  
  // Fallback to English
  if (data.en) return data.en
  
  // Fallback to first available value
  const values = Object.values(data)
  if (values.length > 0) return String(values[0])
  
  return null
}

/**
 * Update user data in localStorage
 */
export const updateUserData = (updatedUser) => {
  try {
    localStorage.setItem('user', JSON.stringify(updatedUser))
    // Dispatch events for different preference changes
    window.dispatchEvent(new CustomEvent('userPreferencesChanged', { 
      detail: { user: updatedUser } 
    }))
    if (updatedUser.language) {
      window.dispatchEvent(new CustomEvent('languageChanged', { 
        detail: { language: updatedUser.language } 
      }))
    }
  } catch (error) {
    console.error('Error updating user data:', error)
  }
}

