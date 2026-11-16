<script setup lang="ts">
import { STYLES } from '../labels'
import type { Style } from '../types'
import { useAlbum } from '../useAlbum'

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })
const emit = defineEmits<{ changed: [style: Style] }>()

const { album, busy, setStyle } = useAlbum()

async function pick(style: Style) {
  if (album.value?.style === style) return
  await setStyle(style)
  emit('changed', style)
}
</script>

<template>
  <div class="picker" :class="{ compact }" role="radiogroup" aria-label="Gestaltungsstil">
    <button
      v-for="s in STYLES"
      :key="s.id"
      class="style"
      :class="{ active: album?.style === s.id }"
      role="radio"
      :aria-checked="album?.style === s.id"
      :disabled="busy"
      :title="s.description"
      @click="pick(s.id)"
    >
      <span class="swatch" :class="`sw-${s.id}`" :style="{ background: s.paper }">
        <i :style="{ background: s.accent }"></i>
        <i></i>
        <i></i>
      </span>
      <span class="text">
        <strong>{{ s.label }}</strong>
        <small v-if="!compact">{{ s.description }}</small>
      </span>
    </button>
  </div>
</template>

<style scoped>
.picker {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.style {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.45rem 0.8rem 0.45rem 0.45rem;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s var(--ease);
}
.style:hover {
  border-color: var(--border-strong);
}
.style.active {
  border-color: var(--accent);
  background: rgba(255, 122, 89, 0.12);
  box-shadow: 0 0 0 1px var(--accent) inset;
}
.style:disabled {
  opacity: 0.5;
  cursor: default;
}
.swatch {
  position: relative;
  flex: none;
  width: 44px;
  height: 31px;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
}
/* Mini-Seite: Titelbalken + zwei Bildfelder */
.swatch i {
  position: absolute;
  background: #b9b4c4;
}
.swatch i:nth-child(1) {
  left: 4px;
  top: 4px;
  width: 16px;
  height: 3px;
  border-radius: 2px;
}
.swatch i:nth-child(2) {
  left: 4px;
  top: 10px;
  width: 20px;
  height: 17px;
  background: linear-gradient(160deg, #ffb15c, #ff5f6d);
}
.swatch i:nth-child(3) {
  left: 26px;
  top: 10px;
  width: 14px;
  height: 17px;
  background: linear-gradient(160deg, #6a8cff, #c04cff);
}
.sw-elegant i:nth-child(1) {
  left: 14px;
}
.sw-elegant i:nth-child(2),
.sw-elegant i:nth-child(3) {
  outline: 1px solid #a8874a;
  outline-offset: 1px;
}
.sw-erinnerungen i:nth-child(2),
.sw-erinnerungen i:nth-child(3) {
  border: 2px solid #fff;
  border-bottom-width: 4px;
  transform: rotate(-3deg);
}
.sw-erinnerungen i:nth-child(3) {
  transform: rotate(4deg);
}
.sw-magazin i:nth-child(1) {
  height: 4px;
  width: 22px;
  border-radius: 0;
  border-left: 2px solid #ff5f6d;
  background: #29262b;
}
.text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.text strong {
  font-size: 0.88rem;
}
.text small {
  font-size: 0.74rem;
  color: var(--muted);
}
.compact .style {
  padding: 0.3rem 0.65rem 0.3rem 0.3rem;
}
.compact .swatch {
  width: 34px;
  height: 24px;
}
.compact .swatch i:nth-child(2),
.compact .swatch i:nth-child(3) {
  top: 8px;
  height: 12px;
}
.compact .swatch i:nth-child(3) {
  left: 21px;
  width: 10px;
}
.compact .swatch i:nth-child(2) {
  width: 14px;
}
</style>
