<script>
  import ProjectCreate from "./components/ProjectCreate.svelte";
  import ProjectDetail from "./components/ProjectDetail.svelte";
  import Projects from "./components/Projects.svelte";
  import Settings from "./components/Settings.svelte";

  let view = "projects";
  let projectId = null;

  function applyHash() {
    const hash = window.location.hash;
    const match = hash.match(/^#\/project\/([a-z0-9]+)/i);
    if (match) {
      projectId = match[1];
      view = "project";
    } else if (hash === "#/new") {
      view = "new";
    } else if (hash === "#/settings") {
      view = "settings";
    } else {
      view = "projects";
    }
  }
  applyHash();
  window.addEventListener("hashchange", applyHash);

  function openProject(id) {
    window.location.hash = `#/project/${id}`;
  }

  function newProject() {
    window.location.hash = "#/new";
  }

  function setView(name) {
    window.location.hash = `#/${name}`;
    applyHash();
  }
</script>

<main>
  <header>
    <h1>UlasApp</h1>
    <nav>
      <button class:active={view !== "settings"} on:click={() => setView("projects")}>
        Projects
      </button>
      <button class:active={view === "settings"} on:click={() => setView("settings")}>Settings</button>
    </nav>
  </header>

  {#if view === "new"}
    <ProjectCreate onCreated={openProject} />
  {:else if view === "project"}
    <ProjectDetail id={projectId} />
  {:else if view === "settings"}
    <Settings />
  {:else}
    <Projects onOpen={openProject} onNew={newProject} />
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
    max-width: 880px;
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
