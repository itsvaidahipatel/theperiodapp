import { useState, useEffect } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { useTranslation } from '../utils/translations'
import { getSelectedLanguage } from '../utils/userPreferences'

const SimpleAuthComponent = ({ onSubmit, isLogin = false, error, loading }) => {
  // For login page, use saved language. For register page, use selectedLanguage
  const { t } = useTranslation(isLogin)
  const selectedLanguage = getSelectedLanguage()
  
  const BLEEDING_OPTIONS = [2, 3, 4, 5, 6, 7, 8] // 8 = "8+"
  const CYCLE_LENGTH_OPTIONS = [21, 24, 28, 30, 32, 35, 40, 45]

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    last_period_date: '',
    avg_bleeding_days: 5,
    cycle_length: 28,
    allergies: [],
    language: selectedLanguage,
    favorite_cuisine: '',
    favorite_exercise: '',
    interests: [],
  })
  const [showPassword, setShowPassword] = useState(false)

  // Update language when selected language changes
  useEffect(() => {
    const handleLanguageChange = () => {
      const newLanguage = getSelectedLanguage()
      setFormData(prev => ({
        ...prev,
        language: newLanguage
      }))
    }
    
    window.addEventListener('languageChanged', handleLanguageChange)
    return () => window.removeEventListener('languageChanged', handleLanguageChange)
  }, [])

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'cycle_length' ? (value === '' ? 28 : parseInt(value, 10)) : value,
    }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const submitData = { ...formData }
    if (!isLogin) {
      const cl = submitData.cycle_length
      submitData.cycle_length = Math.min(45, Math.max(21, typeof cl === 'number' ? cl : (parseInt(cl, 10) || 28)))
      submitData.avg_bleeding_days = Math.min(8, Math.max(2, parseInt(submitData.avg_bleeding_days, 10) || 5))
    }
    if (!submitData.last_period_date) delete submitData.last_period_date
    if (!submitData.favorite_cuisine) delete submitData.favorite_cuisine
    if (!submitData.favorite_exercise) delete submitData.favorite_exercise
    if (submitData.allergies.length === 0) delete submitData.allergies
    if (submitData.interests.length === 0) delete submitData.interests
    onSubmit(submitData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
      {!isLogin && (
        <div>
          <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
            {t('auth.name')}
          </label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            className="w-full px-4 py-3 sm:py-2.5 text-base sm:text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
          />
        </div>
      )}

      <div>
        <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
          {t('auth.email')}
        </label>
        <input
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          required
          autoComplete="email"
          className="w-full px-4 py-3 sm:py-2.5 text-base sm:text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
          {t('auth.password')}
        </label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            minLength={6}
            autoComplete={isLogin ? "current-password" : "new-password"}
            className="w-full px-4 py-3 sm:py-2.5 text-base sm:text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent pr-12"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 p-1 touch-manipulation"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <EyeOff className="h-5 w-5 sm:h-4 sm:w-4" /> : <Eye className="h-5 w-5 sm:h-4 sm:w-4" />}
          </button>
        </div>
      </div>

      {!isLogin && (
        <>
          <div>
            <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
              {t('auth.periodStartDate')} <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              name="last_period_date"
              value={formData.last_period_date}
              onChange={handleChange}
              required
              max={new Date().toISOString().split('T')[0]}
              className="w-full px-4 py-3 sm:py-2.5 text-base sm:text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
              {t('auth.typicalBleedingLength')}
            </label>
            <div className="flex flex-wrap gap-2">
              {BLEEDING_OPTIONS.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setFormData((prev) => ({ ...prev, avg_bleeding_days: n }))}
                  className={`px-4 py-2 rounded-lg font-medium transition ${
                    formData.avg_bleeding_days === n
                      ? 'bg-period-pink text-white ring-2 ring-period-pink ring-offset-1'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {n === 8 ? '8+' : n}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1.5">{t('auth.typicalBleedingLengthHelp')}</p>
          </div>

          <div>
            <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
              {t('auth.cycleLength')} <span className="text-red-500">*</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {CYCLE_LENGTH_OPTIONS.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setFormData((prev) => ({ ...prev, cycle_length: n }))}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition ${
                    formData.cycle_length === n
                      ? 'bg-period-pink text-white ring-2 ring-period-pink ring-offset-1'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1.5">{t('auth.cycleLengthHelp')}</p>
          </div>

          <div className="space-y-4 pt-2">
            <div>
              <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
                {t('auth.language')}
              </label>
              <select
                name="language"
                value={formData.language}
                onChange={handleChange}
                className="w-full px-4 py-3 sm:py-2.5 text-base sm:text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent bg-white"
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="gu">Gujarati</option>
              </select>
            </div>

            <div>
              <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
                {t('auth.favoriteCuisine')}
              </label>
              <select
                name="favorite_cuisine"
                value={formData.favorite_cuisine}
                onChange={handleChange}
                className="w-full px-4 py-3 sm:py-2.5 text-base sm:text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent bg-white"
              >
                <option value="">Select Cuisine</option>
                <option value="international">International</option>
                <option value="south_indian">South Indian</option>
                <option value="north_indian">North Indian</option>
                <option value="gujarati">Gujarati</option>
              </select>
            </div>

            <div>
              <label className="block text-sm sm:text-base font-medium text-gray-700 mb-2">
                {t('auth.favoriteExercise')}
              </label>
              <select
                name="favorite_exercise"
                value={formData.favorite_exercise}
                onChange={handleChange}
                className="w-full px-4 py-3 sm:py-2.5 text-base sm:text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent bg-white"
              >
                <option value="">Select Exercise Category</option>
                <option value="Yoga">Yoga</option>
                <option value="Cardio">Cardio</option>
                <option value="Strength">Strength</option>
                <option value="Mind">Mind</option>
                <option value="Stretching">Stretching</option>
              </select>
            </div>
          </div>
        </>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm sm:text-base">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-period-pink text-white py-3.5 sm:py-3 rounded-lg font-semibold text-base sm:text-sm hover:bg-opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed touch-manipulation active:scale-[0.98]"
      >
        {loading ? t('common.loading') : isLogin ? t('auth.loginButton') : t('auth.registerButton')}
      </button>
    </form>
  )
}

export default SimpleAuthComponent

