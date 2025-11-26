import { Heart } from 'lucide-react'

const LoadingSpinner = ({ message = 'Loading...' }) => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <div className="relative inline-block">
          {/* Animated heart with pulsing effect */}
          <Heart 
            className="h-16 w-16 text-period-pink animate-pulse mx-auto mb-4"
            fill="currentColor"
            style={{
              animation: 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }}
          />
          {/* Rotating circle around heart */}
          <div 
            className="absolute inset-0 border-4 border-period-pink border-t-transparent rounded-full animate-spin"
            style={{
              width: '4.5rem',
              height: '4.5rem',
              top: '-0.25rem',
              left: '-0.25rem',
              animation: 'spin 1s linear infinite',
            }}
          />
        </div>
        <p className="text-gray-600 text-lg font-medium mt-4">{message}</p>
        {/* Dots animation */}
        <div className="flex justify-center gap-1 mt-2">
          <span 
            className="w-2 h-2 bg-period-pink rounded-full animate-bounce"
            style={{ animationDelay: '0s' }}
          />
          <span 
            className="w-2 h-2 bg-period-pink rounded-full animate-bounce"
            style={{ animationDelay: '0.2s' }}
          />
          <span 
            className="w-2 h-2 bg-period-pink rounded-full animate-bounce"
            style={{ animationDelay: '0.4s' }}
          />
        </div>
      </div>
    </div>
  )
}

export default LoadingSpinner





