const POLL_MS = 600;
let lastTrackId = -1;
let lastTitle   = "";
let data        = null;

async function fetchData() {
  try {
    const r = await fetch(`../data/now_playing.json?t=${Date.now()}`);
    if (!r.ok) return;
    const fresh = await r.json();

    // Nouveau titre détecté → re-fetch immédiatement après 80ms pour s'assurer
    // que la cover est bien copiée avant de l'afficher
    const trackChanged = fresh.track_id !== undefined
      ? fresh.track_id !== lastTrackId
      : fresh.title !== lastTitle;

    data = fresh;
    update(trackChanged);

    if (trackChanged) {
      lastTrackId = fresh.track_id ?? lastTrackId;
      setTimeout(fetchData, 80);
    }
  } catch(e) {}
}

function fmt(sec) {
  const s = Math.floor(sec);
  return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
}

function update(trackChanged = false) {
  if (!data) return;
  const player = document.getElementById("player");

  if (!data.playing && !data.title) {
    player.classList.add("hidden");
    return;
  }
  player.classList.remove("hidden");

  // Changement de titre → transition cover
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

// Poll régulier
setInterval(fetchData, POLL_MS);
fetchData();

// Interpolation fluide de la progression (indépendante du poll)
setInterval(updateProgress, 200);
