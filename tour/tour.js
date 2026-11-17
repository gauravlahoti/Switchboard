/* Jev tour (spec 97). One clock drives every scene. Elements carry timing in
   data attributes; this file only decides what is visible at time t, so play,
   pause and seeking all come from the same render(). No dependencies. */
(() => {
    const $ = (id) => document.getElementById(id);
    const frame = $('frame');
    const stage = $('stage');
    const guide = $('guide');
    const playBtn = $('play');
    const prevBtn = $('prev');
    const nextBtn = $('next');
    const fsBtn = $('fs');
    const soundBtn = $('sound');
    const collapseBtn = $('collapse');
    const themeBtn = $('theme');
    const segsEl = $('segs');
    const titleEl = $('gTitle');
    const sayEl = $('gSay');
    const clockEl = $('clock');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

    const WELCOME_TITLE = 'Jev, explained';
    const WELCOME_SAY = 'Welcome. Press Start Tour for a five-minute look at Jev, a model that decides instead of writing.';

    const ease = (p) => 1 - Math.pow(1 - p, 3);
    const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
    const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

    const scenes = [...stage.querySelectorAll('.scene')].map((el) => {
        const items = [...el.querySelectorAll('[data-at]')].map((n) => ({
            n,
            at: parseFloat(n.dataset.at),
            until: n.dataset.until != null ? parseFloat(n.dataset.until) : Infinity,
            st: 0,
        }));
        const typers = [...el.querySelectorAll('[data-type]')].map((n) => {
            const full = n.textContent.trim();
            const a = document.createElement('span');
            const b = document.createElement('span');
            b.className = 'rest';
            b.textContent = full;
            n.textContent = '';
            n.append(a, b);
            return { a, b, full, start: parseFloat(n.dataset.type), cps: parseFloat(n.dataset.cps || '36'), k: -1 };
        });
        const ramps = [...el.querySelectorAll('[data-ramp]')].map((n) => ({
            n,
            start: parseFloat(n.dataset.ramp),
            dur: parseFloat(n.dataset.rdur || '1.3'),
            to: parseFloat(n.dataset.to),
            d: parseInt(n.dataset.d ?? '2', 10),
            outs: [...n.querySelectorAll('[data-out]')],
            last: -1,
        }));
        return {
            el, items, typers, ramps, start: 0,
            dur: parseFloat(el.dataset.dur),
            title: el.dataset.title,
            say: el.dataset.say || '',
            // Narration clip for this scene, if it has one. It starts voiceAt seconds into the scene.
            voice: el.dataset.voice
                ? { src: el.dataset.voice, at: parseFloat(el.dataset.voiceAt || '0.6'), audio: null, ok: true }
                : null,
        };
    });

    let total = 0;
    scenes.forEach((s) => { s.start = total; total += s.dur; });

    const segs = scenes.map((s, i) => {
        const li = document.createElement('li');
        li.style.flexGrow = String(s.dur);
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'seg';
        b.setAttribute('aria-label', `Scene ${i + 1} of ${scenes.length}: ${s.title}`);
        b.title = s.title;
        b.addEventListener('click', (e) => { e.stopPropagation(); gotoScene(i); });
        li.append(b);
        segsEl.append(li);
        return { b, p: -1 };
    });

    let t = 0;
    let cur = -1;
    let playing = false;
    let welcome = true;
    let last = 0;
    let raf = 0;
    let lastClock = '';
    let muted = false;
    try { muted = localStorage.getItem('tour-muted') === '1'; } catch (e) { /* storage blocked */ }

    function setCaption(title, say, animate) {
        titleEl.textContent = title;
        if (sayEl.textContent === say) return;
        sayEl.textContent = say;
        if (animate && !reduced.matches && sayEl.animate) {
            sayEl.animate(
                [{ opacity: 0, translate: '0 0.35em' }, { opacity: 1, translate: '0 0' }],
                { duration: 420, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' },
            );
        }
    }

    /* ---------- narration ----------
       The clock is the only timeline. Each frame we work out where the clip
       should be (scene time minus its start offset) and nudge the audio to
       match, so pause, resume, seek and scene jumps all stay in sync. */
    function makeAudio(v) {
        if (typeof Audio === 'undefined') { v.ok = false; return null; }
        const a = new Audio(v.src);
        a.preload = 'auto';
        a.addEventListener('error', () => { v.ok = false; updateSoundUi(); });
        return a;
    }
    scenes.forEach((s) => { if (s.voice) s.voice.audio = makeAudio(s.voice); });

    function updateSoundUi() {
        const voiced = scenes.filter((s) => s.voice);
        const anyOk = voiced.some((s) => s.voice.ok);
        soundBtn.hidden = voiced.length === 0;
        soundBtn.disabled = !anyOk;
        guide.toggleAttribute('data-muted', muted || !anyOk);
        soundBtn.setAttribute(
            'aria-label',
            !anyOk ? 'Narration clip not available yet' : muted ? 'Unmute narration' : 'Mute narration',
        );
    }

    function pauseVoice() {
        for (const s of scenes) {
            const a = s.voice && s.voice.audio;
            if (a && !a.paused) a.pause();
        }
    }

    function syncVoice(s, lt) {
        for (const o of scenes) {
            const oa = o !== s && o.voice && o.voice.audio;
            if (oa && !oa.paused) oa.pause();
        }
        const v = s.voice;
        const a = v && v.ok ? v.audio : null;
        if (!a) return;
        const pos = lt - v.at;
        const finished = Number.isFinite(a.duration) && pos >= a.duration;
        if (!playing || muted || welcome || pos < 0 || finished) {
            if (!a.paused) a.pause();
            return;
        }
        if (Math.abs(a.currentTime - pos) > 0.4) a.currentTime = pos;
        if (a.paused) a.play().catch(() => { /* blocked until a gesture; the next frame retries */ });
    }

    function render() {
        let i = scenes.findIndex((s) => t < s.start + s.dur);
        if (i < 0) i = scenes.length - 1;
        if (i !== cur) {
            scenes.forEach((s, j) => {
                s.el.classList.toggle('is-active', j === i);
                s.el.setAttribute('aria-hidden', j === i ? 'false' : 'true');
            });
            cur = i;
            if (welcome) setCaption(WELCOME_TITLE, WELCOME_SAY, false);
            else setCaption(scenes[i].title, scenes[i].say, true);
        }
        const s = scenes[i];
        const lt = clamp(t - s.start, 0, s.dur);

        for (const it of s.items) {
            const st = lt >= it.until ? 2 : lt >= it.at ? 1 : 0;
            if (st !== it.st) {
                it.st = st;
                it.n.classList.toggle('in', st === 1);
                it.n.classList.toggle('gone', st === 2);
            }
        }
        for (const ty of s.typers) {
            const k = lt < ty.start ? 0 : Math.min(ty.full.length, Math.floor((lt - ty.start) * ty.cps));
            if (k !== ty.k) {
                ty.k = k;
                ty.a.textContent = ty.full.slice(0, k);
                ty.b.textContent = ty.full.slice(k);
            }
        }
        for (const r of s.ramps) {
            const p = clamp((lt - r.start) / r.dur, 0, 1);
            const v = r.to * ease(p);
            const key = Math.round(v * 1000);
            if (key !== r.last) {
                r.last = key;
                r.n.style.setProperty('--v', v.toFixed(4));
                const txt = v.toFixed(r.d);
                for (const o of r.outs) o.textContent = txt;
            }
        }

        syncVoice(s, lt);

        segs.forEach((sg, j) => {
            const p = welcome ? 0 : j < i ? 1 : j > i ? 0 : lt / scenes[j].dur;
            const q = Math.round(p * 500);
            if (q !== sg.p) {
                sg.p = q;
                sg.b.style.setProperty('--p', p.toFixed(3));
            }
            const aria = !welcome && j === i ? 'step' : 'false';
            if (sg.b.getAttribute('aria-current') !== aria) sg.b.setAttribute('aria-current', aria);
        });

        const c = `${fmt(welcome ? 0 : t)} / ${fmt(total)}`;
        if (c !== lastClock) { lastClock = c; clockEl.textContent = c; }
    }

    // Re-render with transitions off, so a jump or restart opens a clean scene.
    function snapRender() {
        stage.classList.add('snap');
        render();
        void stage.offsetWidth;
        stage.classList.remove('snap');
    }

    function setPlayUi() {
        const ended = t >= total && !welcome;
        frame.classList.toggle('is-paused', !playing);
        frame.classList.toggle('is-welcome', welcome);
        frame.classList.toggle('is-ended', ended && !playing);
        playBtn.textContent = playing ? 'Pause' : welcome ? 'Start Tour' : ended ? 'Replay' : 'Resume';
        prevBtn.disabled = welcome;
        nextBtn.disabled = welcome || cur >= scenes.length - 1;
    }

    function loop(now) {
        const dt = Math.min(0.1, (now - last) / 1000);
        last = now;
        t = Math.min(total, t + dt);
        render();
        if (cur >= scenes.length - 1) nextBtn.disabled = true;
        else if (nextBtn.disabled) nextBtn.disabled = false;
        if (t >= total) { pause(); return; }
        raf = requestAnimationFrame(loop);
    }

    function play() {
        if (welcome || t >= total) {
            welcome = false;
            t = 0;
            cur = -1;
            snapRender();
        }
        playing = true;
        last = performance.now();
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(loop);
        setPlayUi();
    }

    function pause() {
        playing = false;
        cancelAnimationFrame(raf);
        pauseVoice();
        setPlayUi();
    }

    const toggle = () => (playing ? pause() : play());

    function seek(time) {
        welcome = false;
        t = clamp(time, 0, total);
        snapRender();
        setPlayUi();
    }

    function gotoScene(i) {
        const s = scenes[clamp(i, 0, scenes.length - 1)];
        // With reduced motion a scene opens on its finished frame, so nothing
        // is left hidden and nothing moves.
        seek(s.start + (reduced.matches ? s.dur - 0.001 : 0));
    }

    function sceneIndex() {
        const i = scenes.findIndex((s) => t < s.start + s.dur);
        return i < 0 ? scenes.length - 1 : i;
    }

    const goPrev = () => {
        const i = sceneIndex();
        gotoScene(t - scenes[i].start > 2 ? i : i - 1);
    };
    const goNext = () => gotoScene(sceneIndex() + 1);

    /* ---------- controls ---------- */
    playBtn.addEventListener('click', toggle);
    prevBtn.addEventListener('click', goPrev);
    nextBtn.addEventListener('click', goNext);
    stage.addEventListener('click', toggle);

    soundBtn.addEventListener('click', () => {
        muted = !muted;
        try { localStorage.setItem('tour-muted', muted ? '1' : '0'); } catch (e) { /* storage blocked */ }
        updateSoundUi();
        render();
    });
    updateSoundUi();

    collapseBtn.addEventListener('click', () => {
        const collapsed = guide.toggleAttribute('data-collapsed');
        collapseBtn.setAttribute('aria-expanded', String(!collapsed));
        collapseBtn.setAttribute('aria-label', collapsed ? 'Expand guide' : 'Collapse guide');
    });

    if (frame.requestFullscreen) {
        fsBtn.hidden = false;
        fsBtn.addEventListener('click', () => {
            if (document.fullscreenElement) document.exitFullscreen();
            else frame.requestFullscreen().catch(() => {});
        });
    }

    /* ---------- theme ---------- */
    const root = document.documentElement;
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    function applyTheme(theme, save) {
        root.setAttribute('data-theme', theme);
        themeBtn.setAttribute('aria-label', theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
        if (metaTheme) metaTheme.setAttribute('content', theme === 'light' ? '#F3F6F5' : '#000000');
        if (save) {
            try { localStorage.setItem('tour-theme', theme); } catch (e) { /* storage blocked */ }
        }
    }
    applyTheme(root.getAttribute('data-theme') === 'light' ? 'light' : 'dark', false);
    themeBtn.addEventListener('click', () => {
        applyTheme(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light', true);
    });

    document.addEventListener('keydown', (e) => {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        const onControl = e.target instanceof HTMLButtonElement || e.target instanceof HTMLAnchorElement;
        switch (e.key) {
            case ' ':
            case 'k':
                if (onControl && e.key === ' ') return;
                e.preventDefault();
                toggle();
                break;
            case 'ArrowRight':
                e.preventDefault();
                goNext();
                break;
            case 'ArrowLeft':
                e.preventDefault();
                goPrev();
                break;
            case 'Home':
                e.preventDefault();
                gotoScene(0);
                break;
            case 'f':
                if (frame.requestFullscreen) fsBtn.click();
                break;
            case 't':
                themeBtn.click();
                break;
            case 'm':
                soundBtn.click();
                break;
            default:
        }
    });

    /* ---------- start ---------- */
    // The tour opens on a welcome frame and waits for Start Tour. The title
    // scene is shown finished, so the first thing seen is a real picture.
    const q = new URLSearchParams(location.search);
    if (q.has('t') || q.has('hold') || q.has('pause')) {
        welcome = false;
        const startAt = parseFloat(q.get('t') || '0');
        t = clamp(Number.isFinite(startAt) ? startAt : 0, 0, total);
        render();
        setPlayUi();
        if (q.has('hold')) { frame.classList.add('hold'); frame.classList.remove('is-paused'); }
        if (q.has('play')) play();
    } else {
        t = scenes[0].dur - 0.001;
        render();
        setPlayUi();
    }
})();
