import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import SimpleAuthComponent from '../components/SimpleAuthComponent'
import { registerUser } from '../utils/api'

const Register = () => {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (formData) => {
    setLoading(true)
    setError('')
    
    try {
      await registerUser(formData)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-period-pink to-period-purple flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <h1 className="text-3xl font-bold text-center text-period-pink mb-2">
          Create Account
        </h1>
        <p className="text-center text-gray-600 mb-6">
          Start your journey to better cycle health
        </p>
        
        <SimpleAuthComponent
          onSubmit={handleSubmit}
          isLogin={false}
          error={error}
          loading={loading}
        />
        
        <p className="text-center mt-6 text-gray-600">
          Already have an account?{' '}
          <Link to="/login" className="text-period-pink hover:underline">
            Login here
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Register

