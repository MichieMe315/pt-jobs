// Minimal, dependency-free autocomplete for inputs marked with data-autocomplete="location".
// Uses Mapbox Geocoding API (forward geocoding).

(function () {
  function makeDropdown() {
    const box = document.createElement('div');
    box.className = 'mbx-dropdown';
    box.style.position = 'absolute';
    box.style.zIndex = 2000;
    box.style.width = '100%';
    box.style.maxHeight = '240px';
    box.style.overflowY = 'auto';
    box.style.background = 'white';
    box.style.border = '1px solid #ccc';
    box.style.borderRadius = '0.25rem';
    box.style.boxShadow = '0 4px 16px rgba(0,0,0,0.2)';
    box.style.display = 'none';
    return box;
  }

  function attachAutocomplete(input) {
    if (input.__mbxAttached) return;
    input.__mbxAttached = true;

    const token = window.__MAPBOX_TOKEN__;
    if (!token) return;

    input.setAttribute('autocomplete', 'off');

    // Wrap in relatively positioned container so dropdown can size/position properly
    const wrap = document.createElement('div');
    wrap.style.position = 'relative';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    const dd = makeDropdown();
    wrap.appendChild(dd);

    let ctrl = { timer: null, opened: false };

    function close() {
      dd.style.display = 'none';
      dd.innerHTML = '';
      ctrl.opened = false;
    }

    function open(items) {
      dd.innerHTML = '';
      items.forEach(item => {
        const row = document.createElement('div');
        row.textContent = item.place_name;
        row.style.padding = '8px 10px';
        row.style.cursor = 'pointer';
        row.addEventListener('mousedown', e => {
          e.preventDefault();
          input.value = item.place_name;
          close();
        });
        row.addEventListener('mouseover', () => row.style.background = '#f2f2f2');
        row.addEventListener('mouseout', () => row.style.background = 'white');
        dd.appendChild(row);
      });
      if (items.length) {
        dd.style.display = 'block';
        ctrl.opened = true;
      } else {
        close();
      }
    }

    async function search(q) {
      const url = new URL('https://api.mapbox.com/geocoding/v5/mapbox.places/' + encodeURIComponent(q) + '.json');
      url.searchParams.set('access_token', token);
      url.searchParams.set('autocomplete', 'true');
      url.searchParams.set('limit', '6');
      // Optional: bias to CA
      url.searchParams.set('country', 'CA,US');

      const res = await fetch(url.toString());
      if (!res.ok) return [];
      const data = await res.json();
      return (data.features || []);
    }

    input.addEventListener('input', () => {
      const q = (input.value || '').trim();
      if (ctrl.timer) clearTimeout(ctrl.timer);
      if (!q) {
        close();
        return;
      }
      ctrl.timer = setTimeout(async () => {
        try {
          const items = await search(q);
          open(items);
        } catch (_) {
          close();
        }
      }, 200);
    });

    input.addEventListener('blur', () => {
      // close a tick later to allow click selection
      setTimeout(close, 120);
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close();
    });
  }

  window.__initMapboxAutocomplete = function () {
    const nodes = document.querySelectorAll('input[data-autocomplete="location"]');
    nodes.forEach(attachAutocomplete);
  };
})();
