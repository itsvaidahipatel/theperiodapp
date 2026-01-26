import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import SimpleAuthComponent from '../components/SimpleAuthComponent'
import { registerUser } from '../utils/api'
import { useTranslation } from '../utils/translations'
import { getUserLanguage } from '../utils/userPreferences'

const Register = () => {
  const { t, language } = useTranslation()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  // Debug: Log language on mount and test translations
  useEffect(() => {
    const currentLang = getUserLanguage()
    console.log('Register component mounted. Current language:', currentLang)
    console.log('useTranslation hook language:', language)
    console.log('localStorage selectedLanguage:', localStorage.getItem('selectedLanguage'))
    
    // Test a translation
    console.log('Testing translation for "auth.createAccount":', t('auth.createAccount'))
    console.log('Testing translation for "auth.registerDescription":', t('auth.registerDescription'))
  }, [language, t])

  const handleSubmit = async (formData) => {
    setLoading(true)
    setError('')
    
    try {
      await registerUser(formData)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || t('auth.registerError') || 'Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-period-pink to-period-purple flex items-center justify-center p-4 sm:p-6 py-8 sm:py-6">
      <div className="bg-white rounded-lg shadow-xl p-6 sm:p-8 max-w-md w-full max-h-[95vh] overflow-y-auto">
        <h1 className="text-2xl sm:text-3xl font-bold text-center text-period-pink mb-2">
          {t('auth.createAccount') || 'Create Account'}
        </h1>
        <p className="text-center text-gray-600 mb-6 text-sm sm:text-base">
          {t('auth.registerDescription') || 'Start your journey to better cycle health'}
        </p>
        
        <SimpleAuthComponent
          onSubmit={handleSubmit}
          isLogin={false}
          error={error}
          loading={loading}
        />
        
        <p className="text-center mt-6 text-gray-600 text-sm sm:text-base">
          {t('auth.switchToLogin') || 'Already have an account?'}{' '}
          <Link to="/login" className="text-period-pink hover:underline font-medium">
            {t('auth.login') || 'Login here'}
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Register

