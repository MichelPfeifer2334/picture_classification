import type { Album, AppConfig, Health, JobState, UploadResult } from './types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init)
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      detail = (await resp.json()).detail ?? detail
    } catch {
      /* Antwort ohne JSON-Body */
    }
    throw new Error(`${resp.status}: ${detail}`)
  }
  return (await resp.json()) as T
}

export const api = {
  health: () => request<Health>('/api/health'),
  config: () => request<AppConfig>('/api/config'),
  createAlbum: () => request<Album>('/api/albums', { method: 'POST' }),
  getAlbum: (id: string) => request<Album>(`/api/albums/${id}`),

  uploadImages(id: string, files: File[]) {
    const form = new FormData()
    for (const f of files) form.append('files', f, f.name)
    return request<UploadResult>(`/api/albums/${id}/images`, { method: 'POST', body: form })
  },

  startClassification: (id: string) =>
    request<JobState>(`/api/albums/${id}/classify`, { method: 'POST' }),

  thumbUrl: (albumId: string, imageId: string) =>
    `/api/albums/${albumId}/images/${imageId}/thumb`,

  pdfUrl: (albumId: string, excludeBad: boolean) =>
    `/api/albums/${albumId}/export.pdf?exclude_bad=${excludeBad}`,
}
