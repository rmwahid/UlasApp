<script>
  export let onCreated = () => {};

  let title = "";
  let productName = "";
  let price = "";
  let points = "";
  let photo = null;
  let photoUrl = "";
  let music = null;
  let musicName = "";
  let busy = false;
  let error = "";

  function pickPhoto(event) {
    const file = event.target.files[0] || null;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    photo = file;
    photoUrl = photo ? URL.createObjectURL(photo) : "";
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
      form.set("title", title || productName);
      form.set("product_name", productName);
      form.set("price", price);
      form.set("points", points);
      form.set("photo", photo);
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
</script>

<section>
  <h2>New review video</h2>
  <p class="hint">
    One product photo in, a vertical text + music review video out. Music is optional.
  </p>

  <div class="uploads">
    <label class="drop photo-drop" class:filled={photo}>
      <input type="file" accept="image/*" on:change={pickPhoto} />
      {#if photoUrl}
        <img src={photoUrl} alt="Product preview" />
        <div class="meta">
          <span class="name">{photo.name}</span>
          <span class="size">{formatSize(photo.size)}</span>
        </div>
      {:else}
        <span class="emoji">🖼️</span>
        <span class="label">Product photo</span>
        <span class="sub">click to choose - it becomes the video background</span>
      {/if}
    </label>

    <label class="drop" class:filled={music}>
      <input type="file" accept="audio/*" on:change={pickMusic} />
      <span class="emoji">🎵</span>
      <span class="label">Music <em>optional</em></span>
      {#if musicName}
        <span class="sub">{musicName}</span>
      {:else}
        <span class="sub">silent video when skipped</span>
      {/if}
    </label>
  </div>

  <form on:submit|preventDefault={submit}>
    <div class="grid">
      <label>
        Product name
        <input bind:value={productName} required placeholder="e.g. Watch X" />
      </label>
      <label>
        Price
        <input bind:value={price} placeholder="e.g. Rp 299.000" />
      </label>
    </div>
    <label>
      Key points
      <textarea
        bind:value={points}
        rows="4"
        placeholder="What you like, what could be better, who it is for"
      ></textarea>
    </label>
    <label>
      Job title (optional)
      <input bind:value={title} placeholder="Defaults to the product name" />
    </label>
    <button type="submit" disabled={busy || !photo}>
      {busy ? "Starting..." : "Generate video"}
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
    margin: 0 0 18px;
  }
  .uploads {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
  }
  .drop {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 150px;
    padding: 14px;
    border: 1.5px dashed #3a4450;
    border-radius: 12px;
    cursor: pointer;
    text-align: center;
    overflow: hidden;
    transition: border-color 0.15s ease, background 0.15s ease;
  }
  .drop:hover {
    border-color: #f5b52e;
    background: #171d26;
  }
  .drop.filled {
    border-style: solid;
    border-color: #2f9e6e;
  }
  .drop input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }
  .drop .emoji {
    font-size: 28px;
  }
  .drop .label {
    font-size: 14px;
    font-weight: 600;
  }
  .drop .label em {
    color: #f5b52e;
    font-style: normal;
    font-size: 11px;
    margin-left: 4px;
  }
  .drop .sub {
    font-size: 12px;
    color: #93a1b3;
  }
  .photo-drop img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .photo-drop .meta {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(8, 10, 14, 0.72);
    font-size: 12px;
  }
  .photo-drop.filled:hover .meta {
    background: rgba(8, 10, 14, 0.85);
  }
  .meta .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta .size {
    color: #93a1b3;
  }
  form {
    display: grid;
    gap: 12px;
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
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
