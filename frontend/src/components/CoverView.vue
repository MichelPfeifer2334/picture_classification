<script setup lang="ts">
/**
 * Umschlag maßstabsgetreu: zeichnet die Bausteine aus GET /cover (Flächen, Bilder, Texte)
 * genau so, wie das Backend sie ins PDF schreibt. Optional mit Hilfslinien
 * (Beschnitt, Falz, Buchrücken, sicherer Bereich).
 */
import { api } from '../api'
import type { CoverFont, CoverImage, CoverLayout, CoverText } from '../types'

const props = defineProps<{ cover: CoverLayout; albumId: string; guides?: boolean }>()

const pctX = (mm: number) => `${(mm / props.cover.width_mm) * 100}%`
const pctY = (mm: number) => `${(mm / props.cover.height_mm) * 100}%`
const cqw = (mm: number) => `${(mm / props.cover.width_mm) * 100}cqw`

function box(x: number, y: number, w: number, h: number) {
  return { left: pctX(x), top: pctY(y), width: pctX(w), height: pctY(h) }
}

function imageStyle(img: CoverImage) {
  const style: Record<string, string> = box(img.x, img.y, img.w, img.h)
  if (img.pad_side || img.pad_bottom) {
    // padding-% bezieht sich auf die Breite des Containers (= Umschlagbreite)
    style.padding = `${pctX(img.pad_top)} ${pctX(img.pad_side)} ${pctX(img.pad_bottom)}`
  }
  if (img.rotate) style.transform = `rotate(${-img.rotate}deg)` // PDF: + = gegen den Uhrzeigersinn
  if (img.line_color) {
    style.outline = `max(1px, 0.06cqw) solid ${img.line_color}`
    style.outlineOffset = cqw(2)
  }
  return style
}

const FONTS: Record<CoverFont, { family: string; weight: number; style: string }> = {
  sans: { family: "'Helvetica Neue', Helvetica, Arial, sans-serif", weight: 400, style: 'normal' },
  'sans-bold': { family: "'Helvetica Neue', Helvetica, Arial, sans-serif", weight: 700, style: 'normal' },
  serif: { family: "'Times New Roman', Times, serif", weight: 400, style: 'normal' },
  'serif-italic': { family: "'Times New Roman', Times, serif", weight: 400, style: 'italic' },
  mono: { family: "'Courier New', Courier, monospace", weight: 400, style: 'normal' },
  'mono-bold': { family: "'Courier New', Courier, monospace", weight: 700, style: 'normal' },
}

function textStyle(t: CoverText) {
  const f = FONTS[t.font]
  return {
    ...box(t.x, t.y, t.w, t.h),
    fontFamily: f.family,
    fontWeight: String(f.weight),
    fontStyle: f.style,
    fontSize: cqw(t.size),
    letterSpacing: cqw(t.spacing),
    color: t.color,
    textAlign: t.align,
  }
}
</script>

<template>
  <div
    class="cover"
    :style="{ aspectRatio: `${cover.width_mm} / ${cover.height_mm}`, background: cover.background }"
  >
    <div
      v-for="img in cover.images"
      :key="img.image_id + img.x"
      class="img"
      :class="{ framed: img.pad_side > 0, tape: img.tape }"
      :style="imageStyle(img)"
    >
      <img
        :src="api.previewUrl(albumId, img.image_id)"
        alt=""
        :style="{ objectPosition: `${img.focus_x * 100}% ${img.focus_y * 100}%` }"
      />
    </div>

    <div
      v-for="(r, i) in cover.rects"
      :key="`r${i}`"
      class="rect"
      :style="{ ...box(r.x, r.y, r.w, r.h), background: r.color, opacity: r.alpha }"
    ></div>

    <div
      v-for="(t, i) in cover.texts"
      :key="`t${i}`"
      class="text"
      :class="{ rotated: t.rotate !== 0 }"
      :style="textStyle(t)"
    >
      <span :style="t.rotate ? { transform: `rotate(${-t.rotate}deg)` } : undefined">{{ t.text }}</span>
    </div>

    <template v-if="guides">
      <!-- Beschnitt: alles außerhalb wird abgeschnitten bzw. um die Pappe geschlagen -->
      <div
        class="guide bleed"
        :style="box(cover.guides.bleed_lr, cover.guides.bleed_tb, cover.width_mm - 2 * cover.guides.bleed_lr, cover.height_mm - 2 * cover.guides.bleed_tb)"
      ></div>
      <!-- Falz links/rechts vom Rücken -->
      <div class="guide fold" :style="box(cover.guides.spine_x - cover.guides.fold, 0, cover.guides.fold, cover.height_mm)"></div>
      <div class="guide fold" :style="box(cover.guides.spine_x + cover.guides.spine_w, 0, cover.guides.fold, cover.height_mm)"></div>
      <div class="guide spine" :style="box(cover.guides.spine_x, 0, cover.guides.spine_w, cover.height_mm)"></div>
      <span class="label" :style="{ left: pctX(cover.guides.bleed_lr + 4), top: pctY(cover.guides.bleed_tb + 3) }">Rückseite</span>
      <span class="label" :style="{ left: pctX(cover.guides.spine_x + cover.guides.spine_w + cover.guides.fold + 4), top: pctY(cover.guides.bleed_tb + 3) }">Vorderseite</span>
    </template>
  </div>
</template>

<style scoped>
.cover {
  position: relative;
  width: 100%;
  overflow: hidden;
  container-type: inline-size;
  border-radius: 3px;
  box-shadow:
    0 24px 50px -20px rgba(0, 0, 0, 0.9),
    0 2px 6px rgba(0, 0, 0, 0.4);
}
.img,
.rect,
.text {
  position: absolute;
}
.img {
  overflow: hidden;
}
.img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.img.framed {
  overflow: visible;
  background: #fff;
  box-shadow: 0.25cqw 0.3cqw 0.6cqw rgba(0, 0, 0, 0.22);
}
.img.tape::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  width: min(30%, 3.8cqw);
  height: 1.12cqw;
  background: rgba(245, 220, 158, 0.72);
  transform: translate(-50%, -50%) rotate(-3deg);
  z-index: 1;
}
.text {
  line-height: 1;
  white-space: nowrap;
}
.text.rotated {
  display: grid;
  place-items: center;
  overflow: visible;
}
.text.rotated span {
  display: block;
  white-space: nowrap;
}
.guide {
  position: absolute;
  pointer-events: none;
  z-index: 5;
}
.guide.bleed {
  outline: 1px dashed rgba(255, 60, 90, 0.9);
}
.guide.fold {
  background: repeating-linear-gradient(45deg, rgba(0, 160, 255, 0.18) 0 4px, transparent 4px 8px);
}
.guide.spine {
  border-left: 1px dashed rgba(0, 160, 255, 0.95);
  border-right: 1px dashed rgba(0, 160, 255, 0.95);
}
.label {
  position: absolute;
  z-index: 6;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(8, 8, 15, 0.7);
  color: #fff;
}
</style>
