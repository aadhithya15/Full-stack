export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'

export const SKIN_TONES = [
  { value: 'fair', label: 'Fair', swatch: '#C5AFA3' },
  { value: 'light', label: 'Light', swatch: '#BBA192' },
  { value: 'wheatish', label: 'Wheatish', swatch: '#AE9181' },
  { value: 'medium', label: 'Medium', swatch: '#BE815E' },
  { value: 'dusky', label: 'Dusky', swatch: '#9E7F6E' },
  { value: 'deep', label: 'Deep', swatch: '#90705C' },
]

export const OCCASIONS = [
  'office', 'wedding', 'party', 'festival', 'interview', 'casual', 'farewell', 'other',
]

export const STYLE_PREFERENCES = ['any', 'traditional', 'western', 'formal', 'casual']
export const GENDERS = ['female', 'male', 'neutral']
export const BUDGETS = ['low', 'medium', 'premium']
export const WEATHER_OPTIONS = ['any', 'hot', 'humid', 'rainy', 'winter']
