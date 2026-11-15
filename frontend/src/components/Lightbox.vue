<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import {
  CATEGORY_ICONS,
  FLAG_LABELS,
  GROUP_LABELS,
  QUALITY_LABELS,
  STRENGTH_LABELS,
  capitalize,
} from '../labels'
import type { ImageRecord } from '../types'
import { useAlbum } from '../useAlbum'
import ScoreRing from './ScoreRing.vue'

const props = defineProps<{ imageId: string; list: ImageRecord[] }>()
const emit = defineEmits<{ close: []; navigate: [id: string] }>()

const { album, categories, images, updateImage, toggleIncluded } = useAlbum()

const index = computed(() => props.list.findIndex((i) => i.id === props.imageId))
const image = computed(() => images.value.find((i) => i.id === props.imageId) ?? null)
const bestOfGroup = computed(() =>
  image.value?.duplicate_of ? images.value.find((i) => i.id === image.value?.duplicate_of) : null,
)

function go(delta: number) {
  const next = props.list[index.value + delta]
  if (next) emit('navigate', next.id)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
  else if (e.key === 'ArrowRight') go(1)
  else if (e.key === 'ArrowLeft') go(-1)
  else if (e.key === ' ' && image.value) {
    e.preventDefault()
    toggleIncluded(image.value)
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})

// Technische Werte relativ zum Album – hilft beim Nachvollziehen von "Unscharf" & Co.
const tech = computed(() => {
  const m = image.value?.metrics
  if (!m) return null
  const all = images.value.map((i) => i.metrics?.sharpness).filter((v): v is number => v != null)
  const sorted = [...all].sort((a, b) => a - b)
  const median = sorted.length ? sorted[Math.floor(sorted.length / 2)]! : m.sharpness
  return {
    sharpness: Math.round(m.sharpness),
    sharpnessRel: median ? Math.round((m.sharpness / median) * 100) : 100,
    brightness: Math.round((m.brightness / 255) * 100),
    dark: Math.round(m.dark_fraction * 100),
    bright: Math.round(m.bright_fraction * 100),
  }
})

const takenAt = computed(() => {
  const t = image.value?.metrics?.taken_at
  return t ? new Date(t).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' }) : null
})
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <button class="close btn btn-ghost" aria-label="Schließen" @click="emit('close')">✕</button>
    <button v-if="index > 0" class="nav prev" aria-label="Vorheriges Bild" @click="go(-1)">‹</button>
    <button v-if="index < list.length - 1" class="nav next" aria-label="Nächstes Bild" @click="go(1)">›</button>

    <div v-if="image && album" class="content">
      <div class="stage">
        <img :key="image.id" :src="api.previewUrl(album.id, image.id)" :alt="image.filename" />
        <span
          v-if="image.classification"
          class="focus"
          title="Bildschwerpunkt (für den Zuschnitt im Buch)"
          :style="{ left: `${image.classification.focus_x * 100}%`, top: `${image.classification.focus_y * 100}%` }"
        ></span>
      </div>

      <aside class="side glass">
        <div class="head">
          <ScoreRing :score="image.score" :size="64" />
          <div>
            <p class="quality" :class="image.quality ?? ''">
              {{ image.quality ? QUALITY_LABELS[image.quality] : 'Noch nicht bewertet' }}
            </p>
            <p class="muted small">
              Modell: {{ image.classification?.aesthetic_score ?? '–' }}/10
              <template v-if="image.flags.length"> · {{ image.flags.length }} Abzüge</template>
            </p>
          </div>
        </div>

        <h3 v-if="image.classification?.caption">{{ image.classification.caption }}</h3>
        <p v-if="image.classification?.reason" class="muted">{{ image.classification.reason }}</p>
        <p v-if="image.error" class="error">{{ image.error }}</p>

        <div v-if="image.flags.length || image.classification?.strengths.length" class="flags">
          <span v-for="st in image.classification?.strengths ?? []" :key="st" class="flag plus">
            ＋ {{ STRENGTH_LABELS[st] ?? st }}
          </span>
          <span v-for="f in image.flags" :key="f" class="flag">{{ FLAG_LABELS[f] ?? f }}</span>
        </div>

        <p v-if="image.classification?.subject" class="muted small">
          Motiv: <strong>{{ image.classification.subject }}</strong>
          <template v-if="image.classification.people">
            · {{ image.classification.people }} {{ image.classification.people === 1 ? 'Person' : 'Personen' }}
          </template>
        </p>

        <div v-if="image.group_size > 1" class="group">
          <template v-if="image.duplicate_of && bestOfGroup">
            <img :src="api.thumbUrl(album.id, bestOfGroup.id)" alt="" />
            <p>
              {{ image.group_kind ? GROUP_LABELS[image.group_kind] : 'Gruppe' }} – ein besseres Bild dieser
              Gruppe ({{ image.group_size }} Bilder) ist bereits im Buch.
            </p>
            <button class="btn btn-ghost small" @click="emit('navigate', bestOfGroup.id)">Ansehen</button>
          </template>
          <p v-else>★ Bestes Bild aus {{ image.group_size }} ähnlichen Aufnahmen.</p>
        </div>

        <label v-if="image.classification" class="field">
          <span>Kategorie</span>
          <select
            :value="image.classification.category"
            @change="updateImage(image.id, { category: ($event.target as HTMLSelectElement).value })"
          >
            <option v-for="c in categories" :key="c" :value="c">{{ CATEGORY_ICONS[c] }} {{ capitalize(c) }}</option>
          </select>
        </label>

        <details v-if="tech" class="tech">
          <summary>Technische Werte</summary>
          <dl>
            <dt>Schärfe</dt>
            <dd>{{ tech.sharpness }} <span>({{ tech.sharpnessRel }} % vom Album-Median)</span></dd>
            <dt>Helligkeit</dt>
            <dd>{{ tech.brightness }} %</dd>
            <dt>Fast schwarz / weiß</dt>
            <dd>{{ tech.dark }} % / {{ tech.bright }} %</dd>
            <dt>Rang in Gruppe</dt>
            <dd>{{ image.rank?.toFixed(2) ?? '–' }} <span>(Score + Technik)</span></dd>
          </dl>
        </details>

        <div class="meta muted small">
          <span>{{ image.filename }}</span>
          <span>{{ image.width }} × {{ image.height }}</span>
          <span v-if="takenAt">{{ takenAt }}</span>
        </div>

        <div class="actions">
          <button class="btn btn-lg" :class="image.included ? '' : 'btn-primary'" @click="toggleIncluded(image)">
            {{ image.included ? 'Aus dem Buch nehmen' : '＋ Ins Buch aufnehmen' }}
          </button>
          <button v-if="image.user_included !== null" class="btn btn-ghost small" @click="updateImage(image.id, { included: null })">
            Automatik wiederherstellen
          </button>
          <p class="muted small hint">← → blättern · Leertaste umschalten · Esc schließen</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: calc(env(safe-area-inset-top, 0px) + 1.5rem) 1.5rem calc(env(safe-area-inset-bottom, 0px) + 1.5rem);
  background: rgba(4, 4, 8, 0.86);
  backdrop-filter: blur(16px);
  animation: fade 0.25s var(--ease);
}
@keyframes fade {
  from {
    opacity: 0;
  }
}
.content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 1.25rem;
  width: min(1400px, 100%);
  max-height: 100%;
  animation: rise 0.35s var(--ease);
}
@keyframes rise {
  from {
    transform: translateY(16px) scale(0.98);
    opacity: 0;
  }
}
.stage {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 0;
  justify-self: center;
}
.focus {
  position: absolute;
  width: 26px;
  height: 26px;
  margin: -13px 0 0 -13px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.25);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.25s;
}
.stage:hover .focus {
  opacity: 1;
}
.stage img {
  max-width: 100%;
  max-height: calc(100vh - 3rem);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  animation: fade 0.3s;
}
.side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  overflow-y: auto;
  max-height: calc(100vh - 3rem);
  background: rgba(20, 20, 31, 0.85);
}
.head {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.quality {
  margin: 0;
  font-size: 1.3rem;
  font-weight: 800;
}
.quality.good {
  color: var(--good);
}
.quality.ok {
  color: var(--ok);
}
.quality.bad {
  color: var(--bad);
}
h3 {
  font-size: 1.15rem;
}
.muted {
  color: var(--muted);
  margin: 0;
  line-height: 1.5;
}
.small {
  font-size: 0.82rem;
}
.error {
  color: var(--bad);
  margin: 0;
}
.flags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.flag {
  font-size: 0.78rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: rgba(251, 113, 133, 0.14);
  color: #fecdd3;
  border: 1px solid rgba(251, 113, 133, 0.3);
}
.flag.plus {
  background: rgba(74, 222, 128, 0.12);
  color: #bbf7d0;
  border-color: rgba(74, 222, 128, 0.3);
}
.muted strong {
  color: var(--text);
}
.tech {
  font-size: 0.82rem;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.6rem 0.8rem;
}
.tech summary {
  cursor: pointer;
  color: var(--text);
}
.tech dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.3rem 0.9rem;
  margin: 0.6rem 0 0;
}
.tech dd {
  margin: 0;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.tech dd span {
  color: var(--muted);
}
.group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 0.85rem;
}
.group p {
  margin: 0;
  flex: 1;
}
.group img {
  width: 52px;
  height: 52px;
  object-fit: cover;
  border-radius: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: var(--muted);
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 1rem;
}
.actions {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.hint {
  text-align: center;
  margin-top: 0.25rem;
}
.close {
  position: fixed;
  top: calc(env(safe-area-inset-top, 0px) + 1rem);
  right: 1rem;
  z-index: 2;
}
.nav {
  position: fixed;
  top: 50%;
  z-index: 2;
  width: 52px;
  height: 52px;
  margin-top: -26px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: rgba(20, 20, 31, 0.7);
  color: var(--text);
  font-size: 1.8rem;
  line-height: 1;
  cursor: pointer;
  backdrop-filter: blur(10px);
  transition: transform 0.2s var(--ease);
}
.nav:hover {
  transform: scale(1.08);
}
.prev {
  left: 1rem;
}
.next {
  right: calc(360px + 2.75rem);
}
@media (max-width: 960px) {
  .overlay {
    place-items: start center;
    overflow-y: auto;
  }
  .content {
    grid-template-columns: 1fr;
  }
  .stage img {
    max-height: 60vh;
  }
  .side {
    max-height: none;
  }
  .next {
    right: 1rem;
  }
}
</style>
