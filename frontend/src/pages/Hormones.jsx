import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import { useDataContext } from '../context/DataContext'
import { useCalendarCache } from '../context/CalendarCacheContext'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import LoadingSpinner from '../components/LoadingSpinner'
import { ArrowLeft, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { getUserLanguage, getLocalizedText } from '../utils/userPreferences'
import { useTranslation } from '../utils/translations'
import { translateHormoneLevel } from '../utils/translateHelpers'
import { getHormonesData } from '../utils/api'

const Hormones = () => {
  const { t } = useTranslation()
  const { wellnessData, loadingWellness } = useDataContext()
  const { cachedPhaseMap, cachedWellnessData } = useCalendarCache()
  const [user, setUser] = useState(null)
  const [language, setLanguage] = useState('en')
  const [localHormonesData, setLocalHormonesData] = useState(null)
  const [fetchingData, setFetchingData] = useState(false)
  const navigate = useNavigate()

  // Get today's phase from calendar cache (FAST - no API call needed!)
  // Use same date format as dashboard: format(new Date(), 'yyyy-MM-dd')
  const today = format(new Date(), 'yyyy-MM-dd') // System date in YYYY-MM-DD format (e.g., "2026-02-08")
  const todayPhaseData = cachedPhaseMap[today]
  const currentPhase = todayPhaseData ? {
    phase: todayPhaseData.phase,
    phase_day_id: todayPhaseData.phase_day_id,
    id: todayPhaseData.phase_day_id
  } : null
  
  // Log for debugging
  useEffect(() => {
    console.log(`📅 Hormones page: Using TODAY's date: ${today}, phase_day_id: ${currentPhase?.phase_day_id || 'NOT FOUND'}`)
  }, [today, currentPhase?.phase_day_id])

  // Check if we have preloaded wellness data for today's phase_day_id
  const preloadedHormones = cachedWellnessData?.phaseDayId === currentPhase?.phase_day_id 
    ? cachedWellnessData?.hormones 
    : null

  // Extract data from context - prioritize preloaded data, then context, then local state
  const hormonesData = preloadedHormones || wellnessData?.hormones || localHormonesData

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      setLanguage(parsedUser.language || 'en')
    } else {
      navigate('/login')
    }
  }, [navigate])

  // Listen for language changes (when user updates profile)
  useEffect(() => {
    const handleLanguageChange = () => {
      const userLanguage = getUserLanguage()
      setLanguage(userLanguage)
    }
    
    // Listen for custom language change event
    window.addEventListener('languageChanged', handleLanguageChange)
    // Also check on focus in case language was updated in another tab
    window.addEventListener('focus', handleLanguageChange)
    
    return () => {
      window.removeEventListener('languageChanged', handleLanguageChange)
      window.removeEventListener('focus', handleLanguageChange)
    }
  }, [])

  // Fetch hormones data using phase_day_id from calendar cache (SIMPLE & FAST!)
  // Only fetch if we don't have preloaded data
  useEffect(() => {
    // Check if we already have preloaded data
    if (preloadedHormones) {
      console.log('✅ Hormones page: Using preloaded data from calendar cache')
      setLocalHormonesData(preloadedHormones)
      return
    }
    
    // Only fetch if we have a phase_day_id from calendar and haven't fetched yet
    if (currentPhase?.phase_day_id && !localHormonesData && !fetchingData && !wellnessData?.hormones) {
      console.log(`🚀 Hormones page: Starting fetch for phase_day_id: ${currentPhase.phase_day_id}`)
      console.log(`   Current state: today=${today}, hasPhaseData=${!!todayPhaseData}, phase_day_id=${currentPhase.phase_day_id}`)
      
      setFetchingData(true)
      
      const fetchHormones = async () => {
        const timeoutId = setTimeout(() => {
          console.warn('⚠️ Hormones page: Fetch timeout after 10 seconds - clearing loading state')
          setFetchingData(false)
        }, 10000) // 10 second timeout
        
        try {
          console.log(`📞 Hormones page: Calling getHormonesData('${currentPhase.phase_day_id}')...`)
          
          // Add timeout to the API call
          const hormonesPromise = getHormonesData(currentPhase.phase_day_id)
          const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('getHormonesData timeout after 8 seconds')), 8000)
          )
          
          const hormones = await Promise.race([hormonesPromise, timeoutPromise])
          
          clearTimeout(timeoutId)
          
          console.log(`📥 Hormones page: Received response:`, hormones ? 'has data' : 'no data')
          
          if (hormones) {
            setLocalHormonesData(hormones)
            console.log('✅ Hormones page: Successfully set hormones data')
          } else {
            console.warn('⚠️ Hormones page: No hormones data in response')
          }
        } catch (error) {
          clearTimeout(timeoutId)
          console.error('❌ Hormones page: Error fetching hormones data:', error.message || error)
          // Don't set data, but clear loading state
        } finally {
          console.log('🏁 Hormones page: Fetch complete, setting fetchingData=false')
          setFetchingData(false)
        }
      }
      fetchHormones()
    } else {
      // Log why we're not fetching
      if (preloadedHormones) {
        console.log(`⏸️ Hormones page: Not fetching - using preloaded data`)
      } else if (!currentPhase?.phase_day_id) {
        console.log(`⏸️ Hormones page: Not fetching - no phase_day_id. currentPhase:`, currentPhase)
      } else if (localHormonesData) {
        console.log(`⏸️ Hormones page: Not fetching - already have localHormonesData`)
      } else if (fetchingData) {
        console.log(`⏸️ Hormones page: Not fetching - already fetching`)
      } else if (wellnessData?.hormones) {
        console.log(`⏸️ Hormones page: Not fetching - already have wellnessData.hormones`)
      }
    }
  }, [currentPhase?.phase_day_id, localHormonesData, fetchingData, wellnessData?.hormones, preloadedHormones, today, todayPhaseData])

  const getTrendIcon = (trend) => {
    if (trend === 'up' || trend === '↑') return <TrendingUp className="h-5 w-5 text-green-600" />
    if (trend === 'down' || trend === '↓') return <TrendingDown className="h-5 w-5 text-red-600" />
    return <Minus className="h-5 w-5 text-gray-600" />
  }

  // Get today's data (either from today field or hormonesData itself for backward compatibility)
  const getTodayData = () => {
    if (!hormonesData) return null
    if (hormonesData.today) return hormonesData.today
    if (!hormonesData.today && !hormonesData.history) {
      // Check if it's an error message
      if (hormonesData.message) return null
      // If data is directly in hormonesData (backward compatibility)
      if (hormonesData.estrogen || hormonesData.progesterone) {
        return hormonesData
      }
    }
    return null
  }

  const todayData = getTodayData()
  const expectedPhaseDayId = hormonesData?.phase_day_id || currentPhase?.phase_day_id || currentPhase?.id

  // Debug logging
  useEffect(() => {
    console.log('📊 Hormones page state:', {
      today,
      todayPhaseData,
      currentPhase,
      hasHormonesData: !!hormonesData,
      fetchingData,
      loadingWellness
    })
  }, [today, todayPhaseData, currentPhase, hormonesData, fetchingData, loadingWellness])

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
            <h1 className="text-2xl font-bold text-period-pink">{t('hormones.title')}</h1>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-4">{t('hormones.title')}</h2>
          {currentPhase && currentPhase.phase && (
            <p className="text-2xl text-gray-700 font-semibold">
              {t('hormones.currentPhase')}: <span className="text-period-pink capitalize">{t(`phase.${currentPhase.phase.toLowerCase()}`)}</span> - {t('dashboard.day')} <span className="text-period-pink">{currentPhase.phase_day_id || currentPhase.id}</span>
            </p>
          )}
        </div>

        {(loadingWellness || fetchingData) ? (
          <LoadingSpinner message="Loading hormone data..." />
        ) : !currentPhase || !currentPhase.phase_day_id ? (
          <div className="text-center py-12 bg-white rounded-lg shadow-lg">
            <p className="text-gray-600 text-lg mb-2">Log your period dates to get these details</p>
          </div>
        ) : todayData && todayData !== null ? (
          <div className="space-y-6">
            {/* Mood Insights, Energy Insights, Best Work Type - Side by Side */}
            <div className="grid md:grid-cols-3 gap-6">
              {/* Mood Insights - Multilingual */}
              {todayData.mood && (
                <div className="bg-blue-50 rounded-lg p-6 border-l-4 border-blue-400">
                  <h3 className="text-lg font-semibold mb-3 text-blue-800">{t('hormones.moodLevel')}</h3>
                  <p className="text-gray-700">{getLocalizedText(todayData.mood, language) || 'N/A'}</p>
                </div>
              )}

              {/* Energy Insights - Multilingual */}
              {todayData.energy && (
                <div className="bg-green-50 rounded-lg p-6 border-l-4 border-green-400">
                  <h3 className="text-lg font-semibold mb-3 text-green-800">{t('hormones.energyLevel')}</h3>
                  <p className="text-gray-700">{getLocalizedText(todayData.energy, language) || 'N/A'}</p>
                </div>
              )}

              {/* Best Work Type - Multilingual */}
              {todayData.best_work_type && (
                <div className="bg-purple-50 rounded-lg p-6 border-l-4 border-purple-400">
                  <h3 className="text-lg font-semibold mb-3 text-purple-800">{t('hormones.bestWorkType')}</h3>
                  <p className="text-gray-700">{getLocalizedText(todayData.best_work_type, language) || 'N/A'}</p>
                </div>
              )}
            </div>

            {/* Brain Note - Full Width Below */}
            {todayData.brain_note && (
              <div className="bg-yellow-50 rounded-lg p-6 border-l-4 border-yellow-400">
                <h3 className="text-lg font-semibold mb-3 text-yellow-800">{t('hormones.brainNote')}</h3>
                <p className="text-gray-700">{getLocalizedText(todayData.brain_note, language) || 'N/A'}</p>
              </div>
            )}

            {/* Today's Hormone Values with Trends */}
            <div className="grid md:grid-cols-2 gap-6">
              {[
                { name: t('hormones.estrogen'), value: todayData.estrogen, trend: todayData.estrogen_trend },
                { name: t('hormones.progesterone'), value: todayData.progesterone, trend: todayData.progesterone_trend },
                { name: t('hormones.fsh'), value: todayData.fsh, trend: todayData.fsh_trend },
                { name: t('hormones.lh'), value: todayData.lh, trend: todayData.lh_trend },
              ].map((hormone) => (
                <div key={hormone.name} className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-xl font-semibold text-gray-800">{hormone.name}</h3>
                    {hormone.trend && getTrendIcon(hormone.trend)}
                  </div>
                  {hormone.value !== null && hormone.value !== undefined && hormone.value !== '' && (
                    <p className="text-3xl font-bold text-period-pink">{translateHormoneLevel(hormone.value)}</p>
                  )}
                  {(!hormone.value || hormone.value === '') && (
                    <p className="text-gray-500">Data not available</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-12 bg-white rounded-lg shadow-lg">
            <p className="text-gray-600 mb-2">No hormone data available for this phase day.</p>
            {expectedPhaseDayId && (
              <p className="text-sm text-gray-500 mb-4">
                Expected phase-day ID: <span className="font-semibold">{expectedPhaseDayId}</span>
              </p>
            )}
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 max-w-2xl mx-auto">
              <p className="text-sm text-yellow-800 mb-2">
                <strong>Note:</strong> The hormones_data table needs to be populated with data for each phase-day ID.
              </p>
              <p className="text-xs text-yellow-700">
                You need to insert hormone data for phase-day IDs like: p1-p12, f1-f30, o1-o8, l1-l25
              </p>
            </div>
          </div>
        )}

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

export default Hormones
