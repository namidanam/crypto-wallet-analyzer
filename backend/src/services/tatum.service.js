import axios from 'axios';
import { rateLimit } from '../utils/rateLimiter.js';
import { logInfo } from '../utils/logger.js';

// Chain identifier mapping for Tatum API
const CHAIN_MAPPING = {
  // EVM chains
  'ethereum-mainnet': 'ethereum',
  'eth-mainnet': 'ethereum',
  'polygon-mainnet': 'polygon',
  'matic-mainnet': 'polygon',
  'bsc-mainnet': 'bsc',
  'binance-mainnet': 'bsc',
  // UTXO chains
  'btc-mainnet': 'bitcoin',
  'bitcoin-mainnet': 'bitcoin',
  'doge-mainnet': 'dogecoin',
  'dogecoin-mainnet': 'dogecoin',
  'ltc-mainnet': 'litecoin',
  'litecoin-mainnet': 'litecoin'
};

const SUPPORTED_CHAINS = Object.keys(CHAIN_MAPPING);

const PAGE_SIZE = 50;
const BLOCKSTREAM_PAGE = 25;
const BLOCKCYPHER_PAGE_LIMIT = 50;

const DEFAULT_BLOCKSTREAM_BASE = 'https://blockstream.info/api';

function blockstreamBaseUrl() {
  return (process.env.BLOCKSTREAM_API_BASE || DEFAULT_BLOCKSTREAM_BASE).replace(/\/$/, '');
}

/** Tatum confirmed times are Unix seconds; mempool may be ms — see Tatum BtcTx schema. */
function utxoTimestampMs(tx) {
  const raw = tx.created ?? tx.blockTime ?? tx.time;
  if (raw == null) return Date.now();
  if (typeof raw === 'number') {
    if (raw < 1e12) return raw * 1000;
    return raw;
  }
  const ms = new Date(raw).getTime();
  return Number.isFinite(ms) ? ms : Date.now();
}

function mapTatumUtxoTx(tx, address) {
  // UTXO txns from Tatum have inputs/outputs arrays rather than a top-level amount.
  // Compute the wallet-relevant value by summing outputs addressed to `address`.
  let computedValue = null;
  const outputs = tx.outputs || tx.vout || [];
  const inputs = tx.inputs || tx.vin || [];

  if (outputs.length) {
    let received = 0;
    for (const o of outputs) {
      const addrs = o.addresses || (o.address ? [o.address] : []);
      if (addrs.includes(address)) {
        received += Number(o.value || 0) || 0;
      }
    }
    computedValue = received;
  }

  // Determine from/to from inputs/outputs when available
  let from = tx.from || tx.sender || address;
  let to = tx.to || tx.recipient || address;
  if (inputs.length) {
    const firstInputAddrs = inputs[0]?.addresses || (inputs[0]?.address ? [inputs[0].address] : []);
    if (firstInputAddrs.length) from = firstInputAddrs[0];
  }
  if (outputs.length) {
    for (const o of outputs) {
      const addrs = o.addresses || (o.address ? [o.address] : []);
      if (addrs.length && !addrs.includes(address)) {
        to = addrs[0];
        break;
      }
    }
  }

  const finalValue = computedValue != null ? String(computedValue) : String(tx.amount ?? tx.value ?? '0');

  return {
    txHash: tx.txid || tx.txId || tx.hash || tx.id,
    blockNumber: Number.isFinite(Number(tx.blockNumber)) ? Number(tx.blockNumber) : 0,
    timestamp: utxoTimestampMs(tx),
    from,
    to,
    value: finalValue,
    assetType: 'NATIVE',
    provider: 'tatum'
  };
}

function mapTatumEvmTx(tx, address) {
  return {
    txHash: tx.txid || tx.txId || tx.hash || tx.id,
    blockNumber: tx.blockNumber || tx.block || 0,
    timestamp: new Date(tx.created || tx.blockTime || tx.time || Date.now()).getTime(),
    from: tx.from || tx.sender || address,
    to: tx.to || tx.recipient || address,
    value: tx.amount || tx.value || '0',
    assetType: 'NATIVE',
    provider: 'tatum'
  };
}

function shouldFallbackFromTatum(err) {
  const status = err?.response?.status;
  return status === 401 || status === 402 || status === 403;
}

function parseTatumOffset(pageToken, prefix) {
  if (pageToken == null) return 0;
  const p = `${prefix}:`;
  if (!pageToken.startsWith(p)) {
    throw new Error(`Invalid pagination token for Tatum (expected ${prefix}:…)`);
  }
  const n = parseInt(pageToken.slice(p.length), 10);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Blockstream Esplora — public fallback when Tatum is missing, expired, or over quota (Bitcoin mainnet).
 * @param {string|null} lastTxid — null = first page (/txs), else /txs/chain/:lastTxid
 */
async function fetchBlockstreamBitcoinTxs(address, lastTxid) {
  const base = blockstreamBaseUrl();
  const url =
    lastTxid == null || lastTxid === ''
      ? `${base}/address/${address}/txs`
      : `${base}/address/${address}/txs/chain/${lastTxid}`;

  const response = await axios.get(url, { timeout: 30000 });
  const data = response.data;

  if (!Array.isArray(data)) {
    throw new Error('Invalid response format from Blockstream API');
  }

  const transactions = data.map(tx => {
    const t = tx.status?.block_time;
    const timestamp =
      t != null && Number.isFinite(Number(t)) ? Number(t) * 1000 : Date.now();
    const voutSum = Array.isArray(tx.vout)
      ? tx.vout.reduce((s, o) => s + (Number(o.value) || 0), 0)
      : 0;

    return {
      txHash: tx.txid,
      blockNumber:
        tx.status?.block_height != null && Number.isFinite(Number(tx.status.block_height))
          ? Number(tx.status.block_height)
          : 0,
      timestamp,
      from: address,
      to: address,
      value: String(voutSum || 0),
      assetType: 'NATIVE',
      provider: 'blockstream'
    };
  });

  const last = data.length ? data[data.length - 1] : null;
  const nextPageToken =
    last && data.length === BLOCKSTREAM_PAGE ? `b:${last.txid}` : null;

  return { transactions, nextPageToken };
}

function mapBlockcypherTx(tx, walletAddress) {
  const ts = tx.confirmed
    ? new Date(tx.confirmed).getTime()
    : tx.received
      ? new Date(tx.received).getTime()
      : Date.now();

  let value = '0';
  if (Array.isArray(tx.outputs)) {
    let sum = 0;
    for (const o of tx.outputs) {
      const addrs = o.addresses;
      if (Array.isArray(addrs) && addrs.includes(walletAddress)) {
        const v = o.value;
        sum += typeof v === 'number' && Number.isFinite(v) ? v : parseInt(String(v || '0'), 10) || 0;
      }
    }
    value = String(sum);
  }
  if (value === '0' && tx.total != null) {
    const t = tx.total;
    value = String(typeof t === 'number' ? t : parseInt(String(t), 10) || 0);
  }

  const bh = tx.block_height;
  return {
    txHash: tx.hash,
    blockNumber: typeof bh === 'number' && bh >= 0 ? bh : 0,
    timestamp: Number.isFinite(ts) ? ts : Date.now(),
    from: walletAddress,
    to: walletAddress,
    value,
    assetType: 'NATIVE',
    provider: 'blockcypher'
  };
}

/**
 * BlockCypher public API — Dogecoin / Litecoin when Tatum is unavailable.
 * @see https://www.blockcypher.com/dev/dogecoin/
 */
async function fetchBlockcypherUtxoTxs(coinPath, address, beforeHeight, bcSlug) {
  const params = { limit: BLOCKCYPHER_PAGE_LIMIT };
  if (beforeHeight != null && Number.isFinite(Number(beforeHeight))) {
    params.before = Number(beforeHeight);
  }
  const bcToken = process.env.BLOCKCYPHER_TOKEN;
  if (bcToken) params.token = bcToken;

  const url = `https://api.blockcypher.com/v1/${coinPath}/addrs/${encodeURIComponent(address)}/full`;
  const { data } = await axios.get(url, { params, timeout: 30000 });

  if (data?.error) {
    throw new Error(`BlockCypher: ${data.error}`);
  }

  const txs = data.txs || [];
  const transactions = txs.map(tx => mapBlockcypherTx(tx, address));

  let pivotHeight = null;
  for (let i = txs.length - 1; i >= 0; i--) {
    const bh = txs[i].block_height;
    if (typeof bh === 'number' && bh >= 0) {
      pivotHeight = bh;
      break;
    }
  }

  const nextPageToken =
    data.hasMore && pivotHeight != null ? `cy:${bcSlug}:${pivotHeight}` : null;

  return { transactions, nextPageToken };
}

async function fetchDogeLiteTxs(address, chain, pageToken, mappedChain) {
  const bcSlug = mappedChain === 'dogecoin' ? 'doge' : 'ltc';
  const coinPath = `${bcSlug}/main`;
  const cyPrefix = `cy:${bcSlug}:`;

  if (pageToken && pageToken.startsWith(cyPrefix)) {
    const h = parseInt(pageToken.slice(cyPrefix.length), 10);
    return fetchBlockcypherUtxoTxs(coinPath, address, h, bcSlug);
  }

  if (pageToken && pageToken.startsWith('u:')) {
    const offset = parseTatumOffset(pageToken, 'u');
    return fetchTatumUtxoInternal(address, mappedChain, offset, 'u');
  }

  const apiKey = process.env.TATUM_API_KEY;
  if (apiKey) {
    try {
      await rateLimit();
      const result = await fetchTatumUtxoInternal(address, mappedChain, 0, 'u');
      // If Tatum returned data, use it; otherwise fall through to BlockCypher
      if (result.transactions.length > 0) {
        return result;
      }
      logInfo(
        `[tatum.service] Tatum returned 0 txs for ${chain}; trying BlockCypher fallback`
      );
    } catch (err) {
      if (!shouldFallbackFromTatum(err)) {
        throw wrapTatumError(address, chain, err);
      }
      logInfo(
        `[tatum.service] Tatum unavailable for ${chain} (${err?.response?.status ?? 'n/a'}); using BlockCypher fallback`
      );
    }
  } else {
    logInfo(`[tatum.service] No TATUM_API_KEY; using BlockCypher for ${chain}`);
  }

  return fetchBlockcypherUtxoTxs(coinPath, address, null, bcSlug);
}

async function fetchTatumUtxoInternal(address, mappedChain, offset, pageTokenPrefix) {
  const apiKey = process.env.TATUM_API_KEY;
  if (!apiKey) {
    throw new Error('TATUM_API_KEY is not set. Cannot fetch Tatum transactions.');
  }

  let response;
  const candidates = [
    {
      url: `https://api.tatum.io/v3/${mappedChain}/transaction/address/${address}`,
      params: { pageSize: PAGE_SIZE, offset }
    },
    {
      url: `https://api.tatum.io/v3/${mappedChain}/address/${address}/transactions`,
      params: {}
    },
    {
      url: `https://api.tatum.io/v3/${mappedChain}/address/${address}`,
      params: { pageSize: PAGE_SIZE, offset }
    }
  ];

  let lastErr;
  for (const candidate of candidates) {
    try {
      response = await axios.get(candidate.url, {
        params: candidate.params,
        headers: { 'x-api-key': apiKey },
        timeout: 30000
      });
      lastErr = null;
      break;
    } catch (e) {
      if (e?.response?.status === 404) {
        lastErr = e;
        continue;
      }
      throw e;
    }
  }
  if (!response && lastErr) throw lastErr;

  const data = response.data;
  if (!data) {
    throw new Error('Invalid response format from Tatum API');
  }

  let transactions = Array.isArray(data) ? data : (data.txs || data.transactions || data.result || []);

  if (!Array.isArray(transactions)) {
    throw new Error('Invalid transactions format from Tatum API');
  }

  const mapped = transactions.map(tx => mapTatumUtxoTx(tx, address));
  const nextPageToken =
    transactions.length === PAGE_SIZE ? `${pageTokenPrefix}:${offset + PAGE_SIZE}` : null;

  return { transactions: mapped, nextPageToken };
}

async function fetchBitcoinTxs(address, chain, pageToken) {
  if (pageToken && pageToken.startsWith('b:')) {
    const lastTxid = pageToken.slice(2);
    return fetchBlockstreamBitcoinTxs(address, lastTxid || null);
  }

  if (pageToken && pageToken.startsWith('t:')) {
    const offset = parseTatumOffset(pageToken, 't');
    return fetchTatumUtxoInternal(address, 'bitcoin', offset, 't');
  }

  const apiKey = process.env.TATUM_API_KEY;
  if (apiKey) {
    try {
      await rateLimit();
      const result = await fetchTatumUtxoInternal(address, 'bitcoin', 0, 't');
      if (result.transactions.length > 0) {
        return result;
      }
      logInfo(
        `[tatum.service] Tatum returned 0 txs for Bitcoin; trying Blockstream fallback`
      );
    } catch (err) {
      if (!shouldFallbackFromTatum(err)) {
        throw wrapTatumError(address, chain, err);
      }
      logInfo(
        `[tatum.service] Tatum unavailable for Bitcoin (${err?.response?.status ?? 'n/a'}); using Blockstream fallback`
      );
    }
  } else {
    logInfo('[tatum.service] No TATUM_API_KEY; using Blockstream for Bitcoin');
  }

  return fetchBlockstreamBitcoinTxs(address, null);
}

function wrapTatumError(address, chain, err) {
  const status = err?.response?.status;
  const code = err?.code;
  const serverMsg =
    err?.response?.data?.error_message ||
    err?.response?.data?.message ||
    err?.response?.data?.error ||
    null;

  console.error(
    `Tatum API Error for ${address} on ${chain}: ${err.message}` +
      (status ? ` (status ${status})` : '') +
      (code ? ` (code ${code})` : '') +
      (serverMsg ? ` (server: ${serverMsg})` : '')
  );

  if (err?.response?.data) {
    console.error('Full error response:', JSON.stringify(err.response.data, null, 2));
  }

  const wrapped = new Error(
    `Failed to fetch transactions from Tatum` +
      (status ? ` (status ${status})` : '') +
      (code ? ` (code ${code})` : '') +
      (serverMsg ? `: ${serverMsg}` : err?.message ? `: ${err.message}` : '')
  );
  wrapped.code = code;
  wrapped.response = err?.response;
  return wrapped;
}

/**
 * @param {string} address
 * @param {string} chain
 * @param {string|null} pageToken — null first page; then opaque tokens from prior response (`nextPageToken`)
 * @returns {Promise<{ transactions: object[], nextPageToken: string|null }>}
 */
async function fetchTatumTxs(address, chain, pageToken = null) {
  if (!CHAIN_MAPPING[chain]) {
    throw new Error(`Chain ${chain} is not supported by Tatum. Supported chains: ${SUPPORTED_CHAINS.join(', ')}`);
  }

  const mappedChain = CHAIN_MAPPING[chain];

  await rateLimit();

  try {
    if (mappedChain === 'bitcoin') {
      return await fetchBitcoinTxs(address, chain, pageToken);
    }

    if (mappedChain === 'dogecoin' || mappedChain === 'litecoin') {
      return await fetchDogeLiteTxs(address, chain, pageToken, mappedChain);
    }

    const apiKey = process.env.TATUM_API_KEY;
    if (!apiKey) {
      throw new Error('TATUM_API_KEY is not set. Cannot fetch Tatum transactions.');
    }

    const offset = pageToken == null ? 0 : parseTatumOffset(pageToken, 'e');

    const response = await axios.get(
      `https://api.tatum.io/v3/ledger/transaction/address/${address}`,
      {
        params: {
          chain: mappedChain,
          pageSize: PAGE_SIZE,
          offset,
          sort: 'DESC'
        },
        headers: { 'x-api-key': apiKey },
        timeout: 30000
      }
    );

    const data = response.data;
    if (!data) {
      throw new Error('Invalid response format from Tatum API');
    }

    const transactions = data.result || (Array.isArray(data) ? data : []);
    if (!Array.isArray(transactions)) {
      throw new Error('Invalid transactions format from Tatum API');
    }

    const mapped = transactions.map(tx => mapTatumEvmTx(tx, address));
    const nextPageToken =
      transactions.length === PAGE_SIZE ? `e:${offset + PAGE_SIZE}` : null;

    return { transactions: mapped, nextPageToken };
  } catch (err) {
    if (err instanceof Error) {
      if (
        err.message.includes('Invalid pagination token') ||
        err.message.includes('not supported by Tatum') ||
        err.message.includes('TATUM_API_KEY is not set') ||
        err.message.includes('Invalid response format from Blockstream API') ||
        err.message.startsWith('BlockCypher:') ||
        err.message.includes('Invalid transactions format from Tatum API') ||
        err.message.includes('Invalid response format from Tatum API')
      ) {
        throw err;
      }
      if (err.message.startsWith('Failed to fetch transactions from Tatum')) throw err;
    }

    if (err?.config?.url && !String(err.config.url).includes('tatum.io')) {
      throw err;
    }

    throw wrapTatumError(address, chain, err);
  }
}

export { fetchTatumTxs };
