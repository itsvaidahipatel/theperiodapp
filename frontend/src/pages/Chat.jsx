import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { sendChatMessage, getChatHistory } from '../utils/api'
import { Send, Bot, User } from 'lucide-react'
import { format } from 'date-fns'

const Chat = () => {
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
    const fetchChatHistory = async () => {
      try {
        const response = await getChatHistory(50)
        if (response.history) {
          const formattedMessages = response.history.flatMap((item) => [
            { type: 'user', text: item.message, timestamp: item.created_at },
            { type: 'bot', text: item.response, timestamp: item.created_at },
          ])
          setMessages(formattedMessages)
        }
      } catch (error) {
        console.error('Failed to fetch chat history:', error)
      }
    }

    fetchChatHistory()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!inputMessage.trim() || loading) return

    const userMessage = inputMessage.trim()
    setInputMessage('')
    setMessages((prev) => [
      ...prev,
      { type: 'user', text: userMessage, timestamp: new Date().toISOString() },
    ])
    setLoading(true)

    try {
      const language = user?.language || 'en'
      const response = await sendChatMessage(userMessage, language)
      
      setMessages((prev) => [
        ...prev,
        { type: 'bot', text: response.response, timestamp: new Date().toISOString() },
      ])
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          type: 'bot',
          text: 'Sorry, I encountered an error. Please try again later.',
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (!user) {
    return <div>Loading...</div>
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 flex flex-col">
        <h1 className="text-3xl font-bold text-gray-800 mb-4">AI Health Assistant</h1>

        {/* Messages */}
        <div className="flex-1 bg-white rounded-lg shadow-lg p-6 mb-4 overflow-y-auto min-h-[400px] max-h-[600px]">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 py-12">
              <Bot className="h-12 w-12 mx-auto mb-4 text-period-pink" />
              <p>Start a conversation about your health and cycle</p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex gap-3 ${
                    message.type === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  {message.type === 'bot' && (
                    <div className="flex-shrink-0">
                      <div className="w-8 h-8 rounded-full bg-period-pink flex items-center justify-center">
                        <Bot className="h-5 w-5 text-white" />
                      </div>
                    </div>
                  )}
                  
                  <div
                    className={`max-w-[70%] rounded-lg p-4 ${
                      message.type === 'user'
                        ? 'bg-period-pink text-white'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.text}</p>
                    <p
                      className={`text-xs mt-2 ${
                        message.type === 'user' ? 'text-white opacity-70' : 'text-gray-500'
                      }`}
                    >
                      {format(new Date(message.timestamp), 'HH:mm')}
                    </p>
                  </div>

                  {message.type === 'user' && (
                    <div className="flex-shrink-0">
                      <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center">
                        <User className="h-5 w-5 text-gray-600" />
                      </div>
                    </div>
                  )}
                </div>
              ))}
              
              {loading && (
                <div className="flex gap-3 justify-start">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 rounded-full bg-period-pink flex items-center justify-center">
                      <Bot className="h-5 w-5 text-white" />
                    </div>
                  </div>
                  <div className="bg-gray-100 rounded-lg p-4">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="flex gap-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Ask about your cycle, health, or wellness..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !inputMessage.trim()}
            className="bg-period-pink text-white px-6 py-3 rounded-lg hover:bg-opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Send className="h-5 w-5" />
            Send
          </button>
        </form>

        {/* Safety Disclaimer - At the bottom */}
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

export default Chat

