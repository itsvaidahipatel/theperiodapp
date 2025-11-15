import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { logout } from '../utils/api'

const LogoutButton = () => {
  const navigate = useNavigate()

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login')
    } catch (error) {
      console.error('Logout error:', error)
      // Still navigate even if API call fails
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      navigate('/login')
    }
  }

  return (
    <button
      onClick={handleLogout}
      className="flex items-center gap-2 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition"
    >
      <LogOut className="h-4 w-4" />
      <span>Logout</span>
    </button>
  )
}

export default LogoutButton

