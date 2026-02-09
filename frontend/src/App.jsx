import { Routes, Route } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import { DataProvider } from './context/DataContext'
import { ViewModeProvider } from './context/ViewModeContext'
import { CalendarCacheProvider } from './context/CalendarCacheContext'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Profile from './pages/Profile'
import Chat from './pages/Chat'
import Hormones from './pages/Hormones'
import Nutrition from './pages/Nutrition'
import Exercise from './pages/Exercise'
import SelfTests from './pages/SelfTests'
import About from './pages/About'
import CycleHealthCheck from './pages/CycleHealthCheck'
import CycleHistoryPage from './pages/CycleHistory'
import CycleStatistics from './pages/CycleStatistics'
import NotFound from './pages/NotFound'

function App() {
  return (
    <ErrorBoundary>
      <ViewModeProvider>
      <DataProvider>
      <CalendarCacheProvider>
        <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />
        <Route
          path="/hormones"
          element={
            <ProtectedRoute>
              <Hormones />
            </ProtectedRoute>
          }
        />
        <Route
          path="/nutrition"
          element={
            <ProtectedRoute>
              <Nutrition />
            </ProtectedRoute>
          }
        />
        <Route
          path="/exercise"
          element={
            <ProtectedRoute>
              <Exercise />
            </ProtectedRoute>
          }
        />
        <Route
          path="/selftests"
          element={
            <ProtectedRoute>
              <SelfTests />
            </ProtectedRoute>
          }
        />
        <Route
          path="/about"
          element={
            <ProtectedRoute>
              <About />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cycle-health-check"
          element={
            <ProtectedRoute>
              <CycleHealthCheck />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cycle-history"
          element={
            <ProtectedRoute>
              <CycleHistoryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cycle-statistics"
          element={
            <ProtectedRoute>
              <CycleStatistics />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
        </Routes>
      </CalendarCacheProvider>
      </DataProvider>
      </ViewModeProvider>
    </ErrorBoundary>
  )
}

export default App

