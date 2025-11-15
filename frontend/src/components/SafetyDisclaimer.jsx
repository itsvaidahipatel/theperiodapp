import { AlertCircle } from 'lucide-react'

const SafetyDisclaimer = () => {
  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded mt-8">
      <div className="flex items-start">
        <AlertCircle className="h-5 w-5 text-yellow-400 mr-3 mt-0.5 flex-shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-yellow-800 mb-2">
            Important Health Information
          </h3>
          <p className="text-sm text-yellow-700 mb-2">
            <strong>Safety Note:</strong> If you experience severe symptoms or have concerns about your health, please consult with a healthcare professional.
          </p>
          <p className="text-sm text-yellow-700">
            <strong>Disclaimer:</strong> This information is for educational purposes only and should not replace professional medical advice. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition.
          </p>
        </div>
      </div>
    </div>
  )
}

export default SafetyDisclaimer

