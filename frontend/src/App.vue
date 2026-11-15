<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import AnalysisPanel from './components/AnalysisPanel.vue'
import AppHeader from './components/AppHeader.vue'
import BookEditor from './components/BookEditor.vue'
import BookPreview from './components/BookPreview.vue'
import Lightbox from './components/Lightbox.vue'
import PhotoCard from './components/PhotoCard.vue'
import SelectionBar from './components/SelectionBar.vue'
import ToastStack from './components/ToastStack.vue'
import UploadZone from './components/UploadZone.vue'
import { useAlbum } from './useAlbum'

const {
  album,
  images,
  running,
  classified,
  visibleGroups,
  visibleImages,
  editorOpen,
  init,
  stopPolling,
  toggleIncluded,
} = useAlbum()

const openId = ref<string | null>(null)

onMounted(init)
onUnmounted(stopPolling)
</script>

<template>
  <div class="app">
    <AppHeader />

    <main>
      <!-- Leerer Zustand: großer Hero -->
      <section v-if="!images.length" class="hero">
        <h2>Aus <span class="gradient-text">Hunderten Urlaubsfotos</span><br />wird ein fertiges Fotobuch.</h2>
        <p>
          Ein lokales KI-Modell bewertet jedes Bild, erkennt Duplikate und Serien und stellt die besten
          Aufnahmen zu Fotobuch-Seiten zusammen. Nichts verlässt deinen Rechner.
        </p>
        <UploadZone :compact="false" />
        <ol class="steps">
          <li><b>1</b> Bilder hochladen</li>
          <li><b>2</b> KI-Analyse</li>
          <li><b>3</b> Auswahl prüfen</li>
          <li><b>4</b> PDF exportieren</li>
        </ol>
      </section>

      <template v-else-if="album">
        <UploadZone :compact="true" />
        <AnalysisPanel />
        <BookPreview v-if="classified && !running" />
        <SelectionBar v-if="classified" />

        <section v-for="group in visibleGroups" :key="group.key" class="group">
          <h3>
            <span v-if="group.icon" class="icon">{{ group.icon }}</span>
            <span class="titles">
              <small v-if="group.subtitle">{{ group.subtitle }}</small>
              {{ group.title }}
            </span>
            <span class="count">
              {{ group.images.filter((i) => i.included).length }} / {{ group.images.length }} im Buch
            </span>
          </h3>
          <TransitionGroup tag="div" name="grid" class="grid">
            <PhotoCard
              v-for="img in group.images"
              :key="img.id"
              :album-id="album.id"
              :image="img"
              :analyzing="running"
              @open="openId = img.id"
              @toggle="toggleIncluded(img)"
            />
          </TransitionGroup>
        </section>

        <p v-if="!visibleGroups.length" class="empty">Keine Bilder für diesen Filter.</p>
      </template>
    </main>

    <Lightbox
      v-if="openId"
      :image-id="openId"
      :list="visibleImages"
      @close="openId = null"
      @navigate="openId = $event"
    />
    <BookEditor v-if="editorOpen" />
    <ToastStack />
  </div>
</template>

<style scoped>
.app {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 clamp(1rem, 3vw, 2.5rem) 5rem;
}
main {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 1.5rem;
  padding-top: clamp(1rem, 6vh, 4rem);
}
.hero h2 {
  font-size: clamp(2rem, 5vw, 3.6rem);
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -0.035em;
}
.hero > p {
  max-width: 620px;
  margin: 0;
  color: var(--muted);
  font-size: 1.05rem;
  line-height: 1.6;
}
.hero :deep(.drop) {
  width: min(760px, 100%);
}
.steps {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.5rem 1.75rem;
  color: var(--muted);
  font-size: 0.88rem;
}
.steps b {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  margin-right: 0.35rem;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text);
  font-size: 0.75rem;
}
.group h3 {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 1rem 0 1rem;
  font-size: 1.25rem;
}
.group .icon {
  font-size: 1.3rem;
}
.group .titles {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.group .titles small {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
}
.group .count {
  margin-left: auto;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--muted);
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
.grid-move,
.grid-enter-active,
.grid-leave-active {
  transition: all 0.45s var(--ease);
}
.grid-enter-from,
.grid-leave-to {
  opacity: 0;
  transform: scale(0.94);
}
.grid-leave-active {
  position: absolute;
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 3rem 0;
}
@media (max-width: 480px) {
  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.6rem;
  }
}
</style>
