import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { updateUserProfile, changePassword, getNotificationPreferences, updateNotificationPreferences, resetCycleData, resetLastPeriod, runSixMonthDiagnostic } from '../utils/api'
import { Save, Lock, Bell, RotateCcw, AlertTriangle, X } from 'lucide-react'
import { updateUserData } from '../utils/userPreferences'
import { useTranslation } from '../utils/translations'
import { useCalendarCache } from '../context/CalendarCacheContext'
import { useDataContext } from '../context/DataContext'

const Profile = () => {
  const { t } = useTranslation()
  const { clearCache } = useCalendarCache()
  const { updatePhaseMap } = useDataContext()
  const [user, setUser] = useState(null)
  const BLEEDING_OPTIONS = [2, 3, 4, 5, 6, 7, 8]
  const [formData, setFormData] = useState({
    name: '',
    language: 'en',
    favorite_cuisine: '',
    favorite_exercise: '',
    avg_bleeding_days: 5,
  })
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [notificationData, setNotificationData] = useState({
    email_notifications_enabled: true,
    upcoming_reminders: true,
    logging_reminders: true,
    health_alerts: true,
  })
  const [activeTab, setActiveTab] = useState('profile')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [showResetLastPeriodConfirm, setShowResetLastPeriodConfirm] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resettingLastPeriod, setResettingLastPeriod] = useState(false)
  const [diagnosticRunning, setDiagnosticRunning] = useState(false)
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
        avg_bleeding_days: parsedUser.avg_bleeding_days ?? 5,
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
      const notificationPrefs = prefs.notification_preferences || {}
      setNotificationData({
        email_notifications_enabled: prefs.email_notifications_enabled ?? true,
        upcoming_reminders: notificationPrefs.upcoming_reminders ?? true,
        logging_reminders: notificationPrefs.logging_reminders ?? true,
        health_alerts: notificationPrefs.health_alerts ?? true,
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
        upcoming_reminders: notificationData.upcoming_reminders,
        logging_reminders: notificationData.logging_reminders,
        health_alerts: notificationData.health_alerts,
      })
      setSuccess(t('profile.notificationsSaved'))
    } catch (err) {
      setError(err.message || 'Failed to update notification preferences')
    } finally {
      setLoading(false)
    }
  }

  const handleResetCycleData = async () => {
    setResetting(true)
    setError('')
    setSuccess('')
    
    try {
      const response = await resetCycleData()
      
      // Update local user data
      const updatedUser = { ...user, ...response.user }
      localStorage.setItem('user', JSON.stringify(updatedUser))
      setUser(updatedUser)
      
      setFormData(prev => ({ ...prev }))
      clearCache()
      updatePhaseMap({})
      sessionStorage.clear()
      window.dispatchEvent(new CustomEvent('resetAllCycles'))
      window.dispatchEvent(new CustomEvent('periodLogged'))
      setSuccess('All cycle data has been reset successfully. Your calendar and statistics are now clean.')
      setShowResetConfirm(false)
      setTimeout(() => {
        window.location.href = '/dashboard'
      }, 1500)
    } catch (err) {
      setError(err.message || 'Failed to reset cycle data')
    } finally {
      setResetting(false)
    }
  }

  const handleResetLastPeriod = async () => {
    setResettingLastPeriod(true)
    setError('')
    setSuccess('')
    
    try {
      const response = await resetLastPeriod()
      
      // Update local user data
      const updatedUser = { ...user, ...response.user }
      localStorage.setItem('user', JSON.stringify(updatedUser))
      setUser(updatedUser)
      clearCache()
      updatePhaseMap({})
      sessionStorage.clear()
      window.dispatchEvent(new CustomEvent('resetLastPeriod'))
      window.dispatchEvent(new CustomEvent('periodLogged'))
      setSuccess(`Last period (${response.deleted_period_date}) has been reset successfully. Your calendar and predictions have been updated.`)
      setShowResetLastPeriodConfirm(false)
      setTimeout(() => {
        window.location.href = '/dashboard'
      }, 1500)
    } catch (err) {
      setError(err.message || 'Failed to reset last period')
    } finally {
      setResettingLastPeriod(false)
    }
  }

  const handleRunSixMonthDiagnostic = async () => {
    setDiagnosticRunning(true)
    setError('')
    setSuccess('')
    try {
      const res = await runSixMonthDiagnostic()
      setSuccess(res?.message || 'Diagnostic complete. Check the backend terminal for [DEBUG] lines.')
    } catch (err) {
      setError(err.message || 'Diagnostic request failed')
    } finally {
      setDiagnosticRunning(false)
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

            {/* Period Settings: Typical bleeding length */}
            <div className="pt-4 border-t border-gray-200">
              <h3 className="text-sm font-semibold text-gray-800 mb-2">{t('profile.periodSettings')}</h3>
              <p className="text-xs text-gray-500 mb-3">{t('profile.typicalBleedingLengthHelp')}</p>
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
              <p className="text-sm text-gray-600 mb-6">
                Choose what email notifications you'd like to receive. You can unsubscribe at any time.
              </p>
            </div>
            
            {/* Master Toggle */}
            <div className="border-b pb-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Notifications
                  </label>
                  <p className="text-xs text-gray-500">
                    Master switch for all email notifications. Turn this off to unsubscribe from all emails.
                  </p>
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
            
            {/* Email Type Options */}
            <div className="space-y-4">
              <div className="text-sm font-semibold text-gray-700 mb-3">What would you like to receive?</div>
              
              {/* Upcoming Period Reminders */}
              <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Upcoming Period Reminders
                  </label>
                  <p className="text-xs text-gray-500">
                    Get a heads-up when your next period is approaching (7 days before, 3 days before)
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="upcoming_reminders"
                    checked={notificationData.upcoming_reminders}
                    onChange={handleNotificationChange}
                    disabled={!notificationData.email_notifications_enabled}
                    className="sr-only peer"
                  />
                  <div className={`w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-period-pink/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-period-pink ${!notificationData.email_notifications_enabled ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                </label>
              </div>
              
              {/* Period Logging Reminders */}
              <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Period Logging Reminders
                  </label>
                  <p className="text-xs text-gray-500">
                    Daily reminders during your predicted period window to log your period (stops automatically when you log)
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="logging_reminders"
                    checked={notificationData.logging_reminders}
                    onChange={handleNotificationChange}
                    disabled={!notificationData.email_notifications_enabled}
                    className="sr-only peer"
                  />
                  <div className={`w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-period-pink/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-period-pink ${!notificationData.email_notifications_enabled ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                </label>
              </div>
              
              {/* Health Insights / Anomaly Alerts */}
              <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Health Insights / Anomaly Alerts
                  </label>
                  <p className="text-xs text-gray-500">
                    Rare, respectful alerts about patterns worth keeping an eye on (max 1 per cycle)
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="health_alerts"
                    checked={notificationData.health_alerts}
                    onChange={handleNotificationChange}
                    disabled={!notificationData.email_notifications_enabled}
                    className="sr-only peer"
                  />
                  <div className={`w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-period-pink/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-period-pink ${!notificationData.email_notifications_enabled ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                </label>
              </div>
            </div>

            {/* Unsubscribe Notice */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <p className="text-xs text-gray-600">
                <strong>Unsubscribe:</strong> To unsubscribe from all emails, turn off "Email Notifications" above. 
                You can also unsubscribe by clicking the link in any email you receive.
              </p>
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

        {/* Reset Last Period Section */}
        <div className="mt-8 bg-orange-50 border-2 border-orange-200 rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0">
              <RotateCcw className="h-6 w-6 text-orange-600" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-orange-800 mb-2">Reset Last Period Start</h3>
              <p className="text-sm text-orange-700 mb-4">
                If you accidentally logged a period, you can remove just the most recently logged period start. This will:
              </p>
              <ul className="text-sm text-orange-700 list-disc list-inside mb-4 space-y-1">
                <li>Delete the most recent period log</li>
                <li>Remove that period from your calendar</li>
                <li>Update your last period date to the previous period (if any)</li>
                <li>Regenerate predictions based on your remaining period history</li>
              </ul>
              <p className="text-sm font-semibold text-orange-800 mb-4">
                ⚠️ This action cannot be undone, but only affects the last logged period.
              </p>
              <button
                onClick={() => setShowResetLastPeriodConfirm(true)}
                className="bg-orange-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-orange-700 transition flex items-center gap-2"
              >
                <RotateCcw className="h-5 w-5" />
                Reset Last Period Start
              </button>
            </div>
          </div>
        </div>

        {/* Reset Cycle Data Section */}
        <div className="mt-8 bg-red-50 border-2 border-red-200 rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0">
              <RotateCcw className="h-6 w-6 text-red-600" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-red-800 mb-2">Reset All Cycle Data</h3>
              <p className="text-sm text-red-700 mb-4">
                This will permanently delete all your cycle data including:
              </p>
              <ul className="text-sm text-red-700 list-disc list-inside mb-4 space-y-1">
                <li>All period logs (past, current, and future)</li>
                <li>All cycle history and statistics</li>
                <li>All phase predictions and calendar data</li>
                <li>Your cycle length and last period date</li>
              </ul>
              <p className="text-sm font-semibold text-red-800 mb-4">
                ⚠️ WARNING: This action cannot be undone! You will lose all your cycle tracking data.
              </p>
              <button
                onClick={() => setShowResetConfirm(true)}
                className="bg-red-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-red-700 transition flex items-center gap-2"
              >
                <RotateCcw className="h-5 w-5" />
                Reset All Cycle Data
              </button>
            </div>
          </div>
        </div>

        {/* Run 6-Month Diagnostic (temporary debug) */}
        <div className="mt-6 bg-gray-50 border border-gray-200 rounded-xl p-4">
          <h3 className="text-lg font-bold text-gray-700 mb-2">Debug: 6-Month Phase Analysis</h3>
          <p className="text-sm text-gray-600 mb-3">
            Runs phase calculation for today ±90 days and prints [DEBUG] lines to the backend terminal.
          </p>
          <button
            type="button"
            onClick={handleRunSixMonthDiagnostic}
            disabled={diagnosticRunning}
            className="bg-gray-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-gray-700 transition disabled:opacity-50 flex items-center gap-2"
          >
            {diagnosticRunning ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                Running...
              </>
            ) : (
              'Run 6-Month Diagnostic'
            )}
          </button>
        </div>

        {/* Reset Last Period Confirmation Modal */}
        {showResetLastPeriodConfirm && (
          <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
              <div className="flex items-start gap-4 mb-6">
                <div className="flex-shrink-0">
                  <AlertTriangle className="h-8 w-8 text-orange-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-2xl font-bold text-orange-800 mb-2">Reset Last Period?</h3>
                  <p className="text-gray-700 mb-4">
                    This will remove only the <strong className="text-orange-600">most recently logged period start</strong>:
                  </p>
                  <ul className="text-sm text-gray-700 list-disc list-inside mb-4 space-y-1">
                    <li>Delete the last period log entry</li>
                    <li>Remove that period from your calendar</li>
                    <li>Update your last period date to the previous period (if any)</li>
                    <li>Regenerate predictions based on remaining history</li>
                  </ul>
                  <div className="bg-orange-50 border-2 border-orange-300 rounded-lg p-4 mb-4">
                    <p className="text-sm font-bold text-orange-800">
                      ⚠️ This action cannot be undone!
                    </p>
                    <p className="text-sm text-orange-700 mt-2">
                      Only the most recent period will be removed. All other period history will remain intact.
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-gray-800 mb-4">
                    Do you want to proceed?
                  </p>
                </div>
              </div>
              
              <div className="flex gap-3">
                <button
                  onClick={() => setShowResetLastPeriodConfirm(false)}
                  disabled={resettingLastPeriod}
                  className="flex-1 bg-gray-200 text-gray-800 px-4 py-3 rounded-lg font-semibold hover:bg-gray-300 transition disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  <X className="h-5 w-5" />
                  Cancel
                </button>
                <button
                  onClick={handleResetLastPeriod}
                  disabled={resettingLastPeriod}
                  className="flex-1 bg-orange-600 text-white px-4 py-3 rounded-lg font-semibold hover:bg-orange-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {resettingLastPeriod ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                      <span>Resetting...</span>
                    </>
                  ) : (
                    <>
                      <RotateCcw className="h-5 w-5" />
                      <span>Yes, Reset Last Period</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Reset All Confirmation Modal */}
        {showResetConfirm && (
          <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
              <div className="flex items-start gap-4 mb-6">
                <div className="flex-shrink-0">
                  <AlertTriangle className="h-8 w-8 text-red-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-2xl font-bold text-red-800 mb-2">Are You Absolutely Sure?</h3>
                  <p className="text-gray-700 mb-4">
                    This action will <strong className="text-red-600">permanently delete</strong> all your cycle data:
                  </p>
                  <ul className="text-sm text-gray-700 list-disc list-inside mb-4 space-y-1">
                    <li>All period logs (past, current, and future)</li>
                    <li>All cycle history and statistics</li>
                    <li>All phase predictions and calendar data</li>
                    <li>Your cycle length and last period date</li>
                  </ul>
                  <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 mb-4">
                    <p className="text-sm font-bold text-red-800">
                      ⚠️ THIS ACTION CANNOT BE UNDONE!
                    </p>
                    <p className="text-sm text-red-700 mt-2">
                      All your cycle tracking data will be permanently erased. You will need to start tracking from scratch.
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-gray-800 mb-4">
                    Are you certain you want to proceed?
                  </p>
                </div>
              </div>
              
              <div className="flex gap-3">
                <button
                  onClick={() => setShowResetConfirm(false)}
                  disabled={resetting}
                  className="flex-1 bg-gray-200 text-gray-800 px-4 py-3 rounded-lg font-semibold hover:bg-gray-300 transition disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  <X className="h-5 w-5" />
                  Cancel
                </button>
                <button
                  onClick={handleResetCycleData}
                  disabled={resetting}
                  className="flex-1 bg-red-600 text-white px-4 py-3 rounded-lg font-semibold hover:bg-red-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {resetting ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                      <span>Resetting...</span>
                    </>
                  ) : (
                    <>
                      <RotateCcw className="h-5 w-5" />
                      <span>Yes, Reset Everything</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

export default Profile
