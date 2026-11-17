/**
 * Zentraler App-Zustand (bewusst ohne Pinia – ein Modul-Singleton reicht für eine Seite).
 */
import { computed, ref } from 'vue'
import { api } from './api'
import { CATEGORY_ICONS, capitalize, formatDay } from './labels'
import type { Album, AlbumSummary, Health, ImageRecord, Style } from './types'

const UPLOAD_BATCH = 8
const POLL_MS = 1500

export type Filter = 'all' | 'selected' | 'rejected' | 'duplicates'
export type GroupMode = 'story' | 'category'

export interface GalleryGroup {
  key: string
  title: string
  subtitle: string
  icon: string
  images: ImageRecord[]
}

export interface Toast {
  id: number
  kind: 'info' | 'success' | 'error'
  text: string
}

const health = ref<Health | null>(null)
const categories = ref<string[]>([])
const album = ref<Album | null>(null)
const uploading = ref<{ done: number; total: number } | null>(null)
const toasts = ref<Toast[]>([])
const filter = ref<Filter>('all')
const categoryFilter = ref<string | null>(null)
const library = ref<AlbumSummary[]>([]) // alle Alben auf der Festplatte (Startseite)
const groupMode = ref<GroupMode>('story')
const editorOpen = ref(false)
const layoutVersion = ref(0) // erhöht sich bei jeder Änderung → Vorschau lädt neu
let pollTimer: number | undefined
let toastId = 0

// --- abgeleitete Werte -----------------------------------------------------------

const images = computed(() => album.value?.images ?? [])
const running = computed(() => album.value?.job.status === 'running')
const busy = computed(() => running.value || uploading.value !== null)
const pending = computed(() => images.value.filter((i) => i.status !== 'classified').length)
const classified = computed(() => images.value.filter((i) => i.status === 'classified').length)

const stats = computed(() => ({
  total: images.value.length,
  selected: images.value.filter((i) => i.included).length,
  duplicates: images.value.filter((i) => i.duplicate_of).length,
  rejected: images.value.filter((i) => !i.included && !i.duplicate_of).length,
}))

const categoryOf = (img: ImageRecord) => img.classification?.category ?? 'unklassifiziert'

const categoryCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const img of images.value) counts.set(categoryOf(img), (counts.get(categoryOf(img)) ?? 0) + 1)
  const order = [...categories.value, 'unklassifiziert']
  return [...counts.entries()].sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
})

function matches(img: ImageRecord) {
  if (categoryFilter.value && categoryOf(img) !== categoryFilter.value) return false
  switch (filter.value) {
    case 'selected':
      return img.included
    case 'rejected':
      return !img.included && !img.duplicate_of
    case 'duplicates':
      return img.group_size > 1
    default:
      return true
  }
}

const byScore = (a: ImageRecord, b: ImageRecord) => (b.rank ?? -1) - (a.rank ?? -1)

/** Galerie-Gruppen: als Urlaubsgeschichte (Kapitel, chronologisch) oder nach Kategorie. */
const visibleGroups = computed<GalleryGroup[]>(() => {
  const chapters = album.value?.chapters ?? []
  if (groupMode.value === 'story' && chapters.length) {
    const byId = new Map(images.value.map((i) => [i.id, i]))
    return chapters
      .map((ch, n) => {
        const list = ch.image_ids.map((id) => byId.get(id)).filter((i): i is ImageRecord => !!i)
        return {
          key: ch.id,
          title: ch.title || `Abschnitt ${n + 1}`,
          subtitle: formatDay(ch.start),
          icon: '',
          images: list.filter(matches),
        }
      })
      .filter((g) => g.images.length)
  }
  const groups = new Map<string, ImageRecord[]>()
  for (const img of images.value) {
    if (!matches(img)) continue
    const key = categoryOf(img)
    groups.set(key, [...(groups.get(key) ?? []), img])
  }
  const order = [...categories.value, 'unklassifiziert']
  return [...groups.entries()]
    .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
    .map(([key, list]) => ({
      key,
      title: capitalize(key),
      subtitle: '',
      icon: CATEGORY_ICONS[key] ?? '•',
      images: list.sort(byScore),
    }))
})

const visibleImages = computed(() => visibleGroups.value.flatMap((g) => g.images))

const eta = computed(() => {
  const job = album.value?.job
  if (!job || job.status !== 'running' || !job.started_at || job.done === 0) return null
  const elapsed = (Date.now() - new Date(job.started_at).getTime()) / 1000
  const perImage = elapsed / job.done
  return { perImage, remaining: perImage * (job.total - job.done) }
})

// --- Hilfsfunktionen ---------------------------------------------------------------

function toast(text: string, kind: Toast['kind'] = 'info') {
  const id = ++toastId
  toasts.value.push({ id, kind, text })
  window.setTimeout(() => (toasts.value = toasts.value.filter((t) => t.id !== id)), 4500)
}

async function guarded<T>(fn: () => Promise<T>): Promise<T | undefined> {
  try {
    return await fn()
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  }
}

function setAlbum(next: Album) {
  const wasRunning = running.value
  album.value = next
  layoutVersion.value++
  if (wasRunning && next.job.status === 'done') {
    toast(`Analyse fertig – ${stats.value.selected} Bilder fürs Buch ausgewählt`, 'success')
  }
}

// --- Aktionen ---------------------------------------------------------------------

/** App-Start: immer mit leerem Album beginnen – gespeicherte Alben stehen in der Liste. */
async function init() {
  health.value = (await guarded(api.health)) ?? null
  categories.value = (await guarded(api.config))?.categories ?? []
  await loadLibrary()
  try {
    localStorage.removeItem('fotobuch.albumId') // Altlast früherer Versionen entfernen
  } catch {
    /* localStorage evtl. gesperrt */
  }
}

// --- Album-Verwaltung --------------------------------------------------------------

async function loadLibrary() {
  library.value = (await guarded(api.listAlbums)) ?? []
}

const unsaved = computed(() =>
  library.value.filter((a) => !a.saved && a.id !== album.value?.id && a.image_count > 0),
)

/** Gespeichertes Album öffnen – mit Analyse, Auswahl, Layout, Umschlag und Stil. */
async function openAlbum(id: string) {
  stopPolling()
  const loaded = await guarded(() => api.getAlbum(id))
  if (!loaded) return
  filter.value = 'all'
  categoryFilter.value = null
  editorOpen.value = false
  setAlbum(loaded)
  if (running.value) startPolling()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

/** Zurück zur Startseite (Album bleibt auf der Festplatte). */
async function closeAlbum() {
  stopPolling()
  album.value = null
  editorOpen.value = false
  await loadLibrary()
}

/** Speichern = Namen vergeben; danach wird jede Änderung automatisch mitgesichert. */
async function saveAlbum(name: string) {
  const id = album.value?.id
  if (!id) return
  const updated = await guarded(() => api.updateAlbum(id, { name, saved: true }))
  if (updated) {
    setAlbum(updated)
    toast(`„${updated.name}“ gespeichert`, 'success')
  }
}

async function deleteAlbum(id: string) {
  await guarded(() => api.deleteAlbum(id))
  if (album.value?.id === id) album.value = null
  await loadLibrary()
  toast('Album gelöscht', 'success')
}

async function cleanupUnsaved() {
  const result = await guarded(() => api.cleanupUnsaved(album.value?.id))
  if (result) toast(`${result.deleted} nicht gespeicherte Analyse(n) gelöscht`, 'success')
  await loadLibrary()
}

/** Namensvorschlag: Titel (Modell) + Monat/Jahr der Aufnahmen. */
const suggestedName = computed(() => {
  const a = album.value
  if (!a) return ''
  const title = a.cover.title || a.suggested_title || 'Urlaub'
  const times = a.images.map((i) => i.metrics?.taken_at).filter((t): t is string => !!t).sort()
  if (!times.length) return title
  const fmt = new Intl.DateTimeFormat('de-DE', { month: 'long', year: 'numeric' })
  return `${title} · ${fmt.format(new Date(times[0]!))}`
})

async function newAlbum() {
  stopPolling()
  const created = await guarded(api.createAlbum)
  if (created) {
    album.value = created
    filter.value = 'all'
    categoryFilter.value = null
  }
}

async function upload(files: File[]) {
  if (!album.value) await newAlbum()
  const id = album.value?.id
  if (!id) return

  uploading.value = { done: 0, total: files.length }
  let added = 0
  const errors: string[] = []
  try {
    for (let i = 0; i < files.length; i += UPLOAD_BATCH) {
      const batch = files.slice(i, i + UPLOAD_BATCH)
      const result = await guarded(() => api.uploadImages(id, batch))
      if (!result) break
      added += result.added.length
      errors.push(...result.errors.map((e) => e.filename))
      if (uploading.value) uploading.value.done += batch.length
    }
  } finally {
    uploading.value = null
    await refresh()
  }
  toast(`${added} Bilder hinzugefügt`, 'success')
  if (errors.length) toast(`${errors.length} Datei(en) übersprungen: ${errors.slice(0, 3).join(', ')}…`, 'error')
}

async function classify(force = false) {
  const id = album.value?.id
  if (!id) return
  const job = await guarded(() => api.startClassification(id, force))
  if (job && album.value) {
    album.value.job = job
    if (job.status === 'running') startPolling()
  }
}

async function refresh() {
  const id = album.value?.id
  if (!id) return
  const fresh = await guarded(() => api.getAlbum(id))
  if (fresh) setAlbum(fresh)
  if (!running.value) stopPolling()
}

async function setMinScore(value: number) {
  const id = album.value?.id
  if (!id) return
  const updated = await guarded(() => api.updateAlbum(id, { min_score: value }))
  if (updated) setAlbum(updated)
}

async function setStyle(style: Style) {
  const id = album.value?.id
  if (!id) return
  const updated = await guarded(() => api.updateAlbum(id, { style }))
  if (updated) setAlbum(updated)
}

async function updateImage(imageId: string, patch: { included?: boolean | null; category?: string }) {
  const id = album.value?.id
  if (!id) return
  const updated = await guarded(() => api.updateImage(id, imageId, patch))
  if (updated) setAlbum(updated)
}

function toggleIncluded(img: ImageRecord) {
  // Klick auf den Automatik-Wert zurück → wieder Automatik
  const next = !img.included
  return updateImage(img.id, { included: next === img.auto_included ? null : next })
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(refresh, POLL_MS)
}

function stopPolling() {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
  pollTimer = undefined
}

export function useAlbum() {
  return {
    // Zustand
    health,
    categories,
    album,
    uploading,
    toasts,
    library,
    unsaved,
    suggestedName,
    filter,
    categoryFilter,
    groupMode,
    editorOpen,
    layoutVersion,
    // abgeleitet
    images,
    running,
    busy,
    pending,
    classified,
    stats,
    categoryCounts,
    visibleGroups,
    visibleImages,
    eta,
    // Aktionen
    init,
    loadLibrary,
    openAlbum,
    closeAlbum,
    saveAlbum,
    deleteAlbum,
    cleanupUnsaved,
    newAlbum,
    upload,
    classify,
    refresh,
    setMinScore,
    setStyle,
    updateImage,
    toggleIncluded,
    stopPolling,
    toast,
  }
}
