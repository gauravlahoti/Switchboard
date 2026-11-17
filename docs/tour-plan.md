# Reflex guided tour: build plan

Status: plan for your review. No tour code is written yet. The narration is in `docs/tour-script.md`.
This is Sprint 4 of spec 96 ("recording, voice, hosting"), made concrete.

## 1. What we are making

A voiced, recorded replay of the Reflex service desk that teaches System One and System Two by showing them
work, then ends with an honest list of trade-offs. It runs on the real console UI, not on slides.

| Part | What the viewer gets | Speech |
|---|---|---|
| 0. Cold open | The recipe request is declined in about a second with no model call | 0.4 min |
| 1. Two ways to think | Animated concept scenes: System One and Two, the usual LLM answer, Jev, how it is trained, where it came from, why we care | 4.9 min |
| 2. Watching it run | Three recorded runs on the console, a measured "fair fight" against an LLM, a map of the seven kinds of job | 5.4 min |
| 3. The trade-offs | One card per cost, each with a real number or story from our own runs | 2.1 min |

Two cuts of one asset: **Express** (about 6 minutes, default) and **Full** (about 14 minutes, scrub by chapter).
Each Express chapter ends with a "go deeper" button that plays the Full beats for that chapter, then returns.

## 2. Already decided (spec 96), and what I added

Kept as is: replay of recorded runs; the UI is a pure function of trace events and replay shares the live code
path; no Jev or LLM key in the public container and writes return 403; every number is measured, never a vendor
claim; own repo on Cloud Run; no em dashes in copy.

Added by this plan:
- Narration follows the recorded events, not a stopwatch.
- Nothing spoken is made up. Outside facts are attributed (see the facts table in the script).
- Public mode is read-only by a mode flag. Live runs stay owner-only behind a passphrase.

## 3. Where we beat the Agentic Harness tour

These are my proposals. I can't see the harness repo from here, so please tell me what you would change about it.

| Idea | Why it is better | Cost |
|---|---|---|
| Narration holds the replay clock when a clip is longer than the gap to the next event | Voice and picture can never drift, even if a clip is re-recorded | Medium, it is the director |
| Time-travel scrubber: drag back and the graph and chat rewind | The UI is a function of events, so rewinding is "reset and re-apply to time t". Few demos can do this | Medium, needs an instant (no animation) render mode |
| Express by default, "go deeper" per chapter, deep links like `#chapter-gate` | Respects attention and still serves the person who wants the detail | Small |
| A measured "fair fight" chapter | Answers the obvious objection ("an LLM can do this with structured output") with our data, not theirs | Medium, needs a benchmark run |
| Inspect mode: pause anywhere and open Jev's raw typed JSON | Turns the tour into something you can poke at | Small, the toggle already exists |
| Word-by-word captions, on by default | Works with sound off, accessible, and the voice timestamps give them for free | Small |
| "Your turn": pick a scenario and it plays the nearest recorded run | Interactive without a key | Small, in spec 96 already |
| A payoff map: seven kinds of job, six lit by this app | A memorable close that ties the demo back to the idea | Small |
| Phone layout and a reduced-motion path | Most LinkedIn clicks are on a phone | Medium |

## 4. Experience design

Visual language: reuse the console's palette so the concept scenes and the app feel like one thing.
Teal is Jev (System One), violet is Gemini (System Two), slate is plain code, amber is a person, soft red is a
refusal. Both themes are supported. No stock footage, no video file: everything is SVG and CSS, so it stays sharp,
small and themeable.

**Persistent chrome during Part 2:** a "who is thinking" ribbon (four lanes lighting as the run progresses) above
the existing Jev and Gemini counters, so the viewer always knows which kind of intelligence is working.

**Stage directions the director can give:** spotlight (dim everything except one node or card), camera (animate
the graph's `viewBox` onto a node), open a card, reveal Jev's JSON line by line, play a concept scene, show a
trade-off card.

| Scene | Visual idea | Data it uses |
|---|---|---|
| 1.1 The question | A chatbot paragraph that software tries and fails to parse, then collapses into clean JSON | none |
| 1.2 Two speeds | "2 x 2" lands instantly, "17 x 24" grinds, over teal and violet washes | none |
| 1.3 The usual answer | An email into an LLM box, a `confidence` field circled as "a guess" | none |
| 1.4 Meet Jev | The same email as state, three question chips flipping to probability bars | a real recorded Jev call |
| 1.5 How it is trained | A three-rung ladder, then tokens one at a time versus all answers at once | none |
| 1.6 Where it came from | A quiet timeline strip with a Kahneman silhouette and a steam engine | none |
| 1.7 Why we care | Three cards that fill with real measured numbers | recordings |
| A5 The fair fight | Two racing bars, two counters, two reliability charts side by side | the benchmark |
| C2 The payoff | Seven tiles, six lit by replaying the node that did the job, one left dark | all recordings |
| 3.x Trade-offs | One calm card each, e.g. the laptop ticket scored "touches production" 53 to 74 percent | recordings, `policy.toml` |

Motion budget: concept scenes are GSAP-style paused timelines so they can be scrubbed and scaled to the length of
the audio. I would self-host the animation library (the container has no outside dependencies, like the fonts).
The library's licence needs a check before we ship it. Everything respects `prefers-reduced-motion` by showing
the end state of each scene instead of animating.

## 5. Architecture

### 5.1 Recording format
One JSON file per run in `recordings/`:

```
{ id, title, profile, text, recorded_at, models: {jev, lite, ...}, git_sha,
  events: [ {type, t, ...}, ... ],        // exactly what the SSE stream sent, already stamped with t in ms
  totals: { jev: {...}, gemini: {...} } } // measured, computed from usage events
```
Two new server events make human actions replayable without any special casing in the UI:
`approval_input {id, by, approve, t}` (emitted when `/api/approve` is called) and `approval_refused {by, t}`
(emitted on the 403). The "switch to John" animation then plays from the event, in live and in replay alike.

### 5.2 Recorder (owner mode only)
`scripts/record.py <slug>` starts a run through the real API, answers the approval through the real endpoint,
and writes the file. Each scenario is recorded three times and the best take is kept (LLM output varies). A
recording is validated on write: required events present, no gaps, no unmasked emails, no key material.

### 5.3 Replay engine
- Extract the page's event handler out of `runLive` into `onEvent(ev)`. Live and replay both call it.
- `Player` schedules events by `t / speed` on a virtual clock, supports 0.5x, 1x, 2x, 4x, pause, and `seek(t)`.
- Human waits (the approval pause) are compressed to a short beat. Real model latency is never compressed,
  because that is the point of the demo.
- `seek(t)` resets the graph and chat, then applies every event up to `t` synchronously in an "instant" mode
  (a root class that switches off animation and transitions).

### 5.4 The director
`tour.json` is a list of beats: `{id, chapter, trigger, clip, text, directives, hold}`. A trigger is an event
match (`run: locked-out, event: safety, outcome: approve`) or `after: <beat>`.

Algorithm:
1. A trigger fires, so the beat starts: play its clip and apply its directives.
2. If `hold` is true, the replay clock stops until the clip ends, plus a quarter second of air.
3. If a second beat triggers while a clip plays, it queues and starts when the first ends.
4. Concept scenes are scaled to the clip length and hit named cues at word times from the voice timestamps.

This is deterministic, so it can be tested with a virtual clock. It is the same kind of test the portfolio uses
for its spoken-reply chunker.

### 5.5 Voice pipeline (ElevenLabs, Gaurav's voice)
`tools/tour_audio.py`:
1. Parse the VO paragraphs from `docs/tour-script.md`.
2. Fill the slots from the recordings and turn numbers into speech ("509 ms" becomes "about half a second").
3. Send each clip to ElevenLabs text to speech with timestamps, using the voice clone.
4. Write `static/tour/audio/<beat>.mp3` and an alignment file. Normalise loudness and trim silence.
5. Cache by a hash of text, voice and settings, so a re-run only pays for clips that changed.

Rules: the ElevenLabs key lives in a git-ignored `.env` on this machine and never reaches the container. The
model ID and endpoints are checked against ElevenLabs' current docs at build time, not taken from memory. A
pronunciation dictionary covers Jev, Noul, RLHF, RLCD, Kahneman, Jevons and TypeSafe. The full script is about
12,000 characters, so one full render is that many credits.

Voice use: it is your own voice, but the end card should say "Narrated with an AI recreation of Gaurav's voice".
Check ElevenLabs' current terms for voice clones when you set up access.

### 5.6 The fair fight (benchmark)
`bench/run_bench.py`:
- A labelled set of at least 100 short messages (off-topic, injection, jailbreak, normal IT). We have 33 now.
- Jev: the three guardrail questions as they are in the app.
- Gemini Lite: the same three questions with structured output, asked for a probability per question.
- Measured per call: latency, tokens, cost. Per model: accuracy against the labels, and a reliability curve
  (when it said 90 percent, how often it was right).
- The script's A5 beat picks its phrases from templates by the measured result. If Gemini wins on accuracy, the
  narration says so. The protocol is shown on screen.
- This is a recorded, offline run. It does not break the spec's "no live comparison" rule.

### 5.7 Public mode and hosting
`REFLEX_MODE=public` is the container default: no keys; `/api/run`, `/api/approve`, `/api/demo/reset` return
403; recordings, `tour.json` and audio are served as static files. A typed message is matched to the nearest
recording by keyword and the UI says so. Cloud Run `reflex`, min 0, max 1. Owner mode needs a passphrase.

**Authorisation flag:** the mode switch and the owner passphrase decide who can trigger model spend and writes.
When we build them I will point out each change for review.

## 6. Recordings to capture

| Slug | Scenario | Used in |
|---|---|---|
| `refund-call` | A real Jev call on the refund email (Refund, Team, Urgency) | Scene 1.4 |
| `recipe` | "I need a food recipe", declined by the guardrail | Cold open, Run A |
| `locked-out` | Carol locked out, approved by John | Run B |
| `social-engineering` | Carol asks for Dan's password reset (outcome to confirm on the recording) | Run C |
| `bench` | The benchmark results | A5, scene 1.7 |
| Optional: `dan-ticket`, `vpn-howto`, `admin-access` | IT-staff register, a how-to, a held request | "Your turn", Full cut |

All data is synthetic and emails are masked. Each recording is checked for key material before it is saved.

## 7. Sprints

Order matters. Numbers must exist before the narration is frozen, and the voice comes last because it needs your
access and the final text.

| Sprint | Work | Size | You can check |
|---|---|---|---|
| S4a | Recorder, schema, two new events, the recordings | M | Play any recording as a raw event list |
| S4b | Benchmark and labelled set | M | The measured fair-fight numbers, good or bad |
| S4c | Replay engine, speed, `seek`, public mode | L | Replay produces the same screen as live, checked by a golden test |
| S4d | Director, chapter rail, captions, spotlight, camera, silent timing | L | The full tour with captions and no sound |
| S4e | Concept scenes and trade-off cards | L | Stills and clips for design review |
| S4f | Voice pipeline and render | M | Hear every clip, fix pronunciations |
| S4g | Polish: phone, reduced motion, 100% zoom in Chrome, load time, deploy | M | The public link |

Sprint 5 of spec 96 (portfolio card, stub, agent entry) stays as it is.

## 8. Tests

- Unit: the director on a virtual clock (no drift, queueing, hold), the slot formatter, the script parser, the
  recording validator.
- Golden: for each recording, the DOM from the live handler equals the DOM from the replay handler.
- Tour lint: every slot filled, every beat has audio, no em dashes, no key material, total duration within range.
- Headless Chrome screenshots of every chapter, in both themes and with reduced motion.

## 9. Risks

| Risk | Mitigation |
|---|---|
| The benchmark does not flatter Jev | The narration is result-driven and we publish it as it is. That makes the video more credible |
| A pronunciation is wrong (Jev, Noul) | Pronunciation dictionary, and you approve each clip by ear |
| Autoplay is blocked | A "Start tour" gesture, as in the harness |
| A live run changes and a recording looks stale | Golden tests, plus re-record when the UI or prompts change |
| Large audio on a cold Cloud Run start | About 12 MB at normal quality. Static files, loaded per chapter |
| Concept scenes look cheap | Design review on stills in S4e before any voice work |
| Our test set is small | State the number on screen, and grow it to 100 or more |

## 10. Decisions and inputs I need

| # | Question | My recommendation |
|---|---|---|
| 1 | What did the harness tour get wrong or feel flat? | Your answer drives section 3 |
| 2 | Include the measured fair fight? | Yes. It is the strongest answer to the objection in your notes |
| 3 | Express as default with "go deeper"? | Yes |
| 4 | Which repo? Code is in `desk`, a scaffold sits in `reflex` | Decide before S4c so hosting is not redone |
| 5 | How is "Jev" pronounced? And "Noul"? | Needed before any audio |
| 6 | A personal line from you in Part 0 or the close (why you built this) | One or two sentences in your own words |
| 7 | ElevenLabs access and a clean voice sample, plus the clone's name or ID | When you are ready, not before S4f |
| 8 | OK to add "Narrated with an AI recreation of my voice" on the end card? | Yes |

## 11. Secrets

Your study notes contained a line that looks like a live API key. I did not copy it into any file. If it is a real
TypeSafe key, treat it as exposed and rotate it in the TypeSafe console, and keep that notes file out of any
repo. Run `detect-secrets scan` before any `git push`.
