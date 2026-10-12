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
  let style = { shape: "ulasan", beats: [], tone: "bersih", accent: null, energy: "normal", badge: "pill" };
  let catalog = null;
  let styleNote = "";
  let beatDraft = [];
  let drafting = false;
  let activeTab = "media";
  let selectedAssetId = null;
  let showVersions = false;
  let showGenerate = false;
  let error = "";
  let note = "";
  let saving = false;
  let askedDescribe = false;
  let drafts = {};
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
    { key: "style", icon: "◐", label: "Style" },
    { key: "music", icon: "♪", label: "Music" },
    { key: "voice", icon: "◍", label: "Voice Clone" },
  ];

  const briefExamples = [
    {
      label: "Daily review",
      direction:
        "buka dengan produknya langsung dipakai, santai seperti cerita ke teman, tunjukkan satu hal yang paling terasa bedanya",
      overlay_style: "harga selalu tampil, sebut satu keunggulan saja",
    },
    {
      label: "Quick unboxing",
      direction:
        "mulai dari paket dibuka, sorot isinya satu per satu singkat, tutup dengan produknya dipakai sekali",
      overlay_style: "nama produk dan harganya muncul di awal",
    },
    {
      label: "Before vs after",
      direction:
        "bandingkan yang lama dengan yang baru: masalah dulu, lalu produknya dipakai dan hasilnya kelihatan",
      overlay_style: "tekankan bedanya, jangan ulang angka harga",
    },
    {
      label: "Durability test",
      direction:
        "buka dengan pertanyaan menantang, lalu uji produknya di kamera (air, jatuh, dipakai seharian) dan tunjukkan hasilnya apa adanya",
      overlay_style: "tulis hasil ujinya, bukan klaim",
    },
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
  $: chipStates = stageChips.map((chip) => ({
    ...chip,
    status: state?.stages?.[chip.key]?.status || "pending",
  }));
  $: selectedUsage = selectedAsset ? selectedAssetUsage(selectedAsset.id) : "";
  $: shapeLabel =
    style.shape === "custom"
      ? "Custom"
      : (catalog?.shapes?.find((item) => item.id === style.shape)?.label ?? "Ulasan");
  $: toneLabel = catalog?.tones?.find((item) => item.id === style.tone)?.label ?? "Bersih";
  $: beatList = style.shape === "custom" ? style.beats : (catalog?.shapes?.find((item) => item.id === style.shape)?.beats ?? []);
  $: estimate = estimateSeconds(style.shape === "custom" ? beatDraft : beatList);
  $: extras = (catalog?.beats ?? []).filter((beat) => !beatDraft.includes(beat.id) || !beat.once_only);

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
        if (message.status === "done") load();
      }
      if (message.type === "done") {
        closeStream();
        note = "";
        load();
      }
    };
    source.onerror = () => {
      closeStream();
      load();
    };
  }

  function draftFor(asset) {
    return asset.id in drafts ? drafts[asset.id] : asset.description || "";
  }

  function rememberDraft(asset) {
    drafts = { ...drafts, [asset.id]: asset.draft };
  }

  function buildShots(shotlist) {
    const overlays = {};
    for (const line of lines) overlays[line.id] = line.overlay || line.section;
    return (shotlist || []).map((shot) => ({
      ...shot,
      thumb: `/api/jobs/${id}/assets/${shot.asset}/thumb`,
      overlayText: overlays[shot.line] || "",
    }));
  }

  function selectedAssetUsage(assetId) {
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
      assets = data.assets.map((asset) => ({ ...asset, draft: draftFor(asset) }));
      versions = data.versions || [];
      lines = data.state.timeline.lines || [];
      shots = buildShots(data.state.shotlist.shots);
      brief = { ...data.state.brief };
      style = { ...data.state.style };
      catalog = data.style_catalog || null;
      beatDraft = [...(style.beats?.length ? style.beats : beatList)];
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
      drafts = { ...drafts, [asset.id]: data.description || "" };
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

  function applyExample(example) {
    brief = { direction: example.direction, overlay_style: example.overlay_style };
    saveBrief();
    note = `Example "${example.label}" filled in. Edit it, then click away to save.`;
  }

  async function draftBrief() {
    drafting = true;
    error = "";
    note = "";
    try {
      const response = await fetch(`/api/jobs/${id}/brief/draft`, { method: "POST" });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Request failed (${response.status})`);
      }
      const draft = await response.json();
      brief = { direction: draft.direction, overlay_style: draft.overlay_style };
      await saveBrief();
      note = "Draft written from the product and the material. Edit it before generating.";
    } catch (err) {
      error = err.message;
    } finally {
      drafting = false;
    }
  }

  function estimateSeconds(list) {
    // The same arithmetic the engine's reading spine uses, so the number shown is the number you get.
    let total = 0;
    list.forEach((beatId, index) => {
      const spec = catalog?.beats?.find((beat) => beat.id === beatId);
      const words = Math.min(spec?.max_words ?? 14, 12);
      const floor = beatId === "hook" ? 2.6 : 1.8;
      total += Math.max(floor, words / 2.7) + (index < list.length - 1 ? 0.35 : 0);
    });
    return Math.max(0, Math.round(total));
  }

  async function saveStyle(changes) {
    error = "";
    styleNote = "";
    try {
      const response = await fetch(`/api/jobs/${id}/style`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Request failed (${response.status})`);
      }
      const data = await response.json();
      style = { ...data.style };
      styleNote = !data.script_exists
        ? "Saved. No script exists yet, so the first generate writes everything."
        : data.script_rewrites
          ? "Saved. The next generate writes a new script with this beat order."
          : "Saved. The script is kept; the next generate only renders again.";
      if (!(style.beats?.length)) beatDraft = [...beatList];
    } catch (err) {
      error = err.message;
    }
  }

  function pickShape(shapeId) {
    saveStyle({ shape: shapeId, beats: [] });
    beatDraft = [...(catalog?.shapes?.find((item) => item.id === shapeId)?.beats ?? [])];
  }

  function addBeat(beatId) {
    if (!beatId) return;
    beatDraft = [...beatDraft, beatId];
  }

  function removeBeat(index) {
    beatDraft = beatDraft.filter((_, position) => position !== index);
  }

  function moveBeat(index, delta) {
    const next = [...beatDraft];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    beatDraft = next;
  }

  function saveBeats() {
    saveStyle({ shape: "custom", beats: beatDraft });
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
        <p class="role-line">
          <strong>Content.</strong> What you want this video to say. The look and the beat order live
          in <button type="button" class="linkish" on:click={() => (activeTab = "style")}>Style</button>.
        </p>
        <div class="row wrap">
          <button type="button" disabled={drafting} on:click={draftBrief}>
            {drafting ? "Menyusun draf..." : "Draft from product and material"}
          </button>
        </div>
        <p class="hint">Or start from an example (you can edit everything after):</p>
        <div class="row wrap">
          {#each briefExamples as example}
            <button type="button" class="chip-button" on:click={() => applyExample(example)}>
              {example.label}
            </button>
          {/each}
        </div>
        <label>
          What should this video say?
          <textarea rows="5" bind:value={brief.direction} on:blur={saveBrief}
            placeholder="Arahannya, misalnya: buka dengan jam di pergelangan tangan, santai, tunjukkan jam kena air tetap jalan"></textarea>
        </label>
        <label>
          Facts that must appear on screen
          <textarea rows="3" bind:value={brief.overlay_style} on:blur={saveBrief}
            placeholder="Isi teksnya, misalnya: harga selalu tampil, sebut ketahanan air"></textarea>
        </label>
        <p class="hint">
          Saving the brief never renders. The words change the script; the size, the colour and the
          badge shape come from Style.
        </p>
      {:else if activeTab === "style"}
        <header class="panel-head"><h2>Style</h2></header>
        <p class="role-line">
          <strong>Form.</strong> The order of the beats and how the video looks. Changing the beat
          order writes a new script; changing the tone only re-renders.
        </p>
        {#if catalog}
          <p class="label-line">Beat order</p>
          <div class="row wrap">
            {#each catalog.shapes as preset}
              <button
                type="button"
                class="chip-button"
                class:active={style.shape === preset.id}
                on:click={() => pickShape(preset.id)}
                title={preset.character}
              >
                {preset.label}
              </button>
            {/each}
            <button
              type="button"
              class="chip-button"
              class:active={style.shape === "custom"}
              on:click={() => (beatDraft = [...beatList], saveBeats())}
            >
              Custom
            </button>
          </div>
          <ol class="beats">
            {#each (style.shape === "custom" ? beatDraft : beatList) as beatId, index}
              <li>
                <span class="beat-label">
                  {catalog.beats.find((beat) => beat.id === beatId)?.label ?? beatId}
                </span>
                {#if beatId === "hook" || beatId === "cta"}
                  <span class="beat-flag">required</span>
                {/if}
              </li>
            {/each}
          </ol>
          <p class="hint">
            Roughly {estimate} seconds. Every beat needs reading time, so more beats means a longer
            video.
          </p>
          <details class="editor">
            <summary>Build your own order</summary>
            <p class="hint">
              Pick beats from the library, put them in order, then save. The hook stays first and the
              CTA stays last; {catalog.min_beats} to {catalog.max_beats} beats.
            </p>
            <ol class="beats editable">
              {#each beatDraft as beatId, index}
                <li>
                  <span class="beat-label">
                    {catalog.beats.find((beat) => beat.id === beatId)?.label ?? beatId}
                  </span>
                  <span class="beat-tools">
                    <button type="button" on:click={() => moveBeat(index, -1)} disabled={index === 0}>↑</button>
                    <button type="button" on:click={() => moveBeat(index, 1)} disabled={index === beatDraft.length - 1}>↓</button>
                    <button type="button" on:click={() => removeBeat(index)} disabled={beatId === "hook" || beatId === "cta"}>✕</button>
                  </span>
                </li>
              {/each}
            </ol>
            <p class="hint">Add a beat:</p>
            <div class="row wrap">
              {#each catalog.beats as beat}
                <button
                  type="button"
                  class="chip-button"
                  on:click={() => addBeat(beat.id)}
                  disabled={beat.once_only && beatDraft.includes(beat.id)}
                >
                  + {beat.label}
                </button>
              {/each}
            </div>
            <div class="row">
              <button type="button" on:click={saveBeats}>Save this order</button>
            </div>
          </details>

          <p class="label-line">Tone</p>
          <ul class="tones">
            {#each catalog.tones as tone}
              <li>
                <button
                  type="button"
                  class="tone"
                  class:active={style.tone === tone.id}
                  on:click={() => saveStyle({ tone: tone.id })}
                >
                  <span
                    class="tone-swatch"
                    style={`background: ${tone.preview.bg}; border-color: ${tone.preview.accent}`}
                  >
                    <span class="tone-dot" style={`background: ${tone.preview.accent}`}></span>
                    <span class="tone-ink" style={`color: ${tone.preview.ink}`}>Aa</span>
                  </span>
                  <span class="tone-name">{tone.label}</span>
                  <span class="tone-character">{tone.character}</span>
                </button>
              </li>
            {/each}
          </ul>

          <p class="label-line">Overrides</p>
          <p class="hint">Only these three, and only if you want to differ from the tone.</p>
          <p class="facts-line">
            Accent colour
            <span class="swatches">
              <button type="button" class="swatch default" class:active={!style.accent} on:click={() => saveStyle({ accent: null })} title="Tone default"></button>
              {#each ["#f5b52e", "#ff4d2e", "#ffd400", "#38d9a9", "#4dabf7", "#e599f7", "#ff8fab", "#ffffff"] as color}
                <button
                  type="button"
                  class="swatch"
                  class:active={style.accent === color}
                  style={`background: ${color}`}
                  on:click={() => saveStyle({ accent: color })}
                  title={color}
                ></button>
              {/each}
            </span>
          </p>
          <p class="facts-line">
            Motion
            <span class="row">
              {#each catalog.energies as option}
                <button type="button" class="chip-button" class:active={style.energy === option} on:click={() => saveStyle({ energy: option })}>
                  {option}
                </button>
              {/each}
            </span>
          </p>
          <p class="facts-line">
            Label badge
            <span class="row">
              {#each catalog.badges as option}
                <button type="button" class="chip-button" class:active={style.badge === option} on:click={() => saveStyle({ badge: option })}>
                  {option === "pill" ? "filled pill" : option === "underline" ? "underline" : "plain text"}
                </button>
              {/each}
            </span>
          </p>
          {#if styleNote}<p class="hint">{styleNote}</p>{/if}
        {/if}
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
            on:input={() => rememberDraft(selectedAsset)}
            on:blur={() => saveAsset(selectedAsset)}
            placeholder="Describe what this file shows"
          ></textarea>
        </label>
        <p class="hint">Saved when you click away. These words are what the shot matching uses.</p>
        <p class="facts-line">Used for: {selectedUsage || "not used in a shot yet"}</p>
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

  <TimelineTracks {shots} {total} music={musicName} {currentTime} onSeek={seekTo} />

  <footer class="statusbar">
    <span class="chips">
      {#each chipStates as chip}
        <span class="chip {chip.status}">{chip.icon} {chip.label} {chip.status}</span>
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
        <p class="facts-line">Shape: {shapeLabel} · Tone: {toneLabel}</p>
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
  .row.wrap {
    flex-wrap: wrap;
  }
  .row.end {
    justify-content: flex-end;
  }
  .role-line {
    margin: 0 0 12px;
    color: #b7c2cf;
    font-size: 12px;
    line-height: 1.5;
  }
  .label-line {
    margin: 14px 0 6px;
    color: #8e9aa8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .linkish {
    background: none;
    border: 0;
    padding: 0;
    color: #f5b52e;
    font: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
  .chip-button {
    padding: 6px 12px;
    font-size: 12px;
  }
  .chip-button.active {
    border-color: #f5b52e;
    color: #f5b52e;
  }
  .beats {
    list-style: none;
    margin: 8px 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .beats li {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border: 1px solid #2a323d;
    border-radius: 8px;
    background: #12161c;
    font-size: 12px;
  }
  .beats.editable li {
    width: 100%;
    justify-content: space-between;
  }
  .beat-flag {
    color: #8e9aa8;
    font-size: 10px;
  }
  .beat-tools {
    display: flex;
    gap: 4px;
  }
  .beat-tools button {
    padding: 2px 7px;
  }
  .editor {
    margin: 10px 0;
    border: 1px solid #232a34;
    border-radius: 10px;
    padding: 10px 12px;
    background: #0f1318;
  }
  .editor summary {
    cursor: pointer;
    font-size: 12px;
    color: #cfd8e3;
  }
  .tones {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }
  .tone {
    display: grid;
    grid-template-columns: auto 1fr;
    grid-template-areas: "swatch name" "swatch character";
    gap: 2px 12px;
    align-items: center;
    width: 100%;
    text-align: left;
    padding: 10px 12px;
  }
  .tone.active {
    border-color: #f5b52e;
  }
  .tone-swatch {
    grid-area: swatch;
    display: grid;
    place-items: center;
    gap: 2px;
    width: 52px;
    height: 52px;
    border: 2px solid;
    border-radius: 10px;
  }
  .tone-dot {
    width: 18px;
    height: 6px;
    border-radius: 3px;
  }
  .tone-ink {
    font-size: 14px;
    font-weight: 700;
  }
  .tone-name {
    grid-area: name;
    font-size: 13px;
    color: #e8ecf1;
  }
  .tone-character {
    grid-area: character;
    font-size: 11px;
    color: #8e9aa8;
    line-height: 1.4;
  }
  .swatches {
    display: flex;
    gap: 5px;
    margin-left: 6px;
    vertical-align: middle;
  }
  .swatch {
    width: 20px;
    height: 20px;
    padding: 0;
    border-radius: 999px;
    border: 2px solid #2a323d;
  }
  .swatch.active {
    border-color: #f5b52e;
  }
  .swatch.default {
    background: linear-gradient(135deg, #2a323d 50%, #0e1116 50%);
  }
  .facts-line .row {
    display: inline-flex;
    margin: 0 0 0 6px;
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
