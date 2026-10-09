<script>
  import { onMount } from "svelte";

  export let onOpen = () => {};
  export let onNew = () => {};

  let projects = [];
  let error = "";
  let loading = true;

  async function load() {
    try {
      const response = await fetch("/api/jobs");
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      projects = await response.json();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<section>
  <header>
    <h2>Projects</h2>
    <button class="primary" on:click={onNew}>New project</button>
  </header>
  <p class="hint">
    One project per product. Inside a project you pick the material, check the descriptions, fill in
    the brief, and generate a video. Each generate adds a new version.
  </p>

  {#if error}
    <p class="error">{error}</p>
  {:else if loading}
    <p class="hint">Loading...</p>
  {:else if projects.length === 0}
    <p class="hint">No projects yet. Start with New project.</p>
  {:else}
    <ul>
      {#each projects as project}
        <li>
          <button on:click={() => onOpen(project.id)}>
            <span class="title">{project.title}</span>
            {#if project.material_count}
              <span class="meta">{project.material_count} material</span>
            {/if}
            {#if project.version_count}
              <span class="meta">{project.version_count} version{project.version_count === 1 ? "" : "s"}</span>
            {/if}
            <span class="badge {project.status}">{project.status}</span>
            <span class="date">{project.created_at.slice(0, 16).replace("T", " ")}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  section {
    background: #141922;
    border: 1px solid #2a323d;
    border-radius: 12px;
    padding: 20px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  h2 {
    margin: 0;
    font-size: 18px;
  }
  button.primary {
    background: linear-gradient(180deg, #ffc94d, #f5a813);
    color: #14181f;
    border: none;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 700;
    cursor: pointer;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }
  li button {
    width: 100%;
    display: flex;
    gap: 12px;
    align-items: center;
    text-align: left;
    background: #0e1116;
    border: 1px solid #2a323d;
    border-radius: 8px;
    padding: 12px;
    color: inherit;
    cursor: pointer;
  }
  .title {
    flex: 1;
  }
  .meta {
    color: #93a1b3;
    font-size: 12px;
    text-align: right;
    min-width: 84px;
  }
  .badge {
    font-size: 12px;
    padding: 2px 10px;
    border-radius: 999px;
    background: #2a323d;
    min-width: 62px;
    text-align: center;
  }
  .badge.done {
    background: #2f9e6e;
  }
  .badge.failed {
    background: #c0392b;
  }
  .badge.running {
    background: #f5b52e;
    color: #14181f;
  }
  .date {
    color: #93a1b3;
    font-size: 12px;
    min-width: 104px;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .hint {
    color: #93a1b3;
    font-size: 13px;
  }
  .error {
    color: #ff8f8f;
  }
</style>
