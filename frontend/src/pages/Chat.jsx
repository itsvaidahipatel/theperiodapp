import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { sendChatMessage, getChatHistory, logout } from '../utils/api'
import { parseMarkdown } from '../utils/markdown'
import { getCachedChatHistory, setCachedChatHistory, clearChatCache } from '../utils/chatCache'
import { useTranslation } from '../utils/translations'
import { Send, Bot, User, ArrowLeft, LogOut } from 'lucide-react'
import { format } from 'date-fns'

const Chat = () => {
  const { t } = useTranslation()
  const [user, setUser] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      setUser(JSON.parse(userData))
    } else {
      navigate('/login')
    }
  }, [navigate])

  useEffect(() => {
    const loadChatHistory = async () => {
      // First, try to load from cache
      const cachedMessages = getCachedChatHistory()
      if (cachedMessages && cachedMessages.length > 0) {
        console.log('Loading chat history from cache:', cachedMessages.length, 'messages')
        setMessages(cachedMessages)
      }
      
      // Then fetch from backend to get latest (and update cache)
      try {
        const response = await getChatHistory(50)
        if (response.history) {
          // Group messages by role (user/assistant pairs)
          const formattedMessages = []
          let currentPair = null
          
          response.history.forEach((item) => {
            if (item.role === 'user') {
              // Start a new pair
              if (currentPair) {
                formattedMessages.push(currentPair)
              }
              currentPair = {
                user: { text: item.message, timestamp: item.created_at },
                bot: null
              }
            } else if (item.role === 'assistant' && currentPair) {
              // Add bot response to current pair
              currentPair.bot = { text: item.message, timestamp: item.created_at }
            }
          })
          
          // Add last pair if exists
          if (currentPair) {
            formattedMessages.push(currentPair)
          }
          
          // Convert to flat message array
          const flatMessages = formattedMessages.flatMap((pair) => [
            { type: 'user', text: pair.user.text, timestamp: pair.user.timestamp },
            { type: 'bot', text: pair.bot?.text || '', timestamp: pair.bot?.timestamp || pair.user.timestamp },
          ]).filter(msg => msg.text) // Remove empty messages
          
          // Update cache with fresh data from backend
          setCachedChatHistory(flatMessages)
          setMessages(flatMessages)
        }
      } catch (error) {
        console.error('Failed to fetch chat history:', error)
        // If fetch fails but we have cache, keep using cache
        if (!cachedMessages || cachedMessages.length === 0) {
          console.log('No cached history available, starting fresh')
        }
      }
    }

    loadChatHistory()
  }, [])

  const handleLogout = async () => {
    try {
      await logout()
      sessionStorage.clear()
      clearChatCache()
      navigate('/login')
    } catch (error) {
      sessionStorage.clear()
      clearChatCache()
      navigate('/login')
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!inputMessage.trim() || loading) return

    const userMessage = inputMessage.trim()
    setInputMessage('')
    
    const userMsg = { type: 'user', text: userMessage, timestamp: new Date().toISOString() }
    setMessages((prev) => {
      const updated = [...prev, userMsg]
      // Update cache immediately with user message
      setCachedChatHistory(updated)
      return updated
    })
    setLoading(true)

    try {
      const language = user?.language || 'en'
      const response = await sendChatMessage(userMessage, language)
      
      if (response && response.response) {
        const botMsg = { type: 'bot', text: response.response, timestamp: new Date().toISOString() }
        setMessages((prev) => {
          const updated = [...prev, botMsg]
          // Update cache with bot response
          setCachedChatHistory(updated)
          return updated
        })
      } else {
        throw new Error('Invalid response format')
      }
    } catch (error) {
      console.error('Chat error:', error)
      console.error('Error details:', error.response)
      
      let errorMessage = 'Sorry, I encountered an error. Please try again later.'
      
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail
      } else if (error.message) {
        errorMessage = error.message
      }
      
      // Check if it's a Gemini API key issue
      if (errorMessage.includes('GEMINI_API_KEY') || errorMessage.includes('not configured')) {
        errorMessage = 'The AI assistant is not properly configured. Please ensure GEMINI_API_KEY is set in the backend environment variables.'
      }
      
      const errorMsg = {
        type: 'bot',
        text: errorMessage,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => {
        const updated = [...prev, errorMsg]
        // Update cache with error message
        setCachedChatHistory(updated)
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  if (!user) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center">{t('common.loading')}</div>
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex flex-col">
      {/* Professional Header */}
      <nav className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/dashboard')}
                className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="h-5 w-5" />
                <span className="hidden sm:inline text-sm font-medium">Dashboard</span>
              </button>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-period-pink to-pink-600 flex items-center justify-center shadow-md">
                  <Bot className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">AI Health Assistant</h1>
                  <p className="text-xs text-gray-500">Always here to help</p>
                </div>
              </div>
            </div>
            
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <LogOut className="h-5 w-5" />
              <span className="hidden sm:inline text-sm font-medium">Logout</span>
            </button>
          </div>
        </div>
      </nav>
      
      <div className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 flex flex-col">
        {/* Professional Chat Container */}
        <div className="flex-1 bg-white rounded-2xl shadow-xl border border-gray-200 flex flex-col overflow-hidden">
          {/* Messages Area - Scrollable */}
          <div className="flex-1 overflow-y-auto bg-gradient-to-b from-white to-gray-50">
            <div className="p-6 space-y-6">
              {/* Welcome Banner - Always Visible */}
              <div className="flex flex-col items-center justify-center py-12 border-b border-gray-200 mb-6">
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-period-pink to-pink-600 flex items-center justify-center shadow-lg mb-6">
                  <Bot className="h-10 w-10 text-white" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">{t('chat.welcome')}</h3>
                <p className="text-gray-500 text-center max-w-md mb-6">
                  {t('chat.description')}
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {[t('chat.suggestions.pcos'), t('chat.suggestions.symptoms'), t('chat.suggestions.tracking'), t('chat.suggestions.nutrition')].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setInputMessage(suggestion)}
                      className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full text-sm transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>

              {/* Messages - Below Welcome Banner */}
              {messages.length > 0 && (
                <div className="space-y-6">
                  {messages.map((message, index) => (
                    <div
                      key={index}
                      className={`flex gap-4 ${
                        message.type === 'user' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      {message.type === 'bot' && (
                        <div className="flex-shrink-0">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-period-pink to-pink-600 flex items-center justify-center shadow-md">
                            <Bot className="h-6 w-6 text-white" />
                          </div>
                        </div>
                      )}
                      
                      <div className={`flex flex-col ${message.type === 'user' ? 'items-end' : 'items-start'} max-w-[75%]`}>
                        <div
                          className={`rounded-2xl px-5 py-4 shadow-sm ${
                            message.type === 'user'
                              ? 'bg-gradient-to-br from-period-pink to-pink-600 text-white rounded-tr-sm'
                              : 'bg-white text-gray-800 border border-gray-200 rounded-tl-sm'
                          }`}
                        >
                          <div className={`text-sm leading-relaxed ${message.type === 'user' ? 'text-white' : 'text-gray-800'}`}>
                            {message.type === 'bot' ? parseMarkdown(message.text) : (
                              <p className="whitespace-pre-wrap">{message.text}</p>
                            )}
                          </div>
                        </div>
                        <p
                          className={`text-xs mt-1.5 px-2 ${
                            message.type === 'user' ? 'text-gray-500' : 'text-gray-400'
                          }`}
                        >
                          {format(new Date(message.timestamp), 'HH:mm')}
                        </p>
                      </div>

                      {message.type === 'user' && (
                        <div className="flex-shrink-0">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gray-400 to-gray-500 flex items-center justify-center shadow-md">
                            <User className="h-6 w-6 text-white" />
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {loading && (
                    <div className="flex gap-4 justify-start">
                      <div className="flex-shrink-0">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-period-pink to-pink-600 flex items-center justify-center shadow-md">
                          <Bot className="h-6 w-6 text-white" />
                        </div>
                      </div>
                      <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-5 py-4 shadow-sm">
                        <div className="flex gap-1.5">
                          <div className="w-2 h-2 bg-period-pink rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                          <div className="w-2 h-2 bg-period-pink rounded-full animate-bounce" style={{ animationDelay: '200ms' }}></div>
                          <div className="w-2 h-2 bg-period-pink rounded-full animate-bounce" style={{ animationDelay: '400ms' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* Professional Input Area */}
          <div className="border-t border-gray-200 bg-white p-4">
            <form onSubmit={handleSend} className="flex gap-3">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  placeholder={t('chat.typeMessage')}
                  className="w-full px-4 py-3 pr-12 bg-gray-50 border border-gray-300 rounded-xl focus:ring-2 focus:ring-period-pink focus:border-period-pink focus:bg-white transition-all text-gray-900 placeholder-gray-400"
                  disabled={loading}
                />
                {inputMessage.trim() && (
                  <button
                    type="button"
                    onClick={() => setInputMessage('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
              <button
                type="submit"
                disabled={loading || !inputMessage.trim()}
                className="bg-gradient-to-r from-period-pink to-pink-600 text-white px-6 py-3 rounded-xl hover:from-pink-600 hover:to-pink-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-md hover:shadow-lg font-medium"
              >
                <Send className="h-5 w-5" />
                <span className="hidden sm:inline">{t('chat.send')}</span>
              </button>
            </form>
            <p className="text-xs text-gray-400 mt-2 text-center">
              AI responses are for informational purposes only. Always consult a healthcare professional for medical advice.
            </p>
          </div>
        </div>

        {/* Safety Disclaimer - At the bottom */}
        <div className="mt-6">
          <SafetyDisclaimer />
        </div>
      </div>
    </div>
  )
}

export default Chat

