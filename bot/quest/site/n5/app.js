const answers = ['0JzQntCU0KPQm9Cs', '0KfQmNCh0JvQng==', '0JvQntCa', 'MjM1OA=='];
let step = Number(localStorage.getItem('n5-step') || 0);
const logEl = document.querySelector('#log');
const statusEl = document.querySelector('#status');

function norm(value) {
  return (value || '').toLowerCase().replaceAll('ё', 'е').replace(/[^a-zа-я0-9]+/g, ' ').trim();
}
function decode(value) { return decodeURIComponent(escape(atob(value))); }
function stamp() { return new Date().toLocaleTimeString('ru-RU', {hour12:false}); }
function log(line) { logEl.textContent += `\n[${stamp()}] ${line}`; logEl.scrollTop = logEl.scrollHeight; }
function render() {
  document.querySelectorAll('.panel').forEach((panel, i) => {
    panel.classList.toggle('locked', i > step);
    panel.classList.toggle('active', i === step);
  });
  statusEl.textContent = step >= answers.length ? 'UNLOCKED' : `STEP ${step + 1}/4`;
  statusEl.classList.toggle('ok', step >= answers.length);
}
function check(i) {
  if (i > step) return;
  const input = document.querySelector(`#a${i}`);
  const expected = decode(answers[i]);
  if (norm(input.value) === norm(expected)) {
    if (i === step) step++;
    localStorage.setItem('n5-step', String(step));
    log(`ACCEPTED: ${expected}. Введи это в Telegram-бот.`);
    if (step >= answers.length) log('NODE N5 COMPLETE. Фрагмент в боте: ВЫЧИСЛИ.');
    render();
  } else {
    log('REJECTED: порядок расчёта нарушен');
    input.focus();
  }
}

document.querySelectorAll('[data-check]').forEach(button => {
  button.addEventListener('click', () => check(Number(button.dataset.check)));
});
document.querySelectorAll('input').forEach((input, i) => {
  input.addEventListener('keydown', event => { if (event.key === 'Enter') check(i); });
});
render();
