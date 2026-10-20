(() => {
  const script = document.currentScript;
  const days = Number(script.dataset.postingDuration);
  const start = document.getElementById('id_posting_date');
  const end = document.getElementById('id_expiry_date');
  if (!start || !end || !Number.isInteger(days) || days < 1) return;
  let previous = start.value;
  function calculated(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    const date = new Date(value + 'T12:00:00Z');
    if (Number.isNaN(date.getTime())) return null;
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  }
  if (!end.value) end.value = calculated(start.value) || '';
  function updateExpiry() {
    // Keep a deliberately entered expiry; update only an empty or automatic one.
    const automatic = calculated(previous);
    if (!end.value || end.value === automatic) end.value = calculated(start.value) || end.value;
    previous = start.value;
  }
  start.addEventListener('change', updateExpiry);
  start.addEventListener('focus', updateExpiry);
  start.addEventListener('blur', updateExpiry);
})();
