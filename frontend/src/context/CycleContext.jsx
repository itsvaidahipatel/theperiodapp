import { createContext, useContext, useState, useCallback, useRef, useMemo, useEffect } from 'react'
import { format, parseISO, differenceInDays, addDays } from 'date-fns'
import { getPhaseMap, getPeriodLogs, getCycleStats } from '../utils/api'
import { enrichPhaseMapItem } from '../utils/phaseMapSlim'
import { useDataContext } from './DataContext'

const CycleContext = createContext()

export const useCycleContext = () => {
  const context = useContext(CycleContext)
  if (!context) {
    throw new Error('useCycleContext must be used within CycleProvider')
  }
  return context
}

// Alias for cleaner API
export const useCycleData = useCycleContext

const PHASE_MAP_DAYS = 304
const toDateKey = (d) => (typeof d === 'string' ? d.slice(0, 10) : format(d, 'yyyy-MM-dd'))

function enrichKeyedPhaseMap(raw, todayStr) {
  const out = {}
  if (!raw || typeof raw !== 'object') return out
  Object.entries(raw).forEach(([k, v]) => {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      out[k] = enrichPhaseMapItem({ ...v, date: v.date || k }, todayStr)
    } else {
      out[k] = v
    }
  })
  return out
}

function buildKeyedPhaseMap(phaseMapArray, todayStr) {
  const keyed = {}
  if (!Array.isArray(phaseMapArray)) return keyed
  phaseMapArray.forEach((item) => {
    const d = item?.date
    if (!d) return
    const dateKey = toDateKey(d)
    if (dateKey.length === 10) keyed[dateKey] = enrichPhaseMapItem(item, todayStr)
  })
  return keyed
}

function extractPeriodStarts(periodLogs) {
  if (!periodLogs?.length) return []
  const seen = new Set()
  const starts = []
  for (const log of periodLogs) {
    const dateStr = toDateKey(log.startDate || log.date || '')
    if (dateStr.length === 10 && !seen.has(dateStr)) {
      seen.add(dateStr)
      starts.push(dateStr)
    }
  }
  return starts.sort()
}

function slicePhaseMapForRange(phaseMap, startDate, endDate, today, allActual = false) {
  const out = []
  let current = typeof startDate === 'string' ? parseISO(startDate) : startDate
  const end = typeof endDate === 'string' ? parseISO(endDate) : endDate
  while (current <= end) {
    const dateKey = format(current, 'yyyy-MM-dd')
    const entry = phaseMap[dateKey]
    if (entry) {
      const isPredicted = allActual ? false : current > today
      out.push({
        date: dateKey,
        phase: typeof entry === 'string' ? entry : entry.phase,
        phase_day_id: typeof entry === 'object' ? entry.phase_day_id : null,
        is_predicted: typeof entry === 'object' ? (entry.is_predicted ?? isPredicted) : isPredicted,
        is_virtual: typeof entry === 'object' ? (entry.is_virtual === true || entry.isVirtual === true) : false,
      })
    }
    current = addDays(current, 1)
  }
  return out
}

const PHASE_MAP_MAX_AGE_MS = 5 * 60 * 1000 // 5 minutes

export function CycleProvider({ children }) {
  const { dashboardData, updatePhaseMap } = useDataContext()
  const updatePhaseMapRef = useRef(updatePhaseMap)
  updatePhaseMapRef.current = updatePhaseMap
  const dashboardDataRef = useRef(dashboardData)
  dashboardDataRef.current = dashboardData

  const [masterPhaseMap, setMasterPhaseMap] = useState({})
  const [cycleStats, setCycleStats] = useState(null)
  const [currentCycle, setCurrentCycle] = useState(null)
  const [allCycles, setAllCycles] = useState([])
  const [periodLogs, setPeriodLogs] = useState([])
  const [isDataReady, setIsDataReady] = useState(false)
  const hasFetchedRef = useRef(false)
  const fetchInProgressRef = useRef(false)
  const phaseMapFetchedAtRef = useRef(0)

  const loadAllData = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setIsDataReady(true)
      return
    }
    if (fetchInProgressRef.current) return
    const now = Date.now()
    if (phaseMapFetchedAtRef.current > 0 && (now - phaseMapFetchedAtRef.current) < PHASE_MAP_MAX_AGE_MS) {
      setIsDataReady(true)
      return
    }
    const existingPhaseMap = dashboardDataRef.current?.phaseMap
    const todayStrBootstrap = format(new Date(), 'yyyy-MM-dd')
    if (existingPhaseMap && Object.keys(existingPhaseMap).length > 0) {
      const enriched = enrichKeyedPhaseMap(existingPhaseMap, todayStrBootstrap)
      setMasterPhaseMap(enriched)
      phaseMapFetchedAtRef.current = now
      updatePhaseMapRef.current?.(enriched)
    }
    fetchInProgressRef.current = true

    try {
      const nowDate = new Date()
      const todayStr = format(nowDate, 'yyyy-MM-dd')
      const start = addDays(nowDate, -Math.floor(PHASE_MAP_DAYS / 2))
      const end = addDays(nowDate, Math.floor(PHASE_MAP_DAYS / 2))
      const startDate = format(start, 'yyyy-MM-dd')
      const endDate = format(end, 'yyyy-MM-dd')

      let keyed =
        existingPhaseMap && Object.keys(existingPhaseMap).length > 0
          ? enrichKeyedPhaseMap(existingPhaseMap, todayStr)
          : null
      if (!keyed) {
        const phaseMapResponse = await getPhaseMap(startDate, endDate).catch(() => ({ phase_map: [] }))
        const phaseMapArray = phaseMapResponse?.phase_map || []
        keyed = buildKeyedPhaseMap(phaseMapArray, todayStr)
        phaseMapFetchedAtRef.current = Date.now()
        setMasterPhaseMap(keyed)
        updatePhaseMapRef.current?.(keyed)
      }

      const [logsResponse, statsResponse] = await Promise.all([
        getPeriodLogs().catch(() => []),
        getCycleStats().catch(() => null),
      ])

      // Set cycle stats
      if (statsResponse) {
        setCycleStats(statsResponse)
      }

      const logs = Array.isArray(logsResponse) ? logsResponse : logsResponse?.data ?? []
      setPeriodLogs(logs)

      const periodStarts = extractPeriodStarts(logs)
      const today = nowDate

      // Extract virtual cycle starts from phase map (backward-projected cycles before first log)
      // Slim phase-map has no is_virtual; treat Period days before first logged start as projected.
      const virtualStarts = []
      if (periodStarts.length > 0 && Object.keys(keyed).length > 0) {
        const firstRealStart = parseISO(periodStarts[0])
        const sortedDates = Object.keys(keyed).sort()
        let lastVirtualPeriodDate = null
        for (const dateKey of sortedDates) {
          const entry = keyed[dateKey]
          const phase = typeof entry === 'string' ? entry : entry?.phase
          const entryDate = parseISO(dateKey)
          if (entryDate >= firstRealStart) break // Stop at first real period
          // Slim API has no is_virtual; any Period before first logged start is projected backward
          if (phase === 'Period' && entryDate < firstRealStart) {
            // Check if this is the start of a new virtual cycle (gap from previous Period day)
            if (!lastVirtualPeriodDate || differenceInDays(entryDate, parseISO(lastVirtualPeriodDate)) >= 21) {
              virtualStarts.push(dateKey)
            }
            lastVirtualPeriodDate = dateKey
          }
        }
        virtualStarts.sort()
      }

      const cycles = []
      const allStarts = [...virtualStarts, ...periodStarts].sort()
      
      // Build cycles from all starts (virtual + real)
      for (let i = 0; i < allStarts.length - 1; i++) {
        const startStr = allStarts[i]
        const endStr = allStarts[i + 1]
        const startD = parseISO(startStr)
        const endD = parseISO(endStr)
        const length = differenceInDays(endD, startD)
        const isVirtualCycle = virtualStarts.includes(startStr)
        const slice = slicePhaseMapForRange(keyed, startD, addDays(endD, -1), today, !isVirtualCycle)
        cycles.push({
          cycleNumber: allStarts.length - i - 1,
          startDate: startStr,
          endDate: endStr,
          length,
          isCurrent: false,
          isAnomaly: length < 21 || length > 45,
          isVirtual: isVirtualCycle,
          cycleData: slice.length ? slice : null,
          cycle_data_json: slice.length ? slice : null,
        })
      }

      if (periodStarts.length > 0) {
        const lastStartStr = periodStarts[periodStarts.length - 1]
        const lastStartDate = parseISO(lastStartStr)
        const currentLength = differenceInDays(today, lastStartDate)
        const liveSlice = slicePhaseMapForRange(keyed, lastStartDate, addDays(lastStartDate, 45), today, false)
        const current = {
          cycleNumber: 0,
          startDate: lastStartStr,
          endDate: null,
          length: currentLength,
          isCurrent: true,
          isAnomaly: false,
          isVirtual: false,
          cycleData: liveSlice.length ? liveSlice : null,
        }
        cycles.push(current)
        setCurrentCycle(current)
      } else {
        setCurrentCycle(null)
      }

      cycles.sort((a, b) => (b.cycleNumber ?? 0) - (a.cycleNumber ?? 0))
      setAllCycles(cycles)
      hasFetchedRef.current = true
      setIsDataReady(true)
    } catch (err) {
      console.error('CycleContext loadAllData error:', err)
      setIsDataReady(true)
    } finally {
      fetchInProgressRef.current = false
    }
  }, [])

  // Legacy alias for backward compatibility
  const fetchCycleData = loadAllData

  const loadOnce = useCallback(() => {
    if (!hasFetchedRef.current) {
      loadAllData()
    }
  }, [loadAllData])

  const refreshCycleData = useCallback(() => {
    hasFetchedRef.current = false
    loadAllData()
  }, [loadAllData])

  const getHistorySlices = useCallback(
    (customPhaseMap = null, customAllCycles = null) => {
      const pm = customPhaseMap ?? masterPhaseMap
      const cycles = customAllCycles ?? allCycles
      if (!cycles.length) return []
      const today = new Date()
      return cycles.map((c) => {
        if (c.cycleData?.length || c.cycle_data_json?.length) {
          return { ...c, cycleData: c.cycleData || c.cycle_data_json }
        }
        const startStr = c.startDate
        if (!startStr) return c
        const startD = parseISO(startStr)
        const endD = c.endDate ? parseISO(c.endDate) : addDays(startD, 45)
        const end = c.isCurrent ? addDays(startD, 45) : addDays(endD, -1)
        const slice = slicePhaseMapForRange(pm, startD, end, today, !c.isCurrent)
        return { ...c, cycleData: slice.length ? slice : null }
      })
    },
    [masterPhaseMap, allCycles]
  )

  const currentPhase = useMemo(() => {
    const todayStr = format(new Date(), 'yyyy-MM-dd')
    const entry = masterPhaseMap[todayStr]
    if (entry) {
      const phase = typeof entry === 'string' ? entry : entry.phase
      const phase_day_id = typeof entry === 'object' ? entry.phase_day_id : null
      return phase ? { phase, phase_day_id } : null
    }
    return null
  }, [masterPhaseMap])

  useEffect(() => {
    loadOnce()
  }, [loadOnce])

  // IMPORTANT: Providers mount before login. If there was no token on initial mount,
  // loadOnce() will early-return and never run again. Listen for authSuccess to
  // immediately fetch phaseMap/cycle data after login/register.
  useEffect(() => {
    const onAuthSuccess = () => {
      refreshCycleData()
    }
    window.addEventListener('authSuccess', onAuthSuccess)
    return () => window.removeEventListener('authSuccess', onAuthSuccess)
  }, [refreshCycleData])

  useEffect(() => {
    const onPeriodLogged = () => {
      refreshCycleData()
    }
    window.addEventListener('periodLogged', onPeriodLogged)
    return () => window.removeEventListener('periodLogged', onPeriodLogged)
  }, [refreshCycleData])

  // Keep manual refresh button in PeriodCalendar working.
  useEffect(() => {
    const onCalendarRefresh = () => refreshCycleData()
    window.addEventListener('calendarRefresh', onCalendarRefresh)
    return () => window.removeEventListener('calendarRefresh', onCalendarRefresh)
  }, [refreshCycleData])

  const value = useMemo(
    () => ({
      masterPhaseMap,
      phaseMap: masterPhaseMap, // Legacy alias for backward compatibility
      cycleStats,
      stats: cycleStats, // Alias for convenience
      currentCycle,
      allCycles,
      periodLogs,
      isDataReady,
      currentPhase,
      loadAllData,
      fetchCycleData, // Legacy alias
      loadOnce,
      refreshCycleData,
      getHistorySlices,
    }),
    [
      masterPhaseMap,
      cycleStats,
      currentCycle,
      allCycles,
      periodLogs,
      isDataReady,
      currentPhase,
      loadAllData,
      loadOnce,
      refreshCycleData,
      getHistorySlices,
    ]
  )

  return <CycleContext.Provider value={value}>{children}</CycleContext.Provider>
}
