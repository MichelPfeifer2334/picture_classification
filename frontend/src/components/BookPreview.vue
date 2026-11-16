<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import type { BookLayout, LayoutPage } from '../types'
import { useAlbum } from '../useAlbum'
import BookPageView from './BookPageView.vue'
import StylePicker from './StylePicker.vue'

const { album, busy, running, stats, layoutVersion, editorOpen } = useAlbum()

/**
 * Doppelseiten wie im gedruckten Buch: vorne und hinten je eine weiße Vorsatzseite
 * (klebt auf dem Deckel), dazwischen die Fotoseiten; null = weiße Seite.
 */
const spreads = computed(() => {
  const pages = layout.value?.pages ?? []
  const seq: (LayoutPage | null)[] = [null, ...pages]
  if (seq.length % 2 === 0) seq.push(null)
  seq.push(null)
  const out: { left: LayoutPage | null; right: LayoutPage | null; first: number }[] = []
  for (let i = 0; i < seq.length; i += 2) out.push({ left: seq[i]!, right: seq[i + 1] ?? null, first: i + 1 })
  return out
})

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
            Seiten {{ layout.page_width_mm }} × {{ layout.page_height_mm }} mm, als Doppelseiten
          </template>
          <template v-else-if="running">Vorschau erscheint nach der Analyse</template>
          <template v-else>Vorschau wird berechnet …</template>
        </p>
      </div>
      <div class="actions">
        <button class="btn btn-lg" :disabled="busy || !layout?.pages.length" @click="editorOpen = true">
          ✎ Buch bearbeiten
        </button>
      </div>
    </div>

    <div class="styles">
      <span class="label">Gestaltung</span>
      <StylePicker />
    </div>

    <p v-if="layout?.unplaced.length" class="notice">
      {{ layout.unplaced.length }} ausgewählte Bilder sind noch auf keiner Seite – sie werden nicht gedruckt.
      <button class="btn btn-ghost small" @click="editorOpen = true">Im Editor platzieren</button>
    </p>

    <div v-if="layout && album && layout.pages.length" class="pages" :class="{ loading }">
      <div v-for="sp in spreads" :key="sp.first" class="spread-wrap">
        <div class="spread">
          <BookPageView v-if="sp.left" :layout="layout" :page="sp.left" :album-id="album.id" />
          <div v-else class="blank" :class="`style-${layout.style}`" :style="{ aspectRatio: `${layout.page_width_mm} / ${layout.page_height_mm}` }"></div>
          <BookPageView v-if="sp.right" :layout="layout" :page="sp.right" :album-id="album.id" />
          <div v-else class="blank" :class="`style-${layout.style}`" :style="{ aspectRatio: `${layout.page_width_mm} / ${layout.page_height_mm}` }"></div>
          <i class="gutter" aria-hidden="true"></i>
        </div>
        <span class="num">Seite {{ sp.first }}–{{ sp.first + 1 }}</span>
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
.styles {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.25rem;
}
.styles .label {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
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
.spread-wrap {
  flex: none;
  width: clamp(360px, 46vw, 620px);
  scroll-snap-align: start;
}
.spread {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-radius: 4px;
  overflow: hidden;
  box-shadow:
    0 18px 40px -16px rgba(0, 0, 0, 0.9),
    0 2px 6px rgba(0, 0, 0, 0.4);
}
.spread :deep(.page) {
  border-radius: 0;
  box-shadow: none;
}
.spread :deep(.page)::after {
  display: none;
}
.blank {
  background: #fff;
}
.blank.style-elegant {
  background: #f7f2e8;
}
.blank.style-erinnerungen {
  background: #efe7da;
}
.gutter {
  /* Schatten im Bund (Mitte der Doppelseite) */
  position: absolute;
  inset: 0 auto 0 50%;
  width: 6%;
  transform: translateX(-50%);
  background: linear-gradient(90deg, transparent, rgba(0, 0, 0, 0.16) 50%, transparent);
  pointer-events: none;
  z-index: 6;
}
.page-wrap {
  flex: none;
  width: clamp(240px, 30vw, 380px);
  scroll-snap-align: start;
  transition: transform 0.35s var(--ease);
}
.spread-wrap:hover .spread {
  transform: translateY(-4px);
}
.spread {
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
