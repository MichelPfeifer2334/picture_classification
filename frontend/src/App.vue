<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from './api'
import ImageCard from './components/ImageCard.vue'
import UploadZone from './components/UploadZone.vue'
import type { Album, Health, ImageRecord } from './types'

const UPLOAD_BATCH = 8 // Bilder pro Upload-Request
const POLL_MS = 1500
const STORAGE_KEY = 'fotobuch.albumId'

const health = ref<Health | null>(null)
const categories = ref<string[]>([])
const album = ref<Album | null>(null)
const uploading = ref<{ done: number; total: number } | null>(null)
const uploadErrors = ref<string[]>([])
const error = ref<string | null>(null)
const excludeBad = ref(false)
let pollTimer: number | undefined

const running = computed(() => album.value?.job.status === 'running')
const busy = computed(() => running.value || uploading.value !== null)
const pending = computed(
  () => album.value?.images.filter((i) => i.status !== 'classified').length ?? 0,
)

// Bilder nach Kategorie gruppieren – Reihenfolge wie im Backend konfiguriert
const groups = computed(() => {
  const map = new Map<string, ImageRecord[]>()
  for (const img of album.value?.images ?? []) {
    const key = img.classification?.category ?? 'unklassifiziert'
    map.set(key, [...(map.get(key) ?? []), img])
  }
  const order = [...categories.value, 'unklassifiziert']
  return [...map.entries()].sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
})

function remember(id: string | null) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* localStorage evtl. gesperrt – nicht schlimm */
  }
}

async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
  error.value = null
  try {
    return await fn()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function newAlbum() {
  stopPolling()
  uploadErrors.value = []
  const created = await run(api.createAlbum)
  if (created) {
    album.value = created
    remember(created.id)
  }
}

async function onFiles(files: File[]) {
  if (!album.value) await newAlbum()
  const id = album.value?.id
  if (!id) return

  uploadErrors.value = []
  uploading.value = { done: 0, total: files.length }
  try {
    for (let i = 0; i < files.length; i += UPLOAD_BATCH) {
      const batch = files.slice(i, i + UPLOAD_BATCH)
      const result = await run(() => api.uploadImages(id, batch))
      if (!result) break
      uploadErrors.value.push(...result.errors.map((e) => `${e.filename}: ${e.error}`))
      if (uploading.value) uploading.value.done += batch.length
    }
  } finally {
    uploading.value = null
    await refresh()
  }
}

async function classify() {
  if (!album.value) return
  const job = await run(() => api.startClassification(album.value!.id))
  if (job) {
    album.value.job = job
    startPolling()
  }
}

async function refresh() {
  if (!album.value) return
  const fresh = await run(() => api.getAlbum(album.value!.id))
  if (fresh) album.value = fresh
  if (!running.value) stopPolling()
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(refresh, POLL_MS)
}

function stopPolling() {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
  pollTimer = undefined
}

onMounted(async () => {
  health.value = (await run(api.health)) ?? null
  categories.value = (await run(api.config))?.categories ?? []

  // Letztes Album nach Neuladen der Seite wieder öffnen
  let saved: string | null = null
  try {
    saved = localStorage.getItem(STORAGE_KEY)
  } catch {
    /* ignorieren */
  }
  if (saved) {
    try {
      album.value = await api.getAlbum(saved)
      if (running.value) startPolling()
    } catch {
      remember(null)
    }
  }
})

onUnmounted(stopPolling)
</script>

<template>
  <main>
    <header>
      <h1>Fotobuch</h1>
      <p v-if="health" class="status">
        Modell <code>{{ health.ollama.model }}</code>:
        <span v-if="health.ollama.model_available" class="ok">bereit</span>
        <span v-else-if="health.ollama.reachable" class="warn">
          nicht installiert (ollama pull {{ health.ollama.model }})
        </span>
        <span v-else class="warn">Ollama nicht erreichbar (ollama serve)</span>
      </p>
    </header>

    <p v-if="error" class="error-box">{{ error }}</p>

    <!-- 1. Upload -->
    <section>
      <h2>1. Bilder hochladen</h2>
      <UploadZone :disabled="busy" @files="onFiles" />
      <p v-if="uploading">Lade hoch … {{ uploading.done }} / {{ uploading.total }}</p>
      <details v-if="uploadErrors.length" class="error-box">
        <summary>{{ uploadErrors.length }} Datei(en) übersprungen</summary>
        <ul>
          <li v-for="e in uploadErrors" :key="e">{{ e }}</li>
        </ul>
      </details>
    </section>

    <template v-if="album && album.images.length">
      <!-- 2. Klassifizieren -->
      <section>
        <h2>2. Klassifizieren</h2>
        <div class="row">
          <button :disabled="busy || pending === 0" @click="classify">
            {{ pending }} Bild(er) klassifizieren
          </button>
          <span v-if="running">
            <progress :value="album.job.done" :max="album.job.total" />
            {{ album.job.done }} / {{ album.job.total }}
          </span>
          <span v-else-if="pending === 0" class="ok">Alle {{ album.images.length }} Bilder klassifiziert</span>
        </div>
      </section>

      <!-- 3. Export -->
      <section>
        <h2>3. PDF exportieren</h2>
        <div class="row">
          <label><input v-model="excludeBad" type="checkbox" /> schlechte Bilder weglassen</label>
          <a
            class="button"
            :class="{ disabled: busy }"
            :href="busy ? undefined : api.pdfUrl(album.id, excludeBad)"
            download="fotobuch.pdf"
          >
            PDF herunterladen
          </a>
          <button class="secondary" :disabled="busy" @click="newAlbum">Neues Album</button>
        </div>
      </section>

      <!-- Galerie -->
      <section v-for="[category, images] in groups" :key="category">
        <h3>{{ category }} <small>({{ images.length }})</small></h3>
        <div class="grid">
          <ImageCard v-for="img in images" :key="img.id" :album-id="album.id" :image="img" />
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem 1rem 3rem;
}
header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}
section {
  margin-top: 1.5rem;
}
h3 {
  text-transform: capitalize;
}
.row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}
.ok {
  color: #15803d;
}
.warn {
  color: #b45309;
}
.error-box {
  background: #fef2f2;
  color: #991b1b;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
}
</style>
