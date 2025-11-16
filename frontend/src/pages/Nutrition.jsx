import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDataContext } from '../context/DataContext'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { ArrowLeft } from 'lucide-react'
import { getUserLanguage, getFavoriteCuisine } from '../utils/userPreferences'
import { parseMarkdown, parseInlineMarkdown } from '../utils/markdown'
import { useTranslation } from '../utils/translations'
import { translateNutrientName, translateCuisineName } from '../utils/translateHelpers'

const Nutrition = () => {
  const { t } = useTranslation()
  const { dashboardData, wellnessData, loadingWellness } = useDataContext()
  const [user, setUser] = useState(null)
  const [selectedCuisine, setSelectedCuisine] = useState('')
  const navigate = useNavigate()

  // Extract data from context
  const currentPhase = dashboardData?.currentPhase || null
  const allRecipes = wellnessData?.nutrition?.recipes || []
  
  // Debug logging
  useEffect(() => {
    console.log('Nutrition page - allRecipes:', allRecipes)
    console.log('Nutrition page - selectedCuisine:', selectedCuisine)
    console.log('Nutrition page - wellnessData:', wellnessData)
  }, [allRecipes, selectedCuisine, wellnessData])
  
  // Filter recipes by selected cuisine on the frontend
  const filteredRecipes = useMemo(() => {
    if (!selectedCuisine || selectedCuisine === 'all') {
      console.log('No cuisine filter, returning all recipes:', allRecipes.length)
      return allRecipes
    }
    
    // Use selected cuisine directly (no mapping needed)
    const dbCuisine = selectedCuisine
    
    const filtered = allRecipes.filter(recipe => {
      const recipeCuisine = recipe.cuisine?.toLowerCase()
      const matches = recipeCuisine === dbCuisine.toLowerCase()
      if (!matches) {
        console.log(`Recipe ${recipe.recipe_name} cuisine "${recipeCuisine}" doesn't match "${dbCuisine}"`)
      }
      return matches
    })
    
    console.log(`Filtered ${filtered.length} recipes for cuisine "${dbCuisine}" from ${allRecipes.length} total recipes`)
    return filtered
  }, [allRecipes, selectedCuisine])
  
  // Create nutritionData object with filtered recipes
  const nutritionData = filteredRecipes.length > 0 ? { recipes: filteredRecipes } : null

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      // Use favorite cuisine from user preferences
      const favoriteCuisine = getFavoriteCuisine() || 'international'
      setSelectedCuisine(favoriteCuisine)
    } else {
      navigate('/login')
    }
  }, [navigate])

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
          <label className="block text-lg font-semibold text-gray-700 mb-3">
            {t('nutrition.filterByCuisine')}
          </label>
          <select
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

        {loadingWellness ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-period-pink mx-auto mb-4"></div>
            <p className="text-gray-600">Loading nutrition data...</p>
          </div>
        ) : filteredRecipes && filteredRecipes.length > 0 ? (
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
                          <p className="font-semibold mb-2">{t('nutrition.nutrients')}:</p>
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
        ) : allRecipes.length > 0 ? (
          <div className="bg-white rounded-lg shadow-lg p-6 text-center">
            <p className="text-gray-600">No recipes available for the selected cuisine.</p>
            <p className="text-sm text-gray-500 mt-2">Try selecting a different cuisine.</p>
          </div>
        ) : (
          <div className="text-center py-12 bg-white rounded-lg shadow-lg">
            <p className="text-gray-600 mb-4">No nutrition data available for this phase day.</p>
            <p className="text-sm text-gray-500">
              Data will be available once cycle predictions are generated.
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

