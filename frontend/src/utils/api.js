const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Helper function to get auth token (persist across refresh)
const getToken = () => {
  return localStorage.getItem('access_token')
}

// Request deduplication: Track in-flight requests to prevent duplicates
const pendingRequests = new Map()

// Helper function to make API requests with retry for 502/503 errors
const apiRequest = async (endpoint, options = {}, retryCount = 0) => {
  const token = getToken()
  
  // CRITICAL: Protected endpoints require authentication
  // Fail early if no token is present for protected endpoints
  // Public endpoints: /auth/register, /auth/login, /auth/logout
  const isPublicEndpoint = endpoint.startsWith('/auth/register') || 
                          endpoint.startsWith('/auth/login') || 
                          endpoint.startsWith('/auth/logout')
  
  if (!token && !isPublicEndpoint) {
    const error = new Error('Not authenticated')
    error.response = { 
      data: { detail: 'Authentication required' }, 
      status: 401 
    }
    throw error
  }
  
  // REQUEST DEDUPLICATION: Check if same request is already in progress
  const requestKey = `${options.method || 'GET'}:${endpoint}`
  if (pendingRequests.has(requestKey)) {
    console.log(`⏳ Request deduplication: Waiting for existing request to ${endpoint}`)
    // Wait for the existing request to complete
    try {
      return await pendingRequests.get(requestKey)
    } catch (error) {
      // If the existing request failed, we'll retry below
      pendingRequests.delete(requestKey)
    }
  }
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Create promise for this request
  const requestPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
      })

      // Handle 502/503 errors (Cloudflare/Supabase temporary errors) with retry
      if (response.status === 502 || response.status === 503) {
        if (retryCount < 3) {
          const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 5000) // Exponential backoff: 1s, 2s, 4s
          console.log(`⚠️ Server error ${response.status} (attempt ${retryCount + 1}/3), retrying in ${retryDelay}ms...`)
          await new Promise(resolve => setTimeout(resolve, retryDelay))
          return apiRequest(endpoint, options, retryCount + 1)
        } else {
          throw new Error(`Server temporarily unavailable (${response.status}). Please try again in a moment.`)
        }
      }

      if (!response.ok) {
        let errorData
        try {
          errorData = await response.json()
        } catch {
          errorData = { detail: `HTTP ${response.status}: ${response.statusText}` }
        }
        
        // Handle authentication errors (401/403) - clear invalid token
        if (response.status === 401 || response.status === 403) {
          // Clear invalid token/user (nuclear option for strict isolation)
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
          try { sessionStorage.clear() } catch {}
          
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
    } finally {
      // Remove from pending requests when done
      pendingRequests.delete(requestKey)
    }
  })()

  // Store the promise for deduplication
  pendingRequests.set(requestKey, requestPromise)
  
  return requestPromise
}

// Auth API functions
export const registerUser = async (payload) => {
  const data = await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (data.access_token) {
    // Clean slate: clear session caches; persist auth to localStorage for refresh
    try { sessionStorage.clear() } catch {}
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    window.dispatchEvent(new CustomEvent('authSuccess'))
  }
  return data
}

export const loginUser = async (payload) => {
  const data = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (data.access_token) {
    // Clean slate: clear session caches; persist auth to localStorage for refresh
    try { sessionStorage.clear() } catch {}
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    window.dispatchEvent(new CustomEvent('authSuccess'))
  }
  return data
}

export const getMe = async () => {
  return apiRequest('/auth/me')
}

export const logout = async () => {
  // Nuclear option: clear everything to prevent leakage between users
  try { sessionStorage.clear() } catch {}
  try { localStorage.clear() } catch {}
  return { msg: 'logged out' }
}

// User API functions
export const updateUserProfile = async (profileData) => {
  const data = await apiRequest('/user/profile', {
    method: 'POST',
    body: JSON.stringify(profileData),
  })
  if (data) {
    // Persist updated profile for refresh
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

export const resetLastPeriod = async () => {
  return apiRequest('/user/reset-last-period', {
    method: 'POST',
  })
}

/** Temporary debug: run 6-month phase analysis; backend prints [DEBUG] lines to terminal. */
export const runSixMonthDiagnostic = async () => {
  return apiRequest('/debug/analyze-phases')
}

// Period API functions
export const logPeriod = async (logData) => {
  return apiRequest('/periods/log', {
    method: 'POST',
    body: JSON.stringify(logData),
  })
}

export const logPeriodEnd = async (endData) => {
  return apiRequest('/periods/log-end', {
    method: 'POST',
    body: JSON.stringify(endData),
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

export const getPhaseMap = async (startDate, endDate, forceRecalculate = false, retryCount = 0) => {
  try {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    if (forceRecalculate) params.append('force_recalculate', 'true')
    const query = params.toString() ? `?${params.toString()}` : ''
    
    // Shorter timeout now (backend returns quickly)
    const timeoutDuration = 10000 // 10 seconds - backend should respond quickly
    
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutDuration)
    
    let response
    try {
      const token = getToken()
      if (!token) {
        const error = new Error('Not authenticated')
        error.response = {
          data: { detail: 'Authentication required' },
          status: 401,
        }
        throw error
      }

      // Make request and check status
      const rawResponse = await fetch(`${API_BASE_URL}/cycles/phase-map${query}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        signal: controller.signal
      })
      
      clearTimeout(timeoutId)
      
      // Handle 202 Accepted (processing)
      if (rawResponse.status === 202) {
        const data = await rawResponse.json()
        console.log('⏳ Phase map is being generated in background:', data)
        
        // If this is the first attempt and we haven't retried, wait and retry once
        if (retryCount === 0) {
          console.log('🔄 Waiting 8 seconds before retry...')
          await new Promise(resolve => setTimeout(resolve, 8000))
          return getPhaseMap(startDate, endDate, forceRecalculate, 1) // Retry once
        } else {
          // Already retried once - return processing status
          return {
            status: 'processing',
            phase_map: [],
            message: data.message || 'Predictions are being generated. Please wait a moment.'
          }
        }
      }
      
      // Handle other status codes
      if (!rawResponse.ok) {
        const errorData = await rawResponse.json().catch(() => ({ detail: `HTTP ${rawResponse.status}` }))
        const error = new Error(errorData.detail || errorData.message || 'Request failed')
        error.response = { data: errorData, status: rawResponse.status }
        throw error
      }
      
      response = await rawResponse.json()
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
