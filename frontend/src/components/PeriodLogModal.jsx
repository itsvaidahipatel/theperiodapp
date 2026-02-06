import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { logPeriod } from '../utils/api'
import { formatDateForInput } from '../utils/indianDate'

const PeriodLogModal = ({ isOpen, onClose, onSuccess, selectedDate }) => {
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
    const selectedDate = new Date(formData.date)
    selectedDate.setHours(0, 0, 0, 0)
    
    if (selectedDate > today) {
      setError('Cannot log period for future dates. Please log periods that have already occurred.')
      setLoading(false)
      return
    }

    try {
      const response = await logPeriod(formData)
      // Handle new response format with validation
      if (response.error) {
        setError(response.error)
        setLoading(false)
        return
      }
      await onSuccess(formData)
      onClose()
    } catch (err) {
      // Handle validation errors from backend
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to log period'
      setError(errorMessage)
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center p-6 border-b">
          <h2 className="text-2xl font-bold text-period-pink">Log Period</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Date
            </label>
            <input
              type="date"
              name="date"
              value={formData.date}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
            />
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
              {loading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default PeriodLogModal

