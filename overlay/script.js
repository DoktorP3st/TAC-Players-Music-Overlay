const POLL_MS = 600;
let lastTrackId    = -1;
let lastTitle      = "";
let data           = null;
let lastVisualHash = "";

async function fetchData() {
  try {
    const r = await fetch(`../data/now_playing.json?t=${Date.now()}`);
    if (!r.ok) return;
    const fresh = await r.json();

    const trackChanged = fresh.track_id !== undefined
      ? fresh.track_id !== lastTrackId
      : fresh.title !== lastTitle;

    data = fresh;

    if (fresh.visual) applyVisual(fresh.visual);

    update(trackChanged);

    if (trackChanged) {
      lastTrackId = fresh.track_id ?? lastTrackId;
      setTimeout(fetchData, 80);
    }
  } catch(e) {}
}

function hexToRgb(hex) {
  const n = parseInt(hex.replace('#', ''), 16);
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}

function applyVisual(v) {
  const hash = JSON.stringify(v);
  if (hash === lastVisualHash) return;
  lastVisualHash = hash;

  const root = document.documentElement;
  root.style.setProperty('--ov-bg',          `rgba(${hexToRgb(v.bg)}, ${v.opacity})`);
  root.style.setProperty('--ov-blur',         `${v.blur}px`);
  root.style.setProperty('--ov-radius',       `${v.radius}px`);
  root.style.setProperty('--ov-width',        `${v.width}px`);
  root.style.setProperty('--ov-accent',        v.accent);
  root.style.setProperty('--ov-title',         v.title_color);
  root.style.setProperty('--ov-artist',        v.artist_color);
  root.style.setProperty('--ov-title-size',   `${v.title_size}px`);
  root.style.setProperty('--ov-artist-size',  `${v.artist_size}px`);
  root.style.setProperty('--ov-transition',   `${v.transition}s`);

  const cover = document.querySelector('.cover-wrap');
  if (cover) cover.style.display = v.show_cover !== false ? '' : 'none';

  const prog = document.querySelector('.progress-wrap');
  if (prog) prog.style.display = v.show_progress !== false ? '' : 'none';
}

function fmt(sec) {
  const s = Math.floor(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function update(trackChanged = false) {
  if (!data) return;
  const player = document.getElementById("player");

  if (!data.playing && !data.title) {
    player.classList.add("hidden");
    return;
  }
  player.classList.remove("hidden");

  if (trackChanged || data.title !== lastTitle) {
    lastTitle = data.title;
    const img = document.getElementById("cover");
    img.style.opacity = "0";
    setTimeout(() => {
      img.src = `../data/cover.jpg?t=${Date.now()}`;
      img.onload = () => { img.style.opacity = "1"; };
    }, 150);
  }

  document.getElementById("title").textContent  = data.title  || "—";
  document.getElementById("artist").textContent = data.artist || "—";

  updateProgress();
}

function updateProgress() {
  if (!data) return;
  let pos = data.position;
  if (data.playing) {
    const elapsed = (Date.now() / 1000) - data.timestamp;
    pos = Math.min(data.duration, data.position + elapsed);
  }
  const pct = data.duration > 0 ? (pos / data.duration * 100).toFixed(1) : 0;
  document.getElementById("fill").style.width = `${pct}%`;
  document.getElementById("pos").textContent  = fmt(pos);
  document.getElementById("dur").textContent  = fmt(data.duration);
}

setInterval(fetchData, POLL_MS);
fetchData();
setInterval(updateProgress, 200);
