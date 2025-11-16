/**
 * Helper functions to translate database values
 */

import { t } from './translations'
import { getUserLanguage } from './userPreferences'

/**
 * Translate hormone level values
 * @param {string} value - Hormone level value from database (e.g., "Low", "Rising", "Medium", "High", "Medium/High")
 * @returns {string} - Translated value
 */
export const translateHormoneLevel = (value) => {
  if (!value) return value
  
  const valueLower = value.toLowerCase().trim()
  const language = getUserLanguage()
  
  // Map database values to translation keys
  const levelMap = {
    'low': 'hormoneLevel.low',
    'rising': 'hormoneLevel.rising',
    'medium': 'hormoneLevel.medium',
    'high': 'hormoneLevel.high',
    'medium/high': 'hormoneLevel.mediumHigh',
    'medium-high': 'hormoneLevel.mediumHigh',
  }
  
  const translationKey = levelMap[valueLower]
  if (translationKey) {
    return t(translationKey, language)
  }
  
  // If no mapping found, return original value
  return value
}

/**
 * Translate nutrient names
 * @param {string} nutrientName - Nutrient name from database
 * @returns {string} - Translated nutrient name
 */
export const translateNutrientName = (nutrientName) => {
  if (!nutrientName) return nutrientName
  
  const language = getUserLanguage()
  
  // Map database nutrient names to translation keys
  const nutrientMap = {
    'Vitamin D': 'nutrient.vitaminD',
    'Protein': 'nutrient.protein',
    'Zinc': 'nutrient.zinc',
    'Calcium': 'nutrient.calcium',
    'Omega-3': 'nutrient.omega3',
    'Choline': 'nutrient.choline',
    'Vitamin A': 'nutrient.vitaminA',
    'B Vitamins': 'nutrient.bVitamins',
    'Healthy Fats': 'nutrient.healthyFats',
    'Antioxidants': 'nutrient.antioxidants',
    'Iron': 'nutrient.iron',
    'Vitamin E': 'nutrient.vitaminE',
    'Complex Carbs': 'nutrient.complexCarbs',
    'Vitamin C': 'nutrient.vitaminC',
    'Magnesium': 'nutrient.magnesium',
    'Fiber': 'nutrient.fiber',
    'Vitamin K': 'nutrient.vitaminK',
    'Hydration': 'nutrient.hydration',
    'Selenium': 'nutrient.selenium',
  }
  
  const translationKey = nutrientMap[nutrientName]
  if (translationKey) {
    return t(translationKey, language)
  }
  
  // If no mapping found, return original value
  return nutrientName
}

/**
 * Translate cuisine names
 * @param {string} cuisineName - Cuisine name from database
 * @returns {string} - Translated cuisine name
 */
export const translateCuisineName = (cuisineName) => {
  if (!cuisineName) return cuisineName
  
  const language = getUserLanguage()
  
  // Map database cuisine names to translation keys
  const cuisineMap = {
    'international': 'cuisine.international',
    'south_indian': 'cuisine.southIndian',
    'north_indian': 'cuisine.northIndian',
    'gujarati': 'cuisine.gujarati',
  }
  
  const translationKey = cuisineMap[cuisineName.toLowerCase()]
  if (translationKey) {
    return t(translationKey, language)
  }
  
  // If no mapping found, return original value
  return cuisineName
}

