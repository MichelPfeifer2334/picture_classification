<script setup lang="ts">
import { computed } from 'vue'
import { api } from '../api'
import { FLAG_LABELS, GROUP_LABELS } from '../labels'
import type { ImageRecord } from '../types'
import ScoreRing from './ScoreRing.vue'

const props = defineProps<{ albumId: string; image: ImageRecord; analyzing: boolean }>()
const emit = defineEmits<{ open: []; toggle: [] }>()

const isBestOfGroup = computed(() => props.image.group_size > 1 && !props.image.duplicate_of)
const manual = computed(() => props.image.user_included !== null)
const focus = computed(() => {
  const c = props.image.classification
  return c ? `${c.focus_x * 100}% ${c.focus_y * 100}%` : '50% 50%'
})
</script>

<template>
  <figure
    class="card"
    :class="{ excluded: !image.included, pending: image.status === 'uploaded' }"
    tabindex="0"
    @click="emit('open')"
    @keydown.enter="emit('open')"
  >
    <img
      :style="{ objectPosition: focus }"
      :src="api.thumbUrl(albumId, image.id)" :alt="image.classification?.caption || image.filename" loading="lazy" />

    <div v-if="image.status === 'uploaded' && analyzing" class="shimmer" aria-hidden="true"></div>

    <div class="top">
      <ScoreRing v-if="image.status === 'classified'" :score="image.score" :size="38" />
      <span v-else-if="image.status === 'error'" class="pill bad">Fehler</span>
      <span v-else class="pill">{{ analyzing ? 'wird analysiert …' : 'neu' }}</span>

      <button
        class="toggle"
        :class="{ on: image.included, manual }"
        :title="image.included ? 'Aus dem Buch nehmen' : 'Ins Buch aufnehmen'"
        @click.stop="emit('toggle')"
      >
        <svg v-if="image.included" viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>
        <svg v-else viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
      </button>
    </div>

    <figcaption>
      <div class="badges">
        <span v-if="isBestOfGroup" class="pill best">★ Beste von {{ image.group_size }}</span>
        <span v-else-if="image.duplicate_of && image.group_kind" class="pill dup">{{ GROUP_LABELS[image.group_kind] }}</span>
        <span v-for="f in image.flags.slice(0, 2)" :key="f" class="pill flag">{{ FLAG_LABELS[f] ?? f }}</span>
      </div>
      <p v-if="image.classification?.caption" class="caption">{{ image.classification.caption }}</p>
    </figcaption>
  </figure>
</template>

<style scoped>
.card {
  position: relative;
  margin: 0;
  aspect-ratio: 4 / 5;
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: zoom-in;
  isolation: isolate;
  transition:
    transform 0.35s var(--ease),
    box-shadow 0.35s var(--ease),
    border-color 0.35s;
  outline: none;
}
.card:hover,
.card:focus-visible {
  transform: translateY(-4px);
  border-color: var(--border-strong);
  box-shadow: 0 24px 50px -20px rgba(0, 0, 0, 0.9);
}
img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition:
    transform 0.6s var(--ease),
    filter 0.4s,
    opacity 0.4s;
}
.card:hover img {
  transform: scale(1.06);
}
.card.excluded img {
  filter: grayscale(0.9) brightness(0.55);
}
.card.excluded:hover img {
  filter: grayscale(0.3) brightness(0.8);
}
.card::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, transparent 28%, transparent 55%, rgba(0, 0, 0, 0.85) 100%);
  pointer-events: none;
}
.shimmer {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(110deg, transparent 30%, rgba(255, 255, 255, 0.16) 50%, transparent 70%);
  background-size: 250% 100%;
  animation: shimmer 1.6s linear infinite;
}
@keyframes shimmer {
  from {
    background-position: 120% 0;
  }
  to {
    background-position: -120% 0;
  }
}
.top {
  position: absolute;
  inset: 0.6rem 0.6rem auto 0.6rem;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.toggle {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1.5px solid rgba(255, 255, 255, 0.5);
  background: rgba(8, 8, 15, 0.55);
  backdrop-filter: blur(8px);
  color: #fff;
  cursor: pointer;
  opacity: 0;
  transform: scale(0.85);
  transition: all 0.25s var(--ease);
}
.card:hover .toggle,
.card:focus-visible .toggle,
.toggle.manual,
.toggle.on {
  opacity: 1;
  transform: scale(1);
}
.toggle.on {
  border: none;
  background: var(--gradient);
  color: #1a0b12;
}
.toggle.manual {
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.35);
}
.toggle svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}
figcaption {
  position: absolute;
  inset: auto 0.75rem 0.75rem 0.75rem;
  z-index: 2;
}
.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.pill {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: rgba(8, 8, 15, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text);
}
.pill.best {
  background: var(--gradient);
  color: #1a0b12;
  border: none;
}
.pill.dup {
  color: var(--ok);
}
.pill.flag {
  color: #fecdd3;
}
.pill.bad {
  color: var(--bad);
}
.caption {
  margin: 0.45rem 0 0;
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1.3;
  text-shadow: 0 1px 8px rgba(0, 0, 0, 0.6);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
