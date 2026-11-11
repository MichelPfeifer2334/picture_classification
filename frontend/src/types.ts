// Spiegel der Pydantic-Modelle aus backend/app/models/album.py

export type Quality = 'good' | 'ok' | 'bad'

export interface Classification {
  category: string
  quality: Quality
  quality_reason: string
  caption: string
}

export interface ImageRecord {
  id: string
  filename: string
  width: number
  height: number
  status: 'uploaded' | 'classified' | 'error'
  classification: Classification | null
  error: string | null
}

export interface JobState {
  status: 'idle' | 'running' | 'done'
  done: number
  total: number
}

export interface Album {
  id: string
  created_at: string
  images: ImageRecord[]
  job: JobState
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
