import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/auth.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 },
});
const { loadUser, logout } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
const user = { id: '1', email: 'test@example.com', name: 'Test' };
function mockResponses(statuses) {
    const calls = [];
    globalThis.fetch = async (url, options) => {
        calls.push([url, options]);
        assert.equal(options.credentials, 'include');
        const status = statuses.shift();
        assert.ok(status, 'Unexpected extra request');
        return new Response(JSON.stringify(user), { status });
    };
    return calls;
}

test('valid session requires no refresh', async () => {
    const calls = mockResponses([200]);
    assert.deepEqual(await loadUser(), user);
    assert.equal(calls.length, 1);
});

test('concurrent checks share one refresh and one retry', async () => {
    const calls = mockResponses([401, 200, 200]);
    const users = await Promise.all([loadUser(), loadUser(), loadUser()]);
    assert.deepEqual(users, [user, user, user]);
    assert.deepEqual(calls.map(([url]) => new URL(url).pathname), ['/auth/me', '/auth/refresh', '/auth/me']);
    assert.equal(calls[1][1].method, 'POST');
});

test('expired refresh returns signed-out state without retrying', async () => {
    const calls = mockResponses([401, 401]);
    assert.equal(await loadUser(), null);
    assert.equal(calls.length, 2);
});

test('second 401 does not cause a refresh loop', async () => {
    mockResponses([401, 200, 401]);
    assert.equal(await loadUser(), null);
});

test('refresh failure is surfaced and a later check can retry', async () => {
    mockResponses([401, 500]);
    await assert.rejects(loadUser(), /refresh your session/);
    mockResponses([200]);
    assert.deepEqual(await loadUser(), user);
});

test('logout waits for rotation and shares duplicate logout calls', async () => {
    const calls = mockResponses([401, 200, 200, 200]);
    const pendingUser = loadUser();
    const firstLogout = logout();
    const secondLogout = logout();
    const duringLogout = loadUser();
    assert.equal(firstLogout, secondLogout);
    await Promise.all([pendingUser, firstLogout, secondLogout]);
    assert.equal(await duringLogout, null);
    assert.deepEqual(calls.map(([url]) => new URL(url).pathname), ['/auth/me', '/auth/refresh', '/auth/me', '/auth/logout']);
    assert.equal(calls[3][1].method, 'POST');
});

test('failed logout surfaces error and permits retry', async () => {
    mockResponses([500, 200]);
    await assert.rejects(logout(), /Unable to log out/);
    await logout();
});
