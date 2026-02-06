import { Link, useLocation } from 'react-router-dom'
import { Home, User, MessageCircle, Activity, LogOut, Smartphone, Monitor } from 'lucide-react'
import { logout } from '../utils/api'
import { useNavigate } from 'react-router-dom'
import { useViewMode } from '../context/ViewModeContext'

const Navbar = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { viewMode, toggleViewMode } = useViewMode()

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login')
    } catch (error) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      navigate('/login')
    }
  }

  const getViewModeIcon = () => {
    if (viewMode === 'mobile') return Smartphone
    return Monitor // Web view
  }

  const getViewModeLabel = () => {
    if (viewMode === 'mobile') return 'Mobile View'
    return 'Web View'
  }

  const ViewModeIcon = getViewModeIcon()

  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/chat', icon: MessageCircle, label: 'Chat' },
    { path: '/profile', icon: User, label: 'Profile' },
  ]

  return (
    <nav className="bg-white shadow-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/dashboard" className="text-2xl font-bold text-period-pink">
            PeriodCycle.AI
          </Link>
          
          <div className="flex items-center gap-2 sm:gap-4">
            {/* View Mode Toggle Button */}
            <button
              onClick={toggleViewMode}
              className="flex items-center gap-2 px-3 py-2 rounded-lg transition text-gray-700 hover:bg-gray-100 border border-gray-200"
              title={getViewModeLabel()}
            >
              <ViewModeIcon className="h-5 w-5" />
              <span className="hidden sm:inline text-sm">{getViewModeLabel()}</span>
            </button>

            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${
                    isActive
                      ? 'bg-period-pink text-white'
                      : 'text-gray-700 hover:bg-period-pink hover:bg-opacity-10'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              )
            })}
            
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition"
            >
              <LogOut className="h-5 w-5" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}

export default Navbar

