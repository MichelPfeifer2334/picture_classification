<script setup lang="ts">
/**
 * Umschlag: Vorschau (Rückseite · Rücken · Vorderseite) + Formular.
 * Leere Felder = Automatik (Titel vom Modell, Zeitraum aus den Aufnahmedaten, "TITEL · JAHR").
 */
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import type { CoverLayout, CoverPatch } from '../types'
import { useAlbum } from '../useAlbum'
import CoverView from './CoverView.vue'
import ImagePicker from './ImagePicker.vue'

const { album, running, layoutVersion, refresh, toast } = useAlbum()

const cover = ref<CoverLayout | null>(null)
const guides = ref(false)
const picking = ref<'front' | 'back' | null>(null)
const saving = ref(false)
let debounce: number | undefined

async function load() {
  const id = album.value?.id
  if (!id || running.value) return
  try {
    cover.value = await api.cover(id)
  } catch {
    cover.value = null
  }
}

watch(
  layoutVersion,
  () => {
    window.clearTimeout(debounce)
    debounce = window.setTimeout(load, 400)
  },
  { immediate: true },
)

async function patch(p: CoverPatch) {
  const id = album.value?.id
  if (!id) return
  saving.value = true
  try {
    cover.value = await api.updateCover(id, p)
    await refresh()
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  } finally {
    saving.value = false
  }
}

/** Textfeld: leer = Automatik (null), sonst der Text. */
function onText(field: 'title' | 'subtitle' | 'spine_text', e: Event) {
  const value = (e.target as HTMLInputElement).value.trim()
  patch({ [field]: value === '' ? null : value })
}

const settings = computed(() => album.value?.cover)

function pick(id: string) {
  if (picking.value === 'front') patch({ front_image_id: id })
  else if (picking.value === 'back') patch({ back_image_id: id })
  picking.value = null
}
</script>

<template>
  <section class="cover-panel glass">
    <div class="head">
      <div>
        <p class="eyebrow">Schritt 4</p>
        <h2>Umschlag</h2>
        <p class="muted">
          <template v-if="cover">
            Hardcover · {{ cover.pages }} Seiten · Buchrücken {{ cover.guides.spine_w.toFixed(0) }} mm
          </template>
          <template v-else>Umschlag wird berechnet …</template>
          <span v-if="saving" class="saving"> · speichert …</span>
        </p>
      </div>
      <label class="toggle">
        <input v-model="guides" type="checkbox" /> Hilfslinien (Beschnitt, Falz, Rücken)
      </label>
    </div>

    <div v-if="cover && album && settings" class="body">
      <CoverView :cover="cover" :album-id="album.id" :guides="guides" />

      <form class="form" @submit.prevent>
        <label>
          <span>Titel</span>
          <input
            :value="settings.title ?? ''"
            :placeholder="`${cover.title} (automatisch)`"
            maxlength="40"
            @change="onText('title', $event)"
          />
        </label>

        <label>
          <span>Untertitel</span>
          <div class="row">
            <input
              :value="settings.subtitle ?? ''"
              :placeholder="settings.subtitle === '' ? 'kein Untertitel' : `${cover.subtitle || '–'} (automatisch)`"
              maxlength="60"
              @change="onText('subtitle', $event)"
            />
            <button
              type="button"
              class="mini"
              :title="settings.subtitle === '' ? 'Automatisch' : 'Keinen Untertitel'"
              @click="patch({ subtitle: settings.subtitle === '' ? null : '' })"
            >
              {{ settings.subtitle === '' ? '↺' : '✕' }}
            </button>
          </div>
        </label>

        <label>
          <span>Buchrücken</span>
          <input
            :value="settings.spine_text ?? ''"
            :placeholder="`${cover.spine_text} (automatisch)`"
            maxlength="40"
            @change="onText('spine_text', $event)"
          />
        </label>

        <div class="field">
          <span>Schreibrichtung Rücken</span>
          <div class="segmented">
            <button
              type="button"
              :class="{ active: cover.spine_direction === 'top_to_bottom' }"
              @click="patch({ spine_direction: 'top_to_bottom' })"
            >
              ↓ von oben nach unten
            </button>
            <button
              type="button"
              :class="{ active: cover.spine_direction === 'bottom_to_top' }"
              @click="patch({ spine_direction: 'bottom_to_top' })"
            >
              ↑ von unten nach oben
            </button>
          </div>
        </div>

        <div class="images">
          <div class="pick">
            <span>Titelbild</span>
            <button type="button" class="thumb" @click="picking = 'front'">
              <img v-if="cover.front_image_id" :src="api.thumbUrl(album.id, cover.front_image_id)" alt="" />
              <em>Ändern</em>
            </button>
            <button v-if="settings.front_image_id" type="button" class="link" @click="patch({ front_image_id: null })">
              ↺ automatisch
            </button>
          </div>
          <div class="pick">
            <span>Rückseite</span>
            <button type="button" class="thumb" @click="picking = 'back'">
              <img v-if="cover.back_image_id" :src="api.thumbUrl(album.id, cover.back_image_id)" alt="" />
              <em>{{ cover.back_image_id ? 'Ändern' : 'Bild wählen' }}</em>
            </button>
            <button v-if="cover.back_image_id" type="button" class="link" @click="patch({ back_image_id: '' })">
              ✕ ohne Bild
            </button>
            <button v-if="settings.back_image_id !== null" type="button" class="link" @click="patch({ back_image_id: null })">
              ↺ automatisch
            </button>
          </div>
        </div>

        <p class="hint">
          Leere Felder füllt die App automatisch. Den Stil (Schrift, Rahmen, Farben) wählst du oben bei
          „Gestaltung“ – er gilt für Buch und Umschlag.
        </p>
      </form>
    </div>

    <ImagePicker
      v-if="picking"
      :title="picking === 'front' ? 'Titelbild wählen' : 'Bild für die Rückseite wählen'"
      :current="picking === 'front' ? cover?.front_image_id ?? null : cover?.back_image_id ?? null"
      @pick="pick"
      @close="picking = null"
    />
  </section>
</template>

<style scoped>
.cover-panel {
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
.saving {
  color: var(--ok);
}
.toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--muted);
  cursor: pointer;
}
.body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 1.75rem;
  align-items: start;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}
label,
.field,
.pick {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: var(--muted);
}
input {
  font: inherit;
  font-size: 0.95rem;
  color: var(--text);
  background: var(--surface-solid);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.55rem 0.75rem;
  width: 100%;
}
input:focus {
  outline: none;
  border-color: var(--accent);
}
.row {
  display: flex;
  gap: 0.4rem;
}
.mini {
  flex: none;
  width: 38px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}
.segmented {
  display: flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
}
.segmented button {
  flex: 1;
  font: inherit;
  font-size: 0.8rem;
  border: none;
  background: transparent;
  color: var(--muted);
  padding: 0.35rem 0.5rem;
  border-radius: 999px;
  cursor: pointer;
}
.segmented button.active {
  background: var(--text);
  color: #1a0b12;
}
.images {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
}
.thumb {
  position: relative;
  padding: 0;
  aspect-ratio: 1;
  border-radius: 10px;
  border: 1px dashed var(--border-strong);
  background: var(--surface);
  overflow: hidden;
  cursor: pointer;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.thumb em {
  position: absolute;
  inset: auto 0 0 0;
  padding: 0.3rem;
  font-style: normal;
  font-size: 0.75rem;
  color: #fff;
  background: rgba(8, 8, 15, 0.65);
}
.link {
  font: inherit;
  font-size: 0.78rem;
  color: var(--muted);
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  padding: 0;
}
.link:hover {
  color: var(--text);
}
.hint {
  margin: 0;
  font-size: 0.78rem;
  color: var(--faint);
  line-height: 1.45;
}
@media (max-width: 1000px) {
  .body {
    grid-template-columns: 1fr;
  }
}
</style>
