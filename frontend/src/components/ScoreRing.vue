<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ score: number | null; size?: number }>(), { size: 40 })

const R = 16
const C = 2 * Math.PI * R
const color = computed(() => {
  const s = props.score ?? 0
  return s >= 7 ? 'var(--good)' : s >= 5 ? 'var(--ok)' : 'var(--bad)'
})
const dash = computed(() => `${((props.score ?? 0) / 10) * C} ${C}`)
</script>

<template>
  <div class="ring" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" :r="R" class="track" />
      <circle
        v-if="score !== null"
        cx="20"
        cy="20"
        :r="R"
        class="value"
        :stroke="color"
        :stroke-dasharray="dash"
      />
    </svg>
    <span>{{ score === null ? '–' : score.toFixed(score % 1 ? 1 : 0) }}</span>
  </div>
</template>

<style scoped>
.ring {
  position: relative;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(8, 8, 15, 0.72);
  backdrop-filter: blur(8px);
}
svg {
  position: absolute;
  inset: 0;
  transform: rotate(-90deg);
}
circle {
  fill: none;
  stroke-width: 3.5;
}
.track {
  stroke: rgba(255, 255, 255, 0.15);
}
.value {
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s var(--ease);
}
span {
  position: relative;
  font-size: 0.78rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
</style>
