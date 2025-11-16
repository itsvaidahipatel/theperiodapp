import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { useTranslation } from '../utils/translations'

const SimpleAuthComponent = ({ onSubmit, isLogin = false, error, loading }) => {
  const { t } = useTranslation()
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    last_period_date: '',
    cycle_length: 28,
    allergies: [],
    language: 'en',
    favorite_cuisine: '',
    favorite_exercise: '',
    interests: [],
  })
  const [showPassword, setShowPassword] = useState(false)
  const [showAdditionalFields, setShowAdditionalFields] = useState(false)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const submitData = { ...formData }
    
    // Clean up empty optional fields
    if (!submitData.last_period_date) delete submitData.last_period_date
    if (!submitData.favorite_cuisine) delete submitData.favorite_cuisine
    if (!submitData.favorite_exercise) delete submitData.favorite_exercise
    if (submitData.allergies.length === 0) delete submitData.allergies
    if (submitData.interests.length === 0) delete submitData.interests
    
    onSubmit(submitData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {!isLogin && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('auth.name')}
          </label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
          />
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('auth.email')}
        </label>
        <input
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
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
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent pr-10"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
          >
            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {!isLogin && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('auth.lastPeriodDate')} <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              name="last_period_date"
              value={formData.last_period_date}
              onChange={handleChange}
              required
              max={new Date().toISOString().split('T')[0]}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">{t('auth.lastPeriodDate')}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('auth.cycleLength')} <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              name="cycle_length"
              value={formData.cycle_length}
              onChange={handleChange}
              required
              min={21}
              max={35}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">{t('auth.cycleLengthHelp')}</p>
          </div>

          <button
            type="button"
            onClick={() => setShowAdditionalFields(!showAdditionalFields)}
            className="text-sm text-period-pink hover:underline"
          >
            {showAdditionalFields ? 'Hide' : 'Show'} Additional Preferences
          </button>

          {showAdditionalFields && (
            <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('auth.language')}
                </label>
                <select
                  name="language"
                  value={formData.language}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
                >
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="gu">Gujarati</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('auth.favoriteCuisine')}
                </label>
                <select
                  name="favorite_cuisine"
                  value={formData.favorite_cuisine}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
                >
                  <option value="">Select Cuisine</option>
                  <option value="international">International</option>
                  <option value="south_indian">South Indian</option>
                  <option value="north_indian">North Indian</option>
                  <option value="gujarati">Gujarati</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('auth.favoriteExercise')}
                </label>
                <select
                  name="favorite_exercise"
                  value={formData.favorite_exercise}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
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
          )}
        </>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-period-pink text-white py-3 rounded-lg font-semibold hover:bg-opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? t('common.loading') : isLogin ? t('auth.loginButton') : t('auth.registerButton')}
      </button>
    </form>
  )
}

export default SimpleAuthComponent

