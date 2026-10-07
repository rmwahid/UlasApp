<script>
  import { onMount } from "svelte";

  let llmBaseUrl = "";
  let llmModel = "";
  let llmApiKey = "";
  let apiKeySet = false;
  let message = "";
  let error = "";

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
  });

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
      <input bind:value={llmApiKey} type="password" placeholder={apiKeySet ? "Leave empty to keep" : "Paste API key"} />
    </label>
    <button type="submit">Save</button>
    {#if message}<p class="ok">{message}</p>{/if}
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
  input {
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
  .ok {
    color: #7fd4c1;
    margin: 0;
  }
  .error {
    color: #ff8f8f;
    margin: 0;
  }
</style>
