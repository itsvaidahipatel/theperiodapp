import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { updateUserProfile, changePassword, getNotificationPreferences, updateNotificationPreferences } from '../utils/api'
import { Save, Lock, Bell } from 'lucide-react'
import { updateUserData } from '../utils/userPreferences'
import { useTranslation } from '../utils/translations'

const Profile = () => {
  const { t } = useTranslation()
  const [user, setUser] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    language: 'en',
    favorite_cuisine: '',
    favorite_exercise: '',
  })
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [notificationData, setNotificationData] = useState({
    email_notifications_enabled: true,
    phase_transitions: true,
    period_reminders: true,
    reminder_days_before: 2,
  })
  const [activeTab, setActiveTab] = useState('profile')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      setFormData({
        name: parsedUser.name || '',
        language: parsedUser.language || 'en',
        favorite_cuisine: parsedUser.favorite_cuisine || '',
        favorite_exercise: parsedUser.favorite_exercise || '',
      })
      
      // Load notification preferences
      loadNotificationPreferences()
    } else {
      navigate('/login')
    }
  }, [navigate])
  
  const loadNotificationPreferences = async () => {
    try {
      const prefs = await getNotificationPreferences()
      setNotificationData({
        email_notifications_enabled: prefs.email_notifications_enabled ?? true,
        phase_transitions: prefs.notification_preferences?.phase_transitions ?? true,
        period_reminders: prefs.notification_preferences?.period_reminders ?? true,
        reminder_days_before: prefs.notification_preferences?.reminder_days_before ?? 2,
      })
    } catch (err) {
      console.error('Failed to load notification preferences:', err)
    }
  }

  const handleProfileChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handlePasswordChange = (e) => {
    const { name, value } = e.target
    setPasswordData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }
  
  const handleNotificationChange = (e) => {
    const { name, value, type, checked } = e.target
    setNotificationData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const handleProfileSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const updatedUser = await updateUserProfile(formData)
      updateUserData(updatedUser) // Use global utility
      setUser(updatedUser)
      setSuccess(t('profile.saved'))
    } catch (err) {
      setError(err.message || 'Failed to update profile')
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess('')

    if (passwordData.new_password !== passwordData.confirm_password) {
      setError('New passwords do not match')
      setLoading(false)
      return
    }

    if (passwordData.new_password.length < 6) {
      setError('Password must be at least 6 characters')
      setLoading(false)
      return
    }

    try {
      await changePassword({
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      })
      setSuccess(t('profile.passwordChanged'))
      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: '',
      })
    } catch (err) {
      setError(err.message || 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }
  
  const handleNotificationSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess('')
    
    try {
      await updateNotificationPreferences({
        email_notifications_enabled: notificationData.email_notifications_enabled,
        notification_preferences: {
          phase_transitions: notificationData.phase_transitions,
          period_reminders: notificationData.period_reminders,
          reminder_days_before: parseInt(notificationData.reminder_days_before),
        }
      })
      setSuccess(t('profile.notificationsSaved'))
    } catch (err) {
      setError(err.message || 'Failed to update notification preferences')
    } finally {
      setLoading(false)
    }
  }

  if (!user) {
    return <div>{t('common.loading')}</div>
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-8">{t('profile.title')}</h1>

        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b">
          <button
            onClick={() => setActiveTab('profile')}
            className={`px-4 py-2 font-semibold border-b-2 transition ${
              activeTab === 'profile'
                ? 'border-period-pink text-period-pink'
                : 'border-transparent text-gray-600 hover:text-gray-800'
            }`}
          >
            {t('profile.title')}
          </button>
          <button
            onClick={() => setActiveTab('password')}
            className={`px-4 py-2 font-semibold border-b-2 transition ${
              activeTab === 'password'
                ? 'border-period-pink text-period-pink'
                : 'border-transparent text-gray-600 hover:text-gray-800'
            }`}
          >
            {t('profile.changePassword')}
          </button>
          <button
            onClick={() => setActiveTab('notifications')}
            className={`px-4 py-2 font-semibold border-b-2 transition ${
              activeTab === 'notifications'
                ? 'border-period-pink text-period-pink'
                : 'border-transparent text-gray-600 hover:text-gray-800'
            }`}
          >
            {t('profile.notifications')}
          </button>
        </div>

        {/* Profile Tab */}
        {activeTab === 'profile' && (
          <form onSubmit={handleProfileSubmit} className="bg-white rounded-lg shadow-lg p-6 space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('profile.name')}
              </label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleProfileChange}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('profile.language')}
              </label>
              <select
                name="language"
                value={formData.language}
                onChange={handleProfileChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="gu">Gujarati</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('profile.favoriteCuisine')}
              </label>
              <select
                name="favorite_cuisine"
                value={formData.favorite_cuisine}
                onChange={handleProfileChange}
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
                {t('profile.favoriteExercise')}
              </label>
              <select
                name="favorite_exercise"
                value={formData.favorite_exercise}
                onChange={handleProfileChange}
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

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            {success && (
              <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-period-pink text-white py-3 rounded-lg font-semibold hover:bg-opacity-90 transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Save className="h-5 w-5" />
              {loading ? t('common.loading') : t('profile.save')}
            </button>
          </form>
        )}

        {/* Password Tab */}
        {activeTab === 'password' && (
          <form onSubmit={handlePasswordSubmit} className="bg-white rounded-lg shadow-lg p-6 space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('profile.currentPassword')}
              </label>
              <input
                type="password"
                name="current_password"
                value={passwordData.current_password}
                onChange={handlePasswordChange}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('profile.newPassword')}
              </label>
              <input
                type="password"
                name="new_password"
                value={passwordData.new_password}
                onChange={handlePasswordChange}
                required
                minLength={6}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('profile.confirmPassword')}
              </label>
              <input
                type="password"
                name="confirm_password"
                value={passwordData.confirm_password}
                onChange={handlePasswordChange}
                required
                minLength={6}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            {success && (
              <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-period-pink text-white py-3 rounded-lg font-semibold hover:bg-opacity-90 transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Lock className="h-5 w-5" />
              {loading ? t('common.loading') : t('profile.changePassword')}
            </button>
          </form>
        )}

        {/* Notifications Tab */}
        {activeTab === 'notifications' && (
          <form onSubmit={handleNotificationSubmit} className="bg-white rounded-lg shadow-lg p-6 space-y-6">
            <div>
              <p className="text-sm text-gray-600 mb-6">{t('profile.notificationsDescription')}</p>
            </div>
            
            {/* Master Toggle */}
            <div className="border-b pb-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('profile.emailNotificationsEnabled')}
                  </label>
                  <p className="text-xs text-gray-500">{t('profile.emailNotificationsEnabledDesc')}</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="email_notifications_enabled"
                    checked={notificationData.email_notifications_enabled}
                    onChange={handleNotificationChange}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-period-pink/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-period-pink"></div>
                </label>
              </div>
            </div>
            
            {/* Phase Transitions */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('profile.phaseTransitions')}
                  </label>
                  <p className="text-xs text-gray-500">{t('profile.phaseTransitionsDesc')}</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="phase_transitions"
                    checked={notificationData.phase_transitions}
                    onChange={handleNotificationChange}
                    disabled={!notificationData.email_notifications_enabled}
                    className="sr-only peer"
                  />
                  <div className={`w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-period-pink/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-period-pink ${!notificationData.email_notifications_enabled ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                </label>
              </div>
              
              {/* Period Reminders */}
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('profile.periodReminders')}
                  </label>
                  <p className="text-xs text-gray-500">{t('profile.periodRemindersDesc')}</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="period_reminders"
                    checked={notificationData.period_reminders}
                    onChange={handleNotificationChange}
                    disabled={!notificationData.email_notifications_enabled}
                    className="sr-only peer"
                  />
                  <div className={`w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-period-pink/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-period-pink ${!notificationData.email_notifications_enabled ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                </label>
              </div>
              
              {/* Reminder Days Before */}
              {notificationData.period_reminders && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('profile.reminderDaysBefore')}
                  </label>
                  <p className="text-xs text-gray-500 mb-2">{t('profile.reminderDaysBeforeDesc')}</p>
                  <select
                    name="reminder_days_before"
                    value={notificationData.reminder_days_before}
                    onChange={handleNotificationChange}
                    disabled={!notificationData.email_notifications_enabled || !notificationData.period_reminders}
                    className={`w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent ${!notificationData.email_notifications_enabled || !notificationData.period_reminders ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <option value={1}>1 day before</option>
                    <option value={2}>2 days before</option>
                    <option value={3}>3 days before</option>
                    <option value={4}>4 days before</option>
                    <option value={5}>5 days before</option>
                  </select>
                </div>
              )}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            {success && (
              <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-period-pink text-white py-3 rounded-lg font-semibold hover:bg-opacity-90 transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Bell className="h-5 w-5" />
              {loading ? t('common.loading') : t('profile.save')}
            </button>
          </form>
        )}

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

export default Profile
