// Generates narration clips for the Jev tour (tour/) with ElevenLabs.
//
//   npm run voices      list the voices on the account (names and ids only)
//   npm run generate    make a clip for every scene that has data-voice
//   npm run generate -- --force   regenerate even if the text has not changed
//
// The narration text is the scene's own data-say line in tour/index.html, so
// the guide panel shows exactly what the voice says. The API key comes from
// ELEVENLABS_API_KEY (loaded from .env.local by the npm scripts). It is never
// read, printed or written here.
import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, '../..');
const tourDir = resolve(siteRoot, 'tour');
const htmlPath = resolve(tourDir, 'index.html');
const manifestPath = resolve(tourDir, 'audio/manifest.json');

const VOICE_NAME = (process.env.TOUR_VOICE_NAME || 'gaurav').toLowerCase();
const MODEL_ID = process.env.TOUR_VOICE_MODEL || 'eleven_v4';
const args = new Set(process.argv.slice(2));

if (!process.env.ELEVENLABS_API_KEY) {
    console.error('ELEVENLABS_API_KEY is not set. Run through npm so .env.local is loaded.');
    process.exit(1);
}

const client = new ElevenLabsClient();

async function allVoices() {
    const res = await client.voices.search({ pageSize: 100 });
    return res.voices ?? [];
}

if (args.has('--list')) {
    const voices = await allVoices();
    for (const v of voices) console.log(`${v.voiceId}  ${v.category ?? ''}  ${v.name}`);
    console.log(`${voices.length} voices`);
    process.exit(0);
}

const decode = (s) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const attr = (tag, name) => {
    const m = tag.match(new RegExp(`\\s${name}="([^"]*)"`));
    return m ? decode(m[1]) : null;
};

const html = readFileSync(htmlPath, 'utf8');
const scenes = [...html.matchAll(/<section class="scene[^>]*>/g)]
    .map((m) => m[0])
    .map((tag) => ({ src: attr(tag, 'data-voice'), text: attr(tag, 'data-say'), title: attr(tag, 'data-title') }))
    .filter((s) => s.src);

if (!scenes.length) {
    console.error('No scene has a data-voice attribute in tour/index.html.');
    process.exit(1);
}

const voices = await allVoices();
const voice = voices.find((v) => v.name?.toLowerCase().includes(VOICE_NAME));
if (!voice) {
    console.error(`No voice named like "${VOICE_NAME}" on this account. Voices found:`);
    for (const v of voices) console.error(`  ${v.category ?? ''}  ${v.name}`);
    console.error('Create or add the voice in ElevenLabs, or set TOUR_VOICE_NAME to one of these.');
    process.exit(1);
}
console.log(`Voice: ${voice.name} (${voice.category ?? 'unknown category'})  Model: ${MODEL_ID}`);

const manifest = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : {};

for (const scene of scenes) {
    const rel = scene.src.replace(/^\//, '');
    const out = resolve(tourDir, rel);
    const fingerprint = createHash('sha256').update(`${voice.voiceId}|${MODEL_ID}|${scene.text}`).digest('hex').slice(0, 16);
    if (!args.has('--force') && existsSync(out) && manifest[rel]?.fingerprint === fingerprint) {
        console.log(`skip   ${rel} (text, voice and model unchanged)`);
        continue;
    }
    console.log(`speak  ${rel}: "${scene.text}"`);
    const stream = await client.textToSpeech.convert(voice.voiceId, {
        text: scene.text,
        modelId: MODEL_ID,
        outputFormat: 'mp3_44100_128',
    });
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(out, Buffer.concat(chunks));
    manifest[rel] = { fingerprint, text: scene.text, voice: voice.name, model: MODEL_ID, bytes: Buffer.concat(chunks).length };
}

mkdirSync(dirname(manifestPath), { recursive: true });
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
console.log('done');
