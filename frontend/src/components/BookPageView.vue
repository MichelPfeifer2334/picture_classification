<script setup lang="ts">
/**
 * Eine Fotobuch-Seite – maßstabsgetreu aus den mm-Koordinaten des Layouts.
 * Wird in der Vorschau (nur Anzeige) und im Editor (Drag & Drop) verwendet.
 */
import { ref } from 'vue'
import { api } from '../api'
import type { BookLayout, LayoutCell, LayoutPage } from '../types'

const props = defineProps<{
  layout: BookLayout
  page: LayoutPage
  albumId: string
  editable?: boolean
  thumb?: (id: string) => string
}>()

const emit = defineEmits<{
  'cell-drag': [cellIndex: number, event: DragEvent]
  'cell-drop': [cellIndex: number, event: DragEvent]
  'page-drop': [event: DragEvent]
  'cell-remove': [cellIndex: number]
  'cell-own-page': [cellIndex: number]
}>()

const dropTarget = ref<number | 'page' | null>(null)

function cellStyle(c: LayoutCell) {
  const l = props.layout
  return {
    left: `${(c.x / l.page_width_mm) * 100}%`,
    top: `${(c.y / l.page_height_mm) * 100}%`,
    width: `${(c.w / l.page_width_mm) * 100}%`,
    height: `${(c.h / l.page_height_mm) * 100}%`,
  }
}

function titleStyle() {
  const l = props.layout
  return {
    left: `${(l.margin_mm / l.page_width_mm) * 100}%`,
    top: `${(l.margin_mm / l.page_height_mm) * 100}%`,
  }
}

const src = (id: string) => (props.thumb ? props.thumb(id) : api.thumbUrl(props.albumId, id))

function onDragOver(e: DragEvent, target: number | 'page') {
  if (!props.editable) return
  e.preventDefault()
  dropTarget.value = target
}

function onDrop(e: DragEvent, target: number | 'page') {
  if (!props.editable) return
  e.preventDefault()
  e.stopPropagation()
  dropTarget.value = null
  if (target === 'page') emit('page-drop', e)
  else emit('cell-drop', target, e)
}
</script>

<template>
  <div
    class="page"
    :class="{ editable, 'drop-page': dropTarget === 'page' }"
    :style="{ aspectRatio: `${layout.page_width_mm} / ${layout.page_height_mm}` }"
    @dragover="onDragOver($event, 'page')"
    @dragleave.self="dropTarget = null"
    @drop="onDrop($event, 'page')"
  >
    <div
      v-for="(cell, i) in page.cells"
      :key="cell.image_id"
      class="cell"
      :class="{ 'drop-cell': dropTarget === i }"
      :style="cellStyle(cell)"
      :draggable="editable"
      @dragstart="emit('cell-drag', i, $event)"
      @dragover.stop="onDragOver($event, i)"
      @dragleave="dropTarget = null"
      @drop="onDrop($event, i)"
    >
      <img
        :src="src(cell.image_id)"
        alt=""
        loading="lazy"
        draggable="false"
        :style="{ objectPosition: `${cell.focus_x * 100}% ${cell.focus_y * 100}%` }"
      />
      <div v-if="editable" class="cell-tools">
        <button title="Auf eigene Seite" @click.stop="emit('cell-own-page', i)">⤢</button>
        <button title="Aus dem Buch nehmen" @click.stop="emit('cell-remove', i)">✕</button>
      </div>
    </div>

    <div
      v-if="page.title"
      class="title"
      :class="{ 'on-photo': page.template === 'full_bleed' }"
      :style="titleStyle()"
    >
      <slot name="title">
        <strong>{{ page.title }}</strong>
      </slot>
      <span v-if="page.subtitle">{{ page.subtitle }}</span>
    </div>
  </div>
</template>

<style scoped>
.page {
  position: relative;
  overflow: hidden;
  container-type: inline-size;
  background: #fbfaf7;
  border-radius: 4px;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.4) inset,
    0 18px 40px -16px rgba(0, 0, 0, 0.9),
    0 2px 6px rgba(0, 0, 0, 0.4);
}
.page::after {
  /* leichter Falz-Schatten links wie bei einem aufgeschlagenen Buch */
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 7%;
  background: linear-gradient(90deg, rgba(0, 0, 0, 0.16), transparent);
  pointer-events: none;
}
.page.drop-page {
  outline: 3px dashed var(--accent);
  outline-offset: 4px;
}
.cell {
  position: absolute;
  overflow: hidden;
  background: #e9e6df;
}
.cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  pointer-events: none;
}
.editable .cell {
  cursor: grab;
}
.editable .cell:active {
  cursor: grabbing;
}
.cell.drop-cell {
  outline: 3px solid var(--accent);
  outline-offset: -3px;
  z-index: 2;
}
.cell.drop-cell img {
  opacity: 0.6;
}
.cell-tools {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}
.cell:hover .cell-tools {
  opacity: 1;
}
.cell-tools button {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: none;
  background: rgba(8, 8, 15, 0.75);
  color: #fff;
  font-size: 0.8rem;
  cursor: pointer;
}
.cell-tools button:hover {
  background: var(--sunset-2);
}
.title {
  position: absolute;
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 0.15em;
  color: #29262b;
  max-width: 80%;
}
.title :deep(strong),
.title :deep(input) {
  font-size: 2.05cqw;
  font-weight: 800;
  letter-spacing: -0.01em;
  line-height: 1.15;
}
.title span {
  font-size: 1cqw;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #85808c;
}
.title.on-photo {
  color: #fff;
  text-shadow: 0 1px 12px rgba(0, 0, 0, 0.5);
}
.title.on-photo span {
  color: rgba(255, 255, 255, 0.85);
}
</style>
