<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAlbum } from '../useAlbum'
import SaveDialog from './SaveDialog.vue'

const { health, album, images, busy, newAlbum, closeAlbum } = useAlbum()

const status = computed(() => {
  const o = health.value?.ollama
  if (!o) return { kind: 'off', text: 'Backend nicht erreichbar' }
  if (o.model_available) return { kind: 'on', text: o.model }
  if (o.reachable) return { kind: 'warn', text: `${o.model} fehlt` }
  return { kind: 'off', text: 'Ollama offline' }
})

const dialog = ref<'save' | 'rename' | null>(null)
/** Aktion, die auf eine Antwort zu einer ungespeicherten Analyse wartet */
const pending = ref<'new' | 'close' | null>(null)
let afterSave: (() => void) | null = null

const hasWork = computed(() => !!album.value && !album.value.saved && images.value.length > 0)

function run(action: 'new' | 'close') {
  if (action === 'new') newAlbum()
  else closeAlbum()
}

/** Neues Album / zurück zur Übersicht – bei ungespeicherter Analyse erst nachfragen. */
function request(action: 'new' | 'close') {
  if (hasWork.value) pending.value = action
  else run(action)
}

function saveThenContinue() {
  const action = pending.value
  pending.value = null
  afterSave = action ? () => run(action) : null
  dialog.value = 'save'
}

function discardAndContinue() {
  const action = pending.value
  pending.value = null
  if (action) run(action)
}

function onSaved() {
  afterSave?.()
  afterSave = null
}
</script>

<template>
  <header class="header">
    <div class="brand" :class="{ clickable: !!album }" @click="album && request('close')">
      <div class="logo" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <div>
        <h1>Fotobuch<span class="gradient-text">.ai</span></h1>
        <p v-if="album?.saved">{{ album.name }}</p>
        <p v-else-if="album && images.length" class="unsaved-note">Nicht gespeichert</p>
        <p v-else>Deine Urlaubsbilder, lokal kuratiert</p>
      </div>
    </div>

    <div class="actions">
      <div class="status" :class="status.kind" :title="status.text">
        <i></i>
        <span>{{ status.text }}</span>
      </div>
      <template v-if="album">
        <button v-if="!album.saved" class="btn btn-primary" :disabled="!images.length" @click="dialog = 'save'">
          💾 Speichern
        </button>
        <button v-else class="btn btn-ghost saved" title="Umbenennen" @click="dialog = 'rename'">
          ✓ Gespeichert
        </button>
        <button class="btn btn-ghost" :disabled="busy" @click="request('close')">☰ Alben</button>
        <button class="btn btn-ghost" :disabled="busy" @click="request('new')">+ Neu</button>
      </template>
    </div>

    <div v-if="pending" class="ask glass" role="alertdialog">
      <span>Diese Analyse ist noch nicht gespeichert.</span>
      <button class="btn btn-primary" @click="saveThenContinue">💾 Speichern</button>
      <button class="btn" @click="discardAndContinue">Ohne Speichern weiter</button>
      <button class="btn btn-ghost" @click="pending = null">Abbrechen</button>
    </div>

    <SaveDialog
      v-if="dialog"
      :rename="dialog === 'rename'"
      @saved="onSaved"
      @close="dialog = null"
    />
  </header>
</template>

<style scoped>
.header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding-block: 1.5rem;
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}
.brand.clickable {
  cursor: pointer;
}
h1 {
  font-size: 1.5rem;
  font-weight: 800;
}
p {
  margin: 0.1rem 0 0;
  color: var(--muted);
  font-size: 0.85rem;
}
.unsaved-note {
  color: var(--ok);
}
.logo {
  position: relative;
  width: 44px;
  height: 44px;
}
.logo span {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  background: var(--gradient);
  transform-origin: center;
}
.logo span:nth-child(1) {
  opacity: 0.35;
  transform: rotate(-14deg) scale(0.9);
}
.logo span:nth-child(2) {
  opacity: 0.6;
  transform: rotate(-6deg) scale(0.95);
}
.logo span:nth-child(3) {
  box-shadow: 0 10px 30px -8px rgba(255, 95, 109, 0.8);
}
.actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.saved {
  color: var(--good);
}
.status {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 0.82rem;
  color: var(--muted);
}
.status i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--bad);
}
.status.on i {
  background: var(--good);
  box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.6);
  animation: pulse 2s infinite;
}
.status.warn i {
  background: var(--ok);
}
@keyframes pulse {
  70% {
    box-shadow: 0 0 0 8px rgba(74, 222, 128, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(74, 222, 128, 0);
  }
}
.ask {
  position: absolute;
  right: 0;
  top: calc(100% - 0.5rem);
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  padding: 0.9rem 1.1rem;
  background: rgba(20, 20, 31, 0.96);
  font-size: 0.9rem;
  animation: drop 0.2s var(--ease);
}
@keyframes drop {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
}
</style>
