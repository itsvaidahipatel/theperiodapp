/**
 * Chat history cache utility
 * Caches chat history in sessionStorage for 24 hours
 */

const CHAT_CACHE_KEY = 'period_gpt_chat_history'
const CHAT_CACHE_TIMESTAMP_KEY = 'period_gpt_chat_timestamp'
const CACHE_DURATION_MS = 24 * 60 * 60 * 1000 // 24 hours in milliseconds

/**
 * Check if cached chat history is still valid (within 24 hours)
 */
const isCacheValid = () => {
  try {
    const timestamp = sessionStorage.getItem(CHAT_CACHE_TIMESTAMP_KEY)
    if (!timestamp) return false
    
    const cacheAge = Date.now() - parseInt(timestamp)
    return cacheAge < CACHE_DURATION_MS
  } catch {
    return false
  }
}

/**
 * Get cached chat history
 */
export const getCachedChatHistory = () => {
  try {
    if (!isCacheValid()) {
      // Cache expired, clear it
      clearChatCache()
      return null
    }
    
    const cached = sessionStorage.getItem(CHAT_CACHE_KEY)
    if (cached) {
      return JSON.parse(cached)
    }
    return null
  } catch (error) {
    console.error('Error reading chat cache:', error)
    return null
  }
}

/**
 * Save chat history to cache
 */
export const setCachedChatHistory = (messages) => {
  try {
    sessionStorage.setItem(CHAT_CACHE_KEY, JSON.stringify(messages))
    sessionStorage.setItem(CHAT_CACHE_TIMESTAMP_KEY, Date.now().toString())
    console.log('Chat history cached successfully')
  } catch (error) {
    console.error('Error saving chat cache:', error)
    // If storage is full, try to clear old cache
    if (error.name === 'QuotaExceededError') {
      clearChatCache()
    }
  }
}

/**
 * Add a new message to cached history
 */
export const addMessageToCache = (message) => {
  try {
    const cached = getCachedChatHistory()
    if (cached) {
      const updated = [...cached, message]
      setCachedChatHistory(updated)
      return updated
    } else {
      // Create new cache with this message
      setCachedChatHistory([message])
      return [message]
    }
  } catch (error) {
    console.error('Error adding message to cache:', error)
    return null
  }
}

/**
 * Clear chat cache
 */
export const clearChatCache = () => {
  try {
    sessionStorage.removeItem(CHAT_CACHE_KEY)
    sessionStorage.removeItem(CHAT_CACHE_TIMESTAMP_KEY)
    console.log('Chat cache cleared')
  } catch (error) {
    console.error('Error clearing chat cache:', error)
  }
}

/**
 * Get cache info for debugging
 */
export const getChatCacheInfo = () => {
  const timestamp = sessionStorage.getItem(CHAT_CACHE_TIMESTAMP_KEY)
  const cached = sessionStorage.getItem(CHAT_CACHE_KEY)
  
  return {
    hasCache: !!cached,
    timestamp: timestamp ? new Date(parseInt(timestamp)).toISOString() : null,
    isValid: isCacheValid(),
    messageCount: cached ? JSON.parse(cached).length : 0
  }
}

