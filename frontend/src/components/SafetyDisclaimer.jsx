import { AlertCircle } from 'lucide-react'
import { useTranslation } from '../utils/translations'

const SafetyDisclaimer = () => {
  const { t } = useTranslation()
  
  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded mt-8">
      <div className="flex items-start">
        <AlertCircle className="h-5 w-5 text-yellow-400 mr-3 mt-0.5 flex-shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-yellow-800 mb-2">
            {t('safety.title')}
          </h3>
          <p className="text-sm text-yellow-700 mb-2">
            {t('safety.note')}
          </p>
          <p className="text-sm text-yellow-700">
            {t('safety.disclaimer')}
          </p>
        </div>
      </div>
    </div>
  )
}

export default SafetyDisclaimer

