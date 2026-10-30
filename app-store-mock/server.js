'use strict';

const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { randomUUID } = require('crypto');
const https = require('https');
const http = require('http');
const { NodeHttpHandler } = require('@smithy/node-http-handler');
const {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
  ListObjectsV2Command,
} = require('@aws-sdk/client-s3');

const PORT = Number(process.env.PORT || 8080);
const BUCKET = process.env.BUCKET_NAME || '';
const BUCKET_HOST = process.env.BUCKET_HOST || '';
const BUCKET_PORT = process.env.BUCKET_PORT || '';
const AWS_ACCESS_KEY_ID = process.env.AWS_ACCESS_KEY_ID || '';
const AWS_SECRET_ACCESS_KEY = process.env.AWS_SECRET_ACCESS_KEY || '';
const LOCAL_DATA_DIR = process.env.LOCAL_DATA_DIR || path.join(__dirname, '.data');
const USE_S3 = Boolean(BUCKET && BUCKET_HOST && AWS_ACCESS_KEY_ID && AWS_SECRET_ACCESS_KEY);

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 512 * 1024 * 1024 },
});

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));

function s3Client() {
  const insecure = String(process.env.BUCKET_INSECURE || 'true').toLowerCase() !== 'false';
  let endpoint = BUCKET_HOST;
  if (!endpoint.startsWith('http')) {
    const portNum = BUCKET_PORT || (insecure ? '80' : '443');
    const scheme = portNum === '80' ? 'http' : 'https';
    endpoint = `${scheme}://${BUCKET_HOST}:${portNum}`;
  }
  const requestHandler = insecure
    ? new NodeHttpHandler({
        httpAgent: new http.Agent({ keepAlive: true }),
        httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false }),
      })
    : undefined;
  return new S3Client({
    endpoint,
    region: process.env.BUCKET_REGION || 'us-east-1',
    forcePathStyle: true,
    credentials: {
      accessKeyId: AWS_ACCESS_KEY_ID,
      secretAccessKey: AWS_SECRET_ACCESS_KEY,
    },
    requestHandler,
  });
}

async function streamToBuffer(stream) {
  const chunks = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

function releasePrefix(appId, releaseId) {
  return `apps/${appId}/releases/${releaseId}`;
}

async function putJson(key, value) {
  const body = Buffer.from(JSON.stringify(value, null, 2), 'utf8');
  if (USE_S3) {
    await s3Client().send(
      new PutObjectCommand({
        Bucket: BUCKET,
        Key: key,
        Body: body,
        ContentType: 'application/json',
      }),
    );
    return;
  }
  const full = path.join(LOCAL_DATA_DIR, key);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, body);
}

async function putBinary(key, body, contentType) {
  if (USE_S3) {
    await s3Client().send(
      new PutObjectCommand({
        Bucket: BUCKET,
        Key: key,
        Body: body,
        ContentType: contentType,
      }),
    );
    return;
  }
  const full = path.join(LOCAL_DATA_DIR, key);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, body);
}

async function getObject(key) {
  if (USE_S3) {
    const out = await s3Client().send(
      new GetObjectCommand({ Bucket: BUCKET, Key: key }),
    );
    return {
      body: await streamToBuffer(out.Body),
      contentType: out.ContentType || 'application/octet-stream',
    };
  }
  const full = path.join(LOCAL_DATA_DIR, key);
  if (!fs.existsSync(full)) {
    const err = new Error('not found');
    err.statusCode = 404;
    throw err;
  }
  return {
    body: fs.readFileSync(full),
    contentType: key.endsWith('.json')
      ? 'application/json'
      : 'application/vnd.android.package-archive',
  };
}

async function listReleaseMetadata(appId) {
  const prefix = `apps/${appId}/releases/`;
  const releases = [];

  if (USE_S3) {
    const out = await s3Client().send(
      new ListObjectsV2Command({ Bucket: BUCKET, Prefix: prefix }),
    );
    const keys = (out.Contents || [])
      .map((o) => o.Key)
      .filter((k) => k && k.endsWith('/metadata.json'));
    for (const key of keys) {
      try {
        const obj = await getObject(key);
        releases.push(JSON.parse(obj.body.toString('utf8')));
      } catch {
        // ignore corrupt entries
      }
    }
  } else {
    const root = path.join(LOCAL_DATA_DIR, 'apps', appId, 'releases');
    if (fs.existsSync(root)) {
      for (const releaseId of fs.readdirSync(root)) {
        const metaPath = path.join(root, releaseId, 'metadata.json');
        if (fs.existsSync(metaPath)) {
          releases.push(JSON.parse(fs.readFileSync(metaPath, 'utf8')));
        }
      }
    }
  }

  return releases.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
}

async function listApps() {
  const apps = new Map();

  if (USE_S3) {
    const out = await s3Client().send(
      new ListObjectsV2Command({ Bucket: BUCKET, Prefix: 'apps/' }),
    );
    for (const obj of out.Contents || []) {
      const match = /^apps\/([^/]+)\/releases\/([^/]+)\/metadata\.json$/.exec(obj.Key || '');
      if (!match) continue;
      const appId = match[1];
      if (!apps.has(appId)) {
        apps.set(appId, { id: appId, releaseCount: 0, latest: null });
      }
      try {
        const meta = JSON.parse((await getObject(obj.Key)).body.toString('utf8'));
        const entry = apps.get(appId);
        entry.releaseCount += 1;
        if (!entry.latest || String(meta.createdAt) > String(entry.latest.createdAt)) {
          entry.latest = meta;
        }
      } catch {
        // ignore
      }
    }
  } else {
    const appsRoot = path.join(LOCAL_DATA_DIR, 'apps');
    if (fs.existsSync(appsRoot)) {
      for (const appId of fs.readdirSync(appsRoot)) {
        const releases = await listReleaseMetadata(appId);
        apps.set(appId, {
          id: appId,
          releaseCount: releases.length,
          latest: releases[0] || null,
        });
      }
    }
  }

  return [...apps.values()].sort((a, b) => a.id.localeCompare(b.id));
}

app.get('/healthz', (_req, res) => {
  res.json({
    status: 'ok',
    storage: USE_S3 ? 's3' : 'local',
    bucket: USE_S3 ? BUCKET : null,
  });
});

app.get('/api/apps', async (_req, res) => {
  try {
    res.json({ items: await listApps() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'falha ao listar aplicações' });
  }
});

app.get('/api/apps/:appId/releases', async (req, res) => {
  try {
    res.json({
      appId: req.params.appId,
      items: await listReleaseMetadata(req.params.appId),
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'falha ao listar releases' });
  }
});

app.get('/api/apps/:appId/releases/:releaseId', async (req, res) => {
  try {
    const key = `${releasePrefix(req.params.appId, req.params.releaseId)}/metadata.json`;
    const obj = await getObject(key);
    res.type('json').send(obj.body);
  } catch (err) {
    if (err.statusCode === 404 || err.name === 'NoSuchKey') {
      res.status(404).json({ error: 'release não encontrada' });
      return;
    }
    console.error(err);
    res.status(500).json({ error: 'falha ao obter release' });
  }
});

app.get('/api/apps/:appId/releases/:releaseId/download', async (req, res) => {
  try {
    const metaKey = `${releasePrefix(req.params.appId, req.params.releaseId)}/metadata.json`;
    const meta = JSON.parse((await getObject(metaKey)).body.toString('utf8'));
    const apkKey = meta.apkObjectKey || `${releasePrefix(req.params.appId, req.params.releaseId)}/app.apk`;
    const apk = await getObject(apkKey);
    const filename = meta.apkFileName || `${req.params.appId}-${req.params.releaseId}.apk`;
    res.setHeader('Content-Type', 'application/vnd.android.package-archive');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send(apk.body);
  } catch (err) {
    if (err.statusCode === 404 || err.name === 'NoSuchKey') {
      res.status(404).json({ error: 'APK não encontrado' });
      return;
    }
    console.error(err);
    res.status(500).json({ error: 'falha ao baixar APK' });
  }
});

app.post('/api/apps/:appId/releases', upload.single('apk'), async (req, res) => {
  try {
    const appId = req.params.appId;
    if (!req.file) {
      res.status(400).json({ error: 'campo multipart "apk" é obrigatório' });
      return;
    }

    const releaseId = randomUUID();
    const createdAt = new Date().toISOString();
    const prefix = releasePrefix(appId, releaseId);
    const apkObjectKey = `${prefix}/app.apk`;
    const metadataObjectKey = `${prefix}/metadata.json`;

    const metadata = {
      id: releaseId,
      appId,
      createdAt,
      versionName: req.body.versionName || req.body.version || 'unknown',
      versionCode: req.body.versionCode || '',
      environment: req.body.environment || req.body.flavor || 'unknown',
      flavor: req.body.flavor || req.body.environment || 'unknown',
      reactNativeVersion: req.body.reactNativeVersion || '',
      gitCommit: req.body.gitCommit || req.body.commit || '',
      gitUrl: req.body.gitUrl || '',
      pipelineRun: req.body.pipelineRun || '',
      taskRun: req.body.taskRun || '',
      buildResult: req.body.buildResult || 'success',
      notes: req.body.notes || '',
      apkFileName: req.file.originalname || `${appId}.apk`,
      apkSizeBytes: req.file.size,
      apkObjectKey,
      metadataObjectKey,
      downloadPath: `/api/apps/${encodeURIComponent(appId)}/releases/${encodeURIComponent(releaseId)}/download`,
    };

    await putBinary(apkObjectKey, req.file.buffer, 'application/vnd.android.package-archive');
    await putJson(metadataObjectKey, metadata);

    console.log(`published ${appId} release ${releaseId} (${metadata.apkSizeBytes} bytes)`);
    res.status(201).json(metadata);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'falha ao publicar release', detail: String(err.message || err) });
  }
});

if (!USE_S3) {
  fs.mkdirSync(LOCAL_DATA_DIR, { recursive: true });
  console.warn('S3 não configurado; usando armazenamento local em', LOCAL_DATA_DIR);
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`app-store-mock listening on :${PORT} storage=${USE_S3 ? 's3' : 'local'}`);
});
