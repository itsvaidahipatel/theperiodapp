import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'

const NotFound = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-period-pink to-period-purple flex items-center justify-center p-4">
      <div className="text-center">
        <h1 className="text-9xl font-bold text-white mb-4">404</h1>
        <h2 className="text-3xl font-semibold text-white mb-4">Page Not Found</h2>
        <p className="text-white opacity-90 mb-8">
          The page you're looking for doesn't exist.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 bg-white text-period-pink px-6 py-3 rounded-lg font-semibold hover:bg-opacity-90 transition"
        >
          <Home className="h-5 w-5" />
          Go Home
        </Link>
      </div>
    </div>
  )
}

export default NotFound

