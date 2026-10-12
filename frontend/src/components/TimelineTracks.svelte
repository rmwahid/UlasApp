<script>
  export let shots = [];
  export let total = 0;
  export let music = null;
  export let currentTime = 0;
  export let onSeek = () => {};

  const ZOOM_STEPS = [8, 12, 20, 30, 44, 64, 90, 130];
  let zoomIndex = 4;
  let width = 0;

  $: pps = ZOOM_STEPS[zoomIndex];
  $: canvas = Math.max(total * pps, width);
  $: tickStep = pps >= 64 ? 1 : pps >= 30 ? 2 : 5;

  function ticks() {
    const marks = [];
    for (let at = 0; at <= total + 0.001; at += tickStep) {
      marks.push(Number(at.toFixed(3)));
    }
    return marks;
  }

  function fitToWidth() {
    if (!total || !width) return;
    const ideal = width / total;
    let best = 0;
    ZOOM_STEPS.forEach((value, index) => {
      if (value <= ideal) best = index;
    });
    zoomIndex = best;
  }

  function seekFromEvent(event) {
    onSeek(Math.min(Math.max(event.offsetX / pps, 0), total || 0));
  }

  function timeLabel(seconds) {
    const whole = Math.max(0, Math.floor(seconds));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  }
</script>

<div class="timeline" bind:clientWidth={width}>
  <div class="head">
    <span class="title">Storyboard</span>
    <span class="hint">click a clip to jump the preview there</span>
    <span class="spacer"></span>
    <span class="zoom">
      zoom
      <input
        type="range"
        min="0"
        max={ZOOM_STEPS.length - 1}
        step="1"
        bind:value={zoomIndex}
        aria-label="Timeline zoom"
      />
    </span>
    <button type="button" on:click={fitToWidth}>fit</button>
  </div>

  <div class="scroller">
    <div class="canvas" style={`width: ${canvas}px`}>
      <div class="ruler" role="presentation" on:click={seekFromEvent}>
        {#each ticks() as mark}
          <span class="tick" style={`left: ${mark * pps}px`}>
            <span class="tick-label">{timeLabel(mark)}</span>
          </span>
        {/each}
      </div>

      <div class="track">
        <span class="track-label">V1</span>
        <div class="lane">
          {#each shots as shot}
            <button
              type="button"
              class="block shot {shot.mode}"
              style={`left: ${shot.start * pps}px; width: ${Math.max((shot.end - shot.start) * pps - 2, 26)}px; background-image: url('${shot.thumb}')`}
              title={`${shot.id} · ${shot.asset} · ${shot.mode} · ${shot.start}s to ${shot.end}s`}
              on:click={() => onSeek(shot.start)}
            >
              <span class="block-line">{shot.asset}</span>
              <span class="block-meta">{(shot.end - shot.start).toFixed(1)}s</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="track">
        <span class="track-label">TXT</span>
        <div class="lane">
          {#each shots as shot}
            <button
              type="button"
              class="block text"
              style={`left: ${shot.start * pps}px; width: ${Math.max((shot.end - shot.start) * pps - 2, 26)}px`}
              title={`${shot.line} on-screen text`}
              on:click={() => onSeek(shot.start)}
            >
              <span class="block-line">{shot.overlayText}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="track">
        <span class="track-label">AUD</span>
        <div class="lane">
          {#if music}
            <span class="block audio" style={`left: 0px; width: ${total * pps}px`}>
              <span class="block-line">{music}</span>
            </span>
          {:else}
            <span class="block empty" style={`left: 0px; width: ${total * pps}px`}>
              <span class="block-line">no music</span>
            </span>
          {/if}
        </div>
      </div>

      <div class="playhead" style={`left: ${currentTime * pps}px`}></div>
    </div>
  </div>
</div>

<style>
  .timeline {
    flex: 0 0 auto;
    display: grid;
    grid-template-rows: auto 1fr;
    height: 202px;
    border-top: 1px solid #2a323d;
    background: #11151c;
    min-height: 0;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    border-bottom: 1px solid #232a34;
    font-size: 12px;
    color: #93a1b3;
  }
  .title {
    font-weight: 700;
    color: #b7c2cf;
  }
  .hint {
    font-size: 11px;
    color: #6b7684;
  }
  .spacer {
    flex: 1;
  }
  .zoom {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .zoom input {
    width: 90px;
    accent-color: #f5b52e;
  }
  .head button {
    background: #171d26;
    color: #b7c2cf;
    border: 1px solid #2a323d;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    cursor: pointer;
  }
  .scroller {
    overflow-x: auto;
    overflow-y: hidden;
    padding: 6px 0 10px;
  }
  .canvas {
    position: relative;
    min-width: 100%;
    height: 100%;
  }
  .ruler {
    position: relative;
    height: 20px;
    margin-left: 44px;
    cursor: pointer;
  }
  .tick {
    position: absolute;
    top: 0;
    bottom: 0;
    border-left: 1px solid #232a34;
  }
  .tick-label {
    position: absolute;
    top: 2px;
    left: 4px;
    font-size: 10px;
    color: #6b7684;
    white-space: nowrap;
  }
  .track {
    display: grid;
    grid-template-columns: 44px 1fr;
    align-items: center;
    height: 34px;
  }
  .track-label {
    font-size: 10px;
    letter-spacing: 0.08em;
    color: #6b7684;
    text-align: center;
  }
  .lane {
    position: relative;
    height: 30px;
    border-left: 1px solid #232a34;
  }
  .block {
    position: absolute;
    top: 1px;
    height: 28px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 1px;
    padding: 0 6px;
    overflow: hidden;
    border-radius: 6px;
    border: 1px solid #33404f;
    background-color: #1b232e;
    background-size: cover;
    background-position: center;
    color: #e8ecf1;
    font-size: 10px;
    text-align: left;
    cursor: pointer;
  }
  .block-line {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .block-meta {
    color: #93a1b3;
  }
  .shot {
    box-shadow: inset 0 0 0 40px rgba(11, 15, 20, 0.55);
  }
  .shot.photo {
    border-color: #35505d;
  }
  .shot.trim {
    border-color: #3b5566;
  }
  .shot.freeze {
    border-color: #5a4f6b;
  }
  .text {
    background-image: none;
    background-color: #2a2418;
    border-color: #6b5a22;
  }
  .audio {
    background-image: none;
    background-color: #16241d;
    border-color: #2f6b4b;
    cursor: default;
  }
  .empty {
    background-image: none;
    background-color: #151a21;
    border: 1px dashed #2a323d;
    color: #6b7684;
    cursor: default;
  }
  .playhead {
    position: absolute;
    top: 0;
    bottom: 0;
    margin-left: 44px;
    width: 2px;
    background: #f5b52e;
    pointer-events: none;
  }
</style>
