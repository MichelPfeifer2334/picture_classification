<script setup lang="ts">
/**
 * Fotobuch-Editor: manuelle Korrekturen am Layout per Drag & Drop.
 *
 * Bedienung
 * - Bild auf ein anderes Bild ziehen      → tauschen (auch seitenübergreifend)
 * - Bild auf freie Seitenfläche ziehen    → auf diese Seite verschieben (max. 4)
 * - Bild auf "＋" zwischen Seiten ziehen  → neue Seite
 * - Bild in die Ablage ziehen / ✕         → aus dem Buch nehmen
 * - Bild aus der Ablage auf eine Seite    → ins Buch aufnehmen
 *
 * Jede Änderung wird sofort gespeichert (PUT /book); das Backend berechnet die Geometrie.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'
import { TEMPLATE_LABELS, TEMPLATES_BY_COUNT, formatDay } from '../labels'
import type { BookLayout, BookPage, ImageRecord } from '../types'
import { useAlbum } from '../useAlbum'
import BookPageView from './BookPageView.vue'

const { album, images, editorOpen, refresh, toast } = useAlbum()

const layout = ref<BookLayout | null>(null)
const saving = ref(false)
const confirmReset = ref(false)
const dragging = ref(false)
const insertTarget = ref<number | null>(null)
const trayActive = ref(false)

interface Drag {
  imageId: string
  page: number | null // null = aus der Ablage
  cell: number
}
let drag: Drag | null = null

// --- abgeleitete Werte -------------------------------------------------------------

const placed = computed(
  () => new Set(layout.value?.pages.flatMap((p) => p.cells.map((c) => c.image_id)) ?? []),
)

const tray = computed(() => {
  const rest = images.value.filter((i) => !placed.value.has(i.id) && i.status !== 'error')
  const byTime = (a: ImageRecord, b: ImageRecord) =>
    (a.metrics?.taken_at ?? a.filename).localeCompare(b.metrics?.taken_at ?? b.filename)
  return {
    waiting: rest.filter((i) => i.included).sort(byTime),
    excluded: rest.filter((i) => !i.included).sort((a, b) => (b.rank ?? 0) - (a.rank ?? 0)),
  }
})

const chapterTitles = computed(
  () => new Map((album.value?.chapters ?? []).map((c) => [c.id, c])),
)

function startsChapter(index: number) {
  const pages = layout.value?.pages ?? []
  return index === 0 || pages[index]!.chapter_id !== pages[index - 1]!.chapter_id
}

// --- Laden & Speichern ---------------------------------------------------------------

async function load() {
  if (!album.value) return
  layout.value = await api.layout(album.value.id)
}

function specs(): BookPage[] {
  return (layout.value?.pages ?? []).map((p) => ({
    template: p.template,
    chapter_id: p.chapter_id,
    image_ids: p.cells.map((c) => c.image_id),
  }))
}

async function commit(pages: BookPage[], include: string[] = [], exclude: string[] = []) {
  if (!album.value) return
  saving.value = true
  try {
    layout.value = await api.saveBook(album.value.id, pages, include, exclude)
    await refresh()
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
    await load()
  } finally {
    saving.value = false
  }
}

/** Bild an seiner Herkunft entfernen (Seite → Vorlage neu wählen lassen). */
function take(pages: BookPage[], d: Drag) {
  if (d.page === null) return
  pages[d.page]!.image_ids.splice(d.cell, 1)
  pages[d.page]!.template = 'auto'
}

// --- Drag & Drop -------------------------------------------------------------------

function startDrag(d: Drag, e: DragEvent) {
  drag = d
  dragging.value = true
  e.dataTransfer?.setData('text/plain', d.imageId)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function endDrag() {
  drag = null
  dragging.value = false
  insertTarget.value = null
  trayActive.value = false
}

function dropOnCell(pageIndex: number, cellIndex: number) {
  const d = drag
  endDrag()
  if (!d) return
  const pages = specs()
  const target = pages[pageIndex]!.image_ids[cellIndex]!
  if (d.page === pageIndex && d.cell === cellIndex) return
  if (d.page !== null) {
    pages[d.page]!.image_ids[d.cell] = target
    pages[pageIndex]!.image_ids[cellIndex] = d.imageId
    commit(pages)
  } else {
    pages[pageIndex]!.image_ids[cellIndex] = d.imageId
    commit(pages, [d.imageId], [target])
  }
}

function dropOnPage(pageIndex: number) {
  const d = drag
  endDrag()
  if (!d || d.page === pageIndex) return
  const pages = specs()
  if (pages[pageIndex]!.image_ids.length >= 4) {
    toast('Höchstens 4 Bilder pro Seite – zum Tauschen direkt auf ein Bild ziehen', 'info')
    return
  }
  take(pages, d)
  pages[pageIndex]!.image_ids.push(d.imageId)
  pages[pageIndex]!.template = 'auto'
  commit(pages, d.page === null ? [d.imageId] : [])
}

function dropInsert(index: number) {
  const d = drag
  endDrag()
  if (!d) return
  const pages = specs()
  const neighbour = pages[index - 1] ?? pages[index]
  take(pages, d)
  pages.splice(index, 0, {
    template: 'auto',
    chapter_id: neighbour?.chapter_id ?? '',
    image_ids: [d.imageId],
  })
  commit(pages, d.page === null ? [d.imageId] : [])
}

function dropOnTray() {
  const d = drag
  endDrag()
  if (!d || d.page === null) return
  const pages = specs()
  take(pages, d)
  commit(pages, [], [d.imageId])
}

// --- Seiten-Aktionen -----------------------------------------------------------------

function removeCell(pageIndex: number, cellIndex: number) {
  const pages = specs()
  const [id] = pages[pageIndex]!.image_ids.splice(cellIndex, 1)
  pages[pageIndex]!.template = 'auto'
  commit(pages, [], id ? [id] : [])
}

function ownPage(pageIndex: number, cellIndex: number) {
  const pages = specs()
  const page = pages[pageIndex]!
  if (page.image_ids.length === 1) return
  const [id] = page.image_ids.splice(cellIndex, 1)
  page.template = 'auto'
  pages.splice(pageIndex + 1, 0, { template: 'single', chapter_id: page.chapter_id, image_ids: [id!] })
  commit(pages)
}

function setTemplate(pageIndex: number, template: string) {
  const pages = specs()
  pages[pageIndex]!.template = template
  commit(pages)
}

function movePage(pageIndex: number, delta: number) {
  const pages = specs()
  const target = pageIndex + delta
  if (target < 0 || target >= pages.length) return
  ;[pages[pageIndex], pages[target]] = [pages[target]!, pages[pageIndex]!]
  commit(pages)
}

function deletePage(pageIndex: number) {
  const pages = specs()
  const [removed] = pages.splice(pageIndex, 1)
  commit(pages, [], removed?.image_ids ?? [])
}

async function saveTitle(chapterId: string, value: string) {
  if (!album.value || !chapterId) return
  const current = chapterTitles.value.get(chapterId)?.title ?? ''
  if (value.trim() === current) return
  try {
    layout.value = await api.updateChapter(album.value.id, chapterId, value)
    await refresh()
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  }
}

async function reset() {
  if (!album.value) return
  confirmReset.value = false
  layout.value = await api.resetBook(album.value.id)
  await refresh()
  toast('Layout automatisch neu erstellt', 'success')
}

function close() {
  editorOpen.value = false
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="editor" :class="{ dragging }" @dragend="endDrag">
    <header class="bar glass">
      <div>
        <h2>Fotobuch bearbeiten</h2>
        <p class="muted">
          <template v-if="layout">{{ layout.pages.length }} Seiten</template>
          <span v-if="saving" class="saving">· speichert …</span>
          <span v-else-if="layout?.manual" class="saved">· gespeichert</span>
        </p>
      </div>
      <p class="hint muted">
        Bild auf Bild = tauschen · auf freie Fläche = verschieben · auf ＋ = neue Seite · in die Ablage =
        entfernen
      </p>
      <div class="bar-actions">
        <template v-if="confirmReset">
          <span class="muted">Alle manuellen Änderungen verwerfen?</span>
          <button class="btn" @click="reset">Ja, neu erstellen</button>
          <button class="btn btn-ghost" @click="confirmReset = false">Abbrechen</button>
        </template>
        <button v-else class="btn btn-ghost" :disabled="!layout?.manual" @click="confirmReset = true">
          ↺ Automatisch neu anordnen
        </button>
        <button class="btn btn-primary" @click="close">Fertig</button>
      </div>
    </header>

    <div v-if="layout && album" class="body">
      <main class="pages">
        <template v-for="(page, i) in layout.pages" :key="page.id">
          <div
            class="insert"
            :class="{ active: insertTarget === i }"
            @dragover.prevent="insertTarget = i"
            @dragleave="insertTarget = null"
            @drop.prevent="dropInsert(i)"
          >
            <span>＋</span>
          </div>

          <article class="page-card">
            <div v-if="startsChapter(i)" class="chapter">
              <span class="chapter-date">{{ formatDay(chapterTitles.get(page.chapter_id)?.start ?? null) }}</span>
              <input
                class="chapter-title"
                :value="chapterTitles.get(page.chapter_id)?.title ?? ''"
                placeholder="Kapitelüberschrift (optional)"
                maxlength="80"
                @change="saveTitle(page.chapter_id, ($event.target as HTMLInputElement).value)"
                @keydown.enter="($event.target as HTMLInputElement).blur()"
              />
            </div>

            <div class="page-head">
              <span class="num">Seite {{ i + 1 }}</span>
              <select
                :value="page.template"
                :disabled="saving"
                @change="setTemplate(i, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="t in TEMPLATES_BY_COUNT[page.cells.length] ?? []" :key="t" :value="t">
                  {{ TEMPLATE_LABELS[t] }}
                </option>
              </select>
              <div class="page-tools">
                <button title="Seite nach vorne" :disabled="i === 0" @click="movePage(i, -1)">←</button>
                <button title="Seite nach hinten" :disabled="i === layout.pages.length - 1" @click="movePage(i, 1)">→</button>
                <button title="Seite löschen (Bilder aus dem Buch nehmen)" class="danger" @click="deletePage(i)">🗑</button>
              </div>
            </div>

            <BookPageView
              :layout="layout"
              :page="page"
              :album-id="album.id"
              editable
              @cell-drag="(c, e) => startDrag({ imageId: page.cells[c]!.image_id, page: i, cell: c }, e)"
              @cell-drop="(c) => dropOnCell(i, c)"
              @page-drop="dropOnPage(i)"
              @cell-remove="(c) => removeCell(i, c)"
              @cell-own-page="(c) => ownPage(i, c)"
            />
          </article>
        </template>

        <div
          class="insert end"
          :class="{ active: insertTarget === layout.pages.length }"
          @dragover.prevent="insertTarget = layout.pages.length"
          @dragleave="insertTarget = null"
          @drop.prevent="dropInsert(layout.pages.length)"
        >
          <span>＋ Neue Seite am Ende</span>
        </div>
      </main>

      <aside
        class="tray glass"
        :class="{ active: trayActive }"
        @dragover.prevent="trayActive = true"
        @dragleave.self="trayActive = false"
        @drop.prevent="dropOnTray"
      >
        <h3>Ablage</h3>
        <p class="muted small">Hierher ziehen, um ein Bild aus dem Buch zu nehmen.</p>

        <template v-if="tray.waiting.length">
          <h4>Ausgewählt, noch ohne Seite <span>{{ tray.waiting.length }}</span></h4>
          <div class="tray-grid">
            <img
              v-for="img in tray.waiting"
              :key="img.id"
              :src="api.thumbUrl(album.id, img.id)"
              :title="img.classification?.caption || img.filename"
              draggable="true"
              class="waiting"
              @dragstart="startDrag({ imageId: img.id, page: null, cell: 0 }, $event)"
            />
          </div>
        </template>

        <h4>Nicht im Buch <span>{{ tray.excluded.length }}</span></h4>
        <div class="tray-grid">
          <img
            v-for="img in tray.excluded"
            :key="img.id"
            :src="api.thumbUrl(album.id, img.id)"
            :title="img.classification?.caption || img.filename"
            draggable="true"
            @dragstart="startDrag({ imageId: img.id, page: null, cell: 0 }, $event)"
          />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.editor {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  flex-direction: column;
  background: rgba(8, 8, 15, 0.96);
  backdrop-filter: blur(10px);
  padding: calc(env(safe-area-inset-top, 0px) + 0.75rem) 1rem calc(env(safe-area-inset-bottom, 0px) + 0.75rem);
  animation: fade 0.25s var(--ease);
}
@keyframes fade {
  from {
    opacity: 0;
  }
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.9rem 1.25rem;
}
.bar h2 {
  font-size: 1.15rem;
}
.muted {
  color: var(--muted);
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
}
.small {
  font-size: 0.8rem;
}
.saving {
  color: var(--ok);
}
.saved {
  color: var(--good);
}
.hint {
  flex: 1;
  text-align: center;
  min-width: 240px;
}
.bar-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 1rem;
  margin-top: 1rem;
}
.pages {
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 1.25rem 0;
  padding: 0.5rem 0.5rem 3rem;
}
.page-card {
  width: calc(50% - 2.5rem);
  min-width: 300px;
  flex-grow: 1;
  max-width: 640px;
}
.insert {
  width: 2.5rem;
  align-self: stretch;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: transparent;
  transition: all 0.2s var(--ease);
}
.dragging .insert {
  color: var(--muted);
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed var(--border-strong);
}
.insert.active {
  color: var(--text) !important;
  background: rgba(255, 95, 109, 0.18) !important;
  border-color: var(--accent) !important;
}
.insert.end {
  width: 100%;
  min-height: 3.5rem;
  margin-top: 0.5rem;
}
.chapter {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-bottom: 0.6rem;
}
.chapter-date {
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
}
.chapter-title {
  font: inherit;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 0.25rem 0.4rem;
  margin-left: -0.4rem;
}
.chapter-title:hover,
.chapter-title:focus {
  border-color: var(--border-strong);
  background: var(--surface);
  outline: none;
}
.page-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}
.page-head .num {
  font-size: 0.8rem;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}
.page-head select {
  font-size: 0.8rem;
  padding: 0.3rem 0.5rem;
}
.page-tools {
  margin-left: auto;
  display: flex;
  gap: 0.25rem;
}
.page-tools button {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}
.page-tools button:hover:not(:disabled) {
  border-color: var(--border-strong);
}
.page-tools button.danger:hover {
  background: rgba(251, 113, 133, 0.2);
}
.page-tools button:disabled {
  opacity: 0.3;
  cursor: default;
}
.tray {
  overflow-y: auto;
  padding: 1.1rem;
  transition: border-color 0.2s, background 0.2s;
}
.tray.active {
  border-color: var(--accent);
  background: rgba(255, 95, 109, 0.08);
}
.tray h3 {
  font-size: 1rem;
}
.tray h4 {
  display: flex;
  justify-content: space-between;
  margin: 1.1rem 0 0.5rem;
  font-size: 0.82rem;
  color: var(--muted);
  font-weight: 600;
}
.tray-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.4rem;
}
.tray-grid img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 8px;
  cursor: grab;
  filter: grayscale(0.6) brightness(0.75);
  transition: filter 0.2s, transform 0.2s var(--ease);
}
.tray-grid img.waiting {
  filter: none;
  outline: 2px solid var(--ok);
  outline-offset: -2px;
}
.tray-grid img:hover {
  filter: none;
  transform: scale(1.05);
}
@media (max-width: 960px) {
  .body {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }
  .pages {
    overflow: visible;
  }
  .page-card {
    width: calc(100% - 2.5rem);
  }
  .hint {
    display: none;
  }
}
</style>
