<script setup lang="ts">
/**
 * Großansicht im Editor: Bild ansehen, Gruppe (Duplikat/Serie/ähnliches Motiv) überblicken
 * und direkt entscheiden – tauschen, zusätzlich aufnehmen oder entfernen.
 */
import { computed } from 'vue'
import { api } from '../api'
import { FLAG_LABELS, GROUP_LABELS, QUALITY_LABELS, STRENGTH_LABELS, formatDay, formatTime } from '../labels'
import type { ImageRecord } from '../types'
import { useAlbum } from '../useAlbum'
import ScoreRing from './ScoreRing.vue'

const props = defineProps<{
  imageId: string
  /** Bild-ID → Seitennummer (0-basiert) für alle Bilder, die im Buch stehen */
  placement: Map<string, number>
}>()

const emit = defineEmits<{
  close: []
  navigate: [id: string]
  replace: [memberId: string] // dieses Bild statt memberId verwenden
  add: [anchorId: string | null] // zusätzlich aufnehmen, neben anchorId (oder passend nach Zeit)
  remove: []
  'own-page': []
}>()

const { album, images } = useAlbum()

const image = computed(() => images.value.find((i) => i.id === props.imageId) ?? null)
const page = computed(() => props.placement.get(props.imageId))
const placed = computed(() => page.value !== undefined)

/** Alle Bilder der Gruppe – die Gruppe hängt am "Gewinner" (duplicate_of zeigt auf ihn). */
const members = computed<ImageRecord[]>(() => {
  const img = image.value
  if (!img) return []
  const leader = img.duplicate_of ?? img.id
  const list = images.value.filter((i) => i.id === leader || i.duplicate_of === leader)
  return list.length > 1 ? list.sort((a, b) => (b.rank ?? 0) - (a.rank ?? 0)) : []
})

const placedMember = computed(() =>
  members.value.find((m) => m.id !== props.imageId && props.placement.has(m.id)),
)

const groupKind = computed(() => members.value.find((m) => m.group_kind)?.group_kind ?? null)

const reason = computed(() => {
  const img = image.value
  if (!img || placed.value) return null
  if (img.included) return 'Ausgewählt, aber noch auf keiner Seite.'
  if (img.user_included === false) return 'Von dir aus dem Buch genommen.'
  if (img.duplicate_of && img.group_kind)
    return `${GROUP_LABELS[img.group_kind]} – ein besseres Bild dieser Gruppe ist ausgewählt.`
  if (img.score !== null && album.value && img.score < album.value.min_score)
    return `Score ${img.score.toFixed(1)} liegt unter deiner Strenge (${album.value.min_score.toFixed(1)}).`
  if (img.status === 'error') return 'Analyse fehlgeschlagen.'
  return 'Nicht ausgewählt.'
})
</script>

<template>
  <div class="peek" @click.self="emit('close')">
    <div v-if="image && album" class="box glass">
      <button class="close" aria-label="Schließen" @click="emit('close')">✕</button>

      <div class="stage">
        <img :key="image.id" :src="api.previewUrl(album.id, image.id)" :alt="image.filename" />
      </div>

      <aside class="side">
        <div class="head">
          <ScoreRing :score="image.score" :size="54" />
          <div>
            <p class="quality" :class="image.quality ?? ''">
              {{ image.quality ? QUALITY_LABELS[image.quality] : 'Nicht bewertet' }}
            </p>
            <p class="muted small">
              {{ formatDay(image.metrics?.taken_at ?? null) }}
              <template v-if="image.metrics?.taken_at">· {{ formatTime(image.metrics.taken_at) }}</template>
            </p>
          </div>
        </div>

        <h3 v-if="image.classification?.caption">{{ image.classification.caption }}</h3>
        <p v-if="image.classification?.reason" class="muted">{{ image.classification.reason }}</p>

        <div v-if="image.flags.length || image.classification?.strengths.length" class="tags">
          <span v-for="st in image.classification?.strengths ?? []" :key="st" class="tag plus">
            ＋ {{ STRENGTH_LABELS[st] ?? st }}
          </span>
          <span v-for="f in image.flags" :key="f" class="tag">{{ FLAG_LABELS[f] ?? f }}</span>
        </div>

        <p class="status" :class="{ in: placed }">
          <template v-if="placed">✓ Im Buch auf Seite {{ (page ?? 0) + 1 }}</template>
          <template v-else>{{ reason }}</template>
        </p>

        <!-- Gruppe -->
        <section v-if="members.length" class="group">
          <h4>
            {{ groupKind ? GROUP_LABELS[groupKind] : 'Gruppe' }} · {{ members.length }} Bilder
          </h4>
          <div class="strip">
            <button
              v-for="m in members"
              :key="m.id"
              class="member"
              :class="{ current: m.id === image.id, inbook: placement.has(m.id) }"
              :title="m.classification?.caption || m.filename"
              @click="emit('navigate', m.id)"
            >
              <img :src="api.thumbUrl(album.id, m.id)" alt="" />
              <span v-if="placement.has(m.id)" class="badge">S. {{ (placement.get(m.id) ?? 0) + 1 }}</span>
              <span class="score">{{ m.score?.toFixed(1) ?? '–' }}</span>
            </button>
          </div>
          <p class="muted small">Grün markiert = im Buch. Klick auf ein Bild zeigt es groß.</p>
        </section>

        <!-- Aktionen -->
        <div class="actions">
          <template v-if="!placed">
            <template v-if="placedMember">
              <button class="btn btn-primary" @click="emit('replace', placedMember.id)">
                ⇄ Statt Bild auf Seite {{ (placement.get(placedMember.id) ?? 0) + 1 }} verwenden
              </button>
              <button class="btn" @click="emit('add', placedMember.id)">
                ＋ Zusätzlich daneben aufnehmen
              </button>
            </template>
            <button v-else class="btn btn-primary" @click="emit('add', null)">
              ＋ Ins Buch aufnehmen (passend zur Aufnahmezeit)
            </button>
          </template>
          <template v-else>
            <button class="btn" @click="emit('own-page')">⤢ Auf eigene Seite</button>
            <button class="btn btn-ghost" @click="emit('remove')">✕ Aus dem Buch nehmen</button>
          </template>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.peek {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(4, 4, 8, 0.82);
  backdrop-filter: blur(12px);
  animation: fade 0.2s var(--ease);
}
@keyframes fade {
  from {
    opacity: 0;
  }
}
.box {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 1.25rem;
  width: min(1200px, 100%);
  max-height: calc(100vh - 3rem);
  padding: 1.25rem;
  background: rgba(20, 20, 31, 0.92);
}
.close {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  z-index: 2;
}
.stage {
  display: grid;
  place-items: center;
  min-height: 0;
}
.stage img {
  max-width: 100%;
  max-height: calc(100vh - 6rem);
  border-radius: 12px;
  animation: fade 0.25s;
}
.side {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  overflow-y: auto;
  padding-right: 0.25rem;
}
.head {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}
.quality {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 800;
}
.quality.good {
  color: var(--good);
}
.quality.ok {
  color: var(--ok);
}
.quality.bad {
  color: var(--bad);
}
h3 {
  font-size: 1.05rem;
}
h4 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  color: var(--muted);
  font-weight: 600;
}
.muted {
  color: var(--muted);
  margin: 0;
  line-height: 1.45;
}
.small {
  font-size: 0.8rem;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.tag {
  font-size: 0.75rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: rgba(251, 113, 133, 0.14);
  color: #fecdd3;
  border: 1px solid rgba(251, 113, 133, 0.3);
}
.tag.plus {
  background: rgba(74, 222, 128, 0.12);
  color: #bbf7d0;
  border-color: rgba(74, 222, 128, 0.3);
}
.status {
  margin: 0;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  font-size: 0.86rem;
  background: rgba(250, 204, 21, 0.1);
  border: 1px solid rgba(250, 204, 21, 0.28);
  color: #fde68a;
}
.status.in {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.3);
  color: #bbf7d0;
}
.group {
  padding: 0.8rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
}
.strip {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(70px, 1fr));
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}
.member {
  position: relative;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 9px;
  overflow: hidden;
  cursor: pointer;
  background: none;
  aspect-ratio: 1;
}
.member img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  filter: grayscale(0.5) brightness(0.8);
}
.member.inbook {
  border-color: var(--good);
}
.member.inbook img,
.member:hover img {
  filter: none;
}
.member.current {
  box-shadow: 0 0 0 2px var(--text);
}
.member .badge,
.member .score {
  position: absolute;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.05rem 0.35rem;
  border-radius: 6px;
  background: rgba(8, 8, 15, 0.75);
  color: #fff;
}
.member .badge {
  top: 3px;
  left: 3px;
  background: var(--good);
  color: #052e16;
}
.member .score {
  bottom: 3px;
  right: 3px;
}
.actions {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.actions .btn {
  white-space: normal;
  text-align: center;
}
@media (max-width: 900px) {
  .box {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }
  .stage img {
    max-height: 50vh;
  }
}
</style>
