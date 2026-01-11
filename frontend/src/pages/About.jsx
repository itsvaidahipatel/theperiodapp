import { useTranslation } from '../utils/translations'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import { ArrowLeft, Send } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { submitFeedback } from '../utils/api'

const About = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [feedbackForm, setFeedbackForm] = useState({
    subject: '',
    message: '',
    type: 'general'
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitStatus, setSubmitStatus] = useState(null) // 'success' or 'error'
  
  const handleFeedbackChange = (e) => {
    const { name, value } = e.target
    setFeedbackForm(prev => ({
      ...prev,
      [name]: value
    }))
  }
  
  const handleFeedbackSubmit = async (e) => {
    e.preventDefault()
    
    if (!feedbackForm.subject.trim() || !feedbackForm.message.trim()) {
      setSubmitStatus('error')
      return
    }
    
    setIsSubmitting(true)
    setSubmitStatus(null)
    
    try {
      await submitFeedback(feedbackForm.subject, feedbackForm.message, feedbackForm.type)
      setSubmitStatus('success')
      setFeedbackForm({ subject: '', message: '', type: 'general' })
      setTimeout(() => setSubmitStatus(null), 5000)
    } catch (error) {
      console.error('Failed to submit feedback:', error)
      setSubmitStatus('error')
      setTimeout(() => setSubmitStatus(null), 5000)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation with Back Button */}
      <nav className="bg-white shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16 gap-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition"
            >
              <ArrowLeft className="h-5 w-5" />
              <span>{t('nav.backToDashboard')}</span>
            </button>
            <h1 className="text-2xl font-bold text-period-pink">{t('about.title')}</h1>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow-lg p-8 space-y-6">
          <div>
            <h2 className="text-3xl font-bold text-gray-800 mb-4">{t('about.whatIs')}</h2>
            <p className="text-gray-700 text-lg leading-relaxed">
              {t('about.description')}
            </p>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-4">{t('about.features')}</h2>
            <ul className="space-y-3">
              <li className="flex items-start gap-3">
                <span className="text-period-pink font-bold text-xl">•</span>
                <span className="text-gray-700">{t('about.feature1')}</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-period-pink font-bold text-xl">•</span>
                <span className="text-gray-700">{t('about.feature2')}</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-period-pink font-bold text-xl">•</span>
                <span className="text-gray-700">{t('about.feature3')}</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-period-pink font-bold text-xl">•</span>
                <span className="text-gray-700">{t('about.feature4')}</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-period-pink font-bold text-xl">•</span>
                <span className="text-gray-700">{t('about.feature5')}</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-period-pink font-bold text-xl">•</span>
                <span className="text-gray-700">{t('about.feature6')}</span>
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-4">{t('about.howItWorks')}</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              {t('about.howItWorksDesc')}
            </p>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-4">{t('about.ourMission')}</h2>
            <p className="text-gray-700 leading-relaxed">
              {t('about.missionDesc')}
            </p>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-6">{t('about.team')}</h2>
            
            {/* Main Creator - Big Format */}
            <div className="mb-8 bg-gradient-to-br from-period-pink/20 to-period-pink/5 rounded-xl p-8 border-4 border-period-pink shadow-lg">
              <div className="flex flex-col md:flex-row items-center md:items-start gap-6">
                <div className="w-48 h-48 rounded-full overflow-hidden border-4 border-period-pink bg-period-pink flex items-center justify-center flex-shrink-0 shadow-lg">
                  {t('about.creatorPhoto') ? (
                    <img 
                      src={t('about.creatorPhoto')} 
                      alt={t('about.creatorName')}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none'
                        e.target.nextSibling.style.display = 'flex'
                      }}
                    />
                  ) : null}
                  <div className={`w-full h-full ${t('about.creatorPhoto') ? 'hidden' : 'flex'} items-center justify-center text-white text-6xl font-bold`}>
                    {t('about.creatorInitials')}
                  </div>
                </div>
                <div className="flex-1 text-center md:text-left">
                  <h3 className="text-3xl font-bold text-period-pink mb-3">{t('about.mainCreator')}</h3>
                  <p className="text-2xl font-bold text-gray-800 mb-2">{t('about.creatorName')}</p>
                  <p className="text-xl text-gray-700 mb-3">{t('about.creatorOccupation')}</p>
                  <p className="text-lg text-gray-600">{t('about.creatorPlace')}</p>
                </div>
              </div>
            </div>

            {/* Medical Support */}
            <div className="flex justify-center">
              <div className="bg-teal-50 rounded-lg p-6 border-2 border-teal-300 max-w-md">
                <div className="flex flex-col items-center text-center">
                  <div className="w-32 h-32 rounded-full mb-4 overflow-hidden border-4 border-teal-500 bg-teal-500 flex items-center justify-center">
                    {t('about.doctorPhoto') ? (
                      <img 
                        src={t('about.doctorPhoto')} 
                        alt={t('about.doctorName')}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.style.display = 'none'
                          e.target.nextSibling.style.display = 'flex'
                        }}
                      />
                    ) : null}
                    <div className={`w-full h-full ${t('about.doctorPhoto') ? 'hidden' : 'flex'} items-center justify-center text-white text-4xl font-bold`}>
                      {t('about.doctorInitials')}
                    </div>
                  </div>
                  <h3 className="text-xl font-bold text-teal-700 mb-2">{t('about.medicalSupport')}</h3>
                  <p className="text-gray-800 font-semibold mb-1">{t('about.doctorName')}</p>
                  <p className="text-gray-600 text-sm mb-2">{t('about.doctorOccupation')}</p>
                  <p className="text-gray-500 text-xs">{t('about.doctorPlace')}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Feedback Form Section */}
          <div className="pt-6 border-t border-gray-200 mt-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">{t('about.feedback')}</h2>
            <p className="text-gray-600 mb-6">{t('about.feedbackDesc')}</p>
            
            <form onSubmit={handleFeedbackSubmit} className="space-y-4">
              <div>
                <label htmlFor="feedbackType" className="block text-sm font-medium text-gray-700 mb-2">
                  {t('about.feedbackType')}
                </label>
                <select
                  id="feedbackType"
                  name="type"
                  value={feedbackForm.type}
                  onChange={handleFeedbackChange}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-period-pink"
                >
                  <option value="general">{t('about.feedbackTypeGeneral')}</option>
                  <option value="question">{t('about.feedbackTypeQuestion')}</option>
                  <option value="suggestion">{t('about.feedbackTypeSuggestion')}</option>
                  <option value="bug">{t('about.feedbackTypeBug')}</option>
                  <option value="other">{t('about.feedbackTypeOther')}</option>
                </select>
              </div>
              
              <div>
                <label htmlFor="feedbackSubject" className="block text-sm font-medium text-gray-700 mb-2">
                  {t('about.feedbackSubject')}
                </label>
                <input
                  type="text"
                  id="feedbackSubject"
                  name="subject"
                  value={feedbackForm.subject}
                  onChange={handleFeedbackChange}
                  placeholder={t('about.feedbackPlaceholderSubject')}
                  required
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-period-pink"
                />
              </div>
              
              <div>
                <label htmlFor="feedbackMessage" className="block text-sm font-medium text-gray-700 mb-2">
                  {t('about.feedbackMessage')}
                </label>
                <textarea
                  id="feedbackMessage"
                  name="message"
                  value={feedbackForm.message}
                  onChange={handleFeedbackChange}
                  placeholder={t('about.feedbackPlaceholderMessage')}
                  required
                  rows={6}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-period-pink resize-none"
                />
              </div>
              
              {submitStatus === 'success' && (
                <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg">
                  {t('about.feedbackSuccess')}
                </div>
              )}
              
              {submitStatus === 'error' && (
                <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
                  {t('about.feedbackError')}
                </div>
              )}
              
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-period-pink text-white px-6 py-3 rounded-lg font-semibold hover:bg-opacity-90 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>{t('about.feedbackSubmitting')}</span>
                  </>
                ) : (
                  <>
                    <Send className="h-5 w-5" />
                    <span>{t('about.feedbackSubmit')}</span>
                  </>
                )}
              </button>
            </form>
          </div>

          <div className="pt-6 border-t border-gray-200">
            <p className="text-gray-600 text-sm">
              {t('about.footer')}
            </p>
          </div>
        </div>

        {/* Safety Disclaimer - At the bottom */}
        <div className="mt-8">
          <SafetyDisclaimer />
        </div>
      </div>
    </div>
  )
}

export default About

