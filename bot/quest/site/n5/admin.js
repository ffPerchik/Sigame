const login = document.querySelector('#login');
const password = document.querySelector('#password');
const error = document.querySelector('#error');
const loginCard = document.querySelector('#login-card');
const dashboard = document.querySelector('#dashboard');
const lock = document.querySelector('#lock');
const result = document.querySelector('#result');

const normalize = value => (value || '')
  .toLowerCase()
  .replaceAll('ё', 'е')
  .replace(/[^a-zа-я0-9]+/g, ' ')
  .trim();

function isPassword(value) {
  return normalize(value) === 'модуль число лок';
}

function enter() {
  if (normalize(login.value) === 'argus' && isPassword(password.value)) {
    loginCard.classList.add('hidden');
    dashboard.classList.remove('hidden');
    lock.focus();
  } else {
    error.textContent = 'Доступ отклонён';
  }
}

function closeNode() {
  if (normalize(lock.value) === '5365') {
    result.classList.remove('hidden');
  } else {
    result.classList.add('hidden');
    lock.classList.add('shake');
    setTimeout(() => lock.classList.remove('shake'), 350);
  }
}

document.querySelector('#enter').addEventListener('click', enter);
document.querySelector('#close-node').addEventListener('click', closeNode);
password.addEventListener('keydown', event => { if (event.key === 'Enter') enter(); });
lock.addEventListener('keydown', event => { if (event.key === 'Enter') closeNode(); });
