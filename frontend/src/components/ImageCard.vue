<script setup lang="ts">
import { api } from '../api'
import type { ImageRecord } from '../types'

defineProps<{ albumId: string; image: ImageRecord }>()

const QUALITY_LABEL = { good: 'gut', ok: 'ok', bad: 'schlecht' } as const
</script>

<template>
  <figure class="card">
    <img :src="api.thumbUrl(albumId, image.id)" :alt="image.filename" loading="lazy" />
    <figcaption>
      <template v-if="image.classification">
        <span class="badge" :class="image.classification.quality">
          {{ QUALITY_LABEL[image.classification.quality] }}
        </span>
        <span class="caption">{{ image.classification.caption }}</span>
        <small :title="image.classification.quality_reason">
          {{ image.classification.quality_reason }}
        </small>
      </template>
      <small v-else-if="image.status === 'error'" class="error">{{ image.error }}</small>
      <small v-else class="muted">noch nicht klassifiziert</small>
      <small class="muted">{{ image.filename }}</small>
    </figcaption>
  </figure>
</template>

<style scoped>
.card {
  margin: 0;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}
img {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  display: block;
  background: #f3f4f6;
}
figcaption {
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.caption {
  font-weight: 600;
}
small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: #6b7280;
}
.error {
  color: #b91c1c;
}
.badge {
  align-self: flex-start;
  font-size: 0.75rem;
  padding: 0.05rem 0.4rem;
  border-radius: 4px;
}
.badge.good {
  background: #dcfce7;
  color: #166534;
}
.badge.ok {
  background: #fef9c3;
  color: #854d0e;
}
.badge.bad {
  background: #fee2e2;
  color: #991b1b;
}
</style>
