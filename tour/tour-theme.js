/* Sets the tour theme before first paint: saved choice, else the OS setting. */
(() => {
    let theme = new URLSearchParams(location.search).get('theme');
    if (theme !== 'light' && theme !== 'dark') {
        try { theme = localStorage.getItem('tour-theme'); } catch (e) { /* storage blocked */ }
    }
    if (theme !== 'light' && theme !== 'dark') {
        theme = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', theme);
})();
