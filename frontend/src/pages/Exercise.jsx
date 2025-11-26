import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDataContext } from '../context/DataContext'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import LoadingSpinner from '../components/LoadingSpinner'
import { ArrowLeft } from 'lucide-react'
import { getUserLanguage, getFavoriteExercise } from '../utils/userPreferences'
import { useTranslation } from '../utils/translations'
import { getPreloadedExerciseData } from '../utils/dataLoader'
import { getExerciseData } from '../utils/api'

const Exercise = () => {
  const { t } = useTranslation()
  const { dashboardData, wellnessData, loadingWellness } = useDataContext()
  const [user, setUser] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState('')
  const [loadingCategory, setLoadingCategory] = useState(false)
  const [exercisesByCategory, setExercisesByCategory] = useState({})
  const navigate = useNavigate()

  // Extract data from context
  const currentPhase = dashboardData?.currentPhase || null
  const phaseDayId = currentPhase?.phase_day_id || currentPhase?.id
  
  // Get exercises from wellnessData
  // wellnessData.exercises can be:
  // - null (no data available or empty array was normalized to null)
  // - {exercises: [...]} (has data)
  // - undefined (not loaded yet)
  const defaultExercises = wellnessData?.exercises !== undefined
    ? (wellnessData.exercises && wellnessData.exercises.exercises && Array.isArray(wellnessData.exercises.exercises) && wellnessData.exercises.exercises.length > 0
        ? wellnessData.exercises.exercises
        : null)  // null means tried to load but no data
    : undefined  // undefined means not loaded yet
  
  // Initialize exercisesByCategory with default exercises (favorite category)
  useEffect(() => {
    // Only initialize if we have actual data (not null, not undefined)
    if (defaultExercises !== undefined && defaultExercises !== null && !exercisesByCategory[selectedCategory]) {
      if (Array.isArray(defaultExercises) && defaultExercises.length > 0) {
        console.log(`📝 Exercise: Initializing with default exercises for ${selectedCategory}:`, defaultExercises.length, 'exercises')
        setExercisesByCategory(prev => ({
          ...prev,
          [selectedCategory]: defaultExercises
        }))
      }
    }
    // If defaultExercises is null, it means wellnessData tried to load but got empty - don't mark as tried yet,
    // let the fetch effect handle it
  }, [defaultExercises, selectedCategory, exercisesByCategory])
  
  // Get exercises for selected category (from cache or API)
  const allExercises = (() => {
    // If we have cached exercises for this category, use them
    if (exercisesByCategory[selectedCategory] !== undefined) {
      return exercisesByCategory[selectedCategory]
    }
    // Otherwise use default exercises (favorite category) - could be array, null, or undefined
    return defaultExercises
  })()
  
  // Debug: Log what we have
  useEffect(() => {
    console.log('🔍 Exercise Debug:', {
      wellnessData,
      exercises: wellnessData?.exercises,
      defaultExercises,
      selectedCategory,
      exercisesByCategory,
      allExercises
    })
  }, [wellnessData, defaultExercises, selectedCategory, exercisesByCategory, allExercises])
  
  // Load exercises for selected category if not in cache
  useEffect(() => {
    if (!selectedCategory || !phaseDayId) {
      console.log(`⏸️ Exercise: Skipping load - selectedCategory: ${selectedCategory}, phaseDayId: ${phaseDayId}`)
      return
    }
    
    // Check if we already have valid data for this category
    const existingData = exercisesByCategory[selectedCategory]
    if (existingData !== undefined && 
        existingData !== null &&
        Array.isArray(existingData) &&
        existingData.length > 0) {
      console.log(`⏸️ Exercise: Already have ${existingData.length} exercises for ${selectedCategory}`)
      return
    }
    
    // If we have null, it means we tried before and got no data - don't retry unless phaseDayId changed
    // (This prevents infinite loops when there's genuinely no data)
    if (existingData === null) {
      console.log(`⏸️ Exercise: Already tried loading ${selectedCategory} and got no data (skipping retry)`)
      return
    }
    
    console.log(`🔄 Exercise: Loading data for category: ${selectedCategory}, phaseDayId: ${phaseDayId}`)
    
    // Check preloaded data first
    const preloaded = getPreloadedExerciseData(phaseDayId, selectedCategory)
    if (preloaded && preloaded.exercises && Array.isArray(preloaded.exercises) && preloaded.exercises.length > 0) {
      console.log(`✅ Using preloaded exercise data for ${selectedCategory}:`, preloaded.exercises.length, 'exercises')
      setExercisesByCategory(prev => ({
        ...prev,
        [selectedCategory]: preloaded.exercises
      }))
      return
    } else if (preloaded && preloaded.exercises && Array.isArray(preloaded.exercises) && preloaded.exercises.length === 0) {
      // Preloaded but empty - mark as no data
      console.log(`⚠️ Preloaded exercise data for ${selectedCategory} is empty`)
      setExercisesByCategory(prev => ({
        ...prev,
        [selectedCategory]: null
      }))
      return
    }
    
    // If not preloaded, fetch from API
    setLoadingCategory(true)
    const language = getUserLanguage()
    console.log(`🌐 Exercise: Making API call - phaseDayId: ${phaseDayId}, category: ${selectedCategory}, language: ${language}`)
    getExerciseData(phaseDayId, language, selectedCategory)
      .then(data => {
        console.log(`📥 Exercise: API response received:`, data)
        // Backend returns {exercises: [...]} or {exercises: []}
        if (data && data.exercises && Array.isArray(data.exercises) && data.exercises.length > 0) {
          console.log(`✅ Exercise: Got ${data.exercises.length} exercises for ${selectedCategory}`)
          setExercisesByCategory(prev => ({
            ...prev,
            [selectedCategory]: data.exercises
          }))
        } else {
          // Empty array or no data - mark as null (no data available)
          console.log(`⚠️ Exercise: No exercises in response for ${selectedCategory}`)
          setExercisesByCategory(prev => ({
            ...prev,
            [selectedCategory]: null
          }))
        }
      })
      .catch(err => {
        console.error(`❌ Error loading exercises for ${selectedCategory}:`, err)
        setExercisesByCategory(prev => ({
          ...prev,
          [selectedCategory]: null
        }))
      })
      .finally(() => {
        setLoadingCategory(false)
      })
  }, [selectedCategory, phaseDayId, exercisesByCategory, wellnessData])

  // Category mapping for display: database value (lowercase) -> display name
  const categoryDisplayMapping = {
    'mind': 'Yoga/Pilates',
    'cardio': 'Outdoor/Cardio',
    'strength': 'Strength Building'
  }

  // Map favorite_exercise (from registration) to database category value (lowercase)
  const favoriteExerciseToCategory = {
    'Yoga': 'mind',
    'Cardio': 'cardio',
    'Strength': 'strength',
    'Mind': 'mind',
    'Stretching': 'mind' // Stretching maps to Mind/Yoga
  }

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      // Set default category to user's favorite_exercise, or default to 'mind'
      const favoriteExercise = getFavoriteExercise() || ''
      // Map favorite_exercise to database category value
      let dbCategory = 'mind' // Default
      if (favoriteExercise) {
        dbCategory = favoriteExerciseToCategory[favoriteExercise] || favoriteExercise.toLowerCase()
      }
      console.log(`💪 Exercise: Setting selectedCategory to: ${dbCategory}`)
      setSelectedCategory(dbCategory)
    } else {
      navigate('/login')
    }
  }, [navigate])
  
  // Force reload when phaseDayId changes - reset cache to allow fresh fetch
  useEffect(() => {
    if (phaseDayId && selectedCategory) {
      console.log(`🔄 Exercise: phaseDayId changed to ${phaseDayId}, resetting cache`)
      setExercisesByCategory({})
    }
  }, [phaseDayId])

  // Listen for language changes
  useEffect(() => {
    const handleLanguageChange = () => {
      const userData = localStorage.getItem('user')
      if (userData) {
        setUser(JSON.parse(userData))
      }
    }
    
    window.addEventListener('languageChanged', handleLanguageChange)
    window.addEventListener('focus', handleLanguageChange)
    
    return () => {
      window.removeEventListener('languageChanged', handleLanguageChange)
      window.removeEventListener('focus', handleLanguageChange)
    }
  }, [])

  // Filter exercises by selected category (case-insensitive)
  // Note: selectedCategory is required (no "All Categories" option), so always filter
  const filteredExercises = (() => {
    // Handle null, undefined, or non-array values
    if (!allExercises || !Array.isArray(allExercises)) {
      return []
    }
    
    return allExercises.filter(ex => {
      // Compare case-insensitively
      const matches = ex.category?.toLowerCase() === selectedCategory.toLowerCase()
      return matches
    })
  })()
  
  console.log('Selected category:', selectedCategory)
  console.log('All exercises:', allExercises)
  console.log('All exercises count:', allExercises ? (Array.isArray(allExercises) ? allExercises.length : 'not an array') : 'null/undefined')
  console.log('Filtered exercises count:', filteredExercises.length)

  // Get unique energy level from filtered exercises (if all have same energy level)
  const energyLevel = filteredExercises.length > 0 && filteredExercises[0]?.energy_level
    ? filteredExercises[0].energy_level
    : null

  if (!user) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation with Back Button */}
      <nav className="bg-white shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16 gap-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition"
            >
              <ArrowLeft className="h-5 w-5" />
              <span>{t('nav.backToDashboard')}</span>
            </button>
            <h1 className="text-2xl font-bold text-period-pink">{t('exercise.title')}</h1>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-4">{t('exercise.moveWithCycle')}</h2>
          {currentPhase && (
            <p className="text-2xl text-gray-700 font-semibold mb-4">
              {t('exercise.currentPhase')}: <span className="text-period-pink capitalize">{t(`phase.${currentPhase.phase.toLowerCase()}`)}</span> - {t('dashboard.day')} <span className="text-period-pink">{currentPhase.phase_day_id || currentPhase.id}</span>
            </p>
          )}
        </div>

        {(loadingWellness || loadingCategory) ? (
          <LoadingSpinner message="Loading exercise data..." />
        ) : filteredExercises && Array.isArray(filteredExercises) && filteredExercises.length > 0 ? (
          <div className="space-y-6">
            {/* Energy Level */}
            {energyLevel && (
              <div className="bg-purple-50 rounded-lg p-4 border-l-4 border-purple-400">
                <p className="text-lg font-semibold text-purple-800">
                  {t('exercise.energyLevel')}: <span className="text-purple-600">{energyLevel}</span>
                </p>
              </div>
            )}

            {/* Category Filter */}
            <div className="mb-6">
              <label htmlFor="category-filter" className="block text-lg font-semibold text-gray-700 mb-3">
                {t('exercise.filterByCategory')}
              </label>
              <select
                id="category-filter"
                name="category"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-4 py-3 text-base border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
              >
                {Object.entries(categoryDisplayMapping).map(([dbValue, displayName]) => (
                  <option key={dbValue} value={dbValue}>{t(`exercise.category.${dbValue}`)}</option>
                ))}
              </select>
            </div>

            {/* Exercises */}
            {filteredExercises.length > 0 ? (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="space-y-6">
                  {filteredExercises.slice(0, 3).map((exercise, index) => (
                    <div key={exercise.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-md transition">
                      <h4 className="text-xl font-semibold mb-4">
                        {t('exercise.exercise')} {index + 1}: {exercise.exercise_name}
                      </h4>

                      {exercise.steps && (() => {
                        // Parse steps - could be string, array, or JSON string
                        let stepsArray = null
                        
                        console.log('Raw steps value:', exercise.steps, 'Type:', typeof exercise.steps)
                        
                        if (Array.isArray(exercise.steps)) {
                          stepsArray = exercise.steps
                        } else if (typeof exercise.steps === 'string') {
                          const trimmed = exercise.steps.trim()
                          // Try to parse as JSON if it looks like JSON array
                          if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
                            try {
                              const parsed = JSON.parse(trimmed)
                              stepsArray = Array.isArray(parsed) ? parsed : [parsed]
                              console.log('Parsed JSON array:', stepsArray)
                            } catch (e) {
                              console.error('JSON parse error:', e)
                              // If parsing fails, try to extract array manually
                              // Handle case where it might be a string representation
                              try {
                                // Remove quotes and brackets, split by comma
                                const cleaned = trimmed.replace(/^\[|\]$/g, '').trim()
                                if (cleaned) {
                                  stepsArray = cleaned.split('","').map(s => s.replace(/^"|"$/g, '').trim()).filter(s => s)
                                } else {
                                  stepsArray = [exercise.steps]
                                }
                              } catch (e2) {
                                stepsArray = [exercise.steps]
                              }
                            }
                          } else {
                            // Plain string, split by newlines or use as single step
                            stepsArray = exercise.steps.split('\n').filter(s => s.trim())
                            if (stepsArray.length === 0) {
                              stepsArray = [exercise.steps]
                            }
                          }
                        } else {
                          stepsArray = [String(exercise.steps)]
                        }
                        
                        console.log('Final stepsArray:', stepsArray)
                        
                        return (
                          <div className="mb-4">
                            <p className="font-semibold mb-2">Steps:</p>
                            <div className="bg-gray-50 rounded-lg p-4">
                              <ol className="list-decimal list-inside text-gray-700 space-y-2 ml-2">
                                {stepsArray.map((step, idx) => (
                                  <li key={idx} className="mb-2 leading-relaxed">{step}</li>
                                ))}
                              </ol>
                            </div>
                          </div>
                        )
                      })()}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow-lg p-6 text-center">
                <p className="text-gray-600 mb-2">No exercise data available for this phase day.</p>
                <p className="text-sm text-gray-500">
                  Data will be available once cycle predictions are generated and exercises are added to the database.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-12 bg-white rounded-lg shadow-lg">
            <p className="text-gray-600 mb-4">No exercise data available for this phase day.</p>
            <p className="text-sm text-gray-500">
              Data will be available once cycle predictions are generated and exercises are added to the database.
            </p>
          </div>
        )}

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

export default Exercise
