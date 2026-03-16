const STORAGE_KEY = 'guess-number-dapp-settings-v2';
const THEME_KEY = 'guess-number-theme';

const state = {
  backendUrl: 'http://127.0.0.1:2020',
  rpcUrl: 'http://127.0.0.1:7545',
  playerAKey: '',
  playerBKey: '',
  playerBAddressOverride: '',
  v4MerkleRoot: '',
  theme: localStorage.getItem(THEME_KEY) || 'dark',
};

const $ = (id) => document.getElementById(id);

function log(message) {
  const ts = new Date().toLocaleTimeString();
  $('log').textContent = `[${ts}] ${message}\n${$('log').textContent}`.trim();
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function setOutput(version, payload) {
  $(`${version}-output`).textContent = typeof payload === 'string' ? payload : pretty(payload);
}

function setGuessBanner(version, label, guess = null) {
  const el = $(`${version}-guess-banner`);
  if (!el) return;
  const normalized = (label || '').toLowerCase();
  let text = 'Pas encore de guess.';
  let klass = 'neutral';

  if (normalized.includes('lower') || normalized.includes('plus petit')) {
    text = guess == null ? 'Le nombre secret est plus grand.' : `Trop bas. Le nombre secret est plus grand que ${guess}.`;
    klass = 'warn';
  } else if (normalized.includes('higher') || normalized.includes('plus grand')) {
    text = guess == null ? 'Le nombre secret est plus petit.' : `Trop haut. Le nombre secret est plus petit que ${guess}.`;
    klass = 'warn';
  } else if (normalized.includes('correct') || normalized.includes('won') || normalized.includes('gagn') || normalized.includes('equal')) {
    text = guess == null ? 'Trouvé. B a gagné.' : `Bien joué. ${guess} est le bon nombre.`;
    klass = 'ok';
  } else if (normalized) {
    text = `Résultat: ${label}`;
  }

  el.textContent = text;
  el.className = `guess-banner ${klass} top-gap`;
}

function setBackendState(ok, text) {
  const el = $('backend-state');
  el.textContent = text;
  el.className = `pill ${ok ? 'ok' : 'bad'}`;
}

function applyTheme(theme) {
  state.theme = theme;
  document.body.classList.toggle('light', theme === 'light');
  $('theme-toggle').textContent = theme === 'light' ? '☀️ Light' : '🌙 Dark';
  localStorage.setItem(THEME_KEY, theme);
}

function saveSettings() {
  state.backendUrl = $('cfg-backend-url').value.trim();
  state.rpcUrl = $('cfg-rpc-url').value.trim();
  state.playerAKey = $('cfg-playera-key').value.trim();
  state.playerBKey = $('cfg-playerb-key').value.trim();
  state.playerBAddressOverride = $('cfg-playerb-address').value.trim();
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    backendUrl: state.backendUrl,
    rpcUrl: state.rpcUrl,
    playerAKey: state.playerAKey,
    playerBKey: state.playerBKey,
    playerBAddressOverride: state.playerBAddressOverride,
    v4MerkleRoot: state.v4MerkleRoot,
  }));
  log('Paramètres enregistrés.');
}

function loadSettings() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    Object.assign(state, JSON.parse(raw));
  }
  $('cfg-backend-url').value = state.backendUrl;
  $('cfg-rpc-url').value = state.rpcUrl;
  $('cfg-playera-key').value = state.playerAKey;
  $('cfg-playerb-key').value = state.playerBKey;
  $('cfg-playerb-address').value = state.playerBAddressOverride;
}

async function api(path, body = null, method = 'POST') {
  saveSettings();
  const options = { method, headers: {} };
  if (method !== 'GET') {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body || {});
  }
  const res = await fetch(`${state.backendUrl}${path}`, options);
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(typeof data === 'object' ? pretty(data) : String(data));
  }
  return data;
}

async function refreshBackendState() {
  try {
    const data = await api('/health', null, 'GET');
    setBackendState(true, `Connected · ${data.service}`);
  } catch (err) {
    setBackendState(false, 'Disconnected');
    log(`Backend KO: ${err.message}`);
  }
}

async function accountInfo(privateKey) {
  if (!privateKey) return null;
  return api('/account/info', { rpc_url: state.rpcUrl, private_key: privateKey });
}

async function resolvedPlayerBAddress() {
  if (state.playerBAddressOverride) return state.playerBAddressOverride;
  if (!state.playerBKey) throw new Error('Clé privée joueur B manquante.');
  const info = await accountInfo(state.playerBKey);
  return info.address;
}

async function refreshAccounts() {
  try {
    const [aInfo, bInfo] = await Promise.all([
      state.playerAKey ? accountInfo(state.playerAKey) : Promise.resolve(null),
      state.playerBKey ? accountInfo(state.playerBKey) : Promise.resolve(null),
    ]);

    $('account-a-address').textContent = aInfo?.address || '—';
    $('account-a-balance').textContent = aInfo ? `${aInfo.balance_eth} ETH` : '—';
    $('account-b-address').textContent = state.playerBAddressOverride || bInfo?.address || '—';
    $('account-b-balance').textContent = bInfo ? `${bInfo.balance_eth} ETH` : '—';
  } catch (err) {
    log(`Refresh comptes KO: ${err.message}`);
  }
}

async function runAction(fn, { version = null, successMessage = null, guessLabel = null, guessValue = null } = {}) {
  try {
    const data = await fn();
    if (version) setOutput(version, data);
    if (guessLabel && version) setGuessBanner(version, guessLabel, guessValue);
    if (successMessage) log(successMessage(data));
    await refreshAccounts();
    await refreshBackendState();
    return data;
  } catch (err) {
    if (version) setOutput(version, err.message);
    log(err.message);
    throw err;
  }
}

function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      tab.classList.add('active');
      $('view-' + tab.dataset.tab).classList.add('active');
    });
  });
}

function initSettings() {
  $('toggle-settings').addEventListener('click', () => $('settings-panel').classList.toggle('open'));
  $('save-settings').addEventListener('click', async () => { saveSettings(); await refreshAccounts(); await refreshBackendState(); });
  $('load-settings').addEventListener('click', async () => { loadSettings(); log('Paramètres rechargés.'); await refreshAccounts(); await refreshBackendState(); });
  $('refresh-accounts').addEventListener('click', refreshAccounts);
  $('check-backend').addEventListener('click', refreshBackendState);
  $('theme-toggle').addEventListener('click', () => applyTheme(state.theme === 'light' ? 'dark' : 'light'));
}

function bindV1() {
  $('v1-deploy').addEventListener('click', async () => {
    await runAction(async () => {
      const playerBAddress = await resolvedPlayerBAddress();
      const data = await api('/v1/deploy', {
        rpc_url: state.rpcUrl,
        playerA_private_key: state.playerAKey,
        playerB_address: playerBAddress,
        secret_number: Number($('v1-secret').value),
        max_attempts: Number($('v1-max').value),
      });
      $('v1-contract').value = data.contract_address;
      return data;
    }, { version: 'v1', successMessage: d => `V1 déployé: ${d.contract_address}` });
  });

  $('v1-state').addEventListener('click', async () => {
    await runAction(async () => api('/v1/state', { rpc_url: state.rpcUrl, contract_address: $('v1-contract').value.trim() }), {
      version: 'v1',
      successMessage: () => 'État V1 rafraîchi.',
    });
  });

  $('v1-guess').addEventListener('click', async () => {
    const guess = Number($('v1-guess-value').value);
    const data = await runAction(async () => api('/v1/guess', {
      rpc_url: state.rpcUrl,
      contract_address: $('v1-contract').value.trim(),
      playerB_private_key: state.playerBKey,
      guess,
    }), { version: 'v1', guessLabel: 'pending', guessValue: guess, successMessage: d => `Guess V1 envoyé: ${d.result_label}` });
    setGuessBanner('v1', data.result_label, guess);
  });
}

function bindV2() {
  $('v2-deploy').addEventListener('click', async () => {
    await runAction(async () => {
      const playerBAddress = await resolvedPlayerBAddress();
      const data = await api('/v2/deploy', {
        rpc_url: state.rpcUrl,
        playerA_private_key: state.playerAKey,
        playerB_address: playerBAddress,
        secret_number: Number($('v2-secret').value),
        max_attempts: Number($('v2-max').value),
        stake_eth: $('v2-stake').value,
      });
      $('v2-contract').value = data.contract_address;
      return data;
    }, { version: 'v2', successMessage: d => `V2 déployé: ${d.contract_address}` });
  });

  $('v2-state').addEventListener('click', async () => {
    await runAction(async () => api('/v2/state', { rpc_url: state.rpcUrl, contract_address: $('v2-contract').value.trim() }), {
      version: 'v2', successMessage: () => 'État V2 rafraîchi.'
    });
  });

  $('v2-join').addEventListener('click', async () => {
    await runAction(async () => api('/v2/join', {
      rpc_url: state.rpcUrl,
      contract_address: $('v2-contract').value.trim(),
      playerB_private_key: state.playerBKey,
    }), { version: 'v2', successMessage: () => 'B a rejoint la partie V2.' });
  });

  $('v2-guess').addEventListener('click', async () => {
    const guess = Number($('v2-guess-value').value);
    const data = await runAction(async () => api('/v2/guess', {
      rpc_url: state.rpcUrl,
      contract_address: $('v2-contract').value.trim(),
      playerB_private_key: state.playerBKey,
      guess,
    }), { version: 'v2', successMessage: d => `Guess V2 envoyé: ${d.result_label}` });
    setGuessBanner('v2', data.result_label, guess);
  });
}

function bindV3() {
  $('v3-deploy').addEventListener('click', async () => {
    await runAction(async () => {
      const data = await api('/v3/deploy', { rpc_url: state.rpcUrl, deployer_private_key: state.playerAKey });
      $('v3-contract').value = data.contract_address;
      return data;
    }, { version: 'v3', successMessage: d => `V3 déployé: ${d.contract_address}` });
  });

  $('v3-create').addEventListener('click', async () => {
    await runAction(async () => {
      const playerBAddress = await resolvedPlayerBAddress();
      const data = await api('/v3/create_game', {
        rpc_url: state.rpcUrl,
        contract_address: $('v3-contract').value.trim(),
        playerA_private_key: state.playerAKey,
        playerB_address: playerBAddress,
        secret_number: Number($('v3-secret').value),
        max_attempts: Number($('v3-max').value),
        stake_eth: $('v3-stake').value,
      });
      $('v3-game-id').value = data.game_id;
      return data;
    }, { version: 'v3', successMessage: d => `Game V3 créée: ${d.game_id}` });
  });

  $('v3-list').addEventListener('click', async () => {
    await runAction(async () => api('/v3/list_games', { rpc_url: state.rpcUrl, contract_address: $('v3-contract').value.trim() }), { version: 'v3', successMessage: () => 'Liste V3 chargée.' });
  });

  $('v3-state').addEventListener('click', async () => {
    await runAction(async () => api('/v3/state', {
      rpc_url: state.rpcUrl,
      contract_address: $('v3-contract').value.trim(),
      game_id: Number($('v3-game-id').value),
    }), { version: 'v3', successMessage: () => 'État V3 rafraîchi.' });
  });

  $('v3-join').addEventListener('click', async () => {
    await runAction(async () => api('/v3/join_game', {
      rpc_url: state.rpcUrl,
      contract_address: $('v3-contract').value.trim(),
      game_id: Number($('v3-game-id').value),
      playerB_private_key: state.playerBKey,
    }), { version: 'v3', successMessage: () => 'B a rejoint la game V3.' });
  });

  $('v3-guess').addEventListener('click', async () => {
    const guess = Number($('v3-guess-value').value);
    const data = await runAction(async () => api('/v3/guess', {
      rpc_url: state.rpcUrl,
      contract_address: $('v3-contract').value.trim(),
      game_id: Number($('v3-game-id').value),
      playerB_private_key: state.playerBKey,
      guess,
    }), { version: 'v3', successMessage: d => `Guess V3 envoyé: ${d.result_label}` });
    setGuessBanner('v3', data.result_label, guess);
  });
}

function bindV4() {
  $('v4-prepare').addEventListener('click', async () => {
    await runAction(async () => {
      const data = await api('/v4/prepare', { secret_number: Number($('v4-secret').value) });
      state.v4MerkleRoot = data.merkle_root;
      saveSettings();
      return { merkle_root: data.merkle_root, info: 'Racine préparée. Déploie maintenant.' };
    }, { version: 'v4', successMessage: () => 'Racine Merkle V4 préparée.' });
  });

  $('v4-deploy').addEventListener('click', async () => {
    await runAction(async () => {
      if (!state.v4MerkleRoot) throw new Error('Prépare d’abord la racine Merkle.');
      const playerBAddress = await resolvedPlayerBAddress();
      const data = await api('/v4/deploy', {
        rpc_url: state.rpcUrl,
        playerA_private_key: state.playerAKey,
        playerB_address: playerBAddress,
        merkle_root: state.v4MerkleRoot,
        max_attempts: Number($('v4-max').value),
        stake_eth: $('v4-stake').value,
      });
      $('v4-contract').value = data.contract_address;
      return data;
    }, { version: 'v4', successMessage: d => `V4 déployé: ${d.contract_address}` });
  });

  $('v4-state').addEventListener('click', async () => {
    await runAction(async () => api('/v4/state', { rpc_url: state.rpcUrl, contract_address: $('v4-contract').value.trim() }), { version: 'v4', successMessage: () => 'État V4 rafraîchi.' });
  });

  $('v4-join').addEventListener('click', async () => {
    await runAction(async () => api('/v4/join', {
      rpc_url: state.rpcUrl,
      contract_address: $('v4-contract').value.trim(),
      playerB_private_key: state.playerBKey,
    }), { version: 'v4', successMessage: () => 'B a rejoint la partie V4.' });
  });

  $('v4-submit-guess').addEventListener('click', async () => {
    const guess = Number($('v4-guess-value').value);
    await runAction(async () => api('/v4/submit_guess', {
      rpc_url: state.rpcUrl,
      contract_address: $('v4-contract').value.trim(),
      playerB_private_key: state.playerBKey,
      guess,
    }), { version: 'v4', successMessage: () => `Guess V4 soumis: ${guess}` });
    setGuessBanner('v4', 'guess soumis, attente de résolution', guess);
  });

  $('v4-resolve-guess').addEventListener('click', async () => {
    const guess = Number($('v4-guess-value').value);
    const data = await runAction(async () => api('/v4/resolve_guess', {
      rpc_url: state.rpcUrl,
      contract_address: $('v4-contract').value.trim(),
      playerA_private_key: state.playerAKey,
      secret_number: Number($('v4-secret').value),
      guess,
    }), { version: 'v4', successMessage: d => `Guess V4 résolu: ${d.result_label}` });
    setGuessBanner('v4', data.result_label, guess);
  });
}

async function init() {
  loadSettings();
  applyTheme(state.theme);
  initTabs();
  initSettings();
  bindV1();
  bindV2();
  bindV3();
  bindV4();
  await refreshBackendState();
  await refreshAccounts();
}

init();
