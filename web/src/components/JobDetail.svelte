<script>
  import { onDestroy } from "svelte";

  export let id;

  let job = null;
  let state = null;
  let videoUrl = null;
  let error = "";
  let source = null;

  const stageLabels = {
    script: "Script",
    visual: "Visual",
    compose: "Compose",
    qa: "QA",
  };

  async function load() {
    try {
      const response = await fetch(`/api/jobs/${id}`);
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const data = await response.json();
      job = data.job;
      state = data.state;
      videoUrl = data.video_url;
    } catch (err) {
      error = err.message;
    }
  }

  function statusFor(stage) {
    const entry = state?.stages?.[stage];
    return entry ? entry.status : "pending";
  }

  load();
  source = new EventSource(`/api/jobs/${id}/events`);
  source.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "stage") {
      if (state && state.stages && state.stages[message.stage]) {
        state.stages[message.stage].status = message.status;
      }
      if (job) {
        job.status = "running";
        job.stage = message.stage;
      }
    }
    if (message.type === "done") {
      source.close();
      load();
    }
  };
  source.onerror = () => {
    source.close();
    load();
  };
  onDestroy(() => {
    if (source) source.close();
  });
</script>

<section>
  {#if error}
    <p class="error">{error}</p>
  {:else if job}
    <h2>{job.title}</h2>
    <p>
      <span class="badge {job.status}">{job.status}</span>
      {#if job.status === "running" && job.stage}
        <span class="stage">stage: {stageLabels[job.stage] || job.stage}</span>
      {/if}
    </p>
    {#if job.error}
      <p class="error">{job.error}</p>
    {/if}

    <div class="stages">
      {#each Object.keys(stageLabels) as stage}
        <span class="chip {statusFor(stage)}">{stageLabels[stage]}: {statusFor(stage)}</span>
      {/each}
    </div>

    <div class="preview">
      <img src={`/api/jobs/${id}/photo`} alt="Product photo" />
      {#if videoUrl}
        <video controls src={videoUrl}></video>
      {:else}
        <p class="hint">The rendered video appears here when the pipeline finishes.</p>
      {/if}
    </div>
  {:else}
    <p class="hint">Loading...</p>
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
    margin: 0 0 8px;
    font-size: 18px;
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
  .stage {
    color: #93a1b3;
    font-size: 13px;
  }
  .stages {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin: 12px 0;
  }
  .chip {
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid #2a323d;
    color: #93a1b3;
  }
  .chip.running {
    border-color: #f5b52e;
    color: #f5b52e;
  }
  .chip.done {
    border-color: #2f9e6e;
    color: #7fd4c1;
  }
  .chip.failed {
    border-color: #c0392b;
    color: #ff8f8f;
  }
  .preview {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 8px;
  }
  img,
  video {
    width: 100%;
    border-radius: 8px;
    background: #0e1116;
  }
  .hint {
    color: #93a1b3;
  }
  .error {
    color: #ff8f8f;
  }
</style>
