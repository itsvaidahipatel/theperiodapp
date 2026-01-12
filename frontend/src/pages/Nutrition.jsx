import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDataContext } from '../context/DataContext'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import LoadingSpinner from '../components/LoadingSpinner'
import { ArrowLeft } from 'lucide-react'
import { getUserLanguage, getFavoriteCuisine } from '../utils/userPreferences'
import { parseMarkdown, parseInlineMarkdown } from '../utils/markdown'
import { useTranslation } from '../utils/translations'
import { translateNutrientName, translateCuisineName } from '../utils/translateHelpers'
import { getPreloadedNutritionData } from '../utils/dataLoader'
import { getNutritionData } from '../utils/api'

const Nutrition = () => {
  const { t } = useTranslation()
  const { dashboardData, wellnessData, loadingWellness } = useDataContext()
  const [user, setUser] = useState(null)
  const [selectedCuisine, setSelectedCuisine] = useState('')
  const [loadingCuisine, setLoadingCuisine] = useState(false)
  const [recipesByCuisine, setRecipesByCuisine] = useState({})
  const navigate = useNavigate()

  // Extract data from context
  const currentPhase = dashboardData?.currentPhase || null
  const phaseDayId = currentPhase?.phase_day_id || currentPhase?.id
  
  // Get recipes from wellnessData
  // wellnessData.nutrition can be:
  // - null (no data available or empty array was normalized to null)
  // - {recipes: [...], wholefoods: []} (has data)
  // - undefined (not loaded yet)
  const defaultRecipes = wellnessData?.nutrition !== undefined
    ? (wellnessData.nutrition && wellnessData.nutrition.recipes && Array.isArray(wellnessData.nutrition.recipes) && wellnessData.nutrition.recipes.length > 0
        ? wellnessData.nutrition.recipes
        : null)  // null means tried to load but no data
    : undefined  // undefined means not loaded yet
  
  // Initialize recipesByCuisine with default recipes (favorite cuisine)
  useEffect(() => {
    // Only initialize if we have actual data (not null, not undefined)
    if (defaultRecipes !== undefined && defaultRecipes !== null && !recipesByCuisine[selectedCuisine]) {
      if (Array.isArray(defaultRecipes) && defaultRecipes.length > 0) {
        console.log(`📝 Nutrition: Initializing with default recipes for ${selectedCuisine}:`, defaultRecipes.length, 'recipes')
        setRecipesByCuisine(prev => ({
          ...prev,
          [selectedCuisine]: defaultRecipes
        }))
      }
    }
    // If defaultRecipes is null, it means wellnessData tried to load but got empty - don't mark as tried yet,
    // let the fetch effect handle it
  }, [defaultRecipes, selectedCuisine, recipesByCuisine])
  
  // Get recipes for selected cuisine (from cache or API)
  const allRecipes = useMemo(() => {
    // If we have cached recipes for this cuisine, use them
    if (recipesByCuisine[selectedCuisine] !== undefined) {
      return recipesByCuisine[selectedCuisine]
    }
    // Otherwise use default recipes (favorite cuisine) - could be array, null, or undefined
    return defaultRecipes
  }, [recipesByCuisine, selectedCuisine, defaultRecipes])
  
  // Debug: Log what we have
  useEffect(() => {
    console.log('🔍 Nutrition Debug:', {
      wellnessData,
      nutrition: wellnessData?.nutrition,
      defaultRecipes,
      selectedCuisine,
      recipesByCuisine,
      allRecipes
    })
  }, [wellnessData, defaultRecipes, selectedCuisine, recipesByCuisine, allRecipes])
  
  // Load recipes for selected cuisine if not in cache
  useEffect(() => {
    if (!selectedCuisine || !phaseDayId) {
      console.log(`⏸️ Nutrition: Skipping load - selectedCuisine: ${selectedCuisine}, phaseDayId: ${phaseDayId}`)
      return
    }
    
    // Check if we already have valid data for this cuisine
    const existingData = recipesByCuisine[selectedCuisine]
    if (existingData !== undefined && 
        existingData !== null &&
        Array.isArray(existingData) &&
        existingData.length > 0) {
      console.log(`⏸️ Nutrition: Already have ${existingData.length} recipes for ${selectedCuisine}`)
      return
    }
    
    // If we have null, it means we tried before and got no data - don't retry unless phaseDayId changed
    // (This prevents infinite loops when there's genuinely no data)
    if (existingData === null) {
      console.log(`⏸️ Nutrition: Already tried loading ${selectedCuisine} and got no data (skipping retry)`)
      return
    }
    
    console.log(`🔄 Nutrition: Loading data for cuisine: ${selectedCuisine}, phaseDayId: ${phaseDayId}`)
    
    // Check preloaded data first
    const preloaded = getPreloadedNutritionData(phaseDayId, selectedCuisine)
    if (preloaded && preloaded.recipes && Array.isArray(preloaded.recipes) && preloaded.recipes.length > 0) {
      console.log(`✅ Using preloaded nutrition data for ${selectedCuisine}:`, preloaded.recipes.length, 'recipes')
      setRecipesByCuisine(prev => ({
        ...prev,
        [selectedCuisine]: preloaded.recipes
      }))
      return
    } else if (preloaded && preloaded.recipes && Array.isArray(preloaded.recipes) && preloaded.recipes.length === 0) {
      // Preloaded but empty - mark as no data
      console.log(`⚠️ Preloaded nutrition data for ${selectedCuisine} is empty`)
      setRecipesByCuisine(prev => ({
        ...prev,
        [selectedCuisine]: null
      }))
      return
    }
    
    // If not preloaded, fetch from API
    setLoadingCuisine(true)
    const language = getUserLanguage()
    // Normalize cuisine name to standard values (handles legacy values)
    const normalizedCuisine = selectedCuisine.toLowerCase()
    const apiCuisine = (normalizedCuisine === 'gujarati' || normalizedCuisine.includes('gujarati') || normalizedCuisine.includes('kathiya'))
      ? 'gujarati'
      : selectedCuisine
    console.log(`🌐 Nutrition: Making API call - phaseDayId: ${phaseDayId}, cuisine: ${selectedCuisine} -> ${apiCuisine}, language: ${language}`)
    getNutritionData(phaseDayId, language, apiCuisine)
      .then(data => {
        console.log(`📥 Nutrition: API response received:`, data)
        // Backend returns {recipes: [...]} or {recipes: []}
        if (data && data.recipes && Array.isArray(data.recipes) && data.recipes.length > 0) {
          console.log(`✅ Nutrition: Got ${data.recipes.length} recipes for ${selectedCuisine}`)
          setRecipesByCuisine(prev => ({
            ...prev,
            [selectedCuisine]: data.recipes
          }))
        } else {
          // Empty array or no data - mark as null (no data available)
          console.log(`⚠️ Nutrition: No recipes in response for ${selectedCuisine}`)
          setRecipesByCuisine(prev => ({
            ...prev,
            [selectedCuisine]: null
          }))
        }
      })
      .catch(err => {
        console.error(`❌ Error loading nutrition for ${selectedCuisine}:`, err)
        setRecipesByCuisine(prev => ({
          ...prev,
          [selectedCuisine]: null
        }))
      })
      .finally(() => {
        setLoadingCuisine(false)
      })
  }, [selectedCuisine, phaseDayId, recipesByCuisine, wellnessData])
  
  // Debug logging
  useEffect(() => {
    console.log('Nutrition page - allRecipes:', allRecipes)
    console.log('Nutrition page - selectedCuisine:', selectedCuisine)
    console.log('Nutrition page - wellnessData:', wellnessData)
  }, [allRecipes, selectedCuisine, wellnessData])
  
  // Filter recipes by selected cuisine on the frontend
  const filteredRecipes = useMemo(() => {
    // Handle different data types: array, null, or undefined
    if (allRecipes === null || allRecipes === undefined) {
      return null
    }
    
    if (!Array.isArray(allRecipes)) {
      console.warn('allRecipes is not an array:', allRecipes)
      return null
    }
    
    if (allRecipes.length === 0) {
      return null
    }
    
    if (!selectedCuisine || selectedCuisine === 'all') {
      return allRecipes
    }
    
    // Use selected cuisine directly (no mapping needed)
    const dbCuisine = selectedCuisine
    
    const filtered = allRecipes.filter(recipe => {
      const recipeCuisine = recipe.cuisine?.toLowerCase()
      return recipeCuisine === dbCuisine.toLowerCase()
    })
    
    return filtered.length > 0 ? filtered : null
  }, [allRecipes, selectedCuisine])
  
  // Create nutritionData object with filtered recipes
  const nutritionData = filteredRecipes && filteredRecipes.length > 0 ? { recipes: filteredRecipes } : null

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      // Use favorite cuisine from user preferences
      const favoriteCuisine = getFavoriteCuisine() || 'international'
      console.log(`🍽️ Nutrition: Setting selectedCuisine to: ${favoriteCuisine}`)
      setSelectedCuisine(favoriteCuisine)
    } else {
      navigate('/login')
    }
  }, [navigate])
  
  // Force reload when phaseDayId changes - reset cache to allow fresh fetch
  useEffect(() => {
    if (phaseDayId && selectedCuisine) {
      console.log(`🔄 Nutrition: phaseDayId changed to ${phaseDayId}, resetting cache`)
      setRecipesByCuisine({})
    }
  }, [phaseDayId])

  // Listen for language changes
  useEffect(() => {
    const handleLanguageChange = () => {
      const userData = localStorage.getItem('user')
      if (userData) {
        const parsedUser = JSON.parse(userData)
        setUser(parsedUser)
      }
    }
    
    window.addEventListener('languageChanged', handleLanguageChange)
    window.addEventListener('focus', handleLanguageChange)
    
    return () => {
      window.removeEventListener('languageChanged', handleLanguageChange)
      window.removeEventListener('focus', handleLanguageChange)
    }
  }, [])

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
            <h1 className="text-2xl font-bold text-period-pink">{t('nutrition.title')}</h1>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-4">{t('nutrition.todaysNourishment')}</h2>
          {currentPhase && (
            <p className="text-2xl text-gray-700 font-semibold mb-4">
              {t('nutrition.currentPhase')}: <span className="text-period-pink capitalize">{t(`phase.${currentPhase.phase.toLowerCase()}`)}</span> - {t('dashboard.day')} <span className="text-period-pink">{currentPhase.phase_day_id || currentPhase.id}</span>
            </p>
          )}
          
          {/* Key Nutrients Section - Get from first recipe only */}
          {!loadingWellness && filteredRecipes && filteredRecipes.length > 0 && (() => {
            const firstRecipe = filteredRecipes[0]
            if (firstRecipe.nutrients && typeof firstRecipe.nutrients === 'object') {
              const keyNutrients = Object.keys(firstRecipe.nutrients).slice(0, 3)
              
              return keyNutrients.length > 0 ? (
                <div className="mb-6 p-4 bg-blue-50 rounded-lg border-l-4 border-blue-400">
                  <p className="text-lg font-semibold text-gray-800 mb-2">
                    {t('nutrition.workOnNutrients')}
                  </p>
                  <div className="flex flex-wrap gap-3">
                    {keyNutrients.map((nutrient, idx) => (
                      <span key={idx} className="px-3 py-1 bg-white rounded-full text-sm font-semibold text-blue-700 border border-blue-300 capitalize">
                        <strong>{translateNutrientName(nutrient)}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              ) : null
            }
            return null
          })()}
        </div>

        {/* Cuisine Filter */}
        <div className="mb-6">
          <label htmlFor="cuisine-filter" className="block text-lg font-semibold text-gray-700 mb-3">
            {t('nutrition.filterByCuisine')}
          </label>
          <select
            id="cuisine-filter"
            name="cuisine"
            value={selectedCuisine}
            onChange={(e) => setSelectedCuisine(e.target.value)}
            className="px-4 py-3 text-base border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
          >
            <option value="international">{t('cuisine.international')}</option>
            <option value="south_indian">{t('cuisine.southIndian')}</option>
            <option value="north_indian">{t('cuisine.northIndian')}</option>
            <option value="gujarati">{t('cuisine.gujarati')}</option>
          </select>
        </div>

        {(loadingWellness || loadingCuisine) ? (
          <LoadingSpinner message="Loading nutrition data..." />
        ) : filteredRecipes && Array.isArray(filteredRecipes) && filteredRecipes.length > 0 ? (
          <div className="space-y-6">
            {/* Recipes */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-2xl font-bold mb-4">{t('nutrition.recipesTitle')}</h3>
              <div className="space-y-6">
                {filteredRecipes.slice(0, 3).map((recipe, index) => (
                    <div key={recipe.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-md transition">
                      <h4 className="text-xl font-semibold mb-4">
                        {t('nutrition.recipe')} {index + 1}: {parseInlineMarkdown(recipe.recipe_name || '')}
                      </h4>
                      
                      {recipe.serves && (
                        <p className="text-gray-700 mb-4">
                          <span className="font-semibold">{t('nutrition.serves')}:</span> {recipe.serves}
                        </p>
                      )}

                      {recipe.ingredients && Array.isArray(recipe.ingredients) && recipe.ingredients.length > 0 && (
                        <div className="mb-4">
                          <p className="font-semibold mb-2">{t('nutrition.ingredients')}:</p>
                          <ul className="list-disc list-inside text-gray-700 space-y-1">
                            {recipe.ingredients.map((ing, idx) => (
                              <li key={idx}>{parseInlineMarkdown(String(ing))}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {recipe.steps && Array.isArray(recipe.steps) && recipe.steps.length > 0 && (
                        <div className="mb-4">
                          <p className="font-semibold mb-2">{t('nutrition.steps')}:</p>
                          <ol className="list-decimal list-inside text-gray-700 space-y-2 ml-4">
                            {recipe.steps.map((step, idx) => {
                              const stepText = typeof step === 'string' ? step : String(step)
                              return (
                                <li key={idx} className="mb-1">{parseInlineMarkdown(stepText)}</li>
                              )
                            })}
                          </ol>
                        </div>
                      )}

                      {recipe.nutrients && typeof recipe.nutrients === 'object' && (
                        <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                          <p className="font-semibold mb-2">{t('nutrition.nutrients')}</p>
                          <div className="flex gap-3 text-sm overflow-x-auto">
                            {Object.entries(recipe.nutrients).map(([key, value]) => {
                              const translatedNutrientName = translateNutrientName(key)
                              return (
                                <span key={key} className="flex gap-1 whitespace-nowrap">
                                  <span className="text-gray-600 capitalize">{parseInlineMarkdown(`**${translatedNutrientName}**`)}:</span>
                                  <span className="font-semibold">{parseInlineMarkdown(String(value))}</span>
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
          </div>
        ) : (
          <div className="text-center py-12 bg-white rounded-lg shadow-lg">
            <p className="text-gray-600 mb-4">No nutrition data available for this phase day.</p>
            <p className="text-sm text-gray-500">
              Data will be available once cycle predictions are generated and nutrition data is added to the database.
            </p>
          </div>
        )}

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

export default Nutrition

