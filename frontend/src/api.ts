import type {
  Album,
  AppConfig,
  BookLayout,
  BookPage,
  Health,
  JobState,
  UploadResult,
} from './types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init)
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* Antwort ohne JSON-Body */
    }
    throw new Error(`${resp.status}: ${detail}`)
  }
  return (await resp.json()) as T
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

export const api = {
  health: () => request<Health>('/api/health'),
  config: () => request<AppConfig>('/api/config'),

  createAlbum: () => request<Album>('/api/albums', { method: 'POST' }),
  getAlbum: (id: string) => request<Album>(`/api/albums/${id}`),
  updateAlbum: (id: string, patch: { min_score?: number }) =>
    request<Album>(`/api/albums/${id}`, json('PATCH', patch)),

  uploadImages(id: string, files: File[]) {
    const form = new FormData()
    for (const f of files) form.append('files', f, f.name)
    return request<UploadResult>(`/api/albums/${id}/images`, { method: 'POST', body: form })
  },

  updateImage: (
    albumId: string,
    imageId: string,
    patch: { included?: boolean | null; category?: string },
  ) => request<Album>(`/api/albums/${albumId}/images/${imageId}`, json('PATCH', patch)),

  startClassification: (id: string, force = false) =>
    request<JobState>(`/api/albums/${id}/classify?force=${force}`, { method: 'POST' }),

  // --- Fotobuch ---
  layout: (id: string) => request<BookLayout>(`/api/albums/${id}/layout`),
  saveBook: (id: string, pages: BookPage[], include: string[] = [], exclude: string[] = []) =>
    request<BookLayout>(`/api/albums/${id}/book`, json('PUT', { pages, include, exclude })),
  resetBook: (id: string) => request<BookLayout>(`/api/albums/${id}/book`, { method: 'DELETE' }),
  updateChapter: (id: string, chapterId: string, title: string) =>
    request<BookLayout>(`/api/albums/${id}/chapters/${chapterId}`, json('PATCH', { title })),

  thumbUrl: (albumId: string, imageId: string) =>
    `/api/albums/${albumId}/images/${imageId}/thumb`,
  previewUrl: (albumId: string, imageId: string) =>
    `/api/albums/${albumId}/images/${imageId}/preview`,
  pdfUrl: (albumId: string) => `/api/albums/${albumId}/export.pdf`,
}
