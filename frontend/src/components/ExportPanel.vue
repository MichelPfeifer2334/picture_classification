<script setup lang="ts">
/** Druckdateien für den Anbieter: Preflight-Prüfung + Download von Innenteil und Umschlag. */
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import type { Preflight } from '../types'
import { useAlbum } from '../useAlbum'

const { album, busy, running, layoutVersion } = useAlbum()

const pre = ref<Preflight | null>(null)
const loading = ref(false)
let debounce: number | undefined

async function load() {
  const id = album.value?.id
  if (!id || running.value) return
  loading.value = true
  try {
    pre.value = await api.preflight(id)
  } catch {
    pre.value = null
  } finally {
    loading.value = false
  }
}

watch(
  layoutVersion,
  () => {
    window.clearTimeout(debounce)
    debounce = window.setTimeout(load, 500)
  },
  { immediate: true },
)

const counts = computed(() => ({
  error: pre.value?.issues.filter((i) => i.level === 'error').length ?? 0,
  warning: pre.value?.issues.filter((i) => i.level === 'warning').length ?? 0,
}))

const ICONS = { error: '⛔', warning: '⚠️', info: 'ℹ️' } as const
</script>

<template>
  <section class="export glass">
    <div class="head">
      <div>
        <p class="eyebrow">Schritt 5</p>
        <h2>Druckdateien</h2>
        <p class="muted">{{ pre?.profile ?? 'Anbieterprofil wird geladen …' }}</p>
      </div>
      <div class="actions">
        <a
          class="btn btn-lg"
          :class="{ disabled: busy || !pre?.content_pages }"
          :href="busy || !album ? undefined : api.interiorUrl(album.id)"
          download="fotobuch-innenteil.pdf"
        >
          ⬇ Innenteil
        </a>
        <a
          class="btn btn-primary btn-lg"
          :class="{ disabled: busy || !pre?.content_pages }"
          :href="busy || !album ? undefined : api.coverUrl(album.id)"
          download="fotobuch-umschlag.pdf"
        >
          ⬇ Umschlag
        </a>
      </div>
    </div>

    <div v-if="pre" class="stats" :class="{ loading }">
      <div class="stat">
        <strong>{{ pre.total_pages }}</strong>
        <span>Seiten gesamt</span>
      </div>
      <div class="stat">
        <strong>{{ pre.content_pages }}</strong>
        <span>Fotoseiten (max. {{ pre.max_content_pages }})</span>
      </div>
      <div class="stat">
        <strong>{{ pre.blank_pages + 2 }}</strong>
        <span>weiße Seiten (inkl. 2 Vorsatz)</span>
      </div>
      <div class="stat">
        <strong>{{ pre.spine_mm.toFixed(0) }} mm</strong>
        <span>Buchrücken</span>
      </div>
      <div class="status" :class="pre.ok ? 'ok' : 'bad'">
        {{ pre.ok ? (counts.warning ? `Druckbereit · ${counts.warning} Hinweis(e)` : 'Druckbereit ✓') : `${counts.error} Problem(e) beheben` }}
      </div>
    </div>

    <ul v-if="pre?.issues.length" class="issues">
      <li v-for="(issue, i) in pre.issues" :key="i" :class="issue.level">
        <span aria-hidden="true">{{ ICONS[issue.level] }}</span>
        {{ issue.text }}
      </li>
    </ul>

    <details class="howto">
      <summary>So lädst du das Buch bei Saal Digital hoch</summary>
      <ol>
        <li>Bei Saal Digital das Produkt <strong>Fotobuch 28 × 28, Hardcover</strong> öffnen und die Bestellung per <strong>PDF-Upload</strong> wählen.</li>
        <li>Die Seitenzahl auf <strong>{{ pre?.total_pages ?? '…' }} Seiten</strong> stellen – genau so viele Seiten hat dein PDF.</li>
        <li>Papier und Cover-Oberfläche wie in deinen Vorlagen wählen (Innenteil Fotopapier glänzend, Cover matt, ohne Barcode).</li>
        <li><strong>fotobuch-innenteil.pdf</strong> als Innenseiten und <strong>fotobuch-umschlag.pdf</strong> als Cover hochladen.</li>
        <li>Die Vorschau bei Saal prüfen – Rückentitel mittig, nichts Wichtiges im Falz – und bestellen.</li>
      </ol>
    </details>
  </section>
</template>

<style scoped>
.export {
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
}
.muted {
  color: var(--muted);
  margin: 0.4rem 0 0;
}
.stats {
  display: flex;
  align-items: center;
  gap: 1.75rem;
  flex-wrap: wrap;
  transition: opacity 0.3s;
}
.stats.loading {
  opacity: 0.6;
}
.stat {
  display: flex;
  flex-direction: column;
}
.stat strong {
  font-size: 1.4rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.stat span {
  font-size: 0.78rem;
  color: var(--muted);
}
.status {
  margin-left: auto;
  padding: 0.5rem 0.9rem;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.85rem;
}
.status.ok {
  background: rgba(74, 222, 128, 0.12);
  color: #bbf7d0;
  border: 1px solid rgba(74, 222, 128, 0.3);
}
.status.bad {
  background: rgba(251, 113, 133, 0.12);
  color: #fecdd3;
  border: 1px solid rgba(251, 113, 133, 0.3);
}
.issues {
  list-style: none;
  margin: 1.25rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.issues li {
  display: flex;
  gap: 0.6rem;
  padding: 0.55rem 0.8rem;
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
  line-height: 1.45;
  background: var(--surface);
  border: 1px solid var(--border);
}
.issues li.error {
  border-color: rgba(251, 113, 133, 0.4);
}
.issues li.warning {
  border-color: rgba(250, 204, 21, 0.35);
}
.howto {
  margin-top: 1.25rem;
  font-size: 0.9rem;
  color: var(--muted);
}
.howto summary {
  cursor: pointer;
  color: var(--text);
}
.howto ol {
  margin: 0.75rem 0 0;
  padding-left: 1.25rem;
  line-height: 1.6;
}
.howto strong {
  color: var(--text);
}
</style>
