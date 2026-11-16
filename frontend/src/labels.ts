// Deutsche Anzeigenamen für Schlüssel aus dem Backend
import type { Style } from './types'

export const FLAG_LABELS: Record<string, string> = {
  blurry: 'Unscharf',
  motion_blur: 'Verwackelt',
  overexposed: 'Überbelichtet',
  underexposed: 'Zu dunkel',
  eyes_closed: 'Augen zu',
  face_cut_off: 'Gesicht angeschnitten',
  unflattering: 'Unvorteilhaft',
  subject_too_small: 'Motiv zu klein',
  obstructed: 'Verdeckt',
  tilted_horizon: 'Schief',
  cluttered: 'Unruhig',
  boring: 'Belanglos',
  screenshot_or_document: 'Dokument',
  accidental: 'Versehen',
}

export const STRENGTH_LABELS: Record<string, string> = {
  smiling: 'Lächeln',
  natural_expression: 'Natürlich',
  great_light: 'Tolles Licht',
  golden_hour: 'Goldene Stunde',
  strong_composition: 'Starke Komposition',
  iconic_place: 'Wahrzeichen',
  emotional_moment: 'Besonderer Moment',
  vivid_colors: 'Kräftige Farben',
}

export const GROUP_LABELS = {
  duplicate: 'Duplikat',
  burst: 'Serienbild',
  similar: 'Ähnliches Motiv',
} as const

export const QUALITY_LABELS = { good: 'Top', ok: 'Okay', bad: 'Schwach' } as const

export const TEMPLATE_LABELS: Record<string, string> = {
  single: 'Einzelbild',
  full_bleed: 'Randlos',
  two_portrait: '2 Hochformate',
  two_landscape: '2 Querformate',
  mixed: 'Quer + Hoch',
  three: '1 groß links + 2',
  three_mirror: '1 groß rechts + 2',
  three_stack: '1 Hoch + 2 Quer',
  three_portrait: '3 Hochformate',
  three_row: 'Panorama + 2',
  four: 'Raster 2 × 2',
  four_feature: '1 groß + 3',
  four_mosaic: 'Mosaik',
}

export const TEMPLATES_BY_COUNT: Record<number, string[]> = {
  1: ['single', 'full_bleed'],
  2: ['two_portrait', 'two_landscape', 'mixed'],
  3: ['three', 'three_mirror', 'three_stack', 'three_portrait', 'three_row'],
  4: ['four', 'four_feature', 'four_mosaic'],
}

export interface StyleInfo {
  id: Style
  label: string
  description: string
  paper: string
  accent: string
}

/** Gestaltungsstile – müssen zu backend/app/services/styles.py passen. */
export const STYLES: StyleInfo[] = [
  { id: 'schlicht', label: 'Schlicht', description: 'Weiß, klare Linien', paper: '#ffffff', accent: '#29262b' },
  { id: 'elegant', label: 'Elegant', description: 'Creme, Goldlinien, Serifen', paper: '#f7f2e8', accent: '#a8874a' },
  { id: 'erinnerungen', label: 'Erinnerungen', description: 'Polaroids & Klebestreifen', paper: '#efe7da', accent: '#e9c98a' },
  { id: 'magazin', label: 'Magazin', description: 'Groß, Versalien, Farbakzent', paper: '#ffffff', accent: '#ff5f6d' },
]

export const CATEGORY_ICONS: Record<string, string> = {
  strand: '🏖️',
  landschaft: '⛰️',
  stadt: '🏛️',
  essen: '🍝',
  personen: '🧑‍🤝‍🧑',
  tiere: '🐾',
  sonstiges: '✨',
  unklassifiziert: '⏳',
}

export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

const DATE_FMT = new Intl.DateTimeFormat('de-DE', { weekday: 'short', day: 'numeric', month: 'long' })
const TIME_FMT = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' })

export function formatDay(iso: string | null): string {
  return iso ? DATE_FMT.format(new Date(iso)) : 'Ohne Datum'
}

export function formatTime(iso: string | null): string {
  return iso ? TIME_FMT.format(new Date(iso)) : ''
}
