const list = document.getElementById('shop-order');
let dragged;
document.getElementById('shop-account-preview').addEventListener('change', event => {
  for (const item of list.querySelectorAll('[data-roles]')) {
    item.hidden = !!event.target.value && !item.dataset.roles.split(' ').includes(event.target.value);
  }
});
list.addEventListener('click', event => {
  const button = event.target.closest('[data-move]');
  if (!button) return;
  const item = button.closest('li');
  const up = button.dataset.move === 'up';
  let neighbor = up ? item.previousElementSibling : item.nextElementSibling;
  while (neighbor?.hidden) neighbor = up ? neighbor.previousElementSibling : neighbor.nextElementSibling;
  if (neighbor) up ? neighbor.before(item) : neighbor.after(item);
  button.focus();
});
list.addEventListener('dragstart', event => { dragged = event.target.closest('li'); });
list.addEventListener('dragover', event => { if (dragged) event.preventDefault(); });
list.addEventListener('dragend', () => { dragged = null; });
list.addEventListener('drop', event => {
  event.preventDefault();
  const target = event.target.closest('li');
  if (!target || !dragged || target === dragged) return;
  const bounds = target.getBoundingClientRect();
  if (event.clientY > bounds.top + bounds.height / 2) target.after(dragged);
  else target.before(dragged);
});
