<script>
  export let onCreated = () => {};

  let title = "";
  let productName = "";
  let price = "";
  let points = "";
  let photo = null;
  let music = null;
  let busy = false;
  let error = "";

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
      form.set("music", music);
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
    One product photo and one music track. The output is a vertical text + music review video.
  </p>
  <form on:submit|preventDefault={submit}>
    <label>
      Product photo
      <input
        type="file"
        accept="image/*"
        required
        on:change={(event) => (photo = event.target.files[0])}
      />
    </label>
    <label>
      Music track
      <input
        type="file"
        accept="audio/*"
        required
        on:change={(event) => (music = event.target.files[0])}
      />
    </label>
    <label>
      Product name
      <input bind:value={productName} required placeholder="e.g. Watch X" />
    </label>
    <label>
      Price
      <input bind:value={price} placeholder="e.g. Rp 299.000" />
    </label>
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
    <button type="submit" disabled={busy || !photo || !music}>
      {busy ? "Starting..." : "Generate"}
    </button>
    {#if error}<p class="error">{error}</p>{/if}
  </form>
</section>

<style>
  section {
    background: #141922;
    border: 1px solid #2a323d;
    border-radius: 12px;
    padding: 20px;
  }
  h2 {
    margin: 0 0 6px;
    font-size: 18px;
  }
  .hint {
    color: #93a1b3;
    font-size: 13px;
    margin: 0 0 16px;
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
  button {
    background: #f5b52e;
    color: #14181f;
    border: none;
    border-radius: 8px;
    padding: 12px;
    font-weight: 700;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .error {
    color: #ff8f8f;
    margin: 0;
  }
</style>
