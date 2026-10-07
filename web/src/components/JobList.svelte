<script>
  import { onMount } from "svelte";

  export let onOpen = () => {};

  let jobs = [];
  let error = "";

  onMount(async () => {
    try {
      const response = await fetch("/api/jobs");
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      jobs = await response.json();
    } catch (err) {
      error = err.message;
    }
  });
</script>

<section>
  <h2>Jobs</h2>
  {#if error}
    <p class="error">{error}</p>
  {:else if jobs.length === 0}
    <p class="hint">No jobs yet. Create one from the New video tab.</p>
  {:else}
    <ul>
      {#each jobs as job}
        <li>
          <button on:click={() => onOpen(job.id)}>
            <span class="title">{job.title}</span>
            <span class="badge {job.status}">{job.status}</span>
            <span class="date">{job.created_at.slice(0, 16).replace("T", " ")}</span>
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
  h2 {
    margin: 0 0 12px;
    font-size: 18px;
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
  }
  .title {
    flex: 1;
  }
  .badge {
    font-size: 12px;
    padding: 2px 10px;
    border-radius: 999px;
    background: #2a323d;
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
  }
  .hint {
    color: #93a1b3;
  }
  .error {
    color: #ff8f8f;
  }
</style>
