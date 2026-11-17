/**
 * Ordner einlesen – ohne den Browser zu überlasten.
 *
 * 1. Bevorzugt: File System Access API (`showDirectoryPicker`, Chrome/Edge). Die Dateien werden
 *    nacheinander gelesen, nur Bilder werden überhaupt geöffnet.
 * 2. Ordner per Drag & Drop: `webkitGetAsEntry` + schrittweises Auslesen.
 * 3. Notlösung für andere Browser: `<input webkitdirectory>` (liest alles auf einmal ein –
 *    bei sehr großen Ordnern oder OneDrive-Ordnern bekannt instabil).
 */

export const IMAGE_EXT = /\.(jpe?g|png|webp|heic|heif|tiff?|bmp)$/i
const MAX_DEPTH = 6 // Unterordner-Tiefe

// Minimal-Typen: die File System Access API ist (noch) nicht in allen TS-DOM-Typen enthalten
interface FsFileHandle {
  kind: 'file'
  name: string
  getFile(): Promise<File>
}
interface FsDirHandle {
  kind: 'directory'
  name: string
  values(): AsyncIterable<FsFileHandle | FsDirHandle>
}
type DirectoryPicker = (options?: { mode?: 'read'; id?: string }) => Promise<FsDirHandle>

export function supportsDirectoryPicker(): boolean {
  return typeof (window as unknown as { showDirectoryPicker?: unknown }).showDirectoryPicker === 'function'
}

async function collectHandle(dir: FsDirHandle, out: File[], depth: number): Promise<void> {
  for await (const entry of dir.values()) {
    if (entry.kind === 'file') {
      if (IMAGE_EXT.test(entry.name)) out.push(await entry.getFile())
    } else if (depth < MAX_DEPTH && !entry.name.startsWith('.')) {
      await collectHandle(entry, out, depth + 1)
    }
  }
}

/** Ordner über den Systemdialog wählen. null = abgebrochen. */
export async function pickDirectory(): Promise<File[] | null> {
  const picker = (window as unknown as { showDirectoryPicker: DirectoryPicker }).showDirectoryPicker
  try {
    const dir = await picker({ mode: 'read', id: 'fotobuch-fotos' })
    const files: File[] = []
    await collectHandle(dir, files, 0)
    return files
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return null
    throw e
  }
}

// --- Drag & Drop von Ordnern (FileSystemEntry-API) ---------------------------------

function readEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => reader.readEntries(resolve, reject))
}

function entryFile(entry: FileSystemFileEntry): Promise<File> {
  return new Promise((resolve, reject) => entry.file(resolve, reject))
}

async function collectEntry(entry: FileSystemEntry, out: File[], depth: number): Promise<void> {
  if (entry.isFile) {
    if (IMAGE_EXT.test(entry.name)) out.push(await entryFile(entry as FileSystemFileEntry))
    return
  }
  if (!entry.isDirectory || depth >= MAX_DEPTH || entry.name.startsWith('.')) return
  const reader = (entry as FileSystemDirectoryEntry).createReader()
  // readEntries liefert in Paketen (Chrome: max. 100) – so lange lesen, bis nichts mehr kommt
  for (let batch = await readEntries(reader); batch.length; batch = await readEntries(reader)) {
    for (const child of batch) await collectEntry(child, out, depth + 1)
  }
}

/** Dateien und Ordner aus einem Drop-Ereignis einsammeln (nur Bilder). */
export async function filesFromDrop(data: DataTransfer): Promise<File[]> {
  const entries = Array.from(data.items)
    .map((item) => item.webkitGetAsEntry?.())
    .filter((e): e is FileSystemEntry => !!e)
  if (!entries.length) return Array.from(data.files).filter((f) => IMAGE_EXT.test(f.name))
  const out: File[] = []
  for (const entry of entries) await collectEntry(entry, out, 0)
  return out
}
