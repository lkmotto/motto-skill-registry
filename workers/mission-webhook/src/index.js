/**
 * GitHub Webhook - Mission Queue Worker
 *
 * Receives GitHub webhook events, validates them, and pushes dispatch
 * tasks into Cloudflare KV for local watchers to pick up.
 *
 * Events handled:
 *   - issues.opened  (if title starts with [mission])
 *   - issues.labeled (label name === "mission" or "mission:*")
 *   - pull_request.closed (merged === true - post-merge validation)
 *
 * Deploy: wrangler deploy
 * Secrets: wrangler secret put GITHUB_WEBHOOK_SECRET
 *           wrangler secret put GITHUB_TOKEN
 */

const ALLOWED_EVENTS = ['issues', 'pull_request'];
const MISSION_LABEL_PREFIX = 'mission';

async function verifySignature(request, secret) {
  const signature = request.headers.get('X-Hub-Signature-256');
  if (!signature) return false;

  const body = await request.clone().text();
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']
  );
  const sigHex = signature.replace('sha256=', '');
  const sigBytes = new Uint8Array(sigHex.length / 2);
  for (let i = 0; i < sigHex.length; i += 2) {
    sigBytes[i / 2] = parseInt(sigHex.substring(i, i + 2), 16);
  }
  const dataBytes = encoder.encode(body);

  return crypto.subtle.verify('HMAC', key, sigBytes, dataBytes);
}

function shouldDispatch(event, payload) {
  // Issue opened with [mission] title prefix
  if (event === 'issues' && payload.action === 'opened') {
    const title = payload.issue?.title || '';
    if (/^\[mission\]/i.test(title)) return { type: 'issue_open', from: 'title' };
  }

  // Issue labeled with 'mission' or 'mission:*'
  if (event === 'issues' && payload.action === 'labeled') {
    const label = payload.label?.name || '';
    if (label === MISSION_LABEL_PREFIX || label.startsWith(MISSION_LABEL_PREFIX + ':')) {
      return { type: 'issue_labeled', from: label };
    }
  }

  // PR merged to main
  if (event === 'pull_request' && payload.action === 'closed') {
    if (payload.pull_request?.merged === true && payload.pull_request?.base?.ref === 'main') {
      return { type: 'pr_merged', from: 'main' };
    }
  }

  return null;
}

async function postComment(env, owner, repo, issueNumber, body) {
  if (!env.GITHUB_TOKEN) return;
  try {
    await fetch(
      `https://api.github.com/repos/${owner}/${repo}/issues/${issueNumber}/comments`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
          'Content-Type': 'application/json',
          'User-Agent': 'mission-webhook-worker',
          'Accept': 'application/vnd.github+json',
        },
        body: JSON.stringify({ body: body }),
      }
    );
  } catch (e) {
    console.error('Failed to post comment:', e.message);
  }
}

async function addLabel(env, owner, repo, issueNumber, label) {
  if (!env.GITHUB_TOKEN) return;
  try {
    await fetch(
      `https://api.github.com/repos/${owner}/${repo}/issues/${issueNumber}/labels`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
          'Content-Type': 'application/json',
          'User-Agent': 'mission-webhook-worker',
          'Accept': 'application/vnd.github+json',
        },
        body: JSON.stringify({ labels: [label] }),
      }
    );
  } catch (e) {
    console.error('Failed to add label:', e.message);
  }
}

async function handleRequest(request, env) {
  if (request.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  const secret = env.GITHUB_WEBHOOK_SECRET;
  if (secret) {
    const valid = await verifySignature(request, secret);
    if (!valid) {
      return new Response('Invalid signature', { status: 401 });
    }
  }

  const event = request.headers.get('X-GitHub-Event');
  if (!event || !ALLOWED_EVENTS.includes(event)) {
    return new Response('OK', { status: 200 });
  }

  const payload = await request.json();
  const dispatch = shouldDispatch(event, payload);

  if (!dispatch) {
    return new Response('OK - not a dispatch trigger', { status: 200 });
  }

  const repo = payload.repository;
  const owner = repo?.owner?.login;
  const repoName = repo?.name;
  const issueNumber = payload.issue?.number || payload.pull_request?.number || 0;

  if (!owner || !repoName) {
    return new Response('Missing repo info', { status: 400 });
  }

  const taskId = `${repoName}:${issueNumber}:${Date.now()}`;
  const task = {
    id: taskId,
    type: dispatch.type,
    trigger: dispatch.from,
    owner: owner,
    repo: repoName,
    issue_number: issueNumber,
    title: payload.issue?.title || payload.pull_request?.title || '',
    body: payload.issue?.body || payload.pull_request?.body || '',
    labels: payload.issue?.labels?.map(function(l) { return l.name; }) || [],
    sender: payload.sender?.login || 'unknown',
    received_at: new Date().toISOString(),
  };

  const key = `queue:pending:${repoName}:${issueNumber}`;
  await env.MISSION_QUEUE.put(key, JSON.stringify(task));

  await postComment(
    env, owner, repoName, issueNumber,
    '🤖 **Mission queued** — a Droid will pick this up shortly.\n\n' +
    'Trigger: `' + dispatch.type + '` (' + dispatch.from + ')\n' +
    'Task ID: `' + taskId + '`'
  );

  await addLabel(env, owner, repoName, issueNumber, 'mission:queued');

  return new Response(JSON.stringify({
    status: 'queued',
    task_id: taskId,
    type: dispatch.type,
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

export default {
  async fetch(request, env) {
    try {
      return await handleRequest(request, env);
    } catch (err) {
      console.error('Webhook error:', err.message);
      return new Response(JSON.stringify({
        error: 'Internal error',
        message: err.message,
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};
