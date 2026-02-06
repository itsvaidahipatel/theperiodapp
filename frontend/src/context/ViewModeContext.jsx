import { createContext, useContext, useState, useEffect } from 'react'

const ViewModeContext = createContext()

export const useViewMode = () => {
  const context = useContext(ViewModeContext)
  if (!context) {
    throw new Error('useViewMode must be used within a ViewModeProvider')
  }
  return context
}

export const ViewModeProvider = ({ children }) => {
  // Get initial view mode from localStorage or default to 'mobile' (mobile-first)
  const [viewMode, setViewMode] = useState(() => {
    const saved = localStorage.getItem('viewMode')
    // If saved is 'auto', convert to 'mobile'
    if (saved === 'auto') return 'mobile'
    // Only allow 'mobile' or 'web'
    return saved === 'web' ? 'web' : 'mobile'
  })

  // Save to localStorage whenever view mode changes
  useEffect(() => {
    localStorage.setItem('viewMode', viewMode)
  }, [viewMode])

  const toggleViewMode = () => {
    setViewMode((prev) => {
      // Toggle between mobile and web only
      return prev === 'mobile' ? 'web' : 'mobile'
    })
  }

  // Helper function to get responsive classes based on view mode
  const getResponsiveClass = (mobileClass, webClass) => {
    if (viewMode === 'mobile') return mobileClass
    return webClass
  }

  // Helper to check if we should force mobile or web view
  const isMobileView = viewMode === 'mobile'
  const isWebView = viewMode === 'web'
  const isAutoView = false // Auto view removed

  return (
    <ViewModeContext.Provider
      value={{
        viewMode,
        setViewMode,
        toggleViewMode,
        getResponsiveClass,
        isMobileView,
        isWebView,
        isAutoView,
      }}
    >
      {children}
    </ViewModeContext.Provider>
  )
}
