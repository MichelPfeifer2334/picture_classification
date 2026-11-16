<script setup lang="ts">
/**
 * Eine Fotobuch-Seite – maßstabsgetreu aus den mm-Koordinaten des Layouts, im gewählten Stil.
 * Wird in der Vorschau (nur Anzeige) und im Editor (Drag & Drop, Klick = Großansicht) verwendet.
 *
 * Stil-Geometrie (Polaroid-Rahmen, Drehung) kommt fertig vom Backend, damit Vorschau und PDF
 * übereinstimmen. Prozent-Abstände beziehen sich auf die Seitenbreite (CSS-Regel für padding).
 */
import { ref } from 'vue'
import { api } from '../api'
import type { BookLayout, LayoutCell, LayoutPage } from '../types'

const props = defineProps<{
  layout: BookLayout
  page: LayoutPage
  albumId: string
  editable?: boolean
}>()

const emit = defineEmits<{
  'cell-drag': [cellIndex: number, event: DragEvent]
  'cell-drop': [cellIndex: number, event: DragEvent]
  'cell-click': [cellIndex: number]
  'page-drop': [event: DragEvent]
  'cell-remove': [cellIndex: number]
  'cell-own-page': [cellIndex: number]
}>()

const dropTarget = ref<number | 'page' | null>(null)

const pct = (mm: number, of: number) => `${(mm / of) * 100}%`

function cellStyle(c: LayoutCell) {
  const l = props.layout
  const style: Record<string, string> = {
    left: pct(c.x, l.page_width_mm),
    top: pct(c.y, l.page_height_mm),
    width: pct(c.w, l.page_width_mm),
    height: pct(c.h, l.page_height_mm),
  }
  if (c.pad_side || c.pad_top || c.pad_bottom) {
    const w = l.page_width_mm // padding-% bezieht sich immer auf die Breite des Containers
    style.padding = `${pct(c.pad_top, w)} ${pct(c.pad_side, w)} ${pct(c.pad_bottom, w)}`
  }
  if (c.rotate) style.transform = `rotate(${-c.rotate}deg)` // PDF: + = gegen Uhrzeigersinn
  return style
}

function titleStyle() {
  const l = props.layout
  return {
    left: pct(l.margin_mm, l.page_width_mm),
    right: pct(l.margin_mm, l.page_width_mm),
    top: pct(l.margin_mm, l.page_height_mm),
  }
}

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
    :class="[`style-${layout.style}`, `tpl-${page.template}`, { editable, 'drop-page': dropTarget === 'page' }]"
    :style="{ aspectRatio: `${layout.page_width_mm} / ${layout.page_height_mm}` }"
    @dragover="onDragOver($event, 'page')"
    @dragleave.self="dropTarget = null"
    @drop="onDrop($event, 'page')"
  >
    <div
      v-for="(cell, i) in page.cells"
      :key="cell.image_id"
      class="cell"
      :class="{ framed: cell.pad_side > 0, 'drop-cell': dropTarget === i }"
      :style="cellStyle(cell)"
      :draggable="editable"
      @click="emit('cell-click', i)"
      @dragstart="emit('cell-drag', i, $event)"
      @dragover.stop="onDragOver($event, i)"
      @dragleave="dropTarget = null"
      @drop="onDrop($event, i)"
    >
      <img
        :src="api.thumbUrl(albumId, cell.image_id)"
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
      <strong>{{ page.title }}</strong>
      <span v-if="page.subtitle">{{ page.subtitle }}</span>
    </div>
  </div>
</template>

<style scoped>
/* ---------------------------------------------------------------------------
   Grundgerüst
--------------------------------------------------------------------------- */
.page {
  --paper: #ffffff;
  --ink: #29262b;
  --muted: #85808c;
  position: relative;
  overflow: hidden;
  container-type: inline-size; /* cqw = 1 % der Seitenbreite → Schrift skaliert mit */
  background: var(--paper);
  border-radius: 3px;
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
  background: linear-gradient(90deg, rgba(0, 0, 0, 0.14), transparent);
  pointer-events: none;
  z-index: 4;
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
  outline: 3px solid var(--sunset-2) !important;
  outline-offset: -3px !important;
  z-index: 3;
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
  z-index: 2;
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

/* Überschrift (Positionen entsprechen dem PDF: Titelband = 16 mm unter dem Rand) */
.title {
  position: absolute;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25cqw;
  color: var(--ink);
}
.title strong {
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 2.05cqw;
  font-weight: 700;
  line-height: 1.15;
}
.title span {
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 1cqw;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}
.title.on-photo,
.title.on-photo span {
  color: #fff;
  text-shadow: 0 1px 12px rgba(0, 0, 0, 0.5);
}

/* ---------------------------------------------------------------------------
   Stil: Elegant – Creme, feine Goldlinie, zentrierte Serifen-Überschrift
--------------------------------------------------------------------------- */
.style-elegant {
  --paper: #f7f2e8;
  --gold: #a8874a;
}
.style-elegant:not(.tpl-full_bleed) .cell {
  overflow: visible;
  outline: max(1px, 0.06cqw) solid var(--gold);
  outline-offset: 0.47cqw; /* 1,4 mm */
}
.style-elegant .title {
  align-items: center;
  text-align: center;
}
.style-elegant .title strong {
  font-family: 'Times New Roman', Times, Georgia, serif;
  font-style: italic;
  font-weight: 400;
  font-size: 2.6cqw;
}
.style-elegant .title span {
  font-family: 'Times New Roman', Times, Georgia, serif;
  letter-spacing: 0.25em;
  color: var(--gold);
}

/* ---------------------------------------------------------------------------
   Stil: Erinnerungen – Papier, Polaroid-Rahmen, leicht gedreht, Klebestreifen
--------------------------------------------------------------------------- */
.style-erinnerungen {
  --paper: #efe7da;
}
.cell.framed {
  overflow: visible;
  background: #fff;
  box-shadow: 0.25cqw 0.3cqw 0.6cqw rgba(0, 0, 0, 0.22);
}
.cell.framed img {
  /* Bild füllt das Rahmeninnere (padding der Zelle) */
  background: #e9e6df;
}
.cell.framed::before {
  /* Klebestreifen oben mittig */
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  width: min(30%, 7.4cqw);
  height: 2.2cqw;
  background: rgba(245, 220, 158, 0.72);
  transform: translate(-50%, -50%) rotate(-3deg);
  z-index: 1;
}
.style-erinnerungen .title strong,
.style-erinnerungen .title span {
  font-family: 'Courier New', Courier, monospace;
}
.style-erinnerungen .title strong {
  font-size: 2cqw;
}
.style-erinnerungen .title span {
  font-size: 1.05cqw;
  text-transform: none;
  letter-spacing: 0;
}

/* ---------------------------------------------------------------------------
   Stil: Magazin – große Versalien mit Farbbalken, Datum in Akzentfarbe
--------------------------------------------------------------------------- */
.style-magazin {
  --accent-mag: #ff5f6d;
}
.style-magazin .title {
  padding-left: 1.5cqw;
  border-left: 0.54cqw solid var(--accent-mag);
}
.style-magazin .title strong {
  font-size: 2.5cqw;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.01em;
}
.style-magazin .title span {
  font-weight: 700;
  font-size: 0.9cqw;
  letter-spacing: 0.3em;
  color: var(--accent-mag);
}
</style>
