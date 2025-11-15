import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Navbar from '../components/Navbar'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { getCurrentPhase, getHormonesData, getNutritionData, getExerciseData } from '../utils/api'
import { TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react'

const Wellness = () => {
  const [user, setUser] = useState(null)
  const [currentPhase, setCurrentPhase] = useState(null)
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'hormones')
  const [hormonesData, setHormonesData] = useState(null)
  const [nutritionData, setNutritionData] = useState(null)
  const [exerciseData, setExerciseData] = useState(null)
  const [selectedCuisine, setSelectedCuisine] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedItems, setExpandedItems] = useState({})
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

  useEffect(() => {
    const fetchCurrentPhase = async () => {
      try {
        const phase = await getCurrentPhase()
        setCurrentPhase(phase)
        
        if (phase?.phase_day_id) {
          await fetchWellnessData(phase.phase_day_id)
        }
      } catch (error) {
        console.error('Failed to fetch current phase:', error)
      }
    }

    fetchCurrentPhase()
  }, [])

  useEffect(() => {
    if (currentPhase?.phase_day_id) {
      fetchWellnessData(currentPhase.phase_day_id)
    }
  }, [selectedCuisine, selectedCategory, currentPhase?.phase_day_id])

  const fetchWellnessData = async (phaseDayId) => {
    if (!user) return

    setLoading(true)
    const language = user.language || 'en'

    try {
      if (activeTab === 'hormones') {
        const data = await getHormonesData(phaseDayId)
        setHormonesData(data)
      } else if (activeTab === 'nutrition') {
        const data = await getNutritionData(phaseDayId, language, selectedCuisine)
        setNutritionData(data)
      } else if (activeTab === 'exercise') {
        const data = await getExerciseData(phaseDayId, language, selectedCategory)
        setExerciseData(data)
      }
    } catch (error) {
      console.error('Failed to fetch wellness data:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = (id) => {
    setExpandedItems((prev) => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  const getTrendIcon = (trend) => {
    if (trend === 'up') return <TrendingUp className="h-4 w-4 text-green-600" />
    if (trend === 'down') return <TrendingDown className="h-4 w-4 text-red-600" />
    return <Minus className="h-4 w-4 text-gray-600" />
  }

  if (!user) {
    return <div>Loading...</div>
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-4">Wellness Guide</h1>
        {currentPhase && (
          <p className="text-gray-600 mb-6">
            Current Phase: <span className="font-semibold">{currentPhase.phase}</span> - Day {currentPhase.phase_day_id}
          </p>
        )}

        <SafetyDisclaimer />

        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b">
          {['hormones', 'nutrition', 'exercise'].map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab)
                if (currentPhase?.phase_day_id) {
                  fetchWellnessData(currentPhase.phase_day_id)
                }
              }}
              className={`px-6 py-3 font-semibold border-b-2 transition capitalize ${
                activeTab === tab
                  ? 'border-period-pink text-period-pink'
                  : 'border-transparent text-gray-600 hover:text-gray-800'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Hormones Tab */}
        {activeTab === 'hormones' && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-bold mb-6">Your Hormones Today</h2>
            {loading ? (
              <div className="text-center py-8">Loading...</div>
            ) : hormonesData ? (
              <div className="space-y-6">
                {hormonesData.energy_level && (
                  <div className="bg-period-pink bg-opacity-10 rounded-lg p-4">
                    <p className="font-semibold text-lg">Energy Level: {hormonesData.energy_level}</p>
                  </div>
                )}

                <div className="grid md:grid-cols-2 gap-4">
                  {[
                    { name: 'Estrogen', value: hormonesData.estrogen, trend: hormonesData.estrogen_trend },
                    { name: 'Progesterone', value: hormonesData.progesterone, trend: hormonesData.progesterone_trend },
                    { name: 'FSH', value: hormonesData.fsh, trend: hormonesData.fsh_trend },
                    { name: 'LH', value: hormonesData.lh, trend: hormonesData.lh_trend },
                  ].map((hormone) => (
                    <div key={hormone.name} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-semibold">{hormone.name}</span>
                        {hormone.trend && getTrendIcon(hormone.trend)}
                      </div>
                      {hormone.value !== null && hormone.value !== undefined && (
                        <p className="text-2xl font-bold text-period-pink">{hormone.value}</p>
                      )}
                    </div>
                  ))}
                </div>

                {hormonesData.emotional_summary && (
                  <div className="bg-purple-50 rounded-lg p-4">
                    <h3 className="font-semibold mb-2">Emotional Summary</h3>
                    <p className="text-gray-700">{hormonesData.emotional_summary}</p>
                  </div>
                )}

                {hormonesData.physical_summary && (
                  <div className="bg-teal-50 rounded-lg p-4">
                    <h3 className="font-semibold mb-2">Physical Summary</h3>
                    <p className="text-gray-700">{hormonesData.physical_summary}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No hormone data available for this phase day.</p>
                <p className="text-sm mt-2">Data will be available once cycle predictions are generated.</p>
              </div>
            )}
          </div>
        )}

        {/* Nutrition Tab */}
        {activeTab === 'nutrition' && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Today's Nourishment</h2>
              <select
                value={selectedCuisine}
                onChange={(e) => setSelectedCuisine(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink"
              >
                <option value="international">International</option>
                <option value="south_indian">South Indian</option>
                <option value="north_indian">North Indian</option>
                <option value="gujarati">Gujarati</option>
              </select>
            </div>

            {loading ? (
              <div className="text-center py-8">Loading...</div>
            ) : nutritionData ? (
              <div className="space-y-6">
                {nutritionData.wholefoods && nutritionData.wholefoods.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3">Whole Foods</h3>
                    <div className="flex flex-wrap gap-3">
                      {nutritionData.wholefoods.map((food, index) => (
                        <div
                          key={index}
                          className="bg-period-mint bg-opacity-20 rounded-lg px-4 py-2"
                        >
                          <p className="font-semibold">{food.name}</p>
                          {food.benefit && (
                            <p className="text-sm text-gray-600">{food.benefit}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {nutritionData.recipes && nutritionData.recipes.length > 0 ? (
                  <div>
                    <h3 className="text-lg font-semibold mb-3">Recipes</h3>
                    <div className="space-y-4">
                      {nutritionData.recipes.map((recipe) => (
                        <div key={recipe.id} className="border border-gray-200 rounded-lg p-4">
                          <h4 className="font-semibold text-lg mb-2">{recipe.recipe_name}</h4>
                          {recipe.image_url && (
                            <img
                              src={recipe.image_url}
                              alt={recipe.recipe_name}
                              className="w-full h-48 object-cover rounded-lg mb-3"
                            />
                          )}
                          {recipe.ingredients && (
                            <div>
                              <p className="font-semibold mb-1">Ingredients:</p>
                              <ul className="list-disc list-inside text-sm text-gray-600">
                                {recipe.ingredients.map((ing, idx) => (
                                  <li key={idx}>{ing}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {recipe.steps && (
                            <div className="mt-3">
                              <button
                                onClick={() => toggleExpand(`recipe-${recipe.id}`)}
                                className="flex items-center gap-2 text-period-pink font-semibold"
                              >
                                {expandedItems[`recipe-${recipe.id}`] ? (
                                  <ChevronUp className="h-4 w-4" />
                                ) : (
                                  <ChevronDown className="h-4 w-4" />
                                )}
                                Steps
                              </button>
                              {expandedItems[`recipe-${recipe.id}`] && (
                                <ol className="list-decimal list-inside text-sm text-gray-600 mt-2">
                                  {recipe.steps.map((step, idx) => (
                                    <li key={idx} className="mb-1">{step}</li>
                                  ))}
                                </ol>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>No recipes available for this phase day and cuisine.</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No nutrition data available for this phase day.</p>
              </div>
            )}
          </div>
        )}

        {/* Exercise Tab */}
        {activeTab === 'exercise' && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Move with Your Cycle</h2>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink"
              >
                <option value="">All Categories</option>
                <option value="Yoga">Yoga</option>
                <option value="Cardio">Cardio</option>
                <option value="Strength">Strength</option>
                <option value="Mind">Mind</option>
                <option value="Stretching">Stretching</option>
              </select>
            </div>

            {loading ? (
              <div className="text-center py-8">Loading...</div>
            ) : exerciseData ? (
              <div className="space-y-4">
                {exerciseData.exercises && exerciseData.exercises.length > 0 ? (
                  exerciseData.exercises.map((exercise) => (
                    <div key={exercise.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <h4 className="font-semibold text-lg">{exercise.exercise_name}</h4>
                          <p className="text-sm text-gray-600">{exercise.category}</p>
                        </div>
                        {exercise.energy_level && (
                          <span className="bg-period-purple bg-opacity-20 px-3 py-1 rounded-full text-sm">
                            {exercise.energy_level} Energy
                          </span>
                        )}
                      </div>
                      {exercise.image_url && (
                        <img
                          src={exercise.image_url}
                          alt={exercise.exercise_name}
                          className="w-full h-48 object-cover rounded-lg mb-3"
                        />
                      )}
                      {exercise.description && (
                        <p className="text-gray-700 mb-3">{exercise.description}</p>
                      )}
                      {exercise.steps && exercise.steps.length > 0 && (
                        <div>
                          <button
                            onClick={() => toggleExpand(`exercise-${exercise.id}`)}
                            className="flex items-center gap-2 text-period-pink font-semibold"
                          >
                            {expandedItems[`exercise-${exercise.id}`] ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                            Steps
                          </button>
                          {expandedItems[`exercise-${exercise.id}`] && (
                            <ol className="list-decimal list-inside text-sm text-gray-600 mt-2">
                              {exercise.steps.map((step, idx) => (
                                <li key={idx} className="mb-1">{step}</li>
                              ))}
                            </ol>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>No exercises available for this phase day and category.</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No exercise data available for this phase day.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default Wellness

