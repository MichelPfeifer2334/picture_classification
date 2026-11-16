<script setup lang="ts">
/**
 * Fotobuch-Editor: manuelle Korrekturen am Layout.
 *
 * Bilder
 * - Bild auf ein anderes Bild ziehen      → tauschen (auch seitenübergreifend)
 * - Bild auf freie Seitenfläche ziehen    → auf diese Seite verschieben (max. 4)
 * - Bild auf "＋" zwischen Seiten ziehen  → neue Seite
 * - Bild in die Ablage ziehen / ✕         → aus dem Buch nehmen
 * - Bild aus der Ablage auf eine Seite    → ins Buch aufnehmen
 * - Klick auf ein Bild                    → Großansicht mit Gruppe (tauschen / zusätzlich aufnehmen)
 *
 * Kapitel
 * - "✂ Neues Kapitel ab hier"  teilt ein Kapitel vor dieser Seite
 * - "⤒ Mit vorherigem verbinden" hängt das Kapitel an das vorherige an
 *
 * Jede Änderung wird sofort gespeichert (PUT /book); das Backend berechnet die Geometrie.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type SaveBookOptions } from '../api'
import { GROUP_LABELS, TEMPLATE_LABELS, TEMPLATES_BY_COUNT } from '../labels'
import type { BookChapterSpec, BookLayout, BookPage, ImageRecord } from '../types'
import { useAlbum } from '../useAlbum'
import BookPageView from './BookPageView.vue'
import ImagePeek from './ImagePeek.vue'
import StylePicker from './StylePicker.vue'

const { album, images, editorOpen, refresh, toast } = useAlbum()

const layout = ref<BookLayout | null>(null)
const saving = ref(false)
const confirmReset = ref(false)
const dragging = ref(false)
const insertTarget = ref<number | null>(null)
const trayActive = ref(false)
const peekId = ref<string | null>(null)

interface Drag {
  imageId: string
  page: number | null // null = aus der Ablage
  cell: number
}
let drag: Drag | null = null

// --- abgeleitete Werte -------------------------------------------------------------

/** Bild-ID → Seitenindex */
const placement = computed(() => {
  const map = new Map<string, number>()
  layout.value?.pages.forEach((p, i) => p.cells.forEach((c) => map.set(c.image_id, i)))
  return map
})

const byTime = (a: ImageRecord, b: ImageRecord) =>
  (a.metrics?.taken_at ?? a.filename).localeCompare(b.metrics?.taken_at ?? b.filename)

const tray = computed(() => {
  const rest = images.value.filter((i) => !placement.value.has(i.id) && i.status !== 'error')
  return {
    waiting: rest.filter((i) => i.included).sort(byTime),
    excluded: rest.filter((i) => !i.included).sort(byTime),
  }
})

const chapterInfo = computed(
  () => new Map((layout.value?.chapters ?? []).map((c) => [c.id, c])),
)

function startsChapter(index: number) {
  const pages = layout.value?.pages ?? []
  return index === 0 || pages[index]!.chapter_id !== pages[index - 1]!.chapter_id
}

function trayBadge(img: ImageRecord): string {
  if (img.user_included === false) return 'entfernt'
  if (img.duplicate_of && img.group_kind) return GROUP_LABELS[img.group_kind]
  if (img.score !== null && album.value && img.score < album.value.min_score) return 'schwächer'
  return ''
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

function chapterSpecs(): BookChapterSpec[] {
  return (layout.value?.chapters ?? []).map((c) => ({ id: c.id, title: c.title }))
}

async function commit(pages: BookPage[], opts: SaveBookOptions = {}) {
  if (!album.value) return
  saving.value = true
  try {
    layout.value = await api.saveBook(album.value.id, pages, {
      chapters: opts.chapters ?? chapterSpecs(),
      include: opts.include,
      exclude: opts.exclude,
    })
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

function locate(pages: BookPage[], imageId: string) {
  for (let p = 0; p < pages.length; p++) {
    const cell = pages[p]!.image_ids.indexOf(imageId)
    if (cell >= 0) return { page: p, cell }
  }
  return null
}

/** Platzierte Bild-ID mit der ähnlichsten Aufnahmezeit (für "passend einfügen"). */
function nearestPlaced(imageId: string): string | null {
  const t = images.value.find((i) => i.id === imageId)?.metrics?.taken_at
  if (!t) return null
  const target = new Date(t).getTime()
  let best: string | null = null
  let bestDiff = Infinity
  for (const img of images.value) {
    const ts = img.metrics?.taken_at
    if (!ts || !placement.value.has(img.id) || img.id === imageId) continue
    const diff = Math.abs(new Date(ts).getTime() - target)
    if (diff < bestDiff) [best, bestDiff] = [img.id, diff]
  }
  return best
}

/** Bild neben anchor einfügen: auf dieselbe Seite (wenn Platz), sonst neue Seite danach. */
function insertNear(pages: BookPage[], imageId: string, anchorId: string | null) {
  const anchor = anchorId ? locate(pages, anchorId) : null
  if (!anchor) {
    pages.push({ template: 'auto', chapter_id: pages.at(-1)?.chapter_id ?? '', image_ids: [imageId] })
    return
  }
  const page = pages[anchor.page]!
  if (page.image_ids.length < 4) {
    page.image_ids.splice(anchor.cell + 1, 0, imageId)
    page.template = 'auto'
  } else {
    pages.splice(anchor.page + 1, 0, { template: 'auto', chapter_id: page.chapter_id, image_ids: [imageId] })
  }
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
    commit(pages, { include: [d.imageId], exclude: [target] })
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
  commit(pages, { include: d.page === null ? [d.imageId] : [] })
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
  commit(pages, { include: d.page === null ? [d.imageId] : [] })
}

function dropOnTray() {
  const d = drag
  endDrag()
  if (!d || d.page === null) return
  const pages = specs()
  take(pages, d)
  commit(pages, { exclude: [d.imageId] })
}

// --- Bild-Aktionen -------------------------------------------------------------------

function removeImage(imageId: string) {
  const pages = specs()
  const loc = locate(pages, imageId)
  if (!loc) return
  pages[loc.page]!.image_ids.splice(loc.cell, 1)
  pages[loc.page]!.template = 'auto'
  commit(pages, { exclude: [imageId] })
}

function ownPage(imageId: string) {
  const pages = specs()
  const loc = locate(pages, imageId)
  if (!loc) return
  const page = pages[loc.page]!
  if (page.image_ids.length === 1) return
  page.image_ids.splice(loc.cell, 1)
  page.template = 'auto'
  pages.splice(loc.page + 1, 0, { template: 'single', chapter_id: page.chapter_id, image_ids: [imageId] })
  commit(pages)
}

/** Großansicht: dieses Bild statt memberId verwenden (gleiche Stelle im Buch). */
function replaceWith(imageId: string, memberId: string) {
  const pages = specs()
  const loc = locate(pages, memberId)
  if (!loc) return
  pages[loc.page]!.image_ids[loc.cell] = imageId
  commit(pages, { include: [imageId], exclude: [memberId] })
  toast('Bild getauscht', 'success')
}

/** Großansicht: zusätzlich aufnehmen – neben anchor oder passend zur Aufnahmezeit. */
function addImage(imageId: string, anchorId: string | null) {
  const pages = specs()
  insertNear(pages, imageId, anchorId ?? nearestPlaced(imageId))
  commit(pages, { include: [imageId] })
  toast('Bild aufgenommen', 'success')
}

// --- Seiten & Kapitel ----------------------------------------------------------------

function setTemplate(pageIndex: number, template: string) {
  const pages = specs()
  pages[pageIndex]!.template = template
  commit(pages)
}

/** Seiten tauschen – die Kapitelzugehörigkeit bleibt an der Position (Kapitel bleiben am Stück). */
function movePage(pageIndex: number, delta: number) {
  const pages = specs()
  const a = pages[pageIndex]
  const b = pages[pageIndex + delta]
  if (!a || !b) return
  ;[a.template, b.template] = [b.template, a.template]
  ;[a.image_ids, b.image_ids] = [b.image_ids, a.image_ids]
  commit(pages)
}

function deletePage(pageIndex: number) {
  const pages = specs()
  const [removed] = pages.splice(pageIndex, 1)
  commit(pages, { exclude: removed?.image_ids ?? [] })
}

/** Kapitel vor dieser Seite teilen: diese und alle folgenden Seiten des Kapitels → neues Kapitel. */
function splitChapter(pageIndex: number) {
  const pages = specs()
  const oldId = pages[pageIndex]!.chapter_id
  const newId = `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
  for (let i = pageIndex; i < pages.length && pages[i]!.chapter_id === oldId; i++) {
    pages[i]!.chapter_id = newId
  }
  commit(pages, { chapters: [...chapterSpecs(), { id: newId, title: '' }] })
  toast('Neues Kapitel angelegt – gib ihm oben eine Überschrift', 'success')
}

/** Kapitel ab dieser Seite an das vorherige Kapitel anhängen. */
function mergeChapter(pageIndex: number) {
  const pages = specs()
  const prevId = pages[pageIndex - 1]?.chapter_id
  const oldId = pages[pageIndex]!.chapter_id
  if (prevId === undefined) return
  for (let i = pageIndex; i < pages.length && pages[i]!.chapter_id === oldId; i++) {
    pages[i]!.chapter_id = prevId
  }
  const stillUsed = pages.some((p) => p.chapter_id === oldId)
  commit(pages, { chapters: chapterSpecs().filter((c) => stillUsed || c.id !== oldId) })
}

async function saveTitle(chapterId: string, value: string) {
  if (!album.value || !chapterId) return
  if (value.trim() === (chapterInfo.value.get(chapterId)?.title ?? '')) return
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
  if (e.key !== 'Escape') return
  if (peekId.value) peekId.value = null
  else close()
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
          <template v-if="layout">{{ layout.pages.length }} Seiten · {{ layout.chapters.length }} Kapitel</template>
          <span v-if="saving" class="saving">· speichert …</span>
          <span v-else-if="layout?.manual" class="saved">· gespeichert</span>
        </p>
      </div>
      <StylePicker compact @changed="load" />
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

    <p class="hint muted">
      Klick = groß ansehen · Bild auf Bild = tauschen · auf freie Fläche = verschieben · auf ＋ = neue
      Seite · in die Ablage = entfernen
    </p>

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

          <article class="page-card" :class="{ 'chapter-start': startsChapter(i) }">
            <div v-if="startsChapter(i)" class="chapter">
              <div class="chapter-row">
                <span class="chapter-date">{{ chapterInfo.get(page.chapter_id)?.subtitle ?? 'Kapitel' }}</span>
                <button
                  v-if="i > 0"
                  class="link"
                  title="Dieses Kapitel an das vorherige anhängen"
                  :disabled="saving"
                  @click="mergeChapter(i)"
                >
                  ⤒ Mit vorherigem verbinden
                </button>
              </div>
              <input
                class="chapter-title"
                :value="chapterInfo.get(page.chapter_id)?.title ?? ''"
                placeholder="Kapitelüberschrift (leer = keine)"
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
                <button
                  v-if="!startsChapter(i)"
                  class="split"
                  title="Ab dieser Seite ein neues Kapitel beginnen"
                  :disabled="saving"
                  @click="splitChapter(i)"
                >
                  ✂ Kapitel
                </button>
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
              @cell-click="(c) => (peekId = page.cells[c]!.image_id)"
              @cell-drag="(c, e) => startDrag({ imageId: page.cells[c]!.image_id, page: i, cell: c }, e)"
              @cell-drop="(c) => dropOnCell(i, c)"
              @page-drop="dropOnPage(i)"
              @cell-remove="(c) => removeImage(page.cells[c]!.image_id)"
              @cell-own-page="(c) => ownPage(page.cells[c]!.image_id)"
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
        <p class="muted small">Klick = groß ansehen · hierher ziehen = aus dem Buch nehmen</p>

        <template v-if="tray.waiting.length">
          <h4>Ausgewählt, noch ohne Seite <span>{{ tray.waiting.length }}</span></h4>
          <div class="tray-grid">
            <button
              v-for="img in tray.waiting"
              :key="img.id"
              class="thumb waiting"
              :title="img.classification?.caption || img.filename"
              draggable="true"
              @click="peekId = img.id"
              @dragstart="startDrag({ imageId: img.id, page: null, cell: 0 }, $event)"
            >
              <img :src="api.thumbUrl(album.id, img.id)" alt="" draggable="false" />
            </button>
          </div>
        </template>

        <h4>Nicht im Buch <span>{{ tray.excluded.length }}</span></h4>
        <div class="tray-grid">
          <button
            v-for="img in tray.excluded"
            :key="img.id"
            class="thumb"
            :title="img.classification?.caption || img.filename"
            draggable="true"
            @click="peekId = img.id"
            @dragstart="startDrag({ imageId: img.id, page: null, cell: 0 }, $event)"
          >
            <img :src="api.thumbUrl(album.id, img.id)" alt="" draggable="false" />
            <span v-if="trayBadge(img)" class="why">{{ trayBadge(img) }}</span>
          </button>
        </div>
      </aside>
    </div>

    <ImagePeek
      v-if="peekId"
      :image-id="peekId"
      :placement="placement"
      @close="peekId = null"
      @navigate="(id) => (peekId = id)"
      @replace="(memberId) => replaceWith(peekId!, memberId)"
      @add="(anchor) => addImage(peekId!, anchor)"
      @remove="removeImage(peekId!)"
      @own-page="ownPage(peekId!)"
    />
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
  padding: 0.8rem 1.1rem;
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
  text-align: center;
  margin: 0.6rem 0 0;
  font-size: 0.8rem;
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
  margin-top: 0.75rem;
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
  padding-left: 0.6rem;
  border-left: 3px solid var(--accent);
}
.chapter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.chapter-date {
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
}
.link {
  font: inherit;
  font-size: 0.75rem;
  color: var(--muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.1rem 0.3rem;
  border-radius: 6px;
}
.link:hover {
  color: var(--text);
  background: var(--surface);
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
  min-width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
}
.page-tools button.split {
  padding: 0 0.55rem;
  color: var(--muted);
}
.page-tools button:hover:not(:disabled) {
  border-color: var(--border-strong);
  color: var(--text);
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
.thumb {
  position: relative;
  padding: 0;
  border: none;
  background: none;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  cursor: zoom-in;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  filter: grayscale(0.6) brightness(0.75);
  transition: filter 0.2s, transform 0.2s var(--ease);
}
.thumb.waiting img {
  filter: none;
}
.thumb.waiting {
  outline: 2px solid var(--ok);
  outline-offset: -2px;
}
.thumb:hover img {
  filter: none;
  transform: scale(1.06);
}
.thumb .why {
  position: absolute;
  left: 3px;
  bottom: 3px;
  font-size: 0.6rem;
  font-weight: 600;
  padding: 0.05rem 0.3rem;
  border-radius: 5px;
  background: rgba(8, 8, 15, 0.75);
  color: #fde68a;
  pointer-events: none;
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
}
</style>
