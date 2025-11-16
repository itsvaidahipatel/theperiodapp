/**
 * Translation system for multilingual support
 * Supports English (en), Hindi (hi), and Gujarati (gu)
 */

import { useState, useEffect } from 'react'
import { getUserLanguage } from './userPreferences'

const translations = {
  en: {
    // Navigation
    'nav.periodGPT': 'Period GPT',
    'nav.profile': 'Profile',
    'nav.logout': 'Logout',
    'nav.backToDashboard': 'Back to Dashboard',
    
    // Dashboard
    'dashboard.welcome': 'Welcome',
    'dashboard.currentPhase': 'Current Phase',
    'dashboard.day': 'Day',
    'dashboard.aiAssistant': 'AI Assistant',
    'dashboard.aiDescription': 'Get personalized health advice and cycle insights from our AI assistant.',
    'dashboard.startChat': 'Start Chat',
    'dashboard.cycleStatistics': 'Cycle Statistics',
    'dashboard.cycleLength': 'Cycle Length',
    'dashboard.daysSincePeriod': 'Days Since Period',
    'dashboard.daysUntilNext': 'Days Until Next',
    'dashboard.days': 'days',
    'dashboard.logPeriod': 'Log Period',
    'dashboard.hormones': 'Hormones',
    'dashboard.hormonesDesc': 'Track your hormone levels and understand your cycle better.',
    'dashboard.nutrition': 'Nutrition',
    'dashboard.nutritionDesc': 'Get personalized nutrition recommendations for your cycle phase.',
    'dashboard.exercise': 'Exercise',
    'dashboard.exerciseDesc': 'Find the best exercises for your current cycle phase.',
    
    // Phase names
    'phase.period': 'Period',
    'phase.follicular': 'Follicular',
    'phase.ovulation': 'Ovulation',
    'phase.luteal': 'Luteal',
    
    // Hormones page
    'hormones.title': 'Hormones',
    'hormones.currentPhase': 'Current Phase',
    'hormones.moodLevel': 'Mood Level',
    'hormones.energyLevel': 'Energy Level',
    'hormones.bestWorkType': 'Best Type of Work you can do today',
    'hormones.brainNote': 'Brain Note',
    'hormones.estrogen': 'Estrogen',
    'hormones.progesterone': 'Progesterone',
    'hormones.fsh': 'FSH',
    'hormones.lh': 'LH',
    'hormones.level': 'Level',
    'hormones.trend': 'Trend',
    'hormones.noData': 'No hormone data available for this phase.',
    
    // Nutrition page
    'nutrition.title': 'Nutrition',
    'nutrition.currentPhase': 'Current Phase',
    'nutrition.todaysNourishment': "Today's Nourishment",
    'nutrition.workOnNutrients': 'We need to work on these nutrients:',
    'nutrition.filterByCuisine': 'Filter by Cuisine',
    'nutrition.recipesTitle': 'Recipes you can try to boost these nutrients',
    'nutrition.recipe': 'Recipe',
    'nutrition.serves': 'Serves',
    'nutrition.ingredients': 'Ingredients',
    'nutrition.steps': 'Steps',
    'nutrition.nutrients': 'Nutrients',
    'nutrition.noRecipes': 'No recipes available for this phase.',
    
    // Exercise page
    'exercise.title': 'Exercise',
    'exercise.currentPhase': 'Current Phase',
    'exercise.moveWithCycle': 'Move with Your Cycle',
    'exercise.energyLevel': 'Energy Level',
    'exercise.filterByCategory': 'Filter by Category',
    'exercise.category.yoga': 'Yoga/Pilates',
    'exercise.category.cardio': 'Outdoor/Cardio',
    'exercise.category.strength': 'Strength Building',
    'exercise.exercise': 'Exercise',
    'exercise.noExercises': 'No exercises available for the selected category.',
    
    // Profile page
    'profile.title': 'Profile Settings',
    'profile.name': 'Name',
    'profile.email': 'Email',
    'profile.language': 'Language',
    'profile.favoriteCuisine': 'Favorite Cuisine',
    'profile.favoriteExercise': 'Favorite Exercise',
    'profile.changePassword': 'Change Password',
    'profile.currentPassword': 'Current Password',
    'profile.newPassword': 'New Password',
    'profile.confirmPassword': 'Confirm Password',
    'profile.save': 'Save',
    'profile.update': 'Update',
    'profile.cancel': 'Cancel',
    'profile.saved': 'Profile updated successfully!',
    'profile.passwordChanged': 'Password changed successfully!',
    
    // Chat page
    'chat.title': 'AI Health Assistant',
    'chat.welcome': 'Welcome to AI Health Assistant',
    'chat.description': "I'm here to help you with questions about your menstrual cycle, health, and wellness. Ask me anything!",
    'chat.suggestions.pcos': 'What is PCOS?',
    'chat.suggestions.symptoms': 'Period symptoms',
    'chat.suggestions.tracking': 'Cycle tracking',
    'chat.suggestions.nutrition': 'Nutrition tips',
    'chat.typeMessage': 'Type your message...',
    'chat.send': 'Send',
    'chat.loading': 'AI is thinking...',
    'chat.error': 'Sorry, I encountered an error. Please try again later.',
    
    // Auth pages
    'auth.login': 'Login',
    'auth.register': 'Register',
    'auth.email': 'Email',
    'auth.password': 'Password',
    'auth.name': 'Name',
    'auth.lastPeriodDate': 'Last Period Date',
    'auth.cycleLength': 'Cycle Length (days)',
    'auth.cycleLengthHelp': 'Average number of days between periods (typically 21-35 days)',
    'auth.language': 'Language',
    'auth.favoriteCuisine': 'Favorite Cuisine',
    'auth.favoriteExercise': 'Favorite Exercise',
    'auth.submit': 'Submit',
    'auth.loginButton': 'Login',
    'auth.registerButton': 'Create Account',
    'auth.switchToLogin': 'Already have an account? Login',
    'auth.switchToRegister': "Don't have an account? Register",
    'auth.showPassword': 'Show Password',
    'auth.hidePassword': 'Hide Password',
    
    // Common
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.back': 'Back',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.close': 'Close',
    'common.select': 'Select',
    
    // Greetings
    'greeting.morning': 'Good morning',
    'greeting.afternoon': 'Good afternoon',
    'greeting.evening': 'Good evening',
    'greeting.night': 'Good night',
    
    // Safety Disclaimer
    'safety.title': 'Important Health Information',
    'safety.note': 'Safety Note: If you experience severe symptoms or have concerns about your health, please consult with a healthcare professional.',
    'safety.disclaimer': 'Disclaimer: This information is for educational purposes only and should not replace professional medical advice. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition.',
    
    // Hormone levels
    'hormoneLevel.low': 'Low',
    'hormoneLevel.rising': 'Rising',
    'hormoneLevel.medium': 'Medium',
    'hormoneLevel.high': 'High',
    'hormoneLevel.mediumHigh': 'Medium/High',
    
    // Nutrient names
    'nutrient.vitaminD': 'Vitamin D',
    'nutrient.protein': 'Protein',
    'nutrient.zinc': 'Zinc',
    'nutrient.calcium': 'Calcium',
    'nutrient.omega3': 'Omega-3',
    'nutrient.choline': 'Choline',
    'nutrient.vitaminA': 'Vitamin A',
    'nutrient.bVitamins': 'B Vitamins',
    'nutrient.healthyFats': 'Healthy Fats',
    'nutrient.antioxidants': 'Antioxidants',
    'nutrient.iron': 'Iron',
    'nutrient.vitaminE': 'Vitamin E',
    'nutrient.complexCarbs': 'Complex Carbs',
    'nutrient.vitaminC': 'Vitamin C',
    'nutrient.magnesium': 'Magnesium',
    'nutrient.fiber': 'Fiber',
    'nutrient.vitaminK': 'Vitamin K',
    'nutrient.hydration': 'Hydration',
    'nutrient.selenium': 'Selenium',
    
    // Cuisine options
    'cuisine.international': 'International',
    'cuisine.southIndian': 'South Indian',
    'cuisine.northIndian': 'North Indian',
    'cuisine.gujarati': 'Gujarati',
    
    // Exercise categories
    'exerciseCat.yoga': 'Yoga',
    'exerciseCat.cardio': 'Cardio',
    'exerciseCat.strength': 'Strength',
    'exerciseCat.mind': 'Mind',
    'exerciseCat.stretching': 'Stretching',
  },
  
  hi: {
    // Navigation
    'nav.periodGPT': 'पीरियड GPT',
    'nav.profile': 'प्रोफ़ाइल',
    'nav.logout': 'लॉग आउट',
    'nav.backToDashboard': 'डैशबोर्ड पर वापस जाएं',
    
    // Dashboard
    'dashboard.welcome': 'स्वागत है',
    'dashboard.currentPhase': 'वर्तमान चरण',
    'dashboard.day': 'दिन',
    'dashboard.aiAssistant': 'AI सहायक',
    'dashboard.aiDescription': 'हमारे AI सहायक से व्यक्तिगत स्वास्थ्य सलाह और चक्र अंतर्दृष्टि प्राप्त करें।',
    'dashboard.startChat': 'चैट शुरू करें',
    'dashboard.cycleStatistics': 'चक्र आंकड़े',
    'dashboard.cycleLength': 'चक्र की अवधि',
    'dashboard.daysSincePeriod': 'पीरियड के बाद के दिन',
    'dashboard.daysUntilNext': 'अगले तक दिन',
    'dashboard.days': 'दिन',
    'dashboard.logPeriod': 'पीरियड लॉग करें',
    'dashboard.hormones': 'हार्मोन',
    'dashboard.hormonesDesc': 'अपने हार्मोन स्तर को ट्रैक करें और अपने चक्र को बेहतर समझें।',
    'dashboard.nutrition': 'पोषण',
    'dashboard.nutritionDesc': 'अपने चक्र चरण के लिए व्यक्तिगत पोषण सिफारिशें प्राप्त करें।',
    'dashboard.exercise': 'व्यायाम',
    'dashboard.exerciseDesc': 'अपने वर्तमान चक्र चरण के लिए सर्वोत्तम व्यायाम खोजें।',
    
    // Phase names
    'phase.period': 'मासिक धर्म',
    'phase.follicular': 'फॉलिक्युलर',
    'phase.ovulation': 'ओव्यूलेशन',
    'phase.luteal': 'ल्यूटियल',
    
    // Hormones page
    'hormones.title': 'हार्मोन',
    'hormones.currentPhase': 'वर्तमान चरण',
    'hormones.moodLevel': 'मूड स्तर',
    'hormones.energyLevel': 'ऊर्जा स्तर',
    'hormones.bestWorkType': 'आज आप किस प्रकार का कार्य कर सकते हैं',
    'hormones.brainNote': 'मस्तिष्क नोट',
    'hormones.estrogen': 'एस्ट्रोजन',
    'hormones.progesterone': 'प्रोजेस्टेरोन',
    'hormones.fsh': 'FSH',
    'hormones.lh': 'LH',
    'hormones.level': 'स्तर',
    'hormones.trend': 'ट्रेंड',
    'hormones.noData': 'इस चरण के लिए कोई हार्मोन डेटा उपलब्ध नहीं है।',
    
    // Nutrition page
    'nutrition.title': 'पोषण',
    'nutrition.currentPhase': 'वर्तमान चरण',
    'nutrition.todaysNourishment': 'आज का पोषण',
    'nutrition.workOnNutrients': 'हमें इन पोषक तत्वों पर काम करने की आवश्यकता है:',
    'nutrition.filterByCuisine': 'भोजन के प्रकार से फ़िल्टर करें',
    'nutrition.recipesTitle': 'इन पोषक तत्वों को बढ़ाने के लिए आप इन व्यंजनों को आज़मा सकते हैं',
    'nutrition.recipe': 'व्यंजन',
    'nutrition.serves': 'सर्विंग्स',
    'nutrition.ingredients': 'सामग्री',
    'nutrition.steps': 'चरण',
    'nutrition.nutrients': 'पोषक तत्व',
    'nutrition.noRecipes': 'इस चरण के लिए कोई व्यंजन उपलब्ध नहीं है।',
    
    // Exercise page
    'exercise.title': 'व्यायाम',
    'exercise.currentPhase': 'वर्तमान चरण',
    'exercise.moveWithCycle': 'अपने चक्र के साथ चलें',
    'exercise.energyLevel': 'ऊर्जा स्तर',
    'exercise.filterByCategory': 'श्रेणी से फ़िल्टर करें',
    'exercise.category.yoga': 'योग/पिलेट्स',
    'exercise.category.cardio': 'आउटडोर/कार्डियो',
    'exercise.category.strength': 'शक्ति निर्माण',
    'exercise.exercise': 'व्यायाम',
    'exercise.noExercises': 'चयनित श्रेणी के लिए कोई व्यायाम उपलब्ध नहीं है।',
    
    // Profile page
    'profile.title': 'प्रोफ़ाइल सेटिंग्स',
    'profile.name': 'नाम',
    'profile.email': 'ईमेल',
    'profile.language': 'भाषा',
    'profile.favoriteCuisine': 'पसंदीदा भोजन',
    'profile.favoriteExercise': 'पसंदीदा व्यायाम',
    'profile.changePassword': 'पासवर्ड बदलें',
    'profile.currentPassword': 'वर्तमान पासवर्ड',
    'profile.newPassword': 'नया पासवर्ड',
    'profile.confirmPassword': 'पासवर्ड की पुष्टि करें',
    'profile.save': 'सहेजें',
    'profile.update': 'अपडेट करें',
    'profile.cancel': 'रद्द करें',
    'profile.saved': 'प्रोफ़ाइल सफलतापूर्वक अपडेट की गई!',
    'profile.passwordChanged': 'पासवर्ड सफलतापूर्वक बदला गया!',
    
    // Chat page
    'chat.title': 'AI स्वास्थ्य सहायक',
    'chat.welcome': 'AI स्वास्थ्य सहायक में आपका स्वागत है',
    'chat.description': 'मैं आपके मासिक धर्म चक्र, स्वास्थ्य और कल्याण के बारे में प्रश्नों में आपकी मदद करने के लिए यहां हूं। कुछ भी पूछें!',
    'chat.suggestions.pcos': 'PCOS क्या है?',
    'chat.suggestions.symptoms': 'पीरियड के लक्षण',
    'chat.suggestions.tracking': 'चक्र ट्रैकिंग',
    'chat.suggestions.nutrition': 'पोषण सुझाव',
    'chat.typeMessage': 'अपना संदेश टाइप करें...',
    'chat.send': 'भेजें',
    'chat.loading': 'AI सोच रहा है...',
    'chat.error': 'क्षमा करें, मुझे एक त्रुटि मिली। कृपया बाद में पुनः प्रयास करें।',
    
    // Auth pages
    'auth.login': 'लॉगिन',
    'auth.register': 'रजिस्टर करें',
    'auth.email': 'ईमेल',
    'auth.password': 'पासवर्ड',
    'auth.name': 'नाम',
    'auth.lastPeriodDate': 'अंतिम पीरियड की तारीख',
    'auth.cycleLength': 'चक्र की अवधि (दिन)',
    'auth.cycleLengthHelp': 'पीरियड्स के बीच औसत दिनों की संख्या (आमतौर पर 21-35 दिन)',
    'auth.language': 'भाषा',
    'auth.favoriteCuisine': 'पसंदीदा भोजन',
    'auth.favoriteExercise': 'पसंदीदा व्यायाम',
    'auth.submit': 'सबमिट करें',
    'auth.loginButton': 'लॉगिन',
    'auth.registerButton': 'खाता बनाएं',
    'auth.switchToLogin': 'पहले से खाता है? लॉगिन करें',
    'auth.switchToRegister': 'खाता नहीं है? रजिस्टर करें',
    'auth.showPassword': 'पासवर्ड दिखाएं',
    'auth.hidePassword': 'पासवर्ड छुपाएं',
    
    // Common
    'common.loading': 'लोड हो रहा है...',
    'common.error': 'त्रुटि',
    'common.back': 'वापस',
    'common.save': 'सहेजें',
    'common.cancel': 'रद्द करें',
    'common.close': 'बंद करें',
    'common.select': 'चुनें',
    
    // Greetings
    'greeting.morning': 'सुप्रभात',
    'greeting.afternoon': 'नमस्ते',
    'greeting.evening': 'नमस्ते',
    'greeting.night': 'शुभ रात्रि',
    
    // Safety Disclaimer
    'safety.title': 'महत्वपूर्ण स्वास्थ्य जानकारी',
    'safety.note': 'सुरक्षा नोट: यदि आपको गंभीर लक्षण अनुभव होते हैं या आपके स्वास्थ्य के बारे में चिंताएं हैं, तो कृपया एक स्वास्थ्य देखभाल पेशेवर से परामर्श करें।',
    'safety.disclaimer': 'अस्वीकरण: यह जानकारी केवल शैक्षिक उद्देश्यों के लिए है और इसे पेशेवर चिकित्सा सलाह का विकल्प नहीं माना जाना चाहिए। किसी भी चिकित्सा स्थिति के बारे में आपके किसी भी प्रश्न के लिए हमेशा अपने चिकित्सक या अन्य योग्य स्वास्थ्य प्रदाता की सलाह लें।',
    
    // Hormone levels
    'hormoneLevel.low': 'कम',
    'hormoneLevel.rising': 'बढ़ रहा',
    'hormoneLevel.medium': 'मध्यम',
    'hormoneLevel.high': 'उच्च',
    'hormoneLevel.mediumHigh': 'मध्यम/उच्च',
    
    // Nutrient names
    'nutrient.vitaminD': 'विटामिन डी',
    'nutrient.protein': 'प्रोटीन',
    'nutrient.zinc': 'जिंक',
    'nutrient.calcium': 'कैल्शियम',
    'nutrient.omega3': 'ओमेगा-3',
    'nutrient.choline': 'कोलीन',
    'nutrient.vitaminA': 'विटामिन ए',
    'nutrient.bVitamins': 'बी विटामिन',
    'nutrient.healthyFats': 'स्वस्थ वसा',
    'nutrient.antioxidants': 'एंटीऑक्सीडेंट',
    'nutrient.iron': 'आयरन',
    'nutrient.vitaminE': 'विटामिन ई',
    'nutrient.complexCarbs': 'जटिल कार्बोहाइड्रेट',
    'nutrient.vitaminC': 'विटामिन सी',
    'nutrient.magnesium': 'मैग्नीशियम',
    'nutrient.fiber': 'फाइबर',
    'nutrient.vitaminK': 'विटामिन के',
    'nutrient.hydration': 'हाइड्रेशन',
    'nutrient.selenium': 'सेलेनियम',
    
    // Cuisine options
    'cuisine.international': 'अंतर्राष्ट्रीय',
    'cuisine.southIndian': 'दक्षिण भारतीय',
    'cuisine.northIndian': 'उत्तर भारतीय',
    'cuisine.gujarati': 'गुजराती',
    
    // Exercise categories
    'exerciseCat.yoga': 'योग',
    'exerciseCat.cardio': 'कार्डियो',
    'exerciseCat.strength': 'शक्ति',
    'exerciseCat.mind': 'मन',
    'exerciseCat.stretching': 'स्ट्रेचिंग',
  },
  
  gu: {
    // Navigation
    'nav.periodGPT': 'પીરિયડ GPT',
    'nav.profile': 'પ્રોફાઇલ',
    'nav.logout': 'લૉગ આઉટ',
    'nav.backToDashboard': 'ડેશબોર્ડ પર પાછા જાઓ',
    
    // Dashboard
    'dashboard.welcome': 'સ્વાગત છે',
    'dashboard.currentPhase': 'વર્તમાન તબક્કો',
    'dashboard.day': 'દિવસ',
    'dashboard.aiAssistant': 'AI સહાયક',
    'dashboard.aiDescription': 'અમારા AI સહાયક પાસેથી વ્યક્તિગત આરોગ્ય સલાહ અને ચક્ર અંતર્દૃષ્ટિ મેળવો.',
    'dashboard.startChat': 'ચેટ શરૂ કરો',
    'dashboard.cycleStatistics': 'ચક્ર આંકડા',
    'dashboard.cycleLength': 'ચક્રની લંબાઈ',
    'dashboard.daysSincePeriod': 'પીરિયડ પછીના દિવસો',
    'dashboard.daysUntilNext': 'આગલા સુધી દિવસો',
    'dashboard.days': 'દિવસો',
    'dashboard.logPeriod': 'પીરિયડ લૉગ કરો',
    'dashboard.hormones': 'હોર્મોન',
    'dashboard.hormonesDesc': 'તમારા હોર્મોન સ્તરને ટ્રેક કરો અને તમારા ચક્રને વધુ સારી રીતે સમજો.',
    'dashboard.nutrition': 'પોષણ',
    'dashboard.nutritionDesc': 'તમારા ચક્ર તબક્કા માટે વ્યક્તિગત પોષણ ભલામણો મેળવો.',
    'dashboard.exercise': 'વ્યાયામ',
    'dashboard.exerciseDesc': 'તમારા વર્તમાન ચક્ર તબક્કા માટે શ્રેષ્ઠ વ્યાયામ શોધો.',
    
    // Phase names
    'phase.period': 'પીરિયડ',
    'phase.follicular': 'ફોલિક્યુલર',
    'phase.ovulation': 'ઓવ્યુલેશન',
    'phase.luteal': 'લ્યુટિયલ',
    
    // Hormones page
    'hormones.title': 'હોર્મોન',
    'hormones.currentPhase': 'વર્તમાન તબક્કો',
    'hormones.moodLevel': 'મૂડ સ્તર',
    'hormones.energyLevel': 'ઊર્જા સ્તર',
    'hormones.bestWorkType': 'આજે તમે કયા પ્રકારનું કાર્ય કરી શકો છો',
    'hormones.brainNote': 'મગજ નોંધ',
    'hormones.estrogen': 'એસ્ટ્રોજન',
    'hormones.progesterone': 'પ્રોજેસ્ટેરોન',
    'hormones.fsh': 'FSH',
    'hormones.lh': 'LH',
    'hormones.level': 'સ્તર',
    'hormones.trend': 'ટ્રેન્ડ',
    'hormones.noData': 'આ તબક્કા માટે કોઈ હોર્મોન ડેટા ઉપલબ્ધ નથી.',
    
    // Nutrition page
    'nutrition.title': 'પોષણ',
    'nutrition.currentPhase': 'વર્તમાન તબક્કો',
    'nutrition.todaysNourishment': 'આજનું પોષણ',
    'nutrition.workOnNutrients': 'આપણે આ પોષક તત્વો પર કામ કરવાની જરૂર છે:',
    'nutrition.filterByCuisine': 'ભોજન પ્રકાર દ્વારા ફિલ્ટર કરો',
    'nutrition.recipesTitle': 'આ પોષક તત્વોને વધારવા માટે તમે આ વ્યંજનો અજમાવી શકો છો',
    'nutrition.recipe': 'વ્યંજન',
    'nutrition.serves': 'સર્વિંગ્સ',
    'nutrition.ingredients': 'ઘટકો',
    'nutrition.steps': 'પગલાઓ',
    'nutrition.nutrients': 'પોષક તત્વો',
    'nutrition.noRecipes': 'આ તબક્કા માટે કોઈ વ્યંજનો ઉપલબ્ધ નથી.',
    
    // Exercise page
    'exercise.title': 'વ્યાયામ',
    'exercise.currentPhase': 'વર્તમાન તબક્કો',
    'exercise.moveWithCycle': 'તમારા ચક્ર સાથે આગળ વધો',
    'exercise.energyLevel': 'ઊર્જા સ્તર',
    'exercise.filterByCategory': 'શ્રેણી દ્વારા ફિલ્ટર કરો',
    'exercise.category.yoga': 'યોગા/પિલેટ્સ',
    'exercise.category.cardio': 'આઉટડોર/કાર્ડિયો',
    'exercise.category.strength': 'શક્તિ નિર્માણ',
    'exercise.exercise': 'વ્યાયામ',
    'exercise.noExercises': 'પસંદ કરેલી શ્રેણી માટે કોઈ વ્યાયામ ઉપલબ્ધ નથી.',
    
    // Profile page
    'profile.title': 'પ્રોફાઇલ સેટિંગ્સ',
    'profile.name': 'નામ',
    'profile.email': 'ઇમેઇલ',
    'profile.language': 'ભાષા',
    'profile.favoriteCuisine': 'મનપસંદ ભોજન',
    'profile.favoriteExercise': 'મનપસંદ વ્યાયામ',
    'profile.changePassword': 'પાસવર્ડ બદલો',
    'profile.currentPassword': 'વર્તમાન પાસવર્ડ',
    'profile.newPassword': 'નવો પાસવર્ડ',
    'profile.confirmPassword': 'પાસવર્ડની પુષ્ટિ કરો',
    'profile.save': 'સાચવો',
    'profile.update': 'અપડેટ કરો',
    'profile.cancel': 'રદ કરો',
    'profile.saved': 'પ્રોફાઇલ સફળતાપૂર્વક અપડેટ થઈ!',
    'profile.passwordChanged': 'પાસવર્ડ સફળતાપૂર્વક બદલાયો!',
    
    // Chat page
    'chat.title': 'AI આરોગ્ય સહાયક',
    'chat.welcome': 'AI આરોગ્ય સહાયકમાં આપનું સ્વાગત છે',
    'chat.description': 'હું તમારા માસિક ચક્ર, આરોગ્ય અને સુખાકારી વિશેના પ્રશ્નોમાં તમારી મદદ કરવા માટે અહીં છું. કંઈપણ પૂછો!',
    'chat.suggestions.pcos': 'PCOS શું છે?',
    'chat.suggestions.symptoms': 'પીરિયડના લક્ષણો',
    'chat.suggestions.tracking': 'ચક્ર ટ્રેકિંગ',
    'chat.suggestions.nutrition': 'પોષણ ટિપ્સ',
    'chat.typeMessage': 'તમારો સંદેશ ટાઇપ કરો...',
    'chat.send': 'મોકલો',
    'chat.loading': 'AI વિચારી રહ્યું છે...',
    'chat.error': 'માફ કરશો, મને એક ભૂલ મળી. કૃપા કરીને પછી ફરી પ્રયાસ કરો.',
    
    // Auth pages
    'auth.login': 'લૉગિન',
    'auth.register': 'રજિસ્ટર કરો',
    'auth.email': 'ઇમેઇલ',
    'auth.password': 'પાસવર્ડ',
    'auth.name': 'નામ',
    'auth.lastPeriodDate': 'છેલ્લી પીરિયડ તારીખ',
    'auth.cycleLength': 'ચક્રની લંબાઈ (દિવસો)',
    'auth.cycleLengthHelp': 'પીરિયડ્સ વચ્ચે સરેરાશ દિવસોની સંખ્યા (સામાન્ય રીતે 21-35 દિવસો)',
    'auth.language': 'ભાષા',
    'auth.favoriteCuisine': 'મનપસંદ ભોજન',
    'auth.favoriteExercise': 'મનપસંદ વ્યાયામ',
    'auth.submit': 'સબમિટ કરો',
    'auth.loginButton': 'લૉગિન',
    'auth.registerButton': 'એકાઉન્ટ બનાવો',
    'auth.switchToLogin': 'પહેલેથી એકાઉન્ટ છે? લૉગિન કરો',
    'auth.switchToRegister': 'એકાઉન્ટ નથી? રજિસ્ટર કરો',
    'auth.showPassword': 'પાસવર્ડ બતાવો',
    'auth.hidePassword': 'પાસવર્ડ છુપાવો',
    
    // Common
    'common.loading': 'લોડ થઈ રહ્યું છે...',
    'common.error': 'ભૂલ',
    'common.back': 'પાછા',
    'common.save': 'સાચવો',
    'common.cancel': 'રદ કરો',
    'common.close': 'બંધ કરો',
    'common.select': 'પસંદ કરો',
    
    // Greetings
    'greeting.morning': 'સુપ્રભાત',
    'greeting.afternoon': 'નમસ્તે',
    'greeting.evening': 'નમસ્તે',
    'greeting.night': 'શુભ રાત્રી',
    
    // Safety Disclaimer
    'safety.title': 'મહત્વપૂર્ણ આરોગ્ય માહિતી',
    'safety.note': 'સુરક્ષા નોંધ: જો તમને ગંભીર લક્ષણોનો અનુભવ થાય છે અથવા તમારા આરોગ્ય વિશે ચિંતાઓ છે, તો કૃપા કરીને આરોગ્ય સંભાળ વ્યવસાયિકની સલાહ લો.',
    'safety.disclaimer': 'અસ્વીકરણ: આ માહિતી ફક્ત શૈક્ષણિક હેતુઓ માટે છે અને તેને વ્યાવસાયિક તબીબી સલાહનો વિકલ્પ ન ગણવી જોઈએ. કોઈપણ તબીબી સ્થિતિ વિશે તમારા કોઈપણ પ્રશ્નો માટે હંમેશા તમારા ચિકિત્સક અથવા અન્ય યોગ્ય આરોગ્ય પ્રદાતાની સલાહ લો.',
    
    // Hormone levels
    'hormoneLevel.low': 'નીચું',
    'hormoneLevel.rising': 'વધતું',
    'hormoneLevel.medium': 'મધ્યમ',
    'hormoneLevel.high': 'ઊંચું',
    'hormoneLevel.mediumHigh': 'મધ્યમ/ઊંચું',
    
    // Nutrient names
    'nutrient.vitaminD': 'વિટામિન ડી',
    'nutrient.protein': 'પ્રોટીન',
    'nutrient.zinc': 'ઝિંક',
    'nutrient.calcium': 'કેલ્શિયમ',
    'nutrient.omega3': 'ઓમેગા-3',
    'nutrient.choline': 'કોલીન',
    'nutrient.vitaminA': 'વિટામિન એ',
    'nutrient.bVitamins': 'બી વિટામિન',
    'nutrient.healthyFats': 'સ્વસ્થ ચરબી',
    'nutrient.antioxidants': 'એન્ટીઓક્સિડન્ટ્સ',
    'nutrient.iron': 'આયર્ન',
    'nutrient.vitaminE': 'વિટામિન ઇ',
    'nutrient.complexCarbs': 'જટિલ કાર્બોહાઇડ્રેટ',
    'nutrient.vitaminC': 'વિટામિન સી',
    'nutrient.magnesium': 'મેગ્નેશિયમ',
    'nutrient.fiber': 'ફાઇબર',
    'nutrient.vitaminK': 'વિટામિન કે',
    'nutrient.hydration': 'હાઇડ્રેશન',
    'nutrient.selenium': 'સેલેનિયમ',
    
    // Cuisine options
    'cuisine.international': 'આંતરરાષ્ટ્રીય',
    'cuisine.southIndian': 'દક્ષિણ ભારતીય',
    'cuisine.northIndian': 'ઉત્તર ભારતીય',
    'cuisine.gujarati': 'ગુજરાતી',
    
    // Exercise categories
    'exerciseCat.yoga': 'યોગા',
    'exerciseCat.cardio': 'કાર્ડિયો',
    'exerciseCat.strength': 'શક્તિ',
    'exerciseCat.mind': 'મન',
    'exerciseCat.stretching': 'સ્ટ્રેચિંગ',
  },
}

/**
 * Get translation for a key
 * @param {string} key - Translation key (e.g., 'dashboard.welcome')
 * @param {string} language - Language code (en, hi, gu) - optional, uses user's language if not provided
 * @returns {string} - Translated text or the key if not found
 */
export const t = (key, language = null) => {
  const lang = language || getUserLanguage()
  return translations[lang]?.[key] || translations.en?.[key] || key
}

/**
 * Hook to use translations in React components
 * Automatically updates when language changes
 */
export const useTranslation = () => {
  const [language, setLanguage] = useState(() => getUserLanguage())
  
  useEffect(() => {
    const handleLanguageChange = () => {
      setLanguage(getUserLanguage())
    }
    
    window.addEventListener('languageChanged', handleLanguageChange)
    return () => window.removeEventListener('languageChanged', handleLanguageChange)
  }, [])
  
  return {
    t: (key) => t(key, language),
    language,
  }
}

