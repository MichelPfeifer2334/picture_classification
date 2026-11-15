<script setup lang="ts">
import { computed } from 'vue'
import { useAlbum } from '../useAlbum'

const { health, album, busy, newAlbum } = useAlbum()

const status = computed(() => {
  const o = health.value?.ollama
  if (!o) return { kind: 'off', text: 'Backend nicht erreichbar' }
  if (o.model_available) return { kind: 'on', text: o.model }
  if (o.reachable) return { kind: 'warn', text: `${o.model} fehlt` }
  return { kind: 'off', text: 'Ollama offline' }
})
</script>

<template>
  <header class="header">
    <div class="brand">
      <div class="logo" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <div>
        <h1>Fotobuch<span class="gradient-text">.ai</span></h1>
        <p>Deine Urlaubsbilder, lokal kuratiert</p>
      </div>
    </div>

    <div class="actions">
      <div class="status" :class="status.kind" :title="status.text">
        <i></i>
        <span>{{ status.text }}</span>
      </div>
      <button v-if="album" class="btn btn-ghost" :disabled="busy" @click="newAlbum">
        + Neues Album
      </button>
    </div>
  </header>
</template>

<style scoped>
.header {
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
h1 {
  font-size: 1.5rem;
  font-weight: 800;
}
p {
  margin: 0.1rem 0 0;
  color: var(--muted);
  font-size: 0.85rem;
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
  gap: 0.75rem;
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
</style>
