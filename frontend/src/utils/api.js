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
    const error = await response.json().catch(() => ({ detail: 'An error occurred' }))
    throw new Error(error.detail || error.message || 'Request failed')
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

export const getPhaseMap = async (startDate, endDate) => {
  try {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    const query = params.toString() ? `?${params.toString()}` : ''
    return await apiRequest(`/cycles/phase-map${query}`)
  } catch (error) {
    // If no phase map exists, return empty map instead of throwing
    if (error.message && (error.message.includes('No phase') || error.message.includes('404'))) {
      return { phase_map: [] }
    }
    throw error
  }
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

