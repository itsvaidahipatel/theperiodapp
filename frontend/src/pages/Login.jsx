import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import SimpleAuthComponent from '../components/SimpleAuthComponent'
import { loginUser } from '../utils/api'
import { useTranslation } from '../utils/translations'

const Login = () => {
  // Use saved language preference for login page (ignore temporary selectedLanguage)
  const { t } = useTranslation(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (formData) => {
    setLoading(true)
    setError('')
    
    try {
      await loginUser({
        email: formData.email,
        password: formData.password,
      })
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || t('auth.loginError') || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-period-pink to-period-purple flex items-center justify-center p-4 sm:p-6 py-8 sm:py-6">
      <div className="bg-white rounded-lg shadow-xl p-6 sm:p-8 max-w-md w-full max-h-[95vh] overflow-y-auto">
        <h1 className="text-2xl sm:text-3xl font-bold text-center text-period-pink mb-2">
          {t('auth.welcomeBack') || 'Welcome Back'}
        </h1>
        <p className="text-center text-gray-600 mb-6 text-sm sm:text-base">
          {t('auth.loginDescription') || 'Login to continue tracking your cycle'}
        </p>
        
        <SimpleAuthComponent
          onSubmit={handleSubmit}
          isLogin={true}
          error={error}
          loading={loading}
        />
        
        <p className="text-center mt-6 text-gray-600 text-sm sm:text-base">
          {t('auth.switchToRegister') || "Don't have an account?"}{' '}
          <Link to="/register" className="text-period-pink hover:underline font-medium">
            {t('auth.register') || 'Register here'}
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Login

