(function() {
  function initOne(input) {
    if (!input || input.dataset.placesAttached === "1") return;
    input.dataset.placesAttached = "1";
    // Restrict to geocode results; change types if you need businesses
    const opts = { types: ['geocode'], fields: ['formatted_address', 'address_components', 'geometry'] };
    const ac = new google.maps.places.Autocomplete(input, opts);

    // Optional: if you want to split city/province fields
    const cityTarget = input.dataset.cityTarget ? document.getElementById(input.dataset.cityTarget) : null;
    const provTarget = input.dataset.provinceTarget ? document.getElementById(input.dataset.provinceTarget) : null;

    ac.addListener('place_changed', function() {
      const place = ac.getPlace();
      if (!place || !place.address_components) return;

      if (cityTarget || provTarget) {
        let city = '';
        let province = '';
        place.address_components.forEach(c => {
          if (c.types.includes('locality')) city = c.long_name;
          if (c.types.includes('administrative_area_level_1')) province = c.long_name;
        });
        if (cityTarget) cityTarget.value = city || cityTarget.value;
        if (provTarget) provTarget.value = province || provTarget.value;
      }

      // If you only have a single location field, overwrite with the formatted address
      if (!cityTarget && !provTarget && place.formatted_address) {
        input.value = place.formatted_address;
      }
    });
  }

  function initAll() {
    const inputs = document.querySelectorAll('.js-places-autocomplete');
    inputs.forEach(initOne);
  }

  // Expose
  window.__initPlacesAutocomplete = initAll;
})();
