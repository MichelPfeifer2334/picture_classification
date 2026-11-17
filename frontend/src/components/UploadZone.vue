<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { IMAGE_EXT, filesFromDrop, pickDirectory, supportsDirectoryPicker } from '../folderPicker'
import { useAlbum } from '../useAlbum'

defineProps<{ compact: boolean }>()

const { busy, uploading, upload, toast } = useAlbum()

const dragging = ref(false)
const reading = ref(false) // Ordner wird gerade eingelesen
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)

onMounted(() => {
  // Notlösung für Browser ohne showDirectoryPicker (Attribut fehlt im TS-Typ von <input>)
  folderInput.value?.setAttribute('webkitdirectory', '')
})

function submit(files: File[]) {
  const images = files.filter((f) => IMAGE_EXT.test(f.name))
  if (images.length) upload(images)
  else toast('Keine Bilder gefunden (JPG, PNG, HEIC, WebP …)', 'info')
}

async function withReading(fn: () => Promise<File[] | null>) {
  reading.value = true
  try {
    const files = await fn()
    if (files) submit(files)
  } catch (e) {
    toast(`Ordner konnte nicht gelesen werden: ${e instanceof Error ? e.message : e}`, 'error')
  } finally {
    reading.value = false
  }
}

function pickFolder() {
  if (supportsDirectoryPicker()) withReading(pickDirectory)
  else folderInput.value?.click()
}

function onDrop(e: DragEvent) {
  dragging.value = false
  if (busy.value || !e.dataTransfer) return
  const data = e.dataTransfer
  withReading(() => filesFromDrop(data))
}

function onChange(e: Event) {
  const input = e.target as HTMLInputElement
  submit(Array.from(input.files ?? []))
  input.value = ''
}
</script>

<template>
  <section
    class="drop glass"
    :class="{ dragging, compact, disabled: busy }"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
  >
    <div class="glow" aria-hidden="true"></div>

    <template v-if="uploading">
      <div class="uploading">
        <p class="big">Bilder werden vorbereitet …</p>
        <div class="bar"><i :style="{ width: `${(uploading.done / uploading.total) * 100}%` }"></i></div>
        <p class="muted">{{ uploading.done }} von {{ uploading.total }}</p>
      </div>
    </template>

    <template v-else>
      <div class="icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
          <rect x="3" y="5" width="18" height="14" rx="3" />
          <circle cx="9" cy="10" r="1.8" />
          <path d="m21 16-5-5-8 8" />
        </svg>
      </div>
      <div class="text">
        <p class="big">{{ compact ? 'Weitere Bilder hinzufügen' : 'Zieh deine Urlaubsbilder hierher' }}</p>
        <p class="muted">JPG, PNG, HEIC – einzeln oder als ganzer Ordner</p>
      </div>
      <div class="buttons">
        <button class="btn btn-primary" :disabled="busy || reading" @click="pickFolder">
          {{ reading ? 'Ordner wird gelesen …' : 'Ordner wählen' }}
        </button>
        <button class="btn" :disabled="busy || reading" @click="fileInput?.click()">Dateien wählen</button>
      </div>
    </template>

    <input ref="fileInput" type="file" multiple accept="image/*,.heic,.heif" hidden @change="onChange" />
    <input ref="folderInput" type="file" multiple hidden @change="onChange" />
  </section>
</template>

<style scoped>
.drop {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 1.25rem;
  padding: 3.5rem 1.5rem;
  border-style: dashed;
  border-width: 1.5px;
  transition:
    border-color 0.3s,
    transform 0.3s var(--ease);
}
.drop.compact {
  flex-direction: row;
  text-align: left;
  padding: 1.1rem 1.4rem;
  gap: 1rem;
}
.drop.compact .text {
  flex: 1;
}
.drop.compact .icon {
  width: 46px;
  height: 46px;
}
.drop.dragging {
  border-color: var(--accent);
  transform: scale(1.01);
}
.drop.disabled {
  opacity: 0.85;
}
.glow {
  position: absolute;
  inset: auto -20% -60% -20%;
  height: 120%;
  background: radial-gradient(closest-side, rgba(255, 95, 109, 0.22), transparent);
  opacity: 0;
  transition: opacity 0.4s;
  pointer-events: none;
}
.drop.dragging .glow,
.drop:hover .glow {
  opacity: 1;
}
.icon {
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  border-radius: 22px;
  background: var(--gradient);
  color: #1a0b12;
  box-shadow: 0 16px 40px -12px rgba(255, 95, 109, 0.8);
}
.icon svg {
  width: 55%;
  height: 55%;
}
.big {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
}
.compact .big {
  font-size: 1rem;
}
.muted {
  margin: 0.25rem 0 0;
  color: var(--muted);
  font-size: 0.88rem;
}
.buttons {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  justify-content: center;
}
.uploading {
  width: min(420px, 100%);
}
.bar {
  margin-top: 1rem;
  height: 8px;
  border-radius: 999px;
  background: var(--surface-2);
  overflow: hidden;
}
.bar i {
  display: block;
  height: 100%;
  background: var(--gradient);
  border-radius: inherit;
  transition: width 0.4s var(--ease);
}
@media (max-width: 640px) {
  .drop.compact {
    flex-direction: column;
    text-align: center;
  }
}
</style>
