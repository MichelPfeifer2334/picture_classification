// Spiegel der Pydantic-Modelle aus backend/app/models/album.py und services/layout.py

export type Quality = 'good' | 'ok' | 'bad'
export type GroupKind = 'duplicate' | 'burst' | 'similar'

export interface Classification {
  category: string
  aesthetic_score: number
  issues: string[]
  strengths: string[]
  subject: string
  people: number
  focus_x: number
  focus_y: number
  reason: string
  caption: string
}

export interface ImageMetrics {
  sharpness: number
  brightness: number
  dark_fraction: number
  bright_fraction: number
  phash: string
  taken_at: string | null
}

export interface ImageRecord {
  id: string
  filename: string
  width: number
  height: number
  status: 'uploaded' | 'classified' | 'error'
  classification: Classification | null
  error: string | null
  metrics: ImageMetrics | null
  score: number | null
  rank: number | null
  quality: Quality | null
  flags: string[]
  duplicate_of: string | null
  group_kind: GroupKind | null
  group_size: number
  auto_included: boolean
  user_included: boolean | null
  included: boolean
}

export interface JobState {
  status: 'idle' | 'running' | 'done'
  phase: 'analyze' | 'titles'
  done: number
  total: number
  started_at: string | null
}

export interface Chapter {
  id: string
  title: string
  title_edited: boolean
  start: string | null
  image_ids: string[]
}

export interface BookPage {
  template: string
  chapter_id: string
  image_ids: string[]
}

export interface Album {
  id: string
  created_at: string
  images: ImageRecord[]
  job: JobState
  min_score: number
  chapters: Chapter[]
  book: BookPage[] | null
}

export interface UploadResult {
  added: ImageRecord[]
  errors: { filename: string; error: string }[]
}

export interface Health {
  status: string
  ollama: { reachable: boolean; model: string; model_available: boolean }
}

export interface AppConfig {
  model: string
  categories: string[]
}

export interface LayoutCell {
  image_id: string
  x: number
  y: number
  w: number
  h: number
  focus_x: number
  focus_y: number
}

export interface LayoutPage {
  id: string
  template: string
  chapter_id: string
  title: string | null
  subtitle: string | null
  cells: LayoutCell[]
}

export interface BookLayout {
  page_width_mm: number
  page_height_mm: number
  bleed_mm: number
  margin_mm: number
  title_band_mm: number
  manual: boolean
  pages: LayoutPage[]
  unplaced: string[]
}
