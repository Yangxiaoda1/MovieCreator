'use strict';

const http = require('node:http');
const cloudbase = require('@cloudbase/node-sdk');

const app = cloudbase.init({ env: cloudbase.SYMBOL_CURRENT_ENV });
const ENV_ID = process.env.STORYBOARD_CLOUDBASE_ENV_ID || process.env.TCB_ENV || 'your-cloudbase-env-id';
const BUCKET = process.env.STORYBOARD_CLOUDBASE_BUCKET || 'your-bucket-name';
const DEFAULT_DOC_ID = process.env.STORYBOARD_DEFAULT_DOC_ID || 'storyboard-review';

function sanitizeDocId(value) {
  const raw = String(value || DEFAULT_DOC_ID).trim();
  return /^[a-zA-Z0-9_-]{1,120}$/.test(raw) ? raw : DEFAULT_DOC_ID;
}

function sanitizeKey(value) {
  const raw = String(value || '').trim();
  return /^[a-zA-Z0-9_-]{1,200}$/.test(raw) ? raw : '';
}

function isConfigured() {
  return ENV_ID && BUCKET && !ENV_ID.startsWith('your-') && !BUCKET.startsWith('your-');
}

function fileIdFor(docId) {
  return `cloud://${ENV_ID}.${BUCKET}/storyboard_reviews/${sanitizeDocId(docId)}.json`;
}

function safeNotes(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const notes = {};
  for (const [key, item] of Object.entries(value)) {
    if (/^[a-zA-Z0-9_-]{1,200}$/.test(key)) notes[key] = String(item ?? '').slice(0, 20000);
  }
  return notes;
}

async function readDocument(docId) {
  if (!isConfigured()) return { notes: {}, updatedAt: 0, updatedBy: '', docId: sanitizeDocId(docId), configured: false };
  try {
    const result = await app.downloadFile({ fileID: fileIdFor(docId), urlType: 'COS_URL' });
    const parsed = JSON.parse(Buffer.from(result.fileContent).toString('utf8'));
    return { notes: safeNotes(parsed.notes), updatedAt: Number(parsed.updatedAt || 0), updatedBy: String(parsed.updatedBy || ''), docId: sanitizeDocId(docId), configured: true };
  } catch (_) {
    return { notes: {}, updatedAt: 0, updatedBy: '', docId: sanitizeDocId(docId), configured: true };
  }
}

async function writeDocument(docId, document) {
  if (!isConfigured()) throw Error('Set STORYBOARD_CLOUDBASE_ENV_ID and STORYBOARD_CLOUDBASE_BUCKET first');
  await app.uploadFile({ cloudPath: `storyboard_reviews/${sanitizeDocId(docId)}.json`, fileContent: Buffer.from(JSON.stringify(document, null, 2) + '\n', 'utf8') });
}

function reply(response, statusCode, payload) {
  response.writeHead(statusCode, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store'
  });
  response.end(JSON.stringify(payload));
}

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

const server = http.createServer(async (request, response) => {
  if (request.method === 'OPTIONS') return reply(response, 204, {});
  const parsedUrl = new URL(request.url, 'http://localhost');
  if (parsedUrl.pathname === '/healthz') return reply(response, 200, { status: 'ok' });
  if (parsedUrl.pathname !== '/') return reply(response, 404, { ok: false, error: 'not found' });
  try {
    if (request.method === 'GET') {
      const docIdParam = parsedUrl.searchParams.get('docId');
      const docId = sanitizeDocId(docIdParam);
      const payload = { ok: true, ...(await readDocument(docId)) };
      return reply(response, 200, payload);
    }
    if (request.method !== 'POST') return reply(response, 405, { ok: false, error: 'method not allowed' });
    const payload = await readBody(request);
    const docId = sanitizeDocId(payload.docId || parsedUrl.searchParams.get('docId'));
    const key = sanitizeKey(payload.key);
    if (!key) return reply(response, 400, { ok: false, error: 'invalid key' });
    const current = await readDocument(docId);
    current.notes[key] = String(payload.value ?? '').slice(0, 20000);
    current.updatedAt = Date.now();
    current.updatedBy = String(payload.updatedBy || 'anonymous-reviewer').slice(0, 120);
    current.docId = docId;
    await writeDocument(docId, current);
    return reply(response, 200, { ok: true, key, docId, updatedAt: current.updatedAt });
  } catch (error) {
    console.error(error);
    return reply(response, 500, { ok: false, error: String(error && error.message || error) });
  }
});

server.listen(9000, '0.0.0.0', () => console.log('storyboardReviewApi listening on port 9000'));
