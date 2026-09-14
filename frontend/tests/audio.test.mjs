// API regression tests use mocked HTTP responses; no audio is sent to Groq.
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

/** Load the existing TypeScript modules without adding a test-runner dependency. */
async function moduleUrl(name, replacements = {}) {
    let source = await readFile(new URL(`../src/${name}.ts`, import.meta.url), 'utf8');
    for (const [from, to] of Object.entries(replacements)) source = source.replace(from, to);
    const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 } });
    return `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
}
const authUrl = await moduleUrl('auth');
const { SessionExpiredError } = await import(authUrl);
const { uploadAudio, loadAudioJob, downloadAudio, downloadTranscript, loadAudioLimits } = await import(await moduleUrl('audio', { '"./auth"': JSON.stringify(authUrl) }));
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
const uploadResult = {
    id: 'job-id', filename: 'voice.wav', size_mb: 1.2, duration: 10, status: 'COMPLETED',
    normalized: { transcription: { text: 'Hello.', detected_languages: ['english'], segments: [{ start: 2, end: 3, text: 'Hello.' }], processing_time_ms: 100 } },
};

/** Record requests while returning a fixed sequence of responses. */
function responses(items) {
    const calls = [];
    globalThis.fetch = async (url, options) => {
        calls.push({url, options});
        assert.equal(options.credentials, 'include');
        assert.ok(items.length, 'Unexpected request');
        const [status, body] = items.shift();
        return new Response(JSON.stringify(body), {status});
    };
    return calls;
}

test('upload maps the completed result and sends the correct multipart fields', async () => {
    const calls = responses([[200, uploadResult]]);
    const job = await uploadAudio(new File(['audio'], 'voice.wav'), 'en');
    assert.equal(job.transcript_text, 'Hello.');
    assert.equal(job.original_filename, 'voice.wav');
    assert.deepEqual(job.segments, uploadResult.normalized.transcription.segments);
    assert.equal(calls[0].url, 'http://localhost:8000/audio/upload');
    assert.equal(calls[0].options.body.get('file').name, 'voice.wav');
    assert.equal(calls[0].options.body.get('language'), 'en');
    assert.equal(calls[0].options.headers, undefined);
});

test('expired upload refreshes once and resends the same form', async () => {
    const calls = responses([[401, {}], [401, {}], [200, {}], [200, {id:'user'}], [200, uploadResult]]);
    await uploadAudio(new File(['audio'], 'voice.wav'), '');
    assert.deepEqual(calls.map(c => new URL(c.url).pathname), ['/audio/upload','/auth/me','/auth/refresh','/auth/me','/audio/upload']);
    assert.equal(calls[0].options.body, calls[4].options.body);
    assert.equal(calls[0].options.body.has('language'), false);
});

test('provider errors are displayed and uploads are not retried', async () => {
    const calls = responses([[502, {detail:'Transcription provider request failed; please retry'}]]);
    await assert.rejects(uploadAudio(new File(['audio'], 'voice.wav'), ''), /Transcription provider/);
    assert.equal(calls.length, 1);
});

test('saved jobs use the owned lookup endpoint', async () => {
    const saved = {id:'job-id', transcript_text:'Saved text'};
    const calls = responses([[200, saved]]);
    assert.deepEqual(await loadAudioJob('job-id'), saved);
    assert.equal(calls[0].url, 'http://localhost:8000/audio/job-id');
});

test('expired refresh throws a session error without retrying the download', async () => {
    const calls = responses([[401,{}], [401,{}], [401,{}]]);
    await assert.rejects(downloadAudio('job-id'), SessionExpiredError);
    assert.equal(calls.length, 3);
});

test('download returns the exact binary response and propagates missing-file errors', async () => {
    const bytes = new Uint8Array([0,255,10,42]);
    globalThis.fetch = async (url, options) => {
        assert.equal(url, 'http://localhost:8000/audio/job-id/download');
        assert.equal(options.credentials, 'include');
        return new Response(bytes);
    };
    assert.deepEqual(new Uint8Array(await (await downloadAudio('job-id')).arrayBuffer()), bytes);
    responses([[404, {detail:'Audio not found'}]]);
    await assert.rejects(downloadAudio('job-id'), /Audio not found/);
});


test('limits match backend settings and transcript exports preserve UTF-8', async () => {
    responses([[200, {max_size_bytes: 25000000, max_duration_seconds: 3600}]]);
    assert.equal((await loadAudioLimits()).max_size_bytes, 25000000);
    for (const format of ['txt', 'srt', 'vtt']) {
        globalThis.fetch = async (url, options) => {
            assert.equal(url, `http://localhost:8000/audio/job-id/export/${format}`);
            assert.equal(options.credentials, 'include');
            return new Response('Hello café.');
        };
        assert.equal(await (await downloadTranscript('job-id', format)).text(), 'Hello café.');
    }
});

test('oversized upload displays the backend limit message', async () => {
    responses([[413, {detail: 'Audio must be at most 25 MB'}]]);
    await assert.rejects(uploadAudio(new File(['audio'], 'voice.wav'), ''), /at most 25 MB/);
});
