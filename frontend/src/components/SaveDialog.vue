<script setup lang="ts">
/** Album speichern bzw. umbenennen. */
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useAlbum } from '../useAlbum'

const props = defineProps<{ rename?: boolean }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const { album, suggestedName, saveAlbum } = useAlbum()

const name = ref(props.rename && album.value?.name ? album.value.name : suggestedName.value)
const input = ref<HTMLInputElement | null>(null)

async function submit() {
  const value = name.value.trim()
  if (!value) return
  await saveAlbum(value)
  emit('saved')
  emit('close')
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await nextTick()
  input.value?.select()
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <form class="box glass" @submit.prevent="submit">
      <h3>{{ rename ? 'Album umbenennen' : 'Analyse speichern' }}</h3>
      <p class="muted">
        Gespeicherte Alben findest du auf der Startseite wieder – mit Bewertung, Auswahl, Buch-Layout,
        Umschlag und Stil. Ab jetzt wird jede Änderung automatisch mitgesichert.
      </p>
      <label>
        <span>Name</span>
        <input ref="input" v-model="name" maxlength="80" placeholder="z. B. Paris · August 2026" />
      </label>
      <div class="actions">
        <button type="button" class="btn btn-ghost" @click="emit('close')">Abbrechen</button>
        <button type="submit" class="btn btn-primary" :disabled="!name.trim()">
          💾 {{ rename ? 'Umbenennen' : 'Speichern' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(4, 4, 8, 0.75);
  backdrop-filter: blur(10px);
  animation: fade 0.2s var(--ease);
}
@keyframes fade {
  from {
    opacity: 0;
  }
}
.box {
  width: min(480px, 100%);
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: rgba(20, 20, 31, 0.95);
}
h3 {
  font-size: 1.2rem;
}
.muted {
  margin: 0;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.5;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: var(--muted);
}
input {
  font: inherit;
  font-size: 1rem;
  color: var(--text);
  background: var(--surface-solid);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.65rem 0.8rem;
}
input:focus {
  outline: none;
  border-color: var(--accent);
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
