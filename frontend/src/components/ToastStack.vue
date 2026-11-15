<script setup lang="ts">
import { useAlbum } from '../useAlbum'

const { toasts } = useAlbum()
</script>

<template>
  <div class="stack" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast glass" :class="t.kind">
        <i aria-hidden="true"></i>
        <span>{{ t.text }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.stack {
  position: fixed;
  right: 1rem;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 1rem);
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: min(420px, calc(100vw - 2rem));
}
.toast {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.85rem 1.1rem;
  background: rgba(20, 20, 31, 0.92);
  font-size: 0.9rem;
}
.toast i {
  flex: none;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
}
.toast.success i {
  background: var(--good);
}
.toast.error i {
  background: var(--bad);
}
.toast-enter-active,
.toast-leave-active {
  transition: all 0.35s var(--ease);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}
</style>
