<script>
  import { onDestroy, onMount } from "svelte";
  import TimelineTracks from "./TimelineTracks.svelte";

  export let id;

  let job = null;
  let state = null;
  let assets = [];
  let versions = [];
  let shots = [];
  let lines = [];
  let brief = { direction: "", overlay_style: "" };
  let activeTab = "media";
  let selectedAssetId = null;
  let showVersions = false;
  let showGenerate = false;
  let error = "";
  let note = "";
  let saving = false;
  let askedDescribe = false;
  let source = null;
  let videoEl = null;
  let playing = false;
  let duration = 0;
  let currentTime = 0;
  let shownVersion = null;
  let posterUrl = null;

  const rail = [
    { key: "media", icon: "▦", label: "Media" },
    { key: "brief", icon: "✎", label: "Brief" },
    { key: "music", icon: "♪", label: "Music" },
    { key: "voice", icon: "◍", label: "Voice Clone" },
  ];

  const stageChips = [
    { key: "describe", icon: "🔍", label: "Describe" },
    { key: "script", icon: "📝", label: "Script" },
    { key: "visual", icon: "🖼️", label: "Shots" },
    { key: "compose", icon: "🎬", label: "Render" },
    { key: "qa", icon: "✅", label: "QA" },
  ];

  const busyStatus = ["queued", "running"];

  $: busy = job ? busyStatus.includes(job.status) : false;
  $: described = assets.filter((asset) => asset.description).length;
  $: selectedAsset = assets.find((asset) => asset.id === selectedAssetId) || null;
  $: total = state?.timeline?.total || 0;
  $: currentVersion = shownVersion ?? (versions.length ? versions[0].number : null);
  $: versionLabel = currentVersion ? `v${currentVersion}` : "";
  $: musicName = state?.inputs?.music ? state.inputs.music.split("/").pop() : null;

  function closeStream() {
    if (source) source.close();
    source = null;
  }

  function openStream() {
    closeStream();
    source = new EventSource(`/api/jobs/${id}/events`);
    source.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "stage") {
        if (state && state.stages && state.stages[message.stage]) {
          state = {
            ...state,
            stages: {
              ...state.stages,
              [message.stage]: { ...state.stages[message.stage], status: message.status },
            },
          };
        }
        if (job) job = { ...job, status: "running", stage: message.stage };
      }
      if (message.type === "done") {
        closeStream();
        load();
      }
    };
    source.onerror = () => {
      closeStream();
      load();
    };
  }

  function buildShots(shotlist) {
    return (shotlist || []).map((shot) => ({
      ...shot,
      thumb: `/api/jobs/${id}/assets/${shot.asset}/thumb`,
    }));
  }

  function usedBy(assetId) {
    return shots
      .filter((shot) => shot.asset === assetId)
      .map((shot) => shot.line)
      .join(", ");
  }

  async function load() {
    try {
      const response = await fetch(`/api/jobs/${id}`);
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const data = await response.json();
      job = data.job;
      state = data.state;
      assets = data.assets.map((asset) => ({ ...asset, draft: asset.description || "" }));
      versions = data.versions || [];
      lines = data.state.timeline.lines || [];
      shots = buildShots(data.state.shotlist.shots);
      brief = { ...data.state.brief };
      posterUrl = data.poster_url;
      if (selectedAssetId && !assets.some((asset) => asset.id === selectedAssetId)) {
        selectedAssetId = null;
      }
      maybeDescribe();
    } catch (err) {
      error = err.message;
    }
  }

  function maybeDescribe() {
    const missing = assets.filter((asset) => !asset.description).length;
    if (askedDescribe || !assets.length || !missing || busy) return;
    askedDescribe = true;
    start("describe");
  }

  async function start(kind) {
    saving = true;
    error = "";
    note = "";
    showGenerate = false;
    try {
      const response = await fetch(`/api/jobs/${id}/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: kind === "render" ? JSON.stringify({ ...brief }) : undefined,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Request failed (${response.status})`);
      }
      note =
        kind === "describe"
          ? "Reading the material with the vision model."
          : "Rendering: script, shots, composition, QA. One project renders at a time.";
      await load();
      openStream();
    } catch (err) {
      error = err.message;
      askedDescribe = false;
    } finally {
      saving = false;
    }
  }

  async function saveAsset(asset) {
    if ((asset.description || "") === asset.draft) return;
    try {
      const response = await fetch(`/api/jobs/${id}/assets/${asset.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: asset.draft }),
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const data = await response.json();
      assets = assets.map((item) =>
        item.id === asset.id
          ? { ...item, description: data.description, draft: data.description || "" }
          : item,
      );
      note = `Description of ${asset.id} saved. It is used the next time you generate.`;
    } catch (err) {
      error = err.message;
    }
  }

  async function saveBrief() {
    try {
      await fetch(`/api/jobs/${id}/brief`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...brief }),
      });
    } catch (err) {
      error = err.message;
    }
  }

  async function reveal() {
    try {
      const response = await fetch(`/api/jobs/${id}/reveal`, { method: "POST" });
      if (!response.ok) throw new Error(`Could not open the folder (${response.status})`);
    } catch (err) {
      error = err.message;
    }
  }

  function pickVersion(version) {
    shownVersion = version.number;
    currentTime = 0;
    duration = 0;
    showVersions = false;
  }

  function togglePlay() {
    if (!videoEl) return;
    if (videoEl.paused) videoEl.play().catch(() => {});
    else videoEl.pause();
  }

  function seek(event) {
    const value = Number(event.target.value);
    currentTime = value;
    if (videoEl) videoEl.currentTime = value;
  }

  function seekTo(seconds) {
    currentTime = seconds;
    if (videoEl) videoEl.currentTime = seconds;
  }

  function statusFor(stage) {
    return state?.stages?.[stage]?.status || "pending";
  }

  function formatTime(seconds) {
    const whole = Math.max(0, Math.floor(seconds || 0));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  }

  function toggleAsset(assetId) {
    selectedAssetId = selectedAssetId === assetId ? null : assetId;
  }

  onMount(load);
  onDestroy(closeStream);
</script>

<div class="workspace">
  <header class="topbar">
    <button type="button" class="back" on:click={() => (window.location.hash = "#/projects")}>
      ← Projects
    </button>
    <span class="mark">▚ UlasApp</span>
    <span class="project">{job ? job.title : "..."}</span>
    {#if job}<span class="badge {job.status}">{job.status}</span>{/if}
    <span class="spacer"></span>
    <button type="button" on:click={() => (showVersions = !showVersions)}>
      Versions ({versions.length})
    </button>
    <button type="button" on:click={() => (window.location.hash = "#/settings")}>Settings</button>
    <button
      type="button"
      class="primary"
      disabled={saving || busy || !assets.length}
      on:click={() => (showGenerate = true)}
    >
      ⚡ {busy ? "Working..." : versions.length ? `Generate v${versions.length + 1}` : "Generate"}
    </button>
  </header>

  {#if error || job?.error}
    <p class="banner">{job?.error || error}</p>
  {/if}

  <div class="middle" class:with-detail={selectedAsset}>
    <nav class="rail" aria-label="Steps">
      {#each rail as item}
        <button
          type="button"
          class:active={activeTab === item.key}
          on:click={() => (activeTab = item.key)}
        >
          <span class="icon">{item.icon}</span>
          <span class="label">{item.label}</span>
        </button>
      {/each}
    </nav>

    <section class="panel">
      {#if activeTab === "media"}
        <header class="panel-head">
          <h2>Material</h2>
          <span class="count">{described} of {assets.length} described</span>
        </header>
        <div class="row">
          <button type="button" disabled={saving} on:click={() => start("describe")}>
            {described ? "Generate missing descriptions" : "Generate descriptions"}
          </button>
        </div>
        <ul class="tiles">
          {#each assets as asset}
            <li>
              <button
                type="button"
                class="tile"
                class:selected={asset.id === selectedAssetId}
                style={`background-image: url('${asset.thumb_url}')`}
                title={asset.name}
                on:click={() => toggleAsset(asset.id)}
              >
                <span class="mark-flag" class:done={asset.description}>
                  {asset.description ? "✓" : "○"}
                </span>
                {#if asset.hero}<span class="star-flag">★</span>{/if}
                <span class="tile-name">{asset.name}</span>
                <span class="tile-facts">
                  {asset.kind}{#if asset.duration} · {asset.duration.toFixed(1)}s{/if}
                </span>
              </button>
            </li>
          {/each}
        </ul>
        <p class="hint">
          ✓ has a description, ○ still needs one. Click a tile to read and fix its description on the
          right.
        </p>
      {:else if activeTab === "brief"}
        <header class="panel-head"><h2>Video brief</h2></header>
        <p class="hint">What you want the video to be, separate from what the material shows.</p>
        <label>
          Creative direction
          <textarea rows="6" bind:value={brief.direction} on:blur={saveBrief}
            placeholder="e.g. open with the watch on my wrist, keep it casual, show it gets wet and still works"></textarea>
        </label>
        <label>
          On-screen text style
          <textarea rows="3" bind:value={brief.overlay_style} on:blur={saveBrief}
            placeholder="e.g. short uppercase lines, price always visible"></textarea>
        </label>
      {:else if activeTab === "music"}
        <header class="panel-head"><h2>Music</h2></header>
        {#if musicName}
          <p class="facts-line">Track: <code>{musicName}</code></p>
        {:else}
          <p class="facts-line">This project has no music.</p>
        {/if}
        <p class="hint">
          The track is chosen when the project is created. A music library, volume mixing and ducking
          under the voice arrive in phase 5.
        </p>
      {:else}
        <header class="panel-head"><h2>Voice Clone</h2></header>
        <p class="facts-line">Not configured yet.</p>
        <p class="hint">
          Phase 3 brings this step: upload a short voice sample, confirm consent, preview the cloned
          voice, and every video can be narrated in your own voice. Nothing to configure here yet, so
          this panel stays empty on purpose.
        </p>
      {/if}
    </section>

    {#if selectedAsset}
      <aside class="detail">
        <header class="panel-head">
          <h2>Description</h2>
          <button type="button" class="close" on:click={() => (selectedAssetId = null)}>✕</button>
        </header>
        <p class="asset-title">{selectedAsset.name}</p>
        <p class="facts-line">
          {selectedAsset.kind}{#if selectedAsset.duration} · {selectedAsset.duration.toFixed(1)}s{/if}
          {#if selectedAsset.scenes > 1} · {selectedAsset.scenes} scenes{/if}
          {#if selectedAsset.hero} · ★ hero{/if}
        </p>
        <label>
          What this file shows
          <textarea
            rows="8"
            bind:value={selectedAsset.draft}
            on:blur={() => saveAsset(selectedAsset)}
            placeholder="Describe what this file shows"
          ></textarea>
        </label>
        <p class="hint">Saved when you click away. These words are what the shot matching uses.</p>
        <p class="facts-line">Used for: {usedBy(selectedAsset.id) || "not used in a shot yet"}</p>
        <a class="open" href={selectedAsset.url} target="_blank" rel="noreferrer">Open the original file</a>
      </aside>
    {/if}

    <section class="stage">
      <div class="stage-head">Preview · 9:16 {#if versionLabel}· {versionLabel}{/if}</div>
      <div class="stage-body">
        {#if currentVersion}
          <!-- svelte-ignore a11y_media_has_caption -->
          <video
            bind:this={videoEl}
            src={`/api/jobs/${id}/versions/${currentVersion}`}
            poster={posterUrl}
            on:timeupdate={(event) => (currentTime = event.target.currentTime)}
            on:loadedmetadata={() => (duration = videoEl?.duration || 0)}
            on:play={() => (playing = true)}
            on:pause={() => (playing = false)}
          ></video>
        {:else}
          <p class="empty">
            Nothing rendered yet. Check the descriptions, fill in the brief, then press Generate.
            <br />(A live composition preview arrives in phase 4.)
          </p>
        {/if}
      </div>
      <div class="transport">
        <button type="button" on:click={togglePlay} disabled={!currentVersion}>
          {playing ? "❚❚" : "▶"}
        </button>
        <input
          type="range"
          min="0"
          max={duration || total || 0}
          step="0.05"
          value={currentTime}
          on:input={seek}
          aria-label="Seek"
        />
        <span class="time">{formatTime(currentTime)} / {formatTime(duration || total)}</span>
      </div>
    </section>
  </div>

  <TimelineTracks {shots} {lines} {total} music={musicName} {currentTime} onSeek={seekTo} />

  <footer class="statusbar">
    <span class="chips">
      {#each stageChips as chip}
        <span class="chip {statusFor(chip.key)}">{chip.icon} {chip.label} {statusFor(chip.key)}</span>
      {/each}
    </span>
    <span class="spacer"></span>
    {#if note}<span class="note">{note}</span>{/if}
    <span class="hint">engine {window.location.host} · one project renders at a time</span>
  </footer>

  {#if showVersions}
    <div class="drawer">
      <header class="panel-head">
        <h2>Versions</h2>
        <button type="button" class="close" on:click={() => (showVersions = false)}>✕</button>
      </header>
      {#if versions.length}
        <ul>
          {#each versions as version}
            <li>
              <button type="button" on:click={() => pickVersion(version)}>
                <span class="vlabel">{version.label}</span>
                <span class="vfile">{version.file}</span>
                <span class="vmeta">
                  {version.resolution} · {version.created_at.slice(11, 19)} · {version.summary}
                </span>
              </button>
            </li>
          {/each}
        </ul>
        <button type="button" class="primary" on:click={reveal}>📂 Open folder</button>
      {:else}
        <p class="hint">No render yet.</p>
      {/if}
    </div>
  {/if}

  {#if showGenerate}
    <div class="modal">
      <div class="sheet">
        <h2>Generate {versions.length ? `v${versions.length + 1}` : ""}</h2>
        <p class="facts-line">Resolution 1080x1920 (9:16) · aspect presets arrive in phase 4</p>
        <p class="facts-line">
          {assets.length} material · {lines.length} script lines · {described} described
        </p>
        <p class="facts-line">Music: {musicName || "none"}</p>
        {#if described < assets.length}
          <p class="hint">
            Some material has no description yet, so matching falls back to your file order for those.
          </p>
        {/if}
        <div class="row end">
          <button type="button" on:click={() => (showGenerate = false)}>Cancel</button>
          <button type="button" class="primary" on:click={() => start("render")}>Generate</button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .workspace {
    position: relative;
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    border: 1px solid #2a323d;
    border-radius: 12px;
    overflow: hidden;
    background: #0f1319;
  }
  .topbar {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background: #141922;
    border-bottom: 1px solid #2a323d;
    font-size: 13px;
  }
  .mark {
    font-weight: 800;
  }
  .project {
    font-weight: 600;
  }
  .spacer {
    flex: 1;
  }
  .badge {
    font-size: 11px;
    padding: 2px 9px;
    border-radius: 999px;
    background: #2a323d;
  }
  .badge.done {
    background: #2f9e6e;
  }
  .badge.failed {
    background: #c0392b;
  }
  .badge.running,
  .badge.queued {
    background: #f5b52e;
    color: #14181f;
  }
  button {
    background: #1a2028;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 12px;
    cursor: pointer;
  }
  button.primary {
    background: linear-gradient(180deg, #ffc94d, #f5a813);
    color: #14181f;
    border: none;
    font-weight: 700;
  }
  button:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .banner {
    flex: 0 0 auto;
    margin: 0;
    padding: 8px 12px;
    background: #3a1f22;
    color: #ffb4b4;
    font-size: 12px;
  }
  .middle {
    flex: 1 1 auto;
    display: grid;
    grid-template-columns: 74px minmax(230px, 330px) minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr);
    min-height: 0;
  }
  .middle.with-detail {
    grid-template-columns: 74px minmax(220px, 310px) minmax(210px, 260px) minmax(0, 1fr);
  }
  .rail {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 4px;
    background: #12161d;
    border-right: 1px solid #232a34;
    overflow-y: auto;
  }
  .rail button {
    display: grid;
    justify-items: center;
    gap: 3px;
    padding: 10px 2px;
    border: none;
    background: transparent;
    color: #8e9aa8;
    font-size: 10px;
    line-height: 1.2;
    text-align: center;
  }
  .rail button.active {
    background: #1b232e;
    color: #f5b52e;
    border-radius: 8px;
  }
  .rail .icon {
    font-size: 15px;
  }
  .panel,
  .detail {
    padding: 12px;
    background: #131820;
    border-right: 1px solid #232a34;
    overflow-y: auto;
  }
  .detail {
    border-left: 1px solid #232a34;
    border-right: none;
  }
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
  }
  .panel-head h2 {
    margin: 0;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #b7c2cf;
  }
  .count {
    font-size: 11px;
    color: #8e9aa8;
  }
  .close {
    padding: 2px 8px;
  }
  .hint {
    margin: 0 0 10px;
    color: #8e9aa8;
    font-size: 12px;
    line-height: 1.45;
  }
  .row {
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
  }
  .row.end {
    justify-content: flex-end;
  }
  .panel label,
  .detail label {
    display: grid;
    gap: 4px;
    margin-bottom: 10px;
    font-size: 11px;
    color: #b7c2cf;
  }
  textarea {
    background: #0e1116;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 6px;
    padding: 8px;
    font: inherit;
    font-size: 12px;
    resize: vertical;
  }
  textarea:focus {
    outline: none;
    border-color: #f5b52e;
  }
  .tiles {
    list-style: none;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(84px, 1fr));
    gap: 8px;
    margin: 0 0 10px;
    padding: 0;
  }
  .tile {
    position: relative;
    display: block;
    width: 100%;
    aspect-ratio: 1 / 1;
    padding: 0;
    border: 1px solid #2a323d;
    border-radius: 8px;
    background-color: #0e1116;
    background-size: cover;
    background-position: center;
    overflow: hidden;
    text-align: left;
  }
  .tile.selected {
    border-color: #f5b52e;
    box-shadow: 0 0 0 1px #f5b52e inset;
  }
  .mark-flag,
  .star-flag {
    position: absolute;
    top: 4px;
    font-size: 10px;
    line-height: 1;
    padding: 2px 5px;
    border-radius: 999px;
    background: rgba(8, 10, 14, 0.8);
  }
  .mark-flag {
    left: 4px;
    color: #8e9aa8;
  }
  .mark-flag.done {
    color: #7fd4c1;
  }
  .star-flag {
    right: 4px;
    color: #f5b52e;
  }
  .tile-name,
  .tile-facts {
    position: absolute;
    left: 0;
    right: 0;
    padding: 2px 6px;
    background: rgba(8, 10, 14, 0.78);
    font-size: 10px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tile-name {
    bottom: 15px;
  }
  .tile-facts {
    bottom: 0;
    color: #8e9aa8;
  }
  .asset-title {
    margin: 0 0 4px;
    font-size: 12px;
    font-weight: 700;
    word-break: break-all;
  }
  .facts-line {
    margin: 0 0 8px;
    color: #8e9aa8;
    font-size: 11px;
  }
  code {
    color: #e8ecf1;
  }
  .open {
    color: #7fd4c1;
    font-size: 11px;
  }
  .stage {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
    background: #0b0e13;
    min-width: 0;
  }
  .stage-head {
    padding: 6px 10px;
    border-bottom: 1px solid #1c222b;
    color: #8e9aa8;
    font-size: 11px;
  }
  .stage-body {
    position: relative;
    min-height: 0;
    overflow: hidden;
    margin: 10px;
  }
  .stage-body video {
    position: absolute;
    inset: 0;
    margin: auto;
    max-width: 100%;
    max-height: 100%;
    border-radius: 8px;
    background: #000;
  }
  .empty {
    color: #6b7684;
    font-size: 12px;
    text-align: center;
    line-height: 1.6;
    margin: 0;
  }
  .transport {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    border-top: 1px solid #1c222b;
  }
  .transport input[type="range"] {
    flex: 1;
    accent-color: #f5b52e;
  }
  .time {
    color: #8e9aa8;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .statusbar {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    background: #12161d;
    border-top: 1px solid #2a323d;
    font-size: 11px;
  }
  .chips {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .chip {
    padding: 2px 8px;
    border: 1px solid #2a323d;
    border-radius: 999px;
    color: #8e9aa8;
  }
  .chip.done {
    border-color: #2f9e6e;
    color: #7fd4c1;
  }
  .chip.running {
    border-color: #f5b52e;
    color: #f5b52e;
  }
  .chip.failed {
    border-color: #c0392b;
    color: #ffb4b4;
  }
  .note {
    color: #7fd4c1;
    font-size: 11px;
  }
  .drawer {
    position: absolute;
    top: 40px;
    right: 0;
    bottom: 34px;
    width: min(420px, 80%);
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 8px;
    padding: 12px;
    background: #141922;
    border-left: 1px solid #2a323d;
    box-shadow: -12px 0 30px rgba(0, 0, 0, 0.45);
    overflow-y: auto;
  }
  .drawer ul {
    list-style: none;
    display: grid;
    gap: 6px;
    margin: 0;
    padding: 0;
  }
  .drawer li button {
    width: 100%;
    display: grid;
    gap: 2px;
    text-align: left;
    background: #0f141b;
  }
  .vlabel {
    font-weight: 700;
    font-size: 12px;
  }
  .vfile {
    font-size: 11px;
    word-break: break-all;
  }
  .vmeta {
    color: #8e9aa8;
    font-size: 10px;
  }
  .modal {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(6, 8, 12, 0.72);
  }
  .sheet {
    display: grid;
    gap: 8px;
    width: min(460px, 88%);
    padding: 16px;
    background: #141922;
    border: 1px solid #2a323d;
    border-radius: 12px;
  }
  .sheet h2 {
    margin: 0;
    font-size: 15px;
  }
</style>
