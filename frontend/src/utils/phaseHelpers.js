/**
 * Helper functions for cycle phase mapping and display
 */

// Map phase to color class
export const getPhaseColorClass = (phase) => {
  const phaseMap = {
    'Period': 'menstrual',
    'Menstrual': 'menstrual',
    'Follicular': 'follicular',
    'Ovulation': 'ovulation',
    'Luteal': 'luteal'
  }
  return phaseMap[phase] || 'menstrual'
}

// Get phase description
export const getPhaseDescription = (phase) => {
  const descriptions = {
    'Period': 'Your body is working hard during menstruation. Rest and take care of yourself.',
    'Menstrual': 'Your body is working hard during menstruation. Rest and take care of yourself.',
    'Follicular': 'Energy is building up. Great time for new beginnings and fresh starts.',
    'Ovulation': 'Peak energy and vitality. Perfect time for important tasks and social activities.',
    'Luteal': 'Time to slow down and listen to your body. Focus on self-care and preparation.'
  }
  return descriptions[phase] || 'Take care of yourself today.'
}

// Get phase emoji
export const getPhaseEmoji = (phase) => {
  const emojis = {
    'Period': '🌙',
    'Menstrual': '🌙',
    'Follicular': '🌱',
    'Ovulation': '✨',
    'Luteal': '🍂'
  }
  return emojis[phase] || '💜'
}

// Get daily tips for phase
export const getPhaseTips = (phase) => {
  const tips = {
    'Period': [
      'Rest and prioritize self-care',
      'Stay hydrated and eat iron-rich foods',
      'Use heat therapy for cramps',
      'Listen to your body and take breaks'
    ],
    'Menstrual': [
      'Rest and prioritize self-care',
      'Stay hydrated and eat iron-rich foods',
      'Use heat therapy for cramps',
      'Listen to your body and take breaks'
    ],
    'Follicular': [
      'Great time to start new projects',
      'Focus on building habits',
      'Engage in light to moderate exercise',
      'Plan and organize your goals'
    ],
    'Ovulation': [
      'Harness your peak energy',
      'Schedule important meetings',
      'Engage in social activities',
      'Take on challenging tasks'
    ],
    'Luteal': [
      'Prepare for your upcoming period',
      'Focus on gentle exercises',
      'Prioritize sleep and rest',
      'Be kind to yourself'
    ]
  }
  return tips[phase] || [
    'Take care of yourself',
    'Stay hydrated',
    'Get enough rest',
    'Listen to your body'
  ]
}

// Get phase color for calendar
export const getPhaseColor = (phase) => {
  const colors = {
    'Period': '#F8BBD9',
    'Menstrual': '#F8BBD9',
    'Follicular': '#B2DFDB',
    'Ovulation': '#FFF8E1',
    'Luteal': '#E1BEE7'
  }
  return colors[phase] || '#F8BBD9'
}

