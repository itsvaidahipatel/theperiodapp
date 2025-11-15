/**
 * Global language utility
 * Gets the user's selected language from localStorage
 * Falls back to 'en' if not available
 * 
 * @deprecated Use getUserLanguage from userPreferences.js instead
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
 * Get localized text from a multilingual object
 * @param {object|string} data - The multilingual data object or plain string
 * @param {string} language - The language code (en, hi, gu)
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

