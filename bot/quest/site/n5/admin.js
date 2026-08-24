const login = document.querySelector('#login');
const password = document.querySelector('#password');
const error = document.querySelector('#error');
const loginCard = document.querySelector('#login-card');
const dashboard = document.querySelector('#dashboard');
const digits = Array.from(document.querySelectorAll('.digit'));
const result = document.querySelector('#result');

const normalize = value => (value || '')
  .toLowerCase()
  .replaceAll('ё', 'е')
  .replace(/[^a-zа-я0-9]+/g, ' ')
  .trim();

function isPassword(value) {
  return normalize(value) === 'модуль число лок';
}

function lockCode() {
  return digits.map(input => input.value.replace(/\D/g, '')).join('');
}

function enter() {
  if (normalize(login.value) === 'argus' && isPassword(password.value)) {
    loginCard.classList.add('hidden');
    dashboard.classList.remove('hidden');
    digits[0].focus();
  } else {
    error.textContent = 'Доступ отклонён';
  }
}

function closeNode() {
  if (lockCode() === '6535') {
    result.classList.remove('hidden');
  } else {
    result.classList.add('hidden');
    document.querySelector('.digit-lock').classList.add('shake');
    setTimeout(() => document.querySelector('.digit-lock').classList.remove('shake'), 350);
  }
}

digits.forEach((input, index) => {
  input.addEventListener('input', event => {
    const value = event.target.value.replace(/\D/g, '').slice(-1);
    event.target.value = value;
    if (value && digits[index + 1]) digits[index + 1].focus();
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'Backspace' && !input.value && digits[index - 1]) digits[index - 1].focus();
    if (event.key === 'Enter') closeNode();
  });
  input.addEventListener('paste', event => {
    event.preventDefault();
    const pasted = (event.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, digits.length);
    pasted.split('').forEach((char, offset) => {
      if (digits[index + offset]) digits[index + offset].value = char;
    });
    const next = Math.min(index + pasted.length, digits.length - 1);
    digits[next].focus();
  });
});

document.querySelector('#enter').addEventListener('click', enter);
document.querySelector('#close-node').addEventListener('click', closeNode);
password.addEventListener('keydown', event => { if (event.key === 'Enter') enter(); });
