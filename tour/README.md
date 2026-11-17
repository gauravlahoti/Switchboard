# Jev tour

A video-style, self-playing explainer of Jev (TypeSafe's System 1 model). Plain static files, no build step,
no network calls. Served by the desk app (`server.py`) at `/tour/`. Design notes: the portfolio repo's
`.claude/specs/97-jev-tour.md`.

## Run it
```bash
uv run uvicorn server:server --port 5180            # then open http://127.0.0.1:5180/tour/
# or just the folder:
python -m http.server 5199                          # then open http://localhost:5199/tour/
```
Keys: Space or K play and pause, Left and Right change scene, Home restarts, F full screen, T theme, M mute.
Debug: `?t=SECONDS`, `?pause`, `?hold` (still frame, no panel), `?theme=light|dark`.

## Files
| File | Job |
|---|---|
| `index.html` | The 13 scenes. Each scene has `data-dur`, `data-title`, `data-say` (the guide line) and optionally `data-voice` |
| `tour.js` | One clock drives everything. Also the guide panel, the theme toggle and narration playback |
| `tour.css`, `tokens.css` | Stage, scenes, panel, light theme. Tokens and fonts are a copy, not a link to the portfolio |
| `tour-theme.js` | Sets the theme before first paint |
| `audio/` | Narration clips (`*.mp3`) and `manifest.json`, written by `scripts/tour-voice/` |

## Narration
```bash
cd scripts/tour-voice
npm install            # once
npm run voices         # list the ElevenLabs voices on the account
npm run generate       # speak every scene that has data-voice (skips unchanged ones)
```
The key is read from the git-ignored `.env.local` in the repo root and never printed. The voice is the one whose
name contains "gaurav" (override with `TOUR_VOICE_NAME`). To voice another scene, add
`data-voice="audio/02-the-idea.mp3"` to it, then run `npm run generate`.
