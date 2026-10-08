<script>
  import { onDestroy } from "svelte";

  export let id;

  let job = null;
  let state = null;
  let assets = [];
  let versions = [];
  let videoUrl = null;
  let posterUrl = null;
  let selectedVersion = null;
  let rows = [];
  let brief = { direction: "", overlay_style: "" };
  let error = "";
  let note = "";
  let saving = false;
  let dirty = false;
  let askedDescribe = false;
  let source = null;

  const stages = [
    { key: "describe", label: "Deskripsi aset", icon: "🔍" },
    { key: "script", label: "Script", icon: "📝" },
    { key: "visual", label: "Shot plan", icon: "🖼️" },
    { key: "compose", label: "Render", icon: "🎬" },
    { key: "qa", label: "QA", icon: "✅" },
  ];

  const busyStatus = ["queued", "running"];

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

  function buildRows(lines, shots) {
    const byLine = {};
    for (const shot of shots) byLine[shot.line] = shot;
    return lines.map((line) => {
      const shot = byLine[line.id] || {};
      const overlay =
        shot.overlay !== null && shot.overlay !== undefined ? shot.overlay : line.overlay || "";
      return {
        line: line.id,
        section: line.section,
        text: line.text,
        hint: line.hint,
        asset: shot.asset || (assets[0] ? assets[0].id : ""),
        overlay,
        locked: Boolean(shot.locked),
        mode: shot.mode || "",
        sourceStart: shot.source_start,
        original: {
          asset: shot.asset || (assets[0] ? assets[0].id : ""),
          overlay,
          locked: Boolean(shot.locked),
        },
      };
    });
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
      videoUrl = data.video_url;
      posterUrl = data.poster_url;
      brief = { ...data.state.brief };
      rows = buildRows(data.state.timeline.lines || [], data.state.shotlist.shots || []);
      dirty = false;
      maybeDescribe();
    } catch (err) {
      error = err.message;
    }
  }

  function maybeDescribe() {
    const undescribed = assets.filter((asset) => !asset.description).length;
    if (askedDescribe || !assets.length || !undescribed || busyStatus.includes(job.status)) return;
    askedDescribe = true;
    start("describe");
  }

  async function start(kind) {
    saving = true;
    error = "";
    note = "";
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
          : "Rendering: script, shot plan, composition, QA. One project renders at a time.";
      await load();
      openStream();
    } catch (err) {
      error = err.message;
      askedDescribe = false;
    } finally {
      saving = false;
    }
  }

  function markDirty() {
    dirty = true;
    note = "";
  }

  function changedRows() {
    return rows.filter(
      (row) =>
        row.asset !== row.original.asset ||
        row.overlay !== row.original.overlay ||
        row.locked !== row.original.locked,
    );
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
      note = `Saved the description of ${asset.id}. It is used the next time you generate.`;
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

  async function saveStoryboard() {
    const edits = changedRows().map((row) => ({
      line: row.line,
      asset: row.asset,
      overlay: row.overlay,
      locked: row.locked,
    }));
    if (!edits.length) return;
    saving = true;
    error = "";
    try {
      const response = await fetch(`/api/jobs/${id}/shotlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edits }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Request failed (${response.status})`);
      }
      note = "Saved. The next generate uses this storyboard.";
      dirty = false;
      await load();
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  }

  async function rebuildShots() {
    saving = true;
    error = "";
    note = "";
    try {
      const response = await fetch(`/api/jobs/${id}/shotlist/auto`, { method: "POST" });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      note = "Shots replaced from the current descriptions; locked lines stayed.";
      await load();
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
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

  function statusFor(stage) {
    const entry = state?.stages?.[stage];
    return entry ? entry.status : "pending";
  }

  function assetById(assetId) {
    return assets.find((asset) => asset.id === assetId) || null;
  }

  function usedAssetIds() {
    return new Set((state?.shotlist?.shots || []).map((shot) => shot.asset));
  }

  function shotMeta(row) {
    if (row.mode === "photo") return "still image, slow zoom";
    if (row.mode === "freeze") return "clip held on its last frame";
    if (row.mode === "trim") return `clip from ${row.sourceStart}s`;
    return row.mode;
  }

  function pickVersion(version) {
    selectedVersion = version.number;
    videoUrl = `${version.url}?v=${encodeURIComponent(version.created_at)}`;
    posterUrl = null;
  }

  function describedCount() {
    return assets.filter((asset) => asset.description).length;
  }

  load();
  openStream();
  onDestroy(closeStream);
</script>

<section>
  {#if error}
    <p class="error">{error}</p>
  {/if}

  {#if job}
    <h2>{job.title}</h2>
    <p>
      <span class="badge {job.status}">{job.status}</span>
      {#if job.error}<span class="error">{job.error}</span>{/if}
    </p>

    <ol class="steps">
      {#each stages as stage}
        <li class="step {statusFor(stage.key)}">
          <span class="icon">{stage.icon}</span>
          <span class="label">{stage.label}</span>
          <span class="state">{statusFor(stage.key)}</span>
        </li>
      {/each}
    </ol>

    {#if assets.length}
      <h3>1 · Material and what the model saw</h3>
      <p class="hint">
        The vision model wrote one line per file. Correct anything it got wrong: these descriptions
        decide which material covers which line. {describedCount()} of {assets.length} described.
      </p>
      <div class="material-actions">
        <button type="button" disabled={saving} on:click={() => start("describe")}>
          {describedCount() ? "Describe the rest" : "Describe the material"}
        </button>
      </div>
      <ul class="assets">
        {#each assets as asset}
          <li class:unused={!usedAssetIds().has(asset.id)}>
            <a href={asset.url} target="_blank" rel="noreferrer">
              <img src={asset.thumb_url} alt={asset.name} />
            </a>
            <div class="asset-meta">
              <span class="asset-name" title={asset.name}>{asset.name}</span>
              <span class="asset-facts">
                {asset.kind}
                {#if asset.duration}
                  - {asset.duration.toFixed(1)}s
                {/if}
                {#if asset.scenes > 1}
                  - {asset.scenes} scenes
                {/if}
                {#if asset.hero}
                  - hero
                {/if}
              </span>
              <textarea
                class="description-input"
                rows="3"
                bind:value={asset.draft}
                placeholder="Describe what this file shows"
                on:blur={() => saveAsset(asset)}
              ></textarea>
            </div>
            {#if !usedAssetIds().has(asset.id)}
              <span class="flag">unused</span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    <h3>2 · Video brief</h3>
    <p class="hint">
      What you want the video to be, separate from what the material shows. The script and the
      on-screen text follow this.
    </p>
    <div class="brief">
      <label>
        Creative direction
        <textarea
          rows="3"
          bind:value={brief.direction}
          on:blur={saveBrief}
          placeholder="e.g. open with the watch on my wrist, keep it casual, show it gets wet and still works"
        ></textarea>
      </label>
      <label>
        On-screen text style
        <textarea
          rows="2"
          bind:value={brief.overlay_style}
          on:blur={saveBrief}
          placeholder="e.g. short uppercase lines, price always visible, no emoji"
        ></textarea>
      </label>
    </div>

    <h3>3 · Generate</h3>
    <div class="generate">
      <button
        type="button"
        class="primary"
        disabled={saving || busyStatus.includes(job.status)}
        on:click={() => start("render")}
      >
        {busyStatus.includes(job.status)
          ? "Working..."
          : versions.length
            ? `Generate version ${versions.length + 1}`
            : "Generate video"}
      </button>
      <span class="hint">One project renders at a time; a second project waits its turn.</span>
    </div>
    {#if note}<p class="note">{note}</p>{/if}

    {#if rows.length}
      <h3>Storyboard</h3>
      <p class="hint">
        Each script line plays one shot. Swap the material, edit the on-screen text, or lock a line
        so the next generate keeps it. Saving only stores the plan: press generate for a new version.
        {#if state.shotlist && state.shotlist.matched_by === "model"}
          Shots were placed by the model from the descriptions.
        {:else if state.shotlist && state.shotlist.matched_by === "manual"}
          Shots follow your storyboard edits.
        {:else}
          Shots follow your file order.
        {/if}
      </p>
      {#if state.shotlist && state.shotlist.notes}
        <p class="note">{state.shotlist.notes}</p>
      {/if}
      <div class="board">
        {#each rows as row}
          <div class="shot" class:locked={row.locked}>
            <div class="shot-thumb">
              {#if assetById(row.asset)}
                <img src={assetById(row.asset).thumb_url} alt={row.asset} />
              {/if}
              <span class="line-id">{row.line}</span>
            </div>
            <div class="shot-body">
              <p class="shot-text">{row.text}</p>
              <p class="shot-meta">
                <span class="section">{row.section}</span>
                {#if row.hint}<span class="hint-text">{row.hint}</span>{/if}
                <span class="mode">{shotMeta(row)}</span>
              </p>
              <div class="shot-controls">
                <select bind:value={row.asset} on:change={markDirty}>
                  {#each assets as asset}
                    <option value={asset.id}>{asset.id} - {asset.name}</option>
                  {/each}
                </select>
                <input
                  class="overlay-input"
                  bind:value={row.overlay}
                  on:input={markDirty}
                  placeholder="text on screen (empty hides it)"
                />
                <button
                  type="button"
                  class="lock"
                  class:on={row.locked}
                  on:click={() => {
                    row.locked = !row.locked;
                    markDirty();
                  }}
                >
                  {row.locked ? "locked" : "lock"}
                </button>
              </div>
            </div>
          </div>
        {/each}
      </div>
      <div class="board-actions">
        <button
          type="button"
          disabled={saving || !dirty || busyStatus.includes(job.status)}
          on:click={saveStoryboard}
        >
          Save storyboard ({changedRows().length})
        </button>
        <button type="button" disabled={saving || busyStatus.includes(job.status)} on:click={rebuildShots}>
          Rebuild shots from the descriptions
        </button>
      </div>
    {/if}

    <h3>Result</h3>
    {#if versions.length}
      <ul class="versions">
        {#each versions as version}
          <li class:active={selectedVersion === version.number}>
            <button type="button" on:click={() => pickVersion(version)}>
              <span class="version-label">{version.label}</span>
              <span class="version-file">{version.file}</span>
              <span class="version-meta">
                {version.resolution} - {version.created_at.slice(0, 19).replace("T", " ")}
              </span>
              <span class="version-meta">{version.summary}</span>
            </button>
          </li>
        {/each}
      </ul>
      <div class="result-actions">
        <button type="button" on:click={reveal}>📂 Open folder</button>
      </div>
    {:else}
      <p class="hint">No render yet. Generate a video and it shows up here as v1.</p>
    {/if}

    <div class="preview">
      {#if videoUrl}
        <!-- svelte-ignore a11y_media_has_caption -->
        <video controls src={videoUrl} poster={posterUrl}></video>
      {:else}
        <p class="hint">The rendered video appears here.</p>
      {/if}
    </div>
  {:else if !error}
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
  h3 {
    font-size: 14px;
    margin: 22px 0 8px;
    color: #b7c2cf;
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
  .badge.running,
  .badge.queued {
    background: #f5b52e;
    color: #14181f;
  }
  .steps {
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0;
    padding: 0;
  }
  .step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border: 1px solid #2a323d;
    border-radius: 999px;
    font-size: 12px;
    color: #93a1b3;
  }
  .step.done {
    border-color: #2f9e6e;
    color: #7fd4c1;
  }
  .step.running {
    border-color: #f5b52e;
    color: #f5b52e;
  }
  .step.failed {
    border-color: #c0392b;
    color: #ff8f8f;
  }
  .step .state {
    font-size: 11px;
    opacity: 0.8;
  }
  .material-actions,
  .generate,
  .result-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }
  button {
    background: #1a2028;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 8px;
    padding: 9px 14px;
    font-size: 13px;
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
  .assets {
    list-style: none;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
    margin: 0;
    padding: 0;
  }
  .assets li {
    position: relative;
    border: 1px solid #2a323d;
    border-radius: 10px;
    overflow: hidden;
    background: #0e1116;
  }
  .assets li.unused {
    opacity: 0.7;
  }
  .assets img {
    display: block;
    width: 100%;
    aspect-ratio: 3 / 4;
    object-fit: cover;
  }
  .asset-meta {
    display: grid;
    gap: 4px;
    padding: 6px 8px;
    font-size: 11px;
  }
  .asset-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .asset-facts {
    color: #93a1b3;
  }
  .description-input {
    background: #131820;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 6px;
    padding: 6px;
    font: inherit;
    font-size: 11px;
    resize: vertical;
  }
  .description-input:focus {
    outline: none;
    border-color: #f5b52e;
  }
  .flag {
    position: absolute;
    top: 6px;
    right: 6px;
    padding: 1px 6px;
    border-radius: 999px;
    background: rgba(8, 10, 14, 0.8);
    color: #ff8f8f;
    font-size: 10px;
    text-transform: uppercase;
  }
  .brief {
    display: grid;
    gap: 10px;
  }
  .brief label {
    display: grid;
    gap: 6px;
    font-size: 12px;
    color: #b7c2cf;
  }
  .brief textarea {
    background: #0e1116;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 8px;
    padding: 10px;
    font: inherit;
    font-size: 13px;
    resize: vertical;
  }
  .brief textarea:focus {
    outline: none;
    border-color: #f5b52e;
  }
  .board {
    display: grid;
    gap: 8px;
  }
  .board-actions {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }
  .shot {
    display: grid;
    grid-template-columns: 76px 1fr;
    gap: 10px;
    padding: 8px;
    border: 1px solid #2a323d;
    border-radius: 10px;
    background: #0e1116;
  }
  .shot.locked {
    border-color: #2f9e6e;
  }
  .shot-thumb {
    position: relative;
  }
  .shot-thumb img {
    display: block;
    width: 100%;
    aspect-ratio: 3 / 4;
    object-fit: cover;
    border-radius: 6px;
  }
  .line-id {
    position: absolute;
    bottom: 4px;
    left: 4px;
    padding: 1px 5px;
    border-radius: 999px;
    background: rgba(8, 10, 14, 0.8);
    font-size: 10px;
  }
  .shot-body {
    display: grid;
    gap: 6px;
    align-content: start;
  }
  .shot-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.35;
  }
  .shot-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0;
    font-size: 11px;
    color: #93a1b3;
  }
  .shot-meta .section {
    color: #7fd4c1;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .shot-controls {
    display: grid;
    grid-template-columns: 1fr 1.2fr auto;
    gap: 6px;
  }
  select,
  .overlay-input {
    background: #131820;
    color: #e8ecf1;
    border: 1px solid #2a323d;
    border-radius: 6px;
    padding: 6px 8px;
    font: inherit;
    font-size: 12px;
    min-width: 0;
  }
  select:focus,
  .overlay-input:focus {
    outline: none;
    border-color: #f5b52e;
  }
  .lock {
    background: #131820;
    color: #93a1b3;
    border: 1px solid #2a323d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
  }
  .lock.on {
    border-color: #2f9e6e;
    color: #7fd4c1;
  }
  .versions {
    list-style: none;
    display: grid;
    gap: 6px;
    margin: 0 0 10px;
    padding: 0;
  }
  .versions button {
    width: 100%;
    display: grid;
    gap: 2px;
    text-align: left;
    background: #0e1116;
  }
  .versions li.active button {
    border-color: #f5b52e;
  }
  .version-label {
    font-weight: 700;
    font-size: 13px;
  }
  .version-file {
    color: #e8ecf1;
    font-size: 12px;
    word-break: break-all;
  }
  .version-meta {
    color: #93a1b3;
    font-size: 11px;
  }
  .preview {
    margin-top: 16px;
  }
  video {
    width: 100%;
    border-radius: 8px;
    background: #0e1116;
    max-height: 70vh;
  }
  .hint {
    color: #93a1b3;
    font-size: 13px;
  }
  .note {
    color: #7fd4c1;
    font-size: 13px;
    margin: 4px 0 0;
  }
  .error {
    color: #ff8f8f;
    font-size: 13px;
  }
</style>
