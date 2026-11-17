<script setup lang="ts">
/** Startseite: gespeicherte Alben öffnen oder löschen, nicht gespeicherte aufräumen. */
import { computed, ref } from 'vue'
import { api } from '../api'
import { useAlbum } from '../useAlbum'

const { library, unsaved, openAlbum, deleteAlbum, cleanupUnsaved } = useAlbum()

const saved = computed(() => library.value.filter((a) => a.saved))
const confirmDelete = ref<string | null>(null)
const confirmCleanup = ref(false)

const fmt = new Intl.DateTimeFormat('de-DE', { day: 'numeric', month: 'short', year: 'numeric' })
const when = (iso: string | null) => (iso ? fmt.format(new Date(iso)) : '')
</script>

<template>
  <section v-if="saved.length || unsaved.length" class="library">
    <h3 v-if="saved.length">Gespeicherte Alben</h3>

    <div v-if="saved.length" class="grid">
      <article v-for="a in saved" :key="a.id" class="card glass">
        <button class="open" :title="`„${a.name}“ öffnen`" @click="openAlbum(a.id)">
          <div class="thumb">
            <img v-if="a.thumb_image_id" :src="api.thumbUrl(a.id, a.thumb_image_id)" alt="" loading="lazy" />
            <span v-if="a.running" class="badge">Analyse läuft</span>
          </div>
          <div class="info">
            <strong>{{ a.name }}</strong>
            <small>
              {{ a.selected_count }} von {{ a.image_count }} Bildern im Buch · zuletzt
              {{ when(a.updated_at ?? a.created_at) }}
            </small>
          </div>
        </button>

        <div class="tools">
          <template v-if="confirmDelete === a.id">
            <span>Endgültig löschen?</span>
            <button class="danger" @click="deleteAlbum(a.id); confirmDelete = null">Ja, löschen</button>
            <button @click="confirmDelete = null">Nein</button>
          </template>
          <button v-else class="icon" title="Album löschen" @click="confirmDelete = a.id">🗑</button>
        </div>
      </article>
    </div>

    <p v-if="unsaved.length" class="unsaved">
      {{ unsaved.length }} nicht gespeicherte Analyse(n) belegen noch Platz auf der Festplatte.
      <template v-if="confirmCleanup">
        Wirklich löschen?
        <button class="link danger" @click="cleanupUnsaved(); confirmCleanup = false">Ja, aufräumen</button>
        <button class="link" @click="confirmCleanup = false">Nein</button>
      </template>
      <button v-else class="link" @click="confirmCleanup = true">Aufräumen</button>
    </p>
  </section>
</template>

<style scoped>
.library {
  width: min(1100px, 100%);
  margin-top: 1rem;
  text-align: left;
}
h3 {
  font-size: 1.05rem;
  margin-bottom: 0.9rem;
  color: var(--muted);
  font-weight: 600;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 1rem;
}
.card {
  position: relative;
  overflow: hidden;
  padding: 0;
  transition: transform 0.3s var(--ease), border-color 0.3s;
}
.card:hover {
  transform: translateY(-3px);
  border-color: var(--border-strong);
}
.open {
  display: block;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.thumb {
  position: relative;
  aspect-ratio: 4 / 3;
  background: var(--surface-2);
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.badge {
  position: absolute;
  left: 0.5rem;
  top: 0.5rem;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--gradient);
  color: #1a0b12;
}
.info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.75rem 0.9rem 0.9rem;
}
.info strong {
  font-size: 1rem;
}
.info small {
  color: var(--muted);
  font-size: 0.78rem;
}
.tools {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
}
.tools span {
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  background: rgba(8, 8, 15, 0.8);
}
.tools button {
  font: inherit;
  font-size: 0.78rem;
  border: none;
  border-radius: 999px;
  padding: 0.25rem 0.6rem;
  background: rgba(8, 8, 15, 0.8);
  color: var(--text);
  cursor: pointer;
}
.tools button.danger {
  background: var(--bad);
  color: #1a0b12;
}
.tools .icon {
  opacity: 0;
  transition: opacity 0.2s;
}
.card:hover .tools .icon {
  opacity: 1;
}
.unsaved {
  margin: 1rem 0 0;
  font-size: 0.85rem;
  color: var(--muted);
}
.link {
  font: inherit;
  background: none;
  border: none;
  color: var(--text);
  text-decoration: underline;
  cursor: pointer;
  padding: 0 0.25rem;
}
.link.danger {
  color: var(--bad);
}
</style>
