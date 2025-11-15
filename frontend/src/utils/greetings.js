export const getTimeBasedGreeting = () => {
  const hour = new Date().getHours()
  
  if (hour >= 5 && hour < 12) {
    return 'Good morning'
  } else if (hour >= 12 && hour < 17) {
    return 'Good afternoon'
  } else if (hour >= 17 && hour < 21) {
    return 'Good evening'
  } else {
    return 'Good night'
  }
}

export const getTimeBasedMessage = (phase) => {
  const hour = new Date().getHours()
  const timeOfDay = hour >= 5 && hour < 12 ? 'morning' : 
                    hour >= 12 && hour < 17 ? 'afternoon' : 
                    hour >= 17 && hour < 21 ? 'evening' : 'night'
  
  const phaseMessages = {
    Period: `Take it easy this ${timeOfDay}. Your body is working hard.`,
    Follicular: `Great ${timeOfDay} to focus on new beginnings and fresh energy.`,
    Ovulation: `Perfect ${timeOfDay} to harness your peak energy and vitality.`,
    Luteal: `Gentle ${timeOfDay} to slow down and listen to your body's needs.`,
  }
  
  return phaseMessages[phase] || `Have a wonderful ${timeOfDay}!`
}

