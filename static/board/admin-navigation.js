(() => {
    const button = document.querySelector(".pt-mobile-nav-button");
    if (!button) return;
    const nav = document.getElementById(button.getAttribute("aria-controls"));
    const mobile = window.matchMedia("(max-width: 767px)");
    const setOpen = (open) => {
        nav.hidden = !open;
        button.setAttribute("aria-expanded", String(open));
    };
    const reset = () => {
        button.hidden = !mobile.matches;
        setOpen(!mobile.matches);
    };
    button.addEventListener("click", () => setOpen(nav.hidden));
    reset();
    mobile.addEventListener("change", reset);
})();
