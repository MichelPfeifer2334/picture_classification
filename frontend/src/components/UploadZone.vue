<script setup lang="ts">
import { onMounted, ref } from 'vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ files: [files: File[]] }>()

const IMAGE_EXT = /\.(jpe?g|png|webp|heic|heif|tiff?|bmp)$/i

const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)

onMounted(() => {
  // Ordnerauswahl: Attribut per JS setzen (nicht im TS-Typ von <input> enthalten)
  folderInput.value?.setAttribute('webkitdirectory', '')
})

function submit(list: FileList | null | undefined) {
  const files = Array.from(list ?? []).filter((f) => IMAGE_EXT.test(f.name))
  if (files.length) emit('files', files)
}

function onDrop(e: DragEvent) {
  dragging.value = false
  submit(e.dataTransfer?.files)
}

function onChange(e: Event) {
  const input = e.target as HTMLInputElement
  submit(input.files)
  input.value = '' // gleiche Dateien erneut wählbar
}
</script>

<template>
  <div
    class="dropzone"
    :class="{ dragging, disabled }"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="!disabled && onDrop($event)"
  >
    <p>Bilder hierher ziehen</p>
    <p class="or">oder</p>
    <div class="buttons">
      <button type="button" :disabled="disabled" @click="fileInput?.click()">
        Dateien wählen
      </button>
      <button type="button" :disabled="disabled" @click="folderInput?.click()">
        Ordner wählen
      </button>
    </div>
    <input ref="fileInput" type="file" multiple accept="image/*,.heic,.heif" hidden @change="onChange" />
    <input ref="folderInput" type="file" multiple hidden @change="onChange" />
  </div>
</template>

<style scoped>
.dropzone {
  border: 2px dashed #9aa4b2;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  background: #fafbfc;
}
.dropzone.dragging {
  border-color: #2563eb;
  background: #eff6ff;
}
.dropzone.disabled {
  opacity: 0.5;
}
.or {
  color: #6b7280;
  margin: 0.25rem 0 0.75rem;
}
.buttons {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
