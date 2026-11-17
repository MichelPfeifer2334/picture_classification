// Spiegel der Pydantic-Modelle aus backend/app/models/album.py und services/layout.py

export type Quality = 'good' | 'ok' | 'bad'
export type Style = 'schlicht' | 'elegant' | 'erinnerungen' | 'magazin'
export type SpineDirection = 'top_to_bottom' | 'bottom_to_top'
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
  updated_at: string | null
  name: string
  saved: boolean
  images: ImageRecord[]
  job: JobState
  min_score: number
  chapters: Chapter[]
  book: BookPage[] | null
  book_chapters: Chapter[] | null
  style: Style
  suggested_title: string
  cover: CoverSettings
}

export interface CoverSettings {
  title: string | null
  subtitle: string | null
  spine_text: string | null
  front_image_id: string | null
  back_image_id: string | null
  spine_direction: SpineDirection
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
  print_profile: string
}

export interface LayoutCell {
  image_id: string
  x: number
  y: number
  w: number
  h: number
  focus_x: number
  focus_y: number
  pad_side: number
  pad_top: number
  pad_bottom: number
  rotate: number
}

export interface LayoutChapter {
  id: string
  title: string
  subtitle: string | null
}

export interface BookChapterSpec {
  id: string
  title: string
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
  style: Style
  manual: boolean
  pages: LayoutPage[]
  chapters: LayoutChapter[]
  unplaced: string[]
}

// --- Umschlag (backend/app/services/cover.py) ---

export interface CoverRect {
  x: number
  y: number
  w: number
  h: number
  color: string
  alpha: number
}

export interface CoverImage {
  image_id: string
  x: number
  y: number
  w: number
  h: number
  focus_x: number
  focus_y: number
  pad_side: number
  pad_top: number
  pad_bottom: number
  rotate: number
  line_color: string | null
  tape: boolean
}

export type CoverFont = 'sans' | 'sans-bold' | 'serif' | 'serif-italic' | 'mono' | 'mono-bold'

export interface CoverText {
  text: string
  x: number
  y: number
  w: number
  h: number
  size: number
  font: CoverFont
  color: string
  align: 'left' | 'center' | 'right'
  spacing: number
  rotate: 0 | 90 | -90
}

export interface CoverLayout {
  width_mm: number
  height_mm: number
  pages: number
  content_pages: number
  style: Style
  guides: { bleed_lr: number; bleed_tb: number; spine_x: number; spine_w: number; fold: number; safe: number }
  background: string
  rects: CoverRect[]
  images: CoverImage[]
  texts: CoverText[]
  title: string
  subtitle: string
  spine_text: string
  spine_direction: SpineDirection
  front_image_id: string | null
  back_image_id: string | null
}

export interface CoverPatch {
  title?: string | null
  subtitle?: string | null
  spine_text?: string | null
  front_image_id?: string | null
  back_image_id?: string | null
  spine_direction?: SpineDirection
}

// --- Preflight (backend/app/services/preflight.py) ---

export interface PreflightIssue {
  level: 'error' | 'warning' | 'info'
  text: string
  page: number | null
  image_id: string | null
}

export interface Preflight {
  profile: string
  total_pages: number
  content_pages: number
  blank_pages: number
  max_content_pages: number
  spine_mm: number
  ok: boolean
  issues: PreflightIssue[]
}

// --- Album-Liste ---

export interface AlbumSummary {
  id: string
  name: string
  saved: boolean
  created_at: string
  updated_at: string | null
  image_count: number
  selected_count: number
  classified: boolean
  thumb_image_id: string | null
  running: boolean
}
