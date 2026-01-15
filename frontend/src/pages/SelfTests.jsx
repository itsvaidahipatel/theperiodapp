import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import SafetyDisclaimer from '../components/SafetyDisclaimer'
import LoadingSpinner from '../components/LoadingSpinner'
import { ArrowLeft, CheckCircle2, AlertCircle, Info, BookOpen } from 'lucide-react'
import { useTranslation } from '../utils/translations'

const SelfTests = () => {
  const { t } = useTranslation()
  const [user, setUser] = useState(null)
  const [activeTest, setActiveTest] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      setUser(JSON.parse(userData))
    } else {
      navigate('/login')
    }
  }, [navigate])

  if (!user) {
    return null
  }

  const testCards = [
    { id: 'pcos', title: t('selftests.pcos.title'), description: t('selftests.pcos.description') },
    { id: 'pregnancy', title: t('selftests.pregnancy.title'), description: t('selftests.pregnancy.description') },
    { id: 'menopause', title: t('selftests.menopause.title'), description: t('selftests.menopause.description') },
    { id: 'endometriosis', title: t('selftests.endometriosis.title'), description: t('selftests.endometriosis.description') },
    { id: 'pms', title: t('selftests.pms.title'), description: t('selftests.pms.description') },
    { id: 'irregularities', title: t('selftests.irregularities.title'), description: t('selftests.irregularities.description') },
    { id: 'thyroid', title: t('selftests.thyroid.title'), description: t('selftests.thyroid.description') },
    { id: 'anemia', title: t('selftests.anemia.title'), description: t('selftests.anemia.description') },
    { id: 'diabetes', title: t('selftests.diabetes.title'), description: t('selftests.diabetes.description') },
    { id: 'sti', title: t('selftests.sti.title'), description: t('selftests.sti.description') },
  ]

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
            <h1 className="text-2xl font-bold text-period-pink">{t('selftests.title')}</h1>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-4">{t('selftests.subtitle')}</h2>
          <p className="text-lg text-gray-600 mb-6">
            {t('selftests.description')}
          </p>
        </div>

        {/* Test Selection Grid */}
        {!activeTest && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            {testCards.map((test) => (
              <div
                key={test.id}
                onClick={() => setActiveTest(test.id)}
                className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition cursor-pointer border-2 border-transparent hover:border-period-pink"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-full bg-period-pink/10 flex items-center justify-center">
                    <CheckCircle2 className="h-6 w-6 text-period-pink" />
                  </div>
                  <h3 className="text-xl font-bold text-gray-800">{test.title}</h3>
                </div>
                <p className="text-gray-600 mb-4">{test.description}</p>
                <button className="w-full bg-period-pink text-white py-2 rounded-lg font-semibold hover:bg-opacity-90 transition">
                  {t('selftests.startTest')}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Active Test Components */}
        {activeTest === 'pcos' && <PCOSChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'pregnancy' && <PregnancyChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'menopause' && <MenopauseChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'endometriosis' && <EndometriosisChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'pms' && <PMSChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'irregularities' && <IrregularitiesChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'thyroid' && <ThyroidChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'anemia' && <AnemiaChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'diabetes' && <DiabetesChecker onBack={() => setActiveTest(null)} />}
        {activeTest === 'sti' && <STIChecker onBack={() => setActiveTest(null)} />}

        {/* Safety Disclaimer - At the bottom when no test is active */}
        {!activeTest && (
          <div className="mt-8">
            <SafetyDisclaimer />
          </div>
        )}
      </div>
    </div>
  )
}

// Common Test Component Structure
const TestComponent = ({ 
  testId, 
  onBack, 
  questions, 
  calculateResult, 
  result, 
  setResult, 
  answers, 
  setAnswers,
  loading,
  setLoading
}) => {
  const { t } = useTranslation()
  const allAnswered = questions.every(q => {
    if (q.type === 'date') {
      return answers[q.id] !== undefined && answers[q.id] !== ''
    }
    return answers[q.id] !== undefined
  })

  const handleAnswer = (questionId, value) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: value
    }))
  }

  const handleCalculate = () => {
    setLoading(true)
    setTimeout(() => {
      const calculated = calculateResult(answers, questions)
      setResult(calculated)
      setLoading(false)
    }, 1000)
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition"
        >
          <ArrowLeft className="h-5 w-5" />
          <span>{t('selftests.backToTests')}</span>
        </button>
        <h3 className="text-2xl font-bold text-gray-800">{t(`selftests.${testId}.title`)}</h3>
      </div>

      {/* Information Section */}
      <div className="mb-6 p-5 bg-blue-50 rounded-lg border-l-4 border-blue-400">
        <div className="flex items-start gap-3 mb-4">
          <BookOpen className="h-6 w-6 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <h4 className="text-lg font-bold text-blue-900 mb-2">{t(`selftests.${testId}.info.title`)}</h4>
            <div className="space-y-3 text-sm text-blue-800">
              <p><strong>{t('selftests.info.whatIs')}:</strong> {t(`selftests.${testId}.info.whatIs`)}</p>
              <p><strong>{t('selftests.info.howCommon')}:</strong> {t(`selftests.${testId}.info.howCommon`)}</p>
              <p><strong>{t('selftests.info.howToSolve')}:</strong> {t(`selftests.${testId}.info.howToSolve`)}</p>
            </div>
          </div>
        </div>
      </div>

      {!result ? (
        <>
          <div className="mb-6 p-4 bg-yellow-50 rounded-lg border-l-4 border-yellow-400">
            <div className="flex items-start gap-3">
              <Info className="h-5 w-5 text-yellow-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-yellow-800">{t(`selftests.${testId}.info`)}</p>
            </div>
          </div>

          <div className="space-y-6">
            {questions.map((q, index) => (
              <div key={q.id} className="border border-gray-200 rounded-lg p-4">
                <p className="font-semibold text-gray-800 mb-4">
                  {index + 1}. {q.question}
                </p>
                {q.type === 'yesno' ? (
                  <div className="flex gap-4">
                    <button
                      onClick={() => handleAnswer(q.id, 'yes')}
                      className={`flex-1 py-3 px-4 rounded-lg font-semibold transition ${
                        answers[q.id] === 'yes'
                          ? 'bg-period-pink text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {t('selftests.yes')}
                    </button>
                    <button
                      onClick={() => handleAnswer(q.id, 'no')}
                      className={`flex-1 py-3 px-4 rounded-lg font-semibold transition ${
                        answers[q.id] === 'no'
                          ? 'bg-gray-700 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {t('selftests.no')}
                    </button>
                  </div>
                ) : q.type === 'date' ? (
                  <input
                    type="date"
                    value={answers[q.id] || ''}
                    onChange={(e) => handleAnswer(q.id, e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-period-pink focus:border-transparent"
                  />
                ) : q.type === 'scale' ? (
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((val) => (
                      <button
                        key={val}
                        onClick={() => handleAnswer(q.id, val)}
                        className={`flex-1 py-2 px-3 rounded-lg font-semibold transition ${
                          answers[q.id] === val
                            ? 'bg-period-pink text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          <div className="mt-8 flex justify-center">
            <button
              onClick={handleCalculate}
              disabled={!allAnswered || loading}
              className="bg-period-pink text-white px-8 py-3 rounded-lg font-semibold hover:bg-opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? t('selftests.calculating') : t('selftests.getResults')}
            </button>
          </div>
        </>
      ) : (
        <div className="space-y-6">
          <div className={`p-6 rounded-lg border-l-4 ${
            result.riskLevel === 'high'
              ? 'bg-red-50 border-red-400'
              : result.riskLevel === 'medium'
              ? 'bg-yellow-50 border-yellow-400'
              : 'bg-green-50 border-green-400'
          }`}>
            <div className="flex items-center gap-3 mb-4">
              {result.riskLevel === 'high' ? (
                <AlertCircle className="h-8 w-8 text-red-600" />
              ) : result.riskLevel === 'medium' ? (
                <AlertCircle className="h-8 w-8 text-yellow-600" />
              ) : (
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              )}
              <div>
                <h4 className="text-2xl font-bold text-gray-800 mb-2">
                  {t(`selftests.${testId}.results.${result.riskLevel}.title`)}
                </h4>
                {result.score && (
                  <p className="text-gray-700">
                    {t(`selftests.${testId}.results.score`)}: {result.score}
                  </p>
                )}
              </div>
            </div>
            <p className="text-gray-700 mt-4">{result.recommendation}</p>
          </div>

          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-2">
              <strong>{t('selftests.important')}:</strong> {t(`selftests.${testId}.disclaimer`)}
            </p>
          </div>

          <div className="flex gap-4 justify-center">
            <button
              onClick={() => {
                setResult(null)
                setAnswers({})
              }}
              className="bg-gray-200 text-gray-700 px-6 py-2 rounded-lg font-semibold hover:bg-gray-300 transition"
            >
              {t('selftests.retake')}
            </button>
            <button
              onClick={onBack}
              className="bg-period-pink text-white px-6 py-2 rounded-lg font-semibold hover:bg-opacity-90 transition"
            >
              {t('selftests.backToTests')}
            </button>
          </div>
        </div>
      )}
      
      {/* Safety Disclaimer - At the bottom of each test */}
      <div className="mt-8">
        <SafetyDisclaimer />
      </div>
    </div>
  )
}

// PCOS Checker
const PCOSChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'irregular_periods', question: t('selftests.pcos.questions.irregular_periods'), type: 'yesno' },
    { id: 'excess_hair', question: t('selftests.pcos.questions.excess_hair'), type: 'yesno' },
    { id: 'acne', question: t('selftests.pcos.questions.acne'), type: 'yesno' },
    { id: 'weight_gain', question: t('selftests.pcos.questions.weight_gain'), type: 'yesno' },
    { id: 'hair_loss', question: t('selftests.pcos.questions.hair_loss'), type: 'yesno' },
    { id: 'dark_skin', question: t('selftests.pcos.questions.dark_skin'), type: 'yesno' },
    { id: 'mood_swings', question: t('selftests.pcos.questions.mood_swings'), type: 'yesno' },
    { id: 'sleep_issues', question: t('selftests.pcos.questions.sleep_issues'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const totalQuestions = questions.length
    const percentage = (yesCount / totalQuestions) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.pcos.results.low.rec')
    
    if (percentage >= 50) {
      riskLevel = 'high'
      recommendation = t('selftests.pcos.results.high.rec')
    } else if (percentage >= 30) {
      riskLevel = 'medium'
      recommendation = t('selftests.pcos.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      yesCount,
      totalQuestions,
      recommendation,
      score: `${yesCount}/${totalQuestions} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="pcos"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// Pregnancy Checker
const PregnancyChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'missed_period', question: t('selftests.pregnancy.questions.missed_period'), type: 'yesno' },
    { id: 'nausea', question: t('selftests.pregnancy.questions.nausea'), type: 'yesno' },
    { id: 'breast_tenderness', question: t('selftests.pregnancy.questions.breast_tenderness'), type: 'yesno' },
    { id: 'fatigue', question: t('selftests.pregnancy.questions.fatigue'), type: 'yesno' },
    { id: 'frequent_urination', question: t('selftests.pregnancy.questions.frequent_urination'), type: 'yesno' },
    { id: 'food_cravings', question: t('selftests.pregnancy.questions.food_cravings'), type: 'yesno' },
    { id: 'mood_changes', question: t('selftests.pregnancy.questions.mood_changes'), type: 'yesno' },
    { id: 'last_period_date', question: t('selftests.pregnancy.questions.last_period_date'), type: 'date' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const totalYesNoQuestions = questions.filter(q => q.type === 'yesno').length
    const percentage = (yesCount / totalYesNoQuestions) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.pregnancy.results.low.rec')
    
    if (percentage >= 60) {
      riskLevel = 'high'
      recommendation = t('selftests.pregnancy.results.high.rec')
    } else if (percentage >= 40) {
      riskLevel = 'medium'
      recommendation = t('selftests.pregnancy.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      yesCount,
      totalQuestions: totalYesNoQuestions,
      recommendation,
      score: `${yesCount}/${totalYesNoQuestions} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="pregnancy"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// Menopause/Perimenopause Checker
const MenopauseChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'age', question: t('selftests.menopause.questions.age'), type: 'yesno' },
    { id: 'irregular_periods', question: t('selftests.menopause.questions.irregular_periods'), type: 'yesno' },
    { id: 'hot_flashes', question: t('selftests.menopause.questions.hot_flashes'), type: 'yesno' },
    { id: 'night_sweats', question: t('selftests.menopause.questions.night_sweats'), type: 'yesno' },
    { id: 'mood_changes', question: t('selftests.menopause.questions.mood_changes'), type: 'yesno' },
    { id: 'sleep_issues', question: t('selftests.menopause.questions.sleep_issues'), type: 'yesno' },
    { id: 'vaginal_dryness', question: t('selftests.menopause.questions.vaginal_dryness'), type: 'yesno' },
    { id: 'decreased_libido', question: t('selftests.menopause.questions.decreased_libido'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.menopause.results.low.rec')
    
    if (percentage >= 60) {
      riskLevel = 'high'
      recommendation = t('selftests.menopause.results.high.rec')
    } else if (percentage >= 40) {
      riskLevel = 'medium'
      recommendation = t('selftests.menopause.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="menopause"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// Endometriosis Checker
const EndometriosisChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'pelvic_pain', question: t('selftests.endometriosis.questions.pelvic_pain'), type: 'yesno' },
    { id: 'painful_periods', question: t('selftests.endometriosis.questions.painful_periods'), type: 'yesno' },
    { id: 'pain_during_sex', question: t('selftests.endometriosis.questions.pain_during_sex'), type: 'yesno' },
    { id: 'heavy_bleeding', question: t('selftests.endometriosis.questions.heavy_bleeding'), type: 'yesno' },
    { id: 'infertility', question: t('selftests.endometriosis.questions.infertility'), type: 'yesno' },
    { id: 'digestive_issues', question: t('selftests.endometriosis.questions.digestive_issues'), type: 'yesno' },
    { id: 'fatigue', question: t('selftests.endometriosis.questions.fatigue'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.endometriosis.results.low.rec')
    
    if (percentage >= 60) {
      riskLevel = 'high'
      recommendation = t('selftests.endometriosis.results.high.rec')
    } else if (percentage >= 40) {
      riskLevel = 'medium'
      recommendation = t('selftests.endometriosis.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="endometriosis"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// PMS/PMDD Checker
const PMSChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'mood_swings', question: t('selftests.pms.questions.mood_swings'), type: 'yesno' },
    { id: 'irritability', question: t('selftests.pms.questions.irritability'), type: 'yesno' },
    { id: 'anxiety', question: t('selftests.pms.questions.anxiety'), type: 'yesno' },
    { id: 'depression', question: t('selftests.pms.questions.depression'), type: 'yesno' },
    { id: 'bloating', question: t('selftests.pms.questions.bloating'), type: 'yesno' },
    { id: 'breast_tenderness', question: t('selftests.pms.questions.breast_tenderness'), type: 'yesno' },
    { id: 'fatigue', question: t('selftests.pms.questions.fatigue'), type: 'yesno' },
    { id: 'food_cravings', question: t('selftests.pms.questions.food_cravings'), type: 'yesno' },
    { id: 'sleep_changes', question: t('selftests.pms.questions.sleep_changes'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.pms.results.low.rec')
    
    if (percentage >= 70) {
      riskLevel = 'high'
      recommendation = t('selftests.pms.results.high.rec')
    } else if (percentage >= 50) {
      riskLevel = 'medium'
      recommendation = t('selftests.pms.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="pms"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// Menstrual Irregularities Checker
const IrregularitiesChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'irregular_cycle', question: t('selftests.irregularities.questions.irregular_cycle'), type: 'yesno' },
    { id: 'missed_periods', question: t('selftests.irregularities.questions.missed_periods'), type: 'yesno' },
    { id: 'heavy_bleeding', question: t('selftests.irregularities.questions.heavy_bleeding'), type: 'yesno' },
    { id: 'light_bleeding', question: t('selftests.irregularities.questions.light_bleeding'), type: 'yesno' },
    { id: 'long_periods', question: t('selftests.irregularities.questions.long_periods'), type: 'yesno' },
    { id: 'short_periods', question: t('selftests.irregularities.questions.short_periods'), type: 'yesno' },
    { id: 'spotting', question: t('selftests.irregularities.questions.spotting'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.irregularities.results.low.rec')
    
    if (percentage >= 60) {
      riskLevel = 'high'
      recommendation = t('selftests.irregularities.results.high.rec')
    } else if (percentage >= 40) {
      riskLevel = 'medium'
      recommendation = t('selftests.irregularities.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="irregularities"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// Thyroid Function Checker
const ThyroidChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'fatigue', question: t('selftests.thyroid.questions.fatigue'), type: 'yesno' },
    { id: 'weight_changes', question: t('selftests.thyroid.questions.weight_changes'), type: 'yesno' },
    { id: 'hair_loss', question: t('selftests.thyroid.questions.hair_loss'), type: 'yesno' },
    { id: 'cold_intolerance', question: t('selftests.thyroid.questions.cold_intolerance'), type: 'yesno' },
    { id: 'irregular_periods', question: t('selftests.thyroid.questions.irregular_periods'), type: 'yesno' },
    { id: 'mood_changes', question: t('selftests.thyroid.questions.mood_changes'), type: 'yesno' },
    { id: 'constipation', question: t('selftests.thyroid.questions.constipation'), type: 'yesno' },
    { id: 'dry_skin', question: t('selftests.thyroid.questions.dry_skin'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.thyroid.results.low.rec')
    
    if (percentage >= 60) {
      riskLevel = 'high'
      recommendation = t('selftests.thyroid.results.high.rec')
    } else if (percentage >= 40) {
      riskLevel = 'medium'
      recommendation = t('selftests.thyroid.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="thyroid"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// Anemia/Iron Deficiency Checker
const AnemiaChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'fatigue', question: t('selftests.anemia.questions.fatigue'), type: 'yesno' },
    { id: 'pale_skin', question: t('selftests.anemia.questions.pale_skin'), type: 'yesno' },
    { id: 'shortness_breath', question: t('selftests.anemia.questions.shortness_breath'), type: 'yesno' },
    { id: 'dizziness', question: t('selftests.anemia.questions.dizziness'), type: 'yesno' },
    { id: 'cold_hands_feet', question: t('selftests.anemia.questions.cold_hands_feet'), type: 'yesno' },
    { id: 'brittle_nails', question: t('selftests.anemia.questions.brittle_nails'), type: 'yesno' },
    { id: 'heavy_periods', question: t('selftests.anemia.questions.heavy_periods'), type: 'yesno' },
    { id: 'vegetarian', question: t('selftests.anemia.questions.vegetarian'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.anemia.results.low.rec')
    
    if (percentage >= 60) {
      riskLevel = 'high'
      recommendation = t('selftests.anemia.results.high.rec')
    } else if (percentage >= 40) {
      riskLevel = 'medium'
      recommendation = t('selftests.anemia.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="anemia"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// Diabetes/Insulin Resistance Checker
const DiabetesChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'increased_thirst', question: t('selftests.diabetes.questions.increased_thirst'), type: 'yesno' },
    { id: 'frequent_urination', question: t('selftests.diabetes.questions.frequent_urination'), type: 'yesno' },
    { id: 'increased_hunger', question: t('selftests.diabetes.questions.increased_hunger'), type: 'yesno' },
    { id: 'weight_loss', question: t('selftests.diabetes.questions.weight_loss'), type: 'yesno' },
    { id: 'fatigue', question: t('selftests.diabetes.questions.fatigue'), type: 'yesno' },
    { id: 'blurred_vision', question: t('selftests.diabetes.questions.blurred_vision'), type: 'yesno' },
    { id: 'slow_healing', question: t('selftests.diabetes.questions.slow_healing'), type: 'yesno' },
    { id: 'family_history', question: t('selftests.diabetes.questions.family_history'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.diabetes.results.low.rec')
    
    if (percentage >= 60) {
      riskLevel = 'high'
      recommendation = t('selftests.diabetes.results.high.rec')
    } else if (percentage >= 40) {
      riskLevel = 'medium'
      recommendation = t('selftests.diabetes.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="diabetes"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

// STI Symptom Checklist
const STIChecker = ({ onBack }) => {
  const { t } = useTranslation()
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const questions = [
    { id: 'unusual_discharge', question: t('selftests.sti.questions.unusual_discharge'), type: 'yesno' },
    { id: 'pain_burning', question: t('selftests.sti.questions.pain_burning'), type: 'yesno' },
    { id: 'sores_bumps', question: t('selftests.sti.questions.sores_bumps'), type: 'yesno' },
    { id: 'pelvic_pain', question: t('selftests.sti.questions.pelvic_pain'), type: 'yesno' },
    { id: 'bleeding_between', question: t('selftests.sti.questions.bleeding_between'), type: 'yesno' },
    { id: 'painful_urination', question: t('selftests.sti.questions.painful_urination'), type: 'yesno' },
    { id: 'fever', question: t('selftests.sti.questions.fever'), type: 'yesno' },
  ]

  const calculateResult = (answers, questions) => {
    const yesCount = Object.values(answers).filter(a => a === 'yes').length
    const percentage = (yesCount / questions.length) * 100

    let riskLevel = 'low'
    let recommendation = t('selftests.sti.results.low.rec')
    
    if (percentage >= 50) {
      riskLevel = 'high'
      recommendation = t('selftests.sti.results.high.rec')
    } else if (percentage >= 30) {
      riskLevel = 'medium'
      recommendation = t('selftests.sti.results.medium.rec')
    }

    return {
      riskLevel,
      percentage: Math.round(percentage),
      recommendation,
      score: `${yesCount}/${questions.length} (${Math.round(percentage)}%)`
    }
  }

  return (
    <TestComponent
      testId="sti"
      onBack={onBack}
      questions={questions}
      calculateResult={calculateResult}
      result={result}
      setResult={setResult}
      answers={answers}
      setAnswers={setAnswers}
      loading={loading}
      setLoading={setLoading}
    />
  )
}

export default SelfTests
