import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCurrentPhase, getNutritionData } from '../utils/api'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { ArrowLeft } from 'lucide-react'
import { getUserLanguage } from '../utils/userPreferences'

const Nutrition = () => {
  const [user, setUser] = useState(null)
  const [currentPhase, setCurrentPhase] = useState(null)
  const [nutritionData, setNutritionData] = useState(null)
  const [selectedCuisine, setSelectedCuisine] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      setSelectedCuisine(parsedUser.favorite_cuisine || 'international')
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

  useEffect(() => {
    const fetchData = async () => {
      if (!user) return

      setLoading(true)
      try {
        // Get today's phase
        const phase = await getCurrentPhase()
        setCurrentPhase(phase)

        // Get nutrition data - backend will automatically use today's phase-day ID
        const language = getUserLanguage()
        const data = await getNutritionData(null, language, selectedCuisine) // No phaseDayId needed
        setNutritionData(data)
      } catch (error) {
        console.error('Failed to fetch nutrition data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [user, selectedCuisine])

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
              <span>Back to Dashboard</span>
            </button>
            <h1 className="text-2xl font-bold text-period-pink">Nutrition</h1>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-4">Today's Nourishment</h2>
          {currentPhase && (
            <p className="text-2xl text-gray-700 font-semibold mb-4">
              Current Phase: <span className="text-period-pink capitalize">{currentPhase.phase}</span> - Day <span className="text-period-pink">{currentPhase.phase_day_id || currentPhase.id}</span>
            </p>
          )}
          
          {/* Key Nutrients Section - Get from first recipe only */}
          {!loading && nutritionData?.recipes && nutritionData.recipes.length > 0 && (() => {
            const firstRecipe = nutritionData.recipes[0]
            if (firstRecipe.nutrients && typeof firstRecipe.nutrients === 'object') {
              const keyNutrients = Object.keys(firstRecipe.nutrients).slice(0, 3)
              
              return keyNutrients.length > 0 ? (
                <div className="mb-6 p-4 bg-blue-50 rounded-lg border-l-4 border-blue-400">
                  <p className="text-lg font-semibold text-gray-800 mb-2">
                    We need to work on these nutrients:
                  </p>
                  <div className="flex flex-wrap gap-3">
                    {keyNutrients.map((nutrient, idx) => (
                      <span key={idx} className="px-3 py-1 bg-white rounded-full text-sm font-semibold text-blue-700 border border-blue-300 capitalize">
                        {nutrient}
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
            Filter by Cuisine
          </label>
          <select
            value={selectedCuisine}
            onChange={(e) => setSelectedCuisine(e.target.value)}
            className="px-4 py-3 text-base border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
          >
            <option value="international">International</option>
            <option value="south_indian">South Indian</option>
            <option value="north_indian">North Indian</option>
            <option value="gujarati">Gujarati</option>
          </select>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-period-pink mx-auto mb-4"></div>
            <p className="text-gray-600">Loading nutrition data...</p>
          </div>
        ) : nutritionData ? (
          <div className="space-y-6">
            {/* Recipes */}
            {nutritionData.recipes && nutritionData.recipes.length > 0 ? (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-2xl font-bold mb-4">Recipes you can try to boost these nutrients</h3>
                <div className="space-y-6">
                  {nutritionData.recipes.slice(0, 3).map((recipe, index) => (
                    <div key={recipe.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-md transition">
                      <h4 className="text-xl font-semibold mb-4">
                        Recipe {index + 1}: {recipe.recipe_name}
                      </h4>
                      
                      {recipe.serves && (
                        <p className="text-gray-700 mb-4">
                          <span className="font-semibold">Serves:</span> {recipe.serves}
                        </p>
                      )}

                      {recipe.ingredients && Array.isArray(recipe.ingredients) && recipe.ingredients.length > 0 && (
                        <div className="mb-4">
                          <p className="font-semibold mb-2">Ingredients:</p>
                          <ul className="list-disc list-inside text-gray-700 space-y-1">
                            {recipe.ingredients.map((ing, idx) => (
                              <li key={idx}>{ing}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {recipe.steps && Array.isArray(recipe.steps) && recipe.steps.length > 0 && (
                        <div className="mb-4">
                          <p className="font-semibold mb-2">Steps:</p>
                          <ol className="list-decimal list-inside text-gray-700 space-y-2 ml-4">
                            {recipe.steps.map((step, idx) => (
                              <li key={idx} className="mb-1">{step}</li>
                            ))}
                          </ol>
                        </div>
                      )}

                      {recipe.nutrients && typeof recipe.nutrients === 'object' && (
                        <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                          <p className="font-semibold mb-2">Nutrients:</p>
                          <div className="flex gap-3 text-sm overflow-x-auto">
                            {Object.entries(recipe.nutrients).map(([key, value]) => (
                              <span key={key} className="flex gap-1 whitespace-nowrap">
                                <span className="text-gray-600 capitalize">{key}:</span>
                                <span className="font-semibold">{String(value)}</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow-lg p-6 text-center">
                <p className="text-gray-600">No recipes available for this phase day and cuisine.</p>
              </div>
            )}
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

