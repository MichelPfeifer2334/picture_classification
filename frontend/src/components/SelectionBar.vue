<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CATEGORY_ICONS, capitalize } from '../labels'
import { useAlbum, type Filter } from '../useAlbum'

const { album, stats, filter, categoryFilter, categoryCounts, groupMode, busy, setMinScore } =
  useAlbum()

// Regler lokal halten, erst beim Loslassen speichern
const localScore = ref(album.value?.min_score ?? 6)
watch(
  () => album.value?.min_score,
  (v) => {
    if (v !== undefined) localScore.value = v
  },
)

const strictness = computed(() => {
  const v = localScore.value
  if (v <= 3) return 'Fast alles'
  if (v <= 5) return 'Großzügig'
  if (v <= 6.5) return 'Ausgewogen'
  if (v <= 8) return 'Streng'
  return 'Nur Highlights'
})

const filters: { key: Filter; label: string; count: () => number }[] = [
  { key: 'all', label: 'Alle', count: () => stats.value.total },
  { key: 'selected', label: 'Im Buch', count: () => stats.value.selected },
  { key: 'rejected', label: 'Aussortiert', count: () => stats.value.rejected },
  { key: 'duplicates', label: 'Gruppen', count: () => stats.value.duplicates },
]
</script>

<template>
  <section class="bar glass">
    <div class="stats">
      <div class="stat">
        <strong class="gradient-text">{{ stats.selected }}</strong>
        <span>im Buch</span>
      </div>
      <div class="stat">
        <strong>{{ stats.total }}</strong>
        <span>gesamt</span>
      </div>
      <div class="stat">
        <strong>{{ stats.duplicates }}</strong>
        <span>aussortierte Doppelte</span>
      </div>
      <div class="stat">
        <strong>{{ stats.rejected }}</strong>
        <span>aussortiert</span>
      </div>
    </div>

    <div class="strict">
      <div class="strict-head">
        <span>Strenge</span>
        <strong>{{ strictness }} <em>· ab {{ localScore.toFixed(1) }}</em></strong>
      </div>
      <input
        v-model.number="localScore"
        type="range"
        min="0"
        max="10"
        step="0.5"
        :disabled="busy"
        :style="{ '--fill': `${localScore * 10}%` }"
        @change="setMinScore(localScore)"
      />
    </div>

    <div class="filters">
      <div class="segmented" role="group" aria-label="Gruppierung">
        <button :class="{ active: groupMode === 'story' }" @click="groupMode = 'story'">🗺️ Urlaubsverlauf</button>
        <button :class="{ active: groupMode === 'category' }" @click="groupMode = 'category'">🏷️ Kategorien</button>
      </div>
      <span class="divider" aria-hidden="true"></span>
      <button
        v-for="f in filters"
        :key="f.key"
        class="chip"
        :class="{ active: filter === f.key }"
        @click="filter = f.key"
      >
        {{ f.label }} <span class="count">{{ f.count() }}</span>
      </button>
      <span class="divider" aria-hidden="true"></span>
      <button class="chip" :class="{ active: categoryFilter === null }" @click="categoryFilter = null">
        Alle Kategorien
      </button>
      <button
        v-for="[cat, n] in categoryCounts"
        :key="cat"
        class="chip"
        :class="{ active: categoryFilter === cat }"
        @click="categoryFilter = categoryFilter === cat ? null : cat"
      >
        {{ CATEGORY_ICONS[cat] ?? '•' }} {{ capitalize(cat) }} <span class="count">{{ n }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.bar {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1.25rem 2.5rem;
  padding: 1.4rem 1.75rem;
  position: sticky;
  top: calc(env(safe-area-inset-top, 0px) + 0.75rem);
  z-index: 10;
}
.stats {
  display: flex;
  gap: 1.75rem;
}
.stat {
  display: flex;
  flex-direction: column;
}
.stat strong {
  font-size: 1.6rem;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.stat span {
  color: var(--muted);
  font-size: 0.78rem;
}
.strict {
  align-self: center;
  max-width: 420px;
  justify-self: end;
  width: 100%;
}
.strict-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.6rem;
  font-size: 0.85rem;
  color: var(--muted);
}
.strict-head strong {
  color: var(--text);
}
.strict-head em {
  font-style: normal;
  color: var(--muted);
  font-weight: 500;
}
.filters {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}
.segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
}
.segmented button {
  font: inherit;
  font-size: 0.85rem;
  border: none;
  background: transparent;
  color: var(--muted);
  padding: 0.35rem 0.8rem;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s var(--ease);
}
.segmented button.active {
  background: var(--text);
  color: #1a0b12;
}
.divider {
  width: 1px;
  height: 22px;
  background: var(--border);
  margin: 0 0.35rem;
}
@media (max-width: 860px) {
  .bar {
    grid-template-columns: 1fr;
    position: static;
  }
  .strict {
    justify-self: stretch;
    max-width: none;
  }
  .stats {
    gap: 1.25rem;
    flex-wrap: wrap;
  }
}
</style>
