import type {
  Album,
  AlbumSummary,
  AppConfig,
  BookChapterSpec,
  BookLayout,
  BookPage,
  CoverLayout,
  CoverPatch,
  Health,
  JobState,
  Preflight,
  Style,
  UploadResult,
} from './types'

export interface SaveBookOptions {
  chapters?: BookChapterSpec[]
  include?: string[]
  exclude?: string[]
}

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
  listAlbums: () => request<AlbumSummary[]>('/api/albums'),
  deleteAlbum: async (id: string) => {
    const resp = await fetch(`/api/albums/${id}`, { method: 'DELETE' })
    if (!resp.ok && resp.status !== 404) throw new Error(`${resp.status}: Löschen fehlgeschlagen`)
  },
  cleanupUnsaved: (keep?: string) =>
    request<{ deleted: number }>(`/api/albums/cleanup${keep ? `?keep=${keep}` : ''}`, { method: 'POST' }),
  updateAlbum: (
    id: string,
    patch: { min_score?: number; style?: Style; name?: string; saved?: boolean },
  ) =>
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
  saveBook: (id: string, pages: BookPage[], opts: SaveBookOptions = {}) =>
    request<BookLayout>(
      `/api/albums/${id}/book`,
      json('PUT', { pages, chapters: opts.chapters, include: opts.include ?? [], exclude: opts.exclude ?? [] }),
    ),
  resetBook: (id: string) => request<BookLayout>(`/api/albums/${id}/book`, { method: 'DELETE' }),
  updateChapter: (id: string, chapterId: string, title: string) =>
    request<BookLayout>(`/api/albums/${id}/chapters/${chapterId}`, json('PATCH', { title })),

  // --- Umschlag & Druck ---
  cover: (id: string) => request<CoverLayout>(`/api/albums/${id}/cover`),
  updateCover: (id: string, patch: CoverPatch) =>
    request<CoverLayout>(`/api/albums/${id}/cover`, json('PATCH', patch)),
  preflight: (id: string) => request<Preflight>(`/api/albums/${id}/preflight`),
  interiorUrl: (id: string) => `/api/albums/${id}/export/innenteil.pdf`,
  coverUrl: (id: string) => `/api/albums/${id}/export/umschlag.pdf`,

  thumbUrl: (albumId: string, imageId: string) =>
    `/api/albums/${albumId}/images/${imageId}/thumb`,
  previewUrl: (albumId: string, imageId: string) =>
    `/api/albums/${albumId}/images/${imageId}/preview`,
  pdfUrl: (albumId: string) => `/api/albums/${albumId}/export.pdf`,
}
