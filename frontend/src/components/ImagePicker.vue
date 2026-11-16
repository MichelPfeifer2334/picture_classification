<script setup lang="ts">
/** Bildauswahl (z. B. für das Titelbild): ausgewählte Bilder zuerst, beste zuerst. */
import { computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { useAlbum } from '../useAlbum'

defineProps<{ title: string; current: string | null }>()
const emit = defineEmits<{ pick: [id: string]; close: [] }>()

const { album, images } = useAlbum()

const sorted = computed(() =>
  [...images.value]
    .filter((i) => i.status === 'classified')
    .sort((a, b) => Number(b.included) - Number(a.included) || (b.rank ?? 0) - (a.rank ?? 0)),
)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="box glass">
      <header>
        <h3>{{ title }}</h3>
        <button class="btn btn-ghost" @click="emit('close')">Schließen</button>
      </header>
      <div v-if="album" class="grid">
        <button
          v-for="img in sorted"
          :key="img.id"
          class="tile"
          :class="{ current: img.id === current, excluded: !img.included }"
          :title="img.classification?.caption || img.filename"
          @click="emit('pick', img.id)"
        >
          <img :src="api.thumbUrl(album.id, img.id)" alt="" loading="lazy" />
          <span class="score">{{ img.score?.toFixed(1) ?? '–' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(4, 4, 8, 0.82);
  backdrop-filter: blur(12px);
}
.box {
  width: min(1000px, 100%);
  max-height: calc(100vh - 3rem);
  display: flex;
  flex-direction: column;
  padding: 1.25rem;
  background: rgba(20, 20, 31, 0.94);
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.grid {
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.6rem;
}
.tile {
  position: relative;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 10px;
  overflow: hidden;
  aspect-ratio: 1;
  cursor: pointer;
  background: none;
}
.tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.25s var(--ease);
}
.tile:hover img {
  transform: scale(1.05);
}
.tile.current {
  border-color: var(--accent);
}
.tile.excluded img {
  filter: grayscale(0.7) brightness(0.7);
}
.score {
  position: absolute;
  right: 4px;
  bottom: 4px;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.05rem 0.35rem;
  border-radius: 6px;
  background: rgba(8, 8, 15, 0.75);
  color: #fff;
}
</style>
