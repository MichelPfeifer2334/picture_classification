<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'
import type { BookLayout } from '../types'
import { useAlbum } from '../useAlbum'
import BookPageView from './BookPageView.vue'

const { album, busy, running, stats, layoutVersion, editorOpen } = useAlbum()

const layout = ref<BookLayout | null>(null)
const loading = ref(false)
let debounce: number | undefined

async function load() {
  const id = album.value?.id
  if (!id || running.value) return
  loading.value = true
  try {
    layout.value = await api.layout(id)
  } catch {
    layout.value = null
  } finally {
    loading.value = false
  }
}

// Bei Änderungen (Auswahl, Kategorie, Regler, Editor) neu laden – kurz entprellt
watch(
  layoutVersion,
  () => {
    window.clearTimeout(debounce)
    debounce = window.setTimeout(load, 350)
  },
  { immediate: true },
)
</script>

<template>
  <section class="book glass">
    <div class="head">
      <div>
        <p class="eyebrow">Schritt 3</p>
        <h2>
          Dein Fotobuch
          <span v-if="layout?.manual" class="badge">manuell bearbeitet</span>
        </h2>
        <p class="muted">
          <template v-if="layout">
            {{ layout.pages.length }} Seiten · {{ stats.selected }} Bilder ·
            {{ layout.pages.filter((p) => p.title).length }} Kapitel ·
            {{ layout.page_width_mm }} × {{ layout.page_height_mm }} mm
          </template>
          <template v-else-if="running">Vorschau erscheint nach der Analyse</template>
          <template v-else>Vorschau wird berechnet …</template>
        </p>
      </div>
      <div class="actions">
        <button class="btn btn-lg" :disabled="busy || !layout?.pages.length" @click="editorOpen = true">
          ✎ Buch bearbeiten
        </button>
        <a
          class="btn btn-primary btn-lg"
          :class="{ disabled: busy || !stats.selected }"
          :href="busy || !album ? undefined : api.pdfUrl(album.id)"
          download="fotobuch.pdf"
        >
          ⬇ PDF exportieren
        </a>
      </div>
    </div>

    <p v-if="layout?.unplaced.length" class="notice">
      {{ layout.unplaced.length }} ausgewählte Bilder sind noch auf keiner Seite – sie werden nicht gedruckt.
      <button class="btn btn-ghost small" @click="editorOpen = true">Im Editor platzieren</button>
    </p>

    <div v-if="layout && album && layout.pages.length" class="pages" :class="{ loading }">
      <div v-for="(page, i) in layout.pages" :key="page.id" class="page-wrap">
        <BookPageView :layout="layout" :page="page" :album-id="album.id" />
        <span class="num">{{ i + 1 }}</span>
      </div>
    </div>
    <p v-else-if="layout && !layout.pages.length" class="muted empty">
      Noch keine Bilder ausgewählt – nimm Bilder per ＋ ins Buch auf oder senke die Strenge.
    </p>
  </section>
</template>

<style scoped>
.book {
  padding: 1.75rem 2rem 2rem;
}
.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.25rem;
}
.actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.eyebrow {
  margin: 0 0 0.3rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
}
h2 {
  font-size: 1.4rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--muted);
}
.muted {
  color: var(--muted);
  margin: 0.4rem 0 0;
}
.notice {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin: 0 0 1rem;
  padding: 0.7rem 1rem;
  border-radius: var(--radius-sm);
  background: rgba(250, 204, 21, 0.1);
  border: 1px solid rgba(250, 204, 21, 0.3);
  color: #fde68a;
  font-size: 0.9rem;
}
.small {
  padding: 0.35rem 0.8rem;
  font-size: 0.82rem;
}
.empty {
  text-align: center;
  padding: 2rem 0 0.5rem;
}
.pages {
  display: flex;
  gap: 1.5rem;
  overflow-x: auto;
  padding: 0.75rem 0.25rem 0.75rem;
  scroll-snap-type: x proximity;
  transition: opacity 0.3s;
}
.pages.loading {
  opacity: 0.6;
}
.page-wrap {
  flex: none;
  width: clamp(240px, 30vw, 380px);
  scroll-snap-align: start;
  transition: transform 0.35s var(--ease);
}
.page-wrap:hover {
  transform: translateY(-4px) rotate(-0.4deg);
}
.num {
  display: block;
  margin-top: 0.5rem;
  text-align: center;
  font-size: 0.75rem;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 640px) {
  .book {
    padding: 1.5rem;
  }
}
</style>
