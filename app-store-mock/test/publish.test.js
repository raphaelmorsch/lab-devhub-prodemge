'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'app-store-mock-'));
process.env.LOCAL_DATA_DIR = dataDir;
process.env.IPA_PUBLISH_TOKEN = 'ipa-test-token';
delete process.env.BUCKET_NAME;
delete process.env.BUCKET_HOST;
delete process.env.AWS_ACCESS_KEY_ID;
delete process.env.AWS_SECRET_ACCESS_KEY;

const { start } = require('../server');

let base;
let server;

test.before(async () => {
  server = start(0);
  await new Promise((resolve) => server.once('listening', resolve));
  const address = server.address();
  base = `http://127.0.0.1:${address.port}`;
});

test.after(async () => {
  await new Promise((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));
});

async function post(field, bytes, filename, token) {
  const form = new FormData();
  form.append(field, new Blob([bytes]), filename);
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${base}/api/apps/demo/releases`, {
    method: 'POST',
    headers,
    body: form,
  });
  const body = await response.json();
  return { status: response.status, body };
}

test('o APK continua publicado sem autenticação', async () => {
  const published = await post('apk', Buffer.from('apk-bytes'), 'app.apk');
  assert.equal(published.status, 201);
  assert.equal(published.body.platform, 'android');
  const downloaded = await fetch(`${base}${published.body.downloadPath}`);
  assert.equal(downloaded.status, 200);
  assert.equal(downloaded.headers.get('content-type'), 'application/vnd.android.package-archive');
  assert.equal(Buffer.from(await downloaded.arrayBuffer()).toString(), 'apk-bytes');
});

test('o IPA exige o token e fica disponível para download', async () => {
  const ipa = Buffer.from('PK\u0003\u0004ipa');
  const rejected = await post('ipa', ipa, 'SidsMobile.ipa');
  assert.equal(rejected.status, 401);
  const published = await post('ipa', ipa, 'SidsMobile.ipa', 'ipa-test-token');
  assert.equal(published.status, 201);
  assert.equal(published.body.platform, 'ios');
  assert.equal(published.body.ipaFileName, 'SidsMobile.ipa');
  const downloaded = await fetch(`${base}${published.body.downloadPath}`);
  assert.equal(downloaded.status, 200);
  assert.match(downloaded.headers.get('content-disposition'), /SidsMobile\.ipa/);
  assert.equal(Buffer.from(await downloaded.arrayBuffer()).toString(), ipa.toString());
  const listed = await fetch(`${base}/api/apps`);
  const apps = await listed.json();
  const demo = apps.items.find((item) => item.id === 'demo');
  assert.equal(demo.latest.platform, 'ios');
});

test('um arquivo que não é IPA é recusado', async () => {
  const published = await post('ipa', Buffer.from('not-an-ipa'), 'app.ipa', 'ipa-test-token');
  assert.equal(published.status, 400);
});
