import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { logPeriod, logPeriodEnd } from '../utils/api'
import { formatDateForInput } from '../utils/indianDate'

const PeriodLogModal = ({ isOpen, onClose, onSuccess, selectedDate, isLoggingEnd = false }) => {
  const [formData, setFormData] = useState({
    date: selectedDate || formatDateForInput(new Date()),
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setFormData({
        date: selectedDate || formatDateForInput(new Date()),
      })
      setError('')
    }
  }, [isOpen, selectedDate])

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    // CRITICAL: Prevent logging periods in future dates
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const selectedDateObj = new Date(formData.date)
    selectedDateObj.setHours(0, 0, 0, 0)
    
    if (selectedDateObj > today) {
      setError('Cannot log period for future dates. Please log periods that have already occurred.')
      setLoading(false)
      return
    }

    try {
      if (isLoggingEnd) {
        // Log period end
        const response = await logPeriodEnd({ date: formData.date })
        if (response.error) {
          setError(response.error)
          setLoading(false)
          return
        }
        await onSuccess({ date: formData.date })
      } else {
        // Log period start
        const response = await logPeriod(formData)
        if (response.error) {
          setError(response.error)
          setLoading(false)
          return
        }
        await onSuccess(formData)
      }
      onClose()
    } catch (err) {
      // Handle validation errors from backend
      const errorMessage = err.response?.data?.detail || err.message || (isLoggingEnd ? 'Failed to log period end' : 'Failed to log period')
      setError(errorMessage)
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center p-6 border-b">
          <h2 className="text-2xl font-bold text-period-pink">
            {isLoggingEnd ? 'Log Period End' : 'Log Period Start'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {!isLoggingEnd && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-blue-800">
                <strong>Note:</strong> Log only the date your period started. The system will automatically track the full period duration based on your cycle history.
              </p>
            </div>
          )}
          
          {isLoggingEnd && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-green-800">
                <strong>Note:</strong> Select the last day of your period. This helps the system learn your exact period length for better predictions.
              </p>
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {isLoggingEnd ? 'Period End Date' : 'Period Start Date'}
            </label>
            <input
              type="date"
              name="date"
              value={formData.date}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">
              {isLoggingEnd ? 'Select the last day of your period' : 'Select the first day of your period'}
            </p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="flex gap-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-period-pink text-white px-4 py-2 rounded-lg hover:bg-opacity-90 transition disabled:opacity-50"
            >
              {loading ? 'Saving...' : (isLoggingEnd ? 'Log End' : 'Log Start')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default PeriodLogModal

