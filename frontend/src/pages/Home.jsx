import { Link } from 'react-router-dom'
import { Heart, Calendar, MessageCircle, Activity } from 'lucide-react'

const Home = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-period-pink via-period-purple to-period-lavender">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-white mb-4">
            Period GPT2
          </h1>
          <p className="text-xl text-white opacity-90 mb-8">
            Your intelligent companion for menstrual cycle tracking and women's health
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              to="/register"
              className="bg-white text-period-pink px-8 py-3 rounded-lg font-semibold hover:bg-opacity-90 transition"
            >
              Get Started
            </Link>
            <Link
              to="/login"
              className="bg-transparent border-2 border-white text-white px-8 py-3 rounded-lg font-semibold hover:bg-white hover:text-period-pink transition"
            >
              Login
            </Link>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-8 mt-16">
          <div className="bg-white rounded-lg p-6 shadow-lg">
            <Calendar className="h-12 w-12 text-period-pink mb-4" />
            <h3 className="text-xl font-semibold mb-2">Cycle Tracking</h3>
            <p className="text-gray-600">
              Track your menstrual cycle with intelligent phase predictions and personalized insights.
            </p>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-lg">
            <Activity className="h-12 w-12 text-period-purple mb-4" />
            <h3 className="text-xl font-semibold mb-2">Health Insights</h3>
            <p className="text-gray-600">
              Get personalized nutrition, exercise, and hormone insights based on your cycle phase.
            </p>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-lg">
            <MessageCircle className="h-12 w-12 text-period-lavender mb-4" />
            <h3 className="text-xl font-semibold mb-2">AI Assistant</h3>
            <p className="text-gray-600">
              Chat with our AI assistant for health-related queries and cycle support.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Home

