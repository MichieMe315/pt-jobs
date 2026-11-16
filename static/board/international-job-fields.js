document.addEventListener("DOMContentLoaded", () => {
    const optIn = document.querySelector("[data-international-job-opt-in]");
    const stage = document.querySelector("[data-international-job-stage]");
    if (!optIn || !stage) return;
    const row = stage.closest("[data-international-stage-row], .form-row");
    const refresh = () => {
        if (row) row.hidden = !optIn.checked;
        stage.required = optIn.checked;
    };
    optIn.addEventListener("change", refresh);
    refresh();
});
