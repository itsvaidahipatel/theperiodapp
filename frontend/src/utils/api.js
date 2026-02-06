const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Helper function to get auth token
const getToken = () => {
  return localStorage.getItem('access_token')
}

// Helper function to make API requests
const apiRequest = async (endpoint, options = {}) => {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let errorData
    try {
      errorData = await response.json()
    } catch {
      errorData = { detail: `HTTP ${response.status}: ${response.statusText}` }
    }
    
    // Handle authentication errors (401/403) - clear invalid token
    if (response.status === 401 || response.status === 403) {
      // Clear invalid token
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      
      // Only redirect if not already on login/register/home page
      // Don't redirect from home page - it's a public route
      const currentPath = window.location.pathname
      const isPublicRoute = currentPath === '/' || 
                           currentPath === '/login' || 
                           currentPath === '/register' ||
                           currentPath.startsWith('/login') ||
                           currentPath.startsWith('/register')
      
      if (!isPublicRoute) {
        // Redirect to login after a short delay to allow error to be logged
        setTimeout(() => {
          window.location.href = '/login'
        }, 100)
      }
    }
    
    const error = new Error(errorData.detail || errorData.message || 'Request failed')
    error.response = { data: errorData, status: response.status }
    throw error
  }

  return response.json()
}

// Auth API functions
export const registerUser = async (payload) => {
  const data = await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (data.access_token) {
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    // Clear selectedLanguage after successful registration - user now has saved preference
    localStorage.removeItem('selectedLanguage')
  }
  return data
}

export const loginUser = async (payload) => {
  const data = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (data.access_token) {
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    // Clear selectedLanguage after successful login - user should use saved preference
    localStorage.removeItem('selectedLanguage')
  }
  return data
}

export const getMe = async () => {
  return apiRequest('/auth/me')
}

export const logout = async () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  return { msg: 'logged out' }
}

// User API functions
export const updateUserProfile = async (profileData) => {
  const data = await apiRequest('/user/profile', {
    method: 'POST',
    body: JSON.stringify(profileData),
  })
  if (data) {
    localStorage.setItem('user', JSON.stringify(data))
  }
  return data
}

export const changePassword = async (passwordData) => {
  return apiRequest('/user/change-password', {
    method: 'POST',
    body: JSON.stringify(passwordData),
  })
}

export const removeFromSaved = async (type, item) => {
  return apiRequest('/user/remove-item', {
    method: 'POST',
    body: JSON.stringify({ type, item }),
  })
}

// Notification Preferences API functions
export const getNotificationPreferences = async () => {
  return apiRequest('/user/notification-preferences')
}

export const updateNotificationPreferences = async (preferences) => {
  return apiRequest('/user/notification-preferences', {
    method: 'POST',
    body: JSON.stringify(preferences),
  })
}

export const resetCycleData = async () => {
  return apiRequest('/user/reset-cycle-data', {
    method: 'POST',
  })
}

// Period API functions
export const logPeriod = async (logData) => {
  return apiRequest('/periods/log', {
    method: 'POST',
    body: JSON.stringify(logData),
  })
}

export const getPeriodLogs = async () => {
  return apiRequest('/periods/logs')
}

export const updatePeriodLog = async (logId, logData) => {
  return apiRequest(`/periods/log/${logId}`, {
    method: 'PUT',
    body: JSON.stringify(logData),
  })
}

export const deletePeriodLog = async (logId) => {
  return apiRequest(`/periods/log/${logId}`, {
    method: 'DELETE',
  })
}

export const getPeriodEpisodes = async () => {
  return apiRequest('/periods/episodes')
}

// Cycle API functions
export const predictCycles = async (pastCycleData, currentDate) => {
  return apiRequest('/cycles/predict', {
    method: 'POST',
    body: JSON.stringify({
      past_cycle_data: pastCycleData,
      current_date: currentDate,
    }),
  })
}

export const getCurrentPhase = async (date) => {
  try {
    const params = date ? `?date=${date}` : ''
    return await apiRequest(`/cycles/current-phase${params}`)
  } catch (error) {
    // If no phase data exists, return null instead of throwing
    if (error.message && (error.message.includes('No phase data') || error.message.includes('404'))) {
      return null
    }
    throw error
  }
}

export const getPhaseMap = async (startDate, endDate, forceRecalculate = false) => {
  try {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    if (forceRecalculate) params.append('force_recalculate', 'true')
    const query = params.toString() ? `?${params.toString()}` : ''
    
    // Calculate date range to determine appropriate timeout
    let timeoutDuration = 30000 // Default 30 seconds
    if (startDate && endDate) {
      try {
        const start = new Date(startDate)
        const end = new Date(endDate)
        const daysDiff = Math.ceil((end - start) / (1000 * 60 * 60 * 24))
        
        // Longer timeout for larger date ranges (initial load = 7 months = ~210 days)
        if (daysDiff > 180) {
          timeoutDuration = 45000 // 45 seconds for large ranges (initial load)
        } else if (daysDiff > 90) {
          timeoutDuration = 35000 // 35 seconds for medium ranges
        }
        // For small ranges (< 90 days), use default 30 seconds
      } catch {
        // If date parsing fails, use default timeout
      }
    }
    
    // Add timeout - longer for initial loads, shorter for navigation
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutDuration)
    
    let response
    try {
      response = await apiRequest(`/cycles/phase-map${query}`, { signal: controller.signal })
      clearTimeout(timeoutId)
    } catch (error) {
      clearTimeout(timeoutId)
      // Only show timeout error for actual timeouts, not other errors
      if (error.name === 'AbortError') {
        throw new Error('Request timeout - predictions are being generated in background. Please try again in a moment.')
      }
      // Don't wrap other errors - let them pass through
      throw error
    }
    
    console.log('getPhaseMap raw response:', response)
    
    // Auto-detect if ovulation phases are missing and trigger recalculation
    if (!forceRecalculate && response?.phase_map && Array.isArray(response.phase_map)) {
      const hasOvulation = response.phase_map.some(item => 
        item.phase === 'Ovulation' || (item.phase_day_id && item.phase_day_id.toLowerCase().startsWith('o'))
      )
      
      // If we have data but no ovulation phases, and we have enough dates to expect ovulation
      if (!hasOvulation && response.phase_map.length > 14) {
        console.log('⚠️ No ovulation phases detected in phase map. Triggering recalculation...')
        // Recursively call with force_recalculate
        return await getPhaseMap(startDate, endDate, true)
      }
    }
    
    return response
  } catch (error) {
    console.error('getPhaseMap error:', error)
    // If no phase map exists, return empty map instead of throwing
    if (error.message && (error.message.includes('No phase') || error.message.includes('404'))) {
      return { phase_map: [] }
    }
    throw error
  }
}

// Feedback API functions
export const submitFeedback = async (subject, message, type = "general") => {
  return await apiRequest("/feedback/submit", {
    method: "POST",
    body: JSON.stringify({ subject, message, type })
  })
}

// Wellness API functions
export const getHormonesData = async (phaseDayId = null, days = 5) => {
  // If phaseDayId not provided, backend will use today's phase-day ID automatically
  // days parameter: 5 = last 4 days + today
  const url = phaseDayId 
    ? `/wellness/hormones?phase_day_id=${phaseDayId}&days=${days}`
    : `/wellness/hormones?days=${days}`
  return apiRequest(url)
}

export const getNutritionData = async (phaseDayId = null, language = 'en', cuisine = null) => {
  // If phaseDayId not provided, backend will use today's phase-day ID automatically
  const params = new URLSearchParams({ language })
  if (phaseDayId) params.append('phase_day_id', phaseDayId)
  if (cuisine) params.append('cuisine', cuisine)
  return apiRequest(`/wellness/nutrition?${params.toString()}`)
}

export const getExerciseData = async (phaseDayId = null, language = 'en', category = null) => {
  // If phaseDayId not provided, backend will use today's phase-day ID automatically
  const params = new URLSearchParams({ language })
  if (phaseDayId) params.append('phase_day_id', phaseDayId)
  if (category) params.append('category', category)
  return apiRequest(`/wellness/exercises?${params.toString()}`)
}

// AI Chat API functions
export const sendChatMessage = async (message, language) => {
  return apiRequest('/ai/chat', {
    method: 'POST',
    body: JSON.stringify({ message, language }),
  })
}

export const getChatHistory = async (limit = 20) => {
  return apiRequest(`/ai/chat-history?limit=${limit}`)
}

// Cycle Health Check API functions
export const getCycleHealthCheck = async () => {
  return apiRequest('/cycles/health-check')
}
// New period service API functions
export const getPeriodPredictions = async (count = 6) => {
  return apiRequest(`/periods/predictions?count=${count}`)
}

export const getCycleStats = async () => {
  return apiRequest('/periods/stats')
}
