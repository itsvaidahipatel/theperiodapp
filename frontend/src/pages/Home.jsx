import { Link, useNavigate } from 'react-router-dom'
import { Heart, Calendar, MessageCircle, Activity, ArrowRight, Shield, Zap, ClipboardCheck, Stethoscope, Smartphone, Monitor } from 'lucide-react'
import { setSelectedLanguage, clearSelectedLanguage, getUserSavedLanguage } from '../utils/userPreferences'
import { useState, useEffect } from 'react'
import { useViewMode } from '../context/ViewModeContext'

const Home = () => {
  const navigate = useNavigate()
  const [hoveredLang, setHoveredLang] = useState(null)
  const { viewMode, toggleViewMode, isMobileView, isWebView } = useViewMode()

  const getViewModeIcon = () => {
    if (viewMode === 'mobile') return Smartphone
    return Monitor // Web view
  }

  const getViewModeLabel = () => {
    if (viewMode === 'mobile') return 'Mobile View'
    return 'Web View'
  }

  const ViewModeIcon = getViewModeIcon()

  // Clear selectedLanguage when logged-in user visits home page
  // This ensures their saved language preference is used, not a stale selectedLanguage
  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      // User is logged in - clear any temporary selectedLanguage
      // They should use their saved preference instead
      clearSelectedLanguage()
      console.log('Home: Logged-in user detected, cleared selectedLanguage. Saved language:', getUserSavedLanguage())
    }
  }, [])

  const handleLanguageSelection = (language) => {
    console.log('Home: Language selected:', language)
    setSelectedLanguage(language)
    // Small delay to ensure localStorage is set before navigation
    setTimeout(() => {
      const verify = localStorage.getItem('selectedLanguage')
      console.log('Home: Verifying language before navigation:', verify)
      navigate('/register')
    }, 10)
  }

  const languageOptions = [
    { 
      code: 'en', 
      label: 'English', 
      native: 'Get Started',
      gradient: 'from-blue-500 to-purple-500'
    },
    { 
      code: 'hi', 
      label: 'हिंदी', 
      native: 'शुरू करें',
      gradient: 'from-pink-500 to-rose-500'
    },
    { 
      code: 'gu', 
      label: 'ગુજરાતી', 
      native: 'શરૂ કરો',
      gradient: 'from-purple-500 to-indigo-500'
    }
  ]

  const features = [
    {
      icon: Calendar,
      title: 'Cycle Tracking',
      description: 'Track your menstrual cycle with intelligent phase predictions and personalized insights.',
      color: 'text-period-pink',
      bgColor: 'bg-pink-50',
      iconBg: 'bg-gradient-to-br from-pink-400 to-pink-600'
    },
    {
      icon: Activity,
      title: 'Health Insights',
      description: 'Get personalized nutrition, exercise, and hormone insights based on your cycle phase.',
      color: 'text-period-purple',
      bgColor: 'bg-purple-50',
      iconBg: 'bg-gradient-to-br from-purple-400 to-purple-600'
    },
    {
      icon: MessageCircle,
      title: 'AI Assistant',
      description: 'Chat with our AI assistant for health-related queries and cycle support.',
      color: 'text-period-lavender',
      bgColor: 'bg-indigo-50',
      iconBg: 'bg-gradient-to-br from-indigo-400 to-indigo-600'
    },
    {
      icon: ClipboardCheck,
      title: 'Self Tests',
      description: 'Take health assessment tests like PCOS checker, pregnancy checker, and more.',
      color: 'text-teal-600',
      bgColor: 'bg-teal-50',
      iconBg: 'bg-gradient-to-br from-teal-400 to-teal-600'
    }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-period-pink via-period-purple to-period-lavender relative overflow-hidden">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-white/10 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-white/10 rounded-full blur-3xl animate-pulse delay-1000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-white/5 rounded-full blur-3xl"></div>
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-16">
        {/* View Mode Toggle Button - Top Right */}
        <div className="absolute top-4 right-4 sm:top-6 sm:right-6 z-10">
          <button
            onClick={toggleViewMode}
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition bg-white/90 backdrop-blur-md border border-white/30 text-gray-700 hover:bg-white shadow-lg hover:shadow-xl"
            title={getViewModeLabel()}
          >
            <ViewModeIcon className="h-5 w-5" />
            <span className="hidden sm:inline text-sm font-medium">{getViewModeLabel()}</span>
          </button>
        </div>

        {/* Hero Section */}
        <div className="text-center mb-12 sm:mb-16 lg:mb-20">
          {/* Logo/Brand Icon */}
          <div className="flex items-center justify-center mb-6 sm:mb-8">
            <div className="relative group">
              <div className="absolute inset-0 bg-white/30 rounded-full blur-xl group-hover:blur-2xl transition-all duration-300"></div>
              <div className="relative bg-white/20 backdrop-blur-md rounded-full p-4 sm:p-5 border-2 border-white/30 shadow-2xl group-hover:scale-110 transition-transform duration-300">
                <Heart className="h-8 w-8 sm:h-12 sm:w-12 text-white fill-white drop-shadow-lg" />
              </div>
            </div>
          </div>

          {/* Main Heading */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-extrabold text-white mb-4 sm:mb-6 leading-tight drop-shadow-lg">
            PeriodCycle
            <span className="block sm:inline text-white/90 text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-light">
              .AI
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-lg lg:text-xl text-white/95 mb-8 sm:mb-10 px-4 max-w-2xl mx-auto leading-relaxed font-light">
            Your intelligent companion for menstrual cycle tracking and women's health
          </p>

          {/* Language Selection Section */}
          <div className="mb-10 sm:mb-12">
            <div className="inline-flex items-center gap-2 mb-6 sm:mb-8 px-4 sm:px-6 py-2 sm:py-3 bg-white/10 backdrop-blur-md rounded-full border border-white/20 shadow-lg">
              <p className="text-white text-sm sm:text-base font-medium">
                Choose Your Language
              </p>
            </div>

            {/* Language Buttons */}
            <div className={`flex ${isMobileView ? 'flex-col' : 'flex-row'} gap-4 sm:gap-5 justify-center items-stretch sm:items-center max-w-4xl mx-auto px-4`}>
              {languageOptions.map((lang) => {
                const isHovered = hoveredLang === lang.code
                
                return (
                  <button
                    key={lang.code}
                    onClick={() => handleLanguageSelection(lang.code)}
                    onMouseEnter={() => setHoveredLang(lang.code)}
                    onMouseLeave={() => setHoveredLang(null)}
                    className={`group relative w-full sm:flex-1 max-w-sm mx-auto sm:mx-0 bg-white text-gray-800 px-6 sm:px-8 py-5 sm:py-6 rounded-2xl font-bold hover:shadow-2xl transition-all duration-300 text-base sm:text-lg shadow-xl transform hover:-translate-y-2 active:translate-y-0 min-h-[72px] flex flex-col items-center justify-center gap-2 overflow-hidden ${
                      isHovered ? 'scale-105' : ''
                    }`}
                  >
                    {/* Gradient overlay on hover */}
                    <div className={`absolute inset-0 bg-gradient-to-br ${lang.gradient} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}></div>
                    
                    {/* Content */}
                    <div className="relative z-10 flex items-center gap-2 sm:gap-3">
                      <span className="font-bold text-lg sm:text-xl">{lang.native}</span>
                    </div>
                    <span className="relative z-10 text-xs sm:text-sm text-gray-600 group-hover:text-gray-800 font-medium">
                      {lang.label}
                    </span>
                    
                    {/* Arrow icon on hover */}
                    <ArrowRight className={`absolute right-4 h-5 w-5 text-period-pink opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all duration-300`} />
                  </button>
                )
              })}
            </div>
          </div>

          {/* Login Link */}
          <div className="mt-8 sm:mt-10">
            <Link
              to="/login"
              className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md border-2 border-white/30 text-white px-6 sm:px-8 py-3 sm:py-4 rounded-xl font-semibold hover:bg-white hover:text-period-pink transition-all duration-300 text-sm sm:text-base shadow-lg hover:shadow-xl transform hover:-translate-y-1 active:translate-y-0"
            >
              Already have an account?
              <span className="font-bold">Login</span>
            </Link>
          </div>
        </div>

        {/* Features Section */}
        <div className={`grid ${isMobileView ? 'grid-cols-1' : 'grid-cols-4'} gap-6 sm:gap-8 mt-12 sm:mt-16 lg:mt-20`}>
          {features.map((feature, index) => {
            const IconComponent = feature.icon
            return (
              <div
                key={index}
                className="group relative bg-white/95 backdrop-blur-sm rounded-2xl sm:rounded-3xl p-6 sm:p-8 shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2 border border-white/20"
              >
                {/* Icon Container */}
                <div className={`relative mb-5 sm:mb-6 inline-flex items-center justify-center`}>
                  <div className={`absolute inset-0 ${feature.bgColor} rounded-2xl blur-xl opacity-50 group-hover:opacity-75 transition-opacity duration-300`}></div>
                  <div className={`relative ${feature.iconBg} p-4 sm:p-5 rounded-2xl shadow-lg group-hover:scale-110 group-hover:rotate-3 transition-all duration-300`}>
                    <IconComponent className="h-6 w-6 sm:h-8 sm:w-8 text-white" />
                  </div>
                </div>

                {/* Content */}
                <h3 className={`text-xl sm:text-2xl font-bold mb-3 sm:mb-4 ${feature.color} group-hover:scale-105 transition-transform duration-300`}>
                  {feature.title}
                </h3>
                <p className="text-gray-600 text-sm sm:text-base leading-relaxed">
                  {feature.description}
                </p>

                {/* Hover Indicator */}
                <div className={`absolute bottom-0 left-0 right-0 h-1 ${feature.iconBg} rounded-b-2xl sm:rounded-b-3xl transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300 origin-left`}></div>
              </div>
            )
          })}
        </div>

        {/* Trust Indicators */}
        <div className="mt-12 sm:mt-16 lg:mt-20 pt-8 sm:pt-12 border-t border-white/20">
          <div className={`grid ${isMobileView ? 'grid-cols-1' : 'grid-cols-3'} gap-6 sm:gap-8 text-center`}>
            <div className="flex flex-col items-center group cursor-default">
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-full mb-3 group-hover:scale-110 transition-transform duration-300">
                <Shield className="h-6 w-6 sm:h-8 sm:w-8 text-white" />
              </div>
              <p className="text-white/95 text-sm sm:text-base font-semibold mb-1">Privacy First</p>
              <p className="text-white/70 text-xs sm:text-sm">Your data is secure</p>
            </div>
            <div className="flex flex-col items-center group cursor-default">
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-full mb-3 group-hover:scale-110 transition-transform duration-300">
                <Zap className="h-6 w-6 sm:h-8 sm:w-8 text-white" />
              </div>
              <p className="text-white/95 text-sm sm:text-base font-semibold mb-1">AI-Powered</p>
              <p className="text-white/70 text-xs sm:text-sm">Intelligent insights</p>
            </div>
            <div className="flex flex-col items-center group cursor-default">
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-full mb-3 group-hover:scale-110 transition-transform duration-300">
                <Stethoscope className="h-6 w-6 sm:h-8 sm:w-8 text-white" />
              </div>
              <p className="text-white/95 text-sm sm:text-base font-semibold mb-1">Expert Backed</p>
              <p className="text-white/70 text-xs sm:text-sm">Medical guidance included</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Home

