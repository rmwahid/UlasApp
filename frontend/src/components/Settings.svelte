<script>
  import { onMount } from "svelte";

  let llmBaseUrl = "";
  let llmModel = "";
  let llmApiKey = "";
  let apiKeySet = false;
  let message = "";
  let error = "";

  let ff = null;
  let ffBusy = "";
  let ffPathInput = "";
  let ffMessage = "";
  let ffError = "";

  onMount(async () => {
    try {
      const response = await fetch("/api/settings");
      const data = await response.json();
      llmBaseUrl = data.llm_base_url;
      llmModel = data.llm_model;
      apiKeySet = data.llm_api_key_set;
    } catch (err) {
      error = err.message;
    }
    await loadFfmpeg();
  });

  async function loadFfmpeg() {
    ffError = "";
    try {
      const response = await fetch("/api/ffmpeg");
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      ff = await response.json();
    } catch (err) {
      ffError = err.message;
    }
  }

  async function save() {
    message = "";
    error = "";
    try {
      const payload = { llm_base_url: llmBaseUrl, llm_model: llmModel };
      if (llmApiKey) payload.llm_api_key = llmApiKey;
      const response = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const data = await response.json();
      apiKeySet = data.llm_api_key_set;
      llmApiKey = "";
      message = "Saved.";
    } catch (err) {
      error = err.message;
    }
  }

  async function ffmpegAction(kind) {
    ffBusy = kind;
    ffMessage = "";
    ffError = "";
    try {
      const response = await fetch(`/api/ffmpeg/${kind}`, { method: "POST" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || body.message || `Request failed (${response.status})`);
      ff = body;
      ffMessage = kind === "install" ? "FFmpeg installed." : "FFmpeg updated.";
    } catch (err) {
      ffError = err.message;
    } finally {
      ffBusy = "";
    }
  }

  async function saveFfmpegPath() {
    ffBusy = "path";
    ffMessage = "";
    ffError = "";
    try {
      const response = await fetch("/api/ffmpeg/path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory: ffPathInput }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || body.message || `Request failed (${response.status})`);
      ff = body;
      ffMessage = "FFmpeg folder applied.";
      ffPathInput = "";
    } catch (err) {
      ffError = err.message;
    } finally {
      ffBusy = "";
    }
  }
</script>

<section>
  <h2>Settings</h2>
  <form on:submit|preventDefault={save}>
    <label>
      LLM base URL (OpenAI-compatible)
      <input bind:value={llmBaseUrl} placeholder="https://api.openai.com/v1" />
    </label>
    <label>
      Model
      <input bind:value={llmModel} placeholder="e.g. gpt-4o-mini" />
    </label>
    <label>
      API key {#if apiKeySet}<span class="set">(stored)</span>{/if}
      <input
        bind:value={llmApiKey}
        type="password"
        placeholder={apiKeySet ? "Leave empty to keep" : "Paste API key"}
      />
    </label>
    <button type="submit">Save</button>
    {#if message}<p class="ok">{message}</p>{/if}
    {#if error}<p class="error">{error}</p>{/if}
  </form>
</section>

<section>
  <h2>FFmpeg</h2>
  <p class="hint">Used by the render stage. Install, update, or point UlasApp at an existing copy.</p>
  {#if ff === null}
    <p class="hint">Checking...</p>
  {:else}
    <div class="ffrow">
      <span class="badge {ff.found ? 'ok' : 'bad'}">
        {ff.found ? (ff.version || "found") : "not found"}
      </span>
      <span class="chip">{ff.source || "unknown"}</span>
      {#if ff.found && !ff.on_path}
        <span class="chip warn">not on PATH</span>
      {/if}
      {#if ff.upgrade_available}
        <span class="chip warn">update available</span>
      {/if}
    </div>
    {#if ff.path}
      <code class="path">{ff.path}</code>
    {/if}

    <div class="actions">
      {#if !ff.found && ff.winget_available}
        <button disabled={!!ffBusy} on:click={() => ffmpegAction("install")}>
          {ffBusy === "install" ? "Installing..." : "Install via winget"}
        </button>
      {:else if ff.found && ff.upgrade_available}
        <button disabled={!!ffBusy} on:click={() => ffmpegAction("upgrade")}>
          {ffBusy === "upgrade" ? "Updating..." : "Update via winget"}
        </button>
      {:else if ff.found}
        <span class="ok">Up to date.</span>
      {:else}
        <span class="hint">winget unavailable - set the folder below.</span>
      {/if}
    </div>

    <details>
      <summary>Use a different FFmpeg folder</summary>
      <div class="pathrow">
        <input bind:value={ffPathInput} placeholder="Folder containing ffprobe.exe" />
        <button disabled={!!ffBusy || !ffPathInput} on:click={saveFfmpegPath}>Use</button>
      </div>
    </details>

    {#if ffBusy}<p class="hint">Working: {ffBusy}... this can take a few minutes.</p>{/if}
    {#if ffMessage}<p class="ok">{ffMessage}</p>{/if}
    {#if ffError}<p class="error">{ffError}</p>{/if}
  {/if}
</section>

<style>
  section {
    background: #141922;
    border: 1px solid #2a323d;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
  }
  h2 {
    margin: 0 0 12px;
    font-size: 18px;
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
  .set {
    color: #7fd4c1;
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
    padding: 10px 16px;
    font-weight: 700;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .ffrow {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .badge {
    font-size: 12px;
    padding: 2px 10px;
    border-radius: 999px;
  }
  .badge.ok {
    background: #2f9e6e;
  }
  .badge.bad {
    background: #c0392b;
  }
  .chip {
    font-size: 12px;
    padding: 2px 10px;
    border-radius: 999px;
    border: 1px solid #2a323d;
    color: #93a1b3;
  }
  .chip.warn {
    border-color: #f5b52e;
    color: #f5b52e;
  }
  .path {
    display: block;
    font-size: 12px;
    color: #93a1b3;
    word-break: break-all;
    margin-bottom: 8px;
  }
  .actions {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 8px;
  }
  details {
    margin: 8px 0;
  }
  summary {
    cursor: pointer;
    color: #b7c2cf;
    font-size: 13px;
  }
  .pathrow {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }
  .pathrow input {
    flex: 1;
  }
  .ok {
    color: #7fd4c1;
    margin: 0;
  }
  .hint {
    color: #93a1b3;
    margin: 0;
  }
  .error {
    color: #ff8f8f;
    margin: 0;
  }
</style>
