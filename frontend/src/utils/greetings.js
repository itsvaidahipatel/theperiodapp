import { t } from './translations'
import { getUserLanguage } from './userPreferences'

export const getTimeBasedGreeting = () => {
  const hour = new Date().getHours()
  const language = getUserLanguage()
  
  if (hour >= 5 && hour < 12) {
    return t('greeting.morning', language)
  } else if (hour >= 12 && hour < 17) {
    return t('greeting.afternoon', language)
  } else if (hour >= 17 && hour < 21) {
    return t('greeting.evening', language)
  } else {
    return t('greeting.night', language)
  }
}

export const getTimeBasedMessage = (phase) => {
  // Phase-specific messages removed - return empty string
  return ''
}

