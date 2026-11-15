<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useAlbum } from '../useAlbum'

const { album, running, busy, pending, classified, eta, stats, classify } = useAlbum()

// Uhr für die Restzeit-Anzeige
const now = ref(Date.now())
const timer = window.setInterval(() => (now.value = Date.now()), 1000)
onUnmounted(() => window.clearInterval(timer))

const progress = computed(() => {
  const job = album.value?.job
  return job && job.total ? job.done / job.total : 0
})

const R = 52
const C = 2 * Math.PI * R

function fmt(seconds: number) {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} s`
  const m = Math.floor(seconds / 60)
  return `${m} min ${Math.round(seconds % 60)} s`
}

const remaining = computed(() => {
  void now.value // neu berechnen jede Sekunde
  return eta.value ? fmt(eta.value.remaining) : 'wird berechnet …'
})
</script>

<template>
  <section class="panel glass">
    <div class="ring-wrap">
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <defs>
          <linearGradient id="sunset" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stop-color="#ffb15c" />
            <stop offset="50%" stop-color="#ff5f6d" />
            <stop offset="100%" stop-color="#c04cff" />
          </linearGradient>
        </defs>
        <circle cx="60" cy="60" :r="R" class="track" />
        <circle
          cx="60"
          cy="60"
          :r="R"
          class="value"
          :class="{ spinning: running && progress === 0 }"
          :stroke-dasharray="`${(running ? Math.max(progress, 0.04) : classified / Math.max(stats.total, 1)) * C} ${C}`"
        />
      </svg>
      <div class="ring-label">
        <template v-if="running">
          <strong>{{ album?.job.done }}</strong><span>/ {{ album?.job.total }}</span>
        </template>
        <template v-else>
          <strong>{{ classified }}</strong><span>/ {{ stats.total }}</span>
        </template>
      </div>
    </div>

    <div class="body">
      <p class="eyebrow">Schritt 2</p>
      <h2 v-if="running && album?.job.phase === 'titles'">Kapitel werden benannt …</h2>
      <h2 v-else-if="running">KI sieht sich deine Bilder an …</h2>
      <h2 v-else-if="pending">{{ pending }} Bilder warten auf die Analyse</h2>
      <h2 v-else>Alle Bilder analysiert</h2>

      <p v-if="running && album?.job.phase === 'titles'" class="muted">
        Die Bilder sind bewertet. Jetzt formuliert das Modell kurze Überschriften für die Abschnitte
        deines Urlaubs.
      </p>
      <p v-else-if="running" class="muted">
        Noch ca. <strong>{{ remaining }}</strong>
        <template v-if="eta"> · {{ eta.perImage.toFixed(1) }} s pro Bild</template>
        <br />Das erste Bild dauert länger, weil das Modell in die GPU geladen wird.
      </p>
      <p v-else-if="pending" class="muted">
        Das lokale Modell bewertet jedes Bild wie ein Fotoredakteur: Motiv, Licht, Gesichter, Mängel.
        Duplikate, Serien und ähnliche Motive werden erkannt – das beste Bild bleibt. Danach entstehen
        Kapitel mit Überschriften entlang deiner Reise.
      </p>
      <p v-else class="muted">
        {{ stats.selected }} von {{ stats.total }} Bildern sind fürs Buch ausgewählt ·
        {{ stats.duplicates }} Duplikate · {{ stats.rejected }} aussortiert
      </p>

      <div class="buttons">
        <button v-if="pending" class="btn btn-primary btn-lg" :disabled="busy" @click="classify()">
          ✦ Analyse starten
        </button>
        <button v-if="classified" class="btn btn-ghost" :disabled="busy" @click="classify(true)">
          ↻ Alles neu analysieren
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 1.75rem 2rem;
}
.ring-wrap {
  position: relative;
  flex: none;
  width: 132px;
  height: 132px;
}
svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
circle {
  fill: none;
  stroke-width: 9;
}
.track {
  stroke: var(--surface-2);
}
.value {
  stroke: url(#sunset);
  stroke-linecap: round;
  transition: stroke-dasharray 0.8s var(--ease);
  filter: drop-shadow(0 0 8px rgba(255, 95, 109, 0.5));
}
.value.spinning {
  transform-origin: center;
  animation: spin 1.2s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.ring-label {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.ring-label strong {
  font-size: 1.9rem;
  line-height: 1;
}
.ring-label span {
  color: var(--muted);
  font-size: 0.85rem;
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
  line-height: 1.55;
  margin: 0.5rem 0 0;
}
.muted strong {
  color: var(--text);
}
.buttons {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-top: 1.1rem;
}
@media (max-width: 640px) {
  .panel {
    flex-direction: column;
    text-align: center;
    padding: 1.5rem;
  }
  .buttons {
    justify-content: center;
  }
}
</style>
