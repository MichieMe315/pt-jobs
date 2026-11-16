(() => {
    const toolbar = document.querySelector(".pt-grid-toolbar");
    if (!toolbar) return;
    const filters = [...toolbar.querySelectorAll("[data-admin-filter]")];
    // Django supplies a complete query for each option. Apply only the keys
    // changed by that option, so several filters and search can be set together.
    const changes = (before, after) => [...new Set([...before.keys(), ...after.keys()])]
        .filter((key) => JSON.stringify(before.getAll(key)) !== JSON.stringify(after.getAll(key)));
    const defaults = filters.map((select) => {
        select.closest("label").hidden = false;
        return new URLSearchParams(select.value);
    });
    toolbar.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = new URLSearchParams(new FormData(toolbar));
        filters.forEach((select, index) => {
            const next = new URLSearchParams(select.value);
            for (const key of changes(defaults[index], next)) {
                query.delete(key);
                next.getAll(key).forEach((value) => query.append(key, value));
            }
        });
        ["p", "all", "e"].forEach((key) => query.delete(key));
        if (query.get("q") === "") query.delete("q");
        const suffix = query.toString();
        window.location.assign(window.location.pathname + (suffix ? "?" + suffix : ""));
    });
    const columns = document.querySelector("[data-columns-toggle]");
    if (columns) {
        const panel = document.getElementById(columns.getAttribute("aria-controls"));
        panel.hidden = true;
        columns.hidden = false;
        columns.addEventListener("click", () => {
            panel.hidden = !panel.hidden;
            columns.setAttribute("aria-expanded", String(!panel.hidden));
        });
    }
})();
