<script>
  import JobDetail from "./components/JobDetail.svelte";
  import JobList from "./components/JobList.svelte";
  import NewJob from "./components/NewJob.svelte";
  import Settings from "./components/Settings.svelte";

  let view = "new";
  let jobId = null;

  function openJob(id) {
    jobId = id;
    view = "job";
  }
</script>

<main>
  <header>
    <h1>UlasApp</h1>
    <nav>
      <button class:active={view === "new"} on:click={() => (view = "new")}>New video</button>
      <button class:active={view === "jobs"} on:click={() => (view = "jobs")}>Jobs</button>
      <button class:active={view === "settings"} on:click={() => (view = "settings")}>
        Settings
      </button>
    </nav>
  </header>

  {#if view === "new"}
    <NewJob onCreated={openJob} />
  {:else if view === "jobs"}
    <JobList onOpen={openJob} />
  {:else if view === "job"}
    <JobDetail id={jobId} />
  {:else}
    <Settings />
  {/if}
</main>

<style>
  :global(body) {
    margin: 0;
    background: #0e1116;
    color: #e8ecf1;
    font-family: system-ui, sans-serif;
  }
  main {
    max-width: 760px;
    margin: 0 auto;
    padding: 24px 16px 64px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 24px;
  }
  h1 {
    font-size: 22px;
    margin: 0;
  }
  nav {
    display: flex;
    gap: 8px;
  }
  button {
    background: #1a2028;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 8px;
    padding: 8px 14px;
    cursor: pointer;
  }
  button.active {
    background: #f5b52e;
    color: #14181f;
    border-color: #f5b52e;
  }
</style>
