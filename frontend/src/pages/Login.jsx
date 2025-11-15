import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import SimpleAuthComponent from '../components/SimpleAuthComponent'
import { loginUser } from '../utils/api'

const Login = () => {
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
      setError(err.message || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-period-pink to-period-purple flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <h1 className="text-3xl font-bold text-center text-period-pink mb-2">
          Welcome Back
        </h1>
        <p className="text-center text-gray-600 mb-6">
          Login to continue tracking your cycle
        </p>
        
        <SimpleAuthComponent
          onSubmit={handleSubmit}
          isLogin={true}
          error={error}
          loading={loading}
        />
        
        <p className="text-center mt-6 text-gray-600">
          Don't have an account?{' '}
          <Link to="/register" className="text-period-pink hover:underline">
            Register here
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Login

