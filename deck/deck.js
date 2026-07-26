const slides = [...document.querySelectorAll('.slide')];
const counter = document.querySelector('#counter');
const progress = document.querySelector('#progress');
const notesPanel = document.querySelector('#notes-panel');
const notesCopy = document.querySelector('#notes-copy');
let current = 0;

function show(index) {
  current = Math.max(0, Math.min(index, slides.length - 1));
  slides.forEach((slide, i) => slide.classList.toggle('active', i === current));
  counter.textContent = `${String(current + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
  progress.style.width = `${((current + 1) / slides.length) * 100}%`;
  notesCopy.textContent = slides[current].querySelector('.notes')?.textContent.trim() || '';
  document.title = `${slides[current].dataset.title} | SquidWard`;
  history.replaceState(null, '', `#${current + 1}`);
}

function toggleNotes() {
  notesPanel.classList.toggle('open');
}

document.querySelector('#prev').addEventListener('click', () => show(current - 1));
document.querySelector('#next').addEventListener('click', () => show(current + 1));
document.querySelector('#notes').addEventListener('click', toggleNotes);
document.querySelector('#fullscreen').addEventListener('click', () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});

document.addEventListener('keydown', (event) => {
  if (['ArrowRight', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); show(current + 1); }
  if (['ArrowLeft', 'PageUp', 'Backspace'].includes(event.key)) { event.preventDefault(); show(current - 1); }
  if (event.key.toLowerCase() === 'n') toggleNotes();
  if (event.key.toLowerCase() === 'f') document.querySelector('#fullscreen').click();
  if (event.key === 'Home') show(0);
  if (event.key === 'End') show(slides.length - 1);
});

let touchStart = 0;
document.addEventListener('touchstart', (event) => { touchStart = event.changedTouches[0].screenX; }, { passive: true });
document.addEventListener('touchend', (event) => {
  const delta = event.changedTouches[0].screenX - touchStart;
  if (Math.abs(delta) > 50) show(current + (delta < 0 ? 1 : -1));
}, { passive: true });

const hashSlide = Number.parseInt(location.hash.slice(1), 10) - 1;
show(Number.isNaN(hashSlide) ? 0 : hashSlide);
