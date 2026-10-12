<script>
  import { onDestroy } from "svelte";

  export let onCreated = () => {};

  const MAX_ASSETS = 20;

  let productName = "";
  let points = "";
  let direction = "";
  let overlayStyle = "";
  let material = [];
  let music = null;
  let musicName = "";
  let busy = false;
  let error = "";
  let nextId = 1;
  let dragIndex = null;
  let overIndex = null;
  let fileDrag = false;

  function kindOf(file) {
    if (file.type.startsWith("image/")) return "photo";
    if (file.type.startsWith("video/")) return "clip";
    const name = file.name.toLowerCase();
    if (/\.(jpe?g|png|webp)$/.test(name)) return "photo";
    if (/\.(mp4|mov|m4v|webm|mkv)$/.test(name)) return "clip";
    return null;
  }

  function addFiles(fileList) {
    const incoming = Array.from(fileList || []);
    if (!incoming.length) return;
    const kept = [];
    let message = "";
    for (const file of incoming) {
      if (material.length + kept.length >= MAX_ASSETS) {
        message = `At most ${MAX_ASSETS} files per project.`;
        break;
      }
      const kind = kindOf(file);
      if (!kind) {
        message = `${file.name} is neither a photo nor a clip.`;
        continue;
      }
      kept.push({
        id: nextId++,
        file,
        kind,
        url: URL.createObjectURL(file),
        hero: false,
      });
    }
    if (kept.length && !material.some((item) => item.hero)) {
      kept[0] = { ...kept[0], hero: true };
    }
    material = [...material, ...kept];
    error = message;
  }

  function pickFiles(event) {
    addFiles(event.target.files);
    event.target.value = "";
  }

  function markHero(id) {
    material = material.map((item) => ({ ...item, hero: item.id === id }));
  }

  function removeItem(id) {
    const item = material.find((entry) => entry.id === id);
    if (item) URL.revokeObjectURL(item.url);
    let kept = material.filter((entry) => entry.id !== id);
    if (kept.length && !kept.some((entry) => entry.hero)) {
      kept = kept.map((entry, index) => (index === 0 ? { ...entry, hero: true } : entry));
    }
    material = kept;
  }

  function startReorder(event, index) {
    dragIndex = index;
    overIndex = index;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(index));
  }

  function overItem(event, index) {
    if (dragIndex === null) return;
    event.preventDefault();
    event.stopPropagation();
    overIndex = index;
  }

  function dropOnItem(event, index) {
    if (dragIndex === null) return;
    event.preventDefault();
    event.stopPropagation();
    const next = [...material];
    const [moved] = next.splice(dragIndex, 1);
    next.splice(index, 0, moved);
    material = next;
    dragIndex = null;
    overIndex = null;
  }

  function endReorder() {
    dragIndex = null;
    overIndex = null;
  }

  function overZone(event) {
    const types = event.dataTransfer ? Array.from(event.dataTransfer.types) : [];
    if (types.includes("Files")) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      fileDrag = true;
    } else if (dragIndex !== null) {
      event.preventDefault();
    }
  }

  function dropOnZone(event) {
    fileDrag = false;
    if (dragIndex !== null || !event.dataTransfer) return;
    if (Array.from(event.dataTransfer.types).includes("Files")) {
      event.preventDefault();
      addFiles(event.dataTransfer.files);
    }
  }

  function leaveZone(event) {
    if (event.target === event.currentTarget) fileDrag = false;
  }

  function pickMusic(event) {
    music = event.target.files[0] || null;
    musicName = music ? music.name : "";
  }

  function formatSize(bytes) {
    if (bytes > 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  async function submit() {
    busy = true;
    error = "";
    try {
      const form = new FormData();
      form.set("product_name", productName);
      form.set("points", points);
      form.set("direction", direction);
      form.set("overlay_style", overlayStyle);
      for (const item of material) form.append("assets", item.file, item.file.name);
      const hero = material.findIndex((item) => item.hero);
      form.set("hero", String(hero < 0 ? 0 : hero));
      if (music) form.set("music", music);
      const response = await fetch("/api/jobs", { method: "POST", body: form });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${response.status})`);
      }
      const data = await response.json();
      onCreated(data.id);
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }

  onDestroy(() => {
    for (const item of material) URL.revokeObjectURL(item.url);
  });
</script>

<section>
  <h2>New project</h2>
  <p class="hint">
    Pick all the photos and clips for this product, drag them into the order you want, and mark the
    one to open with. Nothing renders yet: after this you check the descriptions the vision model
    wrote, then fill in the brief, then generate.
  </p>

  <div
    class="zone"
    class:file-drag={fileDrag}
    role="group"
    aria-label="Product material"
    on:dragover={overZone}
    on:dragleave={leaveZone}
    on:drop={dropOnZone}
  >
    <label class="drop">
      <input type="file" accept="image/*,video/*" multiple on:change={pickFiles} />
      <span class="emoji">📷</span>
      <span class="label">Add photos and clips</span>
      <span class="sub">click to choose, or drop files here</span>
    </label>

    {#if material.length}
      <ol class="material">
        {#each material as item, index (item.id)}
          <li
            class="tile"
            class:over={overIndex === index && dragIndex !== null}
            class:hero={item.hero}
            draggable="true"
            on:dragstart={(event) => startReorder(event, index)}
            on:dragover={(event) => overItem(event, index)}
            on:drop={(event) => dropOnItem(event, index)}
            on:dragend={endReorder}
          >
            <span class="order">{index + 1}</span>
            {#if item.kind === "photo"}
              <img src={item.url} alt={item.file.name} />
            {:else}
              <video src={item.url} muted playsinline preload="metadata"></video>
            {/if}
            <span class="badge">{item.kind}</span>
            <div class="tile-meta">
              <span class="name" title={item.file.name}>{item.file.name}</span>
              <span class="size">{formatSize(item.file.size)}</span>
            </div>
            <div class="tile-actions">
              <button
                type="button"
                class="star"
                class:on={item.hero}
                title={item.hero ? "Opens the video" : "Open the video with this one"}
                on:click={() => markHero(item.id)}
              >
                ★
              </button>
              <button type="button" class="remove" title="Remove" on:click={() => removeItem(item.id)}>
                ✕
              </button>
            </div>
          </li>
        {/each}
      </ol>
      <p class="order-hint">
        {material.length} file{material.length === 1 ? "" : "s"} - dragged order is the priority,
        the starred one opens the hook
      </p>
    {/if}
  </div>

  <label class="music">
    <input type="file" accept="audio/*" on:change={pickMusic} />
    <span>🎵 Music</span>
    <span class="music-name">{musicName || "optional - silent video when skipped"}</span>
  </label>

  <form on:submit|preventDefault={submit}>
    <label>
      Product name
      <input bind:value={productName} required placeholder="e.g. Watch X" />
    </label>
    <label>
      Key points
      <textarea
        bind:value={points}
        rows="4"
        placeholder="What you like, what could be better, the price, who it is for"
      ></textarea>
    </label>
    <fieldset>
      <legend>Video brief</legend>
      <p class="hint">
        Content only: what this video should say and which facts must appear. The look and the beat
        order are set in the project workspace, on the Style step. You can leave these empty and fill
        them later, or let the app draft them from the product.
      </p>
      <label>
        What should this video say?
        <textarea
          bind:value={direction}
          rows="3"
          placeholder="e.g. start with the watch on my wrist, keep it quick and casual, show it gets wet and still works"
        ></textarea>
      </label>
      <label>
        Facts that must appear on screen
        <textarea
          bind:value={overlayStyle}
          rows="2"
          placeholder="e.g. the price always shows, mention the water resistance"
        ></textarea>
      </label>
    </fieldset>
    <button type="submit" disabled={busy || !material.length || !productName.trim()}>
      {busy ? "Creating..." : "Create project"}
    </button>
    {#if error}<p class="error">{error}</p>{/if}
  </form>
</section>

<style>
  section {
    background: #141922;
    border: 1px solid #2a323d;
    border-radius: 14px;
    padding: 22px;
  }
  h2 {
    margin: 0 0 6px;
    font-size: 18px;
  }
  .hint {
    color: #93a1b3;
    font-size: 13px;
  }
  fieldset {
    display: grid;
    gap: 10px;
    border: 1px solid #2a323d;
    border-radius: 10px;
    padding: 14px;
  }
  legend {
    padding: 0 6px;
    color: #b7c2cf;
    font-size: 13px;
  }
  .zone {
    border: 1.5px dashed #3a4450;
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 16px;
    transition: border-color 0.15s ease, background 0.15s ease;
  }
  .zone.file-drag {
    border-color: #f5b52e;
    background: #171d26;
  }
  .drop {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 120px;
    padding: 14px;
    border-radius: 10px;
    cursor: pointer;
    text-align: center;
  }
  .drop:hover {
    background: #171d26;
  }
  .drop input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }
  .drop .emoji {
    font-size: 26px;
  }
  .drop .label {
    font-size: 14px;
    font-weight: 600;
  }
  .drop .sub,
  .order-hint {
    font-size: 12px;
    color: #93a1b3;
  }
  .material {
    list-style: none;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));
    gap: 10px;
    margin: 0 0 10px;
    padding: 0;
  }
  .tile {
    position: relative;
    aspect-ratio: 3 / 4;
    border: 1px solid #2a323d;
    border-radius: 10px;
    overflow: hidden;
    background: #0e1116;
    cursor: grab;
  }
  .tile.hero {
    border-color: #2f9e6e;
  }
  .tile.over {
    border-color: #f5b52e;
    transform: translateY(-2px);
  }
  .tile img,
  .tile video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .order {
    position: absolute;
    top: 6px;
    left: 6px;
    min-width: 20px;
    padding: 1px 5px;
    border-radius: 999px;
    background: rgba(8, 10, 14, 0.78);
    font-size: 11px;
    font-weight: 700;
    text-align: center;
  }
  .badge {
    position: absolute;
    top: 6px;
    right: 6px;
    padding: 1px 6px;
    border-radius: 999px;
    background: rgba(8, 10, 14, 0.78);
    color: #b7c2cf;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .tile-meta {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 8px;
    background: rgba(8, 10, 14, 0.78);
    font-size: 11px;
  }
  .tile-meta .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tile-meta .size {
    color: #93a1b3;
  }
  .tile-actions {
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    transform: translateY(-50%);
    display: flex;
    justify-content: space-between;
    padding: 0 6px;
    opacity: 0;
    transition: opacity 0.15s ease;
  }
  .tile:hover .tile-actions {
    opacity: 1;
  }
  .tile-actions button {
    width: 26px;
    height: 26px;
    padding: 0;
    border-radius: 999px;
    border: 1px solid #2a323d;
    background: rgba(14, 17, 22, 0.92);
    color: #e8ecf1;
    font-size: 13px;
    line-height: 1;
    cursor: pointer;
  }
  .tile-actions .star.on {
    background: #f5b52e;
    border-color: #f5b52e;
    color: #14181f;
  }
  .tile-actions .remove:hover {
    border-color: #ff8f8f;
    color: #ff8f8f;
  }
  .order-hint {
    margin: 0;
  }
  .music {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    margin-bottom: 16px;
    border: 1px solid #2a323d;
    border-radius: 10px;
    font-size: 13px;
    cursor: pointer;
  }
  .music input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }
  .music-name {
    color: #93a1b3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  form {
    display: grid;
    gap: 12px;
  }
  label {
    display: grid;
    gap: 6px;
    font-size: 13px;
    color: #b7c2cf;
  }
  input,
  textarea {
    background: #0e1116;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 8px;
    padding: 10px;
    font: inherit;
  }
  input:focus,
  textarea:focus {
    outline: none;
    border-color: #f5b52e;
  }
  button {
    background: linear-gradient(180deg, #ffc94d, #f5a813);
    color: #14181f;
    border: none;
    border-radius: 10px;
    padding: 12px;
    font-weight: 800;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .error {
    color: #ff8f8f;
    margin: 0;
  }
</style>
