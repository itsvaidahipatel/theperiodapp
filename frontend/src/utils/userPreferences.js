/**
 * Global user preferences utility
 * Gets user preferences from localStorage
 */

/**
 * Get user's saved language preference (from their profile)
 * Use this for login page - ignores temporary selectedLanguage
 */
export const getUserSavedLanguage = () => {
  try {
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      const lang = user.language || 'en'
      console.log('getUserSavedLanguage: User logged in, using saved language:', lang)
      return lang
    }
    
    // If not logged in, check for temporary language preference
    const tempLanguage = localStorage.getItem('selectedLanguage')
    if (tempLanguage) {
      console.log('getUserSavedLanguage: No user, using selectedLanguage:', tempLanguage)
      return tempLanguage
    }
    
    console.log('getUserSavedLanguage: No language found, defaulting to en')
  } catch (error) {
    console.error('Error getting user saved language:', error)
  }
  return 'en' // Default to English
}

/**
 * Get user's language preference
 * For logged-in users: prioritizes saved language over temporary selectedLanguage
 * For non-logged-in users: uses temporary selectedLanguage (for register flow)
 */
export const getUserLanguage = () => {
  try {
    // PRIORITY 1: If user is logged in, use their saved language preference (ignore temporary selectedLanguage)
    const userData = localStorage.getItem('user')
    if (userData) {
      const user = JSON.parse(userData)
      const lang = user.language || 'en'
      console.log('getUserLanguage: User logged in, using saved language:', lang)
      // Clear selectedLanguage if it exists, since user has a saved preference
      const tempLanguage = localStorage.getItem('selectedLanguage')
      if (tempLanguage && tempLanguage !== lang) {
        console.log('getUserLanguage: Clearing selectedLanguage (', tempLanguage, ') as user has saved preference (', lang, ')')
        localStorage.removeItem('selectedLanguage')
      }
      return lang
    }
    
    // PRIORITY 2: For non-logged-in users, check for temporary language preference from home page selection
    const tempLanguage = localStorage.getItem('selectedLanguage')
    if (tempLanguage) {
      console.log('getUserLanguage: No user logged in, using selectedLanguage:', tempLanguage)
      return tempLanguage
    }
    
    console.log('getUserLanguage: No language found, defaulting to en')
  } catch (error) {
    console.error('Error getting user language:', error)
  }
  return 'en' // Default to English
}

/**
 * Set temporary language preference (for non-logged-in users)
 * Only sets if user is not logged in (to avoid overriding saved preferences)
 */
export const setSelectedLanguage = (language) => {
  try {
    // Don't set selectedLanguage if user is logged in - they should use their saved preference
    const userData = localStorage.getItem('user')
    if (userData) {
      console.log('setSelectedLanguage: User is logged in, ignoring selectedLanguage setting. Use saved preference instead.')
      return
    }
    
    console.log('setSelectedLanguage: Setting language to', language)
    localStorage.setItem('selectedLanguage', language)
    // Verify it was set
    const verify = localStorage.getItem('selectedLanguage')
    console.log('setSelectedLanguage: Verified in localStorage:', verify)
    // Dispatch event so components can react to language change
    window.dispatchEvent(new CustomEvent('languageChanged', { 
      detail: { language } 
    }))
  } catch (error) {
    console.error('Error setting selected language:', error)
  }
}

/**
 * Clear temporary language preference
 * Useful when user logs in or when we want to reset to saved preferences
 */
export const clearSelectedLanguage = () => {
  try {
    localStorage.removeItem('selectedLanguage')
    console.log('clearSelectedLanguage: Cleared selectedLanguage from localStorage')
    // Dispatch event so components can react
    window.dispatchEvent(new CustomEvent('languageChanged'))
  } catch (error) {
    console.error('Error clearing selected language:', error)
  }
}

/**
 * Get selected language (from home page selection, before login)
 */
export const getSelectedLanguage = () => {
  try {
    return localStorage.getItem('selectedLanguage') || 'en'
  } catch (error) {
    console.error('Error getting selected language:', error)
    return 'en'
  }
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
    // Clear selectedLanguage when user data is updated - they now have a saved preference
    localStorage.removeItem('selectedLanguage')
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

