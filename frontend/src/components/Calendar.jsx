import { useState, useEffect } from 'react'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'
import { format } from 'date-fns'
import { getPhaseMap } from '../utils/api'
import { phaseDayIdToPhase } from '../utils/phaseMapSlim'

const PhaseCalendar = ({ onDateClick, selectedDate }) => {
  const [phaseMap, setPhaseMap] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchPhaseMap = async () => {
      try {
        const today = new Date()
        const startDate = format(new Date(today.getFullYear(), today.getMonth() - 1, 1), 'yyyy-MM-dd')
        const endDate = format(new Date(today.getFullYear(), today.getMonth() + 2, 0), 'yyyy-MM-dd')
        
        const response = await getPhaseMap(startDate, endDate)
        const map = {}
        
        if (response.phase_map) {
          response.phase_map.forEach((item) => {
            map[item.date] = item
          })
        }
        
        setPhaseMap(map)
      } catch (error) {
        console.error('Failed to fetch phase map:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchPhaseMap()
  }, [])

  const getPhaseColor = (phase) => {
    const colors = {
      Period: 'bg-red-200 text-red-800',
      Menstrual: 'bg-red-200 text-red-800',
      Follicular: 'bg-teal-200 text-teal-800',
      Ovulation: 'bg-yellow-200 text-yellow-800',
      Luteal: 'bg-purple-200 text-purple-800',
    }
    return colors[phase] || 'bg-gray-200 text-gray-800'
  }

  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      const phaseData = phaseMap[dateStr]
      
      if (phaseData) {
        const phase = phaseData.phase || phaseDayIdToPhase(phaseData.phase_day_id)
        return `rounded-full ${getPhaseColor(phase)}`
      }
    }
    return null
  }

  const tileContent = ({ date, view }) => {
    if (view === 'month') {
      const dateStr = format(date, 'yyyy-MM-dd')
      const phaseData = phaseMap[dateStr]
      
      if (phaseData) {
        return (
          <div className="text-xs font-semibold mt-1">
            {phaseData.phase_day_id}
          </div>
        )
      }
    }
    return null
  }

  if (loading) {
    return <div className="text-center py-8">Loading calendar...</div>
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold mb-4">Cycle Calendar</h2>
      <Calendar
        onChange={onDateClick}
        value={selectedDate}
        tileClassName={tileClassName}
        tileContent={tileContent}
        className="w-full"
      />
      
      <div className="mt-6 flex flex-wrap gap-4 justify-center">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-red-200"></div>
          <span className="text-sm">Period</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-teal-200"></div>
          <span className="text-sm">Follicular</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-yellow-200"></div>
          <span className="text-sm" title="Estimated Ovulation (1-3 day window)">Estimated Ovulation (1-3 day window)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-purple-200"></div>
          <span className="text-sm">Luteal</span>
        </div>
      </div>
    </div>
  )
}

export default PhaseCalendar

