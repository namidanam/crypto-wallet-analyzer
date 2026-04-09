import axios from 'axios';
import { rateLimit } from '../utils/rateLimiter.js';
import https from 'https';

const ERC20_TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';

// Chain identifier mapping for Covalent API
// NOTE: Covalent/GoldRush only supports EVM chains, NOT Bitcoin
const CHAIN_MAPPING = {
  'ethereum-mainnet': 'eth-mainnet',
  'eth-mainnet': 'eth-mainnet',
  'polygon-mainnet': 'matic-mainnet',
  'matic-mainnet': 'matic-mainnet',
  'bsc-mainnet': 'bsc-mainnet',
  'binance-mainnet': 'bsc-mainnet'
};

const SUPPORTED_CHAINS = Object.keys(CHAIN_MAPPING);

function normalizeAddress(addr) {
  if (!addr || typeof addr !== 'string') return null;
  return addr.trim().toLowerCase();
}

function safeBigIntString(value) {
  if (value === null || value === undefined) return '0';
  if (typeof value === 'bigint') return value.toString(10);
  if (typeof value === 'number') return Number.isFinite(value) ? BigInt(Math.trunc(value)).toString(10) : '0';
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return '0';
    // Covalent tends to return base-10 strings; fall back to hex if needed.
    try {
      if (trimmed.startsWith('0x') || trimmed.startsWith('0X')) return BigInt(trimmed).toString(10);
      if (/^\d+$/.test(trimmed)) return BigInt(trimmed).toString(10);
    } catch {
      return '0';
    }
  }
  return '0';
}

function tryDecodeTransferFromDecoded(decoded) {
  const params = decoded?.params;
  if (!decoded || decoded?.name !== 'Transfer' || !Array.isArray(params)) return null;

  const getParam = (names) => {
    for (const name of names) {
      const match = params.find(p => normalizeAddress(p?.name) === normalizeAddress(name) || p?.name === name);
      if (match?.value !== undefined) return match.value;
    }
    return undefined;
  };

  const from = getParam(['from', '_from', 'src', 'sender']);
  const to = getParam(['to', '_to', 'dst', 'recipient']);
  const value = getParam(['value', '_value', 'wad', 'amount']);

  if (!from || !to || value === undefined) return null;
  return {
    from: String(from),
    to: String(to),
    amount: safeBigIntString(value)
  };
}

function tryDecodeTransferFromRawLog(logEvent) {
  const topics = logEvent?.raw_log_topics;
  const data = logEvent?.raw_log_data;
  if (!Array.isArray(topics) || topics.length < 3 || typeof data !== 'string') return null;

  if (String(topics[0]).toLowerCase() !== ERC20_TRANSFER_TOPIC) return null;

  const decodeTopicAddress = (topic) => {
    if (!topic || typeof topic !== 'string') return null;
    const hex = topic.toLowerCase().startsWith('0x') ? topic.slice(2) : topic;
    if (hex.length < 40) return null;
    return `0x${hex.slice(-40)}`;
  };

  const from = decodeTopicAddress(topics[1]);
  const to = decodeTopicAddress(topics[2]);
  if (!from || !to) return null;

  return {
    from,
    to,
    amount: safeBigIntString(data)
  };
}

function extractTokenTransfers(logEvents, walletAddress) {
  if (!Array.isArray(logEvents) || !logEvents.length) return [];
  const wallet = normalizeAddress(walletAddress);

  const transfers = [];
  for (const logEvent of logEvents) {
    const decodedTransfer =
      tryDecodeTransferFromDecoded(logEvent?.decoded) ||
      tryDecodeTransferFromRawLog(logEvent);

    if (!decodedTransfer) continue;

    const fromNorm = normalizeAddress(decodedTransfer.from);
    const toNorm = normalizeAddress(decodedTransfer.to);
    if (wallet && fromNorm !== wallet && toNorm !== wallet) continue;

    const tokenAddress =
      logEvent?.sender_contract_address ||
      logEvent?.sender_address ||
      logEvent?.contract_address ||
      null;

    transfers.push({
      tokenAddress: tokenAddress ? String(tokenAddress) : null,
      tokenSymbol: logEvent?.sender_contract_ticker_symbol ? String(logEvent.sender_contract_ticker_symbol) : null,
      tokenDecimals: Number.isFinite(Number(logEvent?.sender_contract_decimals)) ? Number(logEvent.sender_contract_decimals) : null,
      from: decodedTransfer.from,
      to: decodedTransfer.to,
      amount: decodedTransfer.amount,
      logIndex: Number.isFinite(Number(logEvent?.log_offset)) ? Number(logEvent.log_offset) : null
    });
  }

  return transfers;
}

async function fetchGoldrushTxs(address, chain, cursor) {

  // Validate chain is supported
  if (!CHAIN_MAPPING[chain] && !chain.includes('eth') && !chain.includes('matic') && !chain.includes('bsc')) {
    throw new Error(`Chain ${chain} is not supported by GoldRush. Supported chains: ${SUPPORTED_CHAINS.join(', ')}`);
  }

  // Map the chain to correct Covalent format
  const mappedChain = CHAIN_MAPPING[chain] || chain;

  await rateLimit();

  const apiKey = process.env.GOLDRUSH_API_KEY;
  const forceIpv4 = process.env.GOLDRUSH_FORCE_IPV4 === 'true' || process.env.FORCE_IPV4 === 'true';

  if (!apiKey) {
    throw new Error('GOLDRUSH_API_KEY is not set. Cannot fetch Goldrush transactions.');
  }
  // :)) ((: 
  // Keep-alive improves performance for paginated fetches.
  // TLS verification should be enabled; allow opting out only if explicitly set.
  const httpsAgent = new https.Agent({
    rejectUnauthorized: process.env.GOLDRUSH_INSECURE_TLS === 'true' ? false : true,
    keepAlive: true,
  });

  try {
    const headers = {
      // GoldRush commonly uses bearer tokens; some deployments accept x-api-key style too.
      Authorization: `Bearer ${apiKey}`,
      'x-api-key': apiKey,
    };

    const params = {};
    if (cursor) params.cursor = cursor;

    const response = await axios.get(
      `https://api.covalenthq.com/v1/${mappedChain}/address/${address}/transactions_v2/`,
      {
        params: {
          key: apiKey,
          cursor // optional
        },
        timeout: 30000
      }
    );

    // Some APIs wrap payload in `data`.
    const data = response.data?.data ?? response.data;

    const items = data?.items ?? [];
    if (!Array.isArray(items)) {
      throw new Error('Invalid response format from Goldrush API');
    }

    return {
      transactions: items.map(tx => ({
        ...(() => {
          const nativeValue = tx?.value ?? '0';
          const tokenTransfers = extractTokenTransfers(tx?.log_events, address);

          const envelopeFrom = tx?.from_address;
          const envelopeTo = tx?.to_address;

          // Heuristic: when the tx carries 0 native value and has exactly one
          // ERC20 Transfer involving the wallet, treat the ERC20 transfer as the primary ledger entry.
          if (tokenTransfers.length === 1 && safeBigIntString(nativeValue) === '0') {
            const primary = tokenTransfers[0];
            return {
              txHash: tx.tx_hash,
              blockNumber: tx.block_number,
              timestamp: new Date(tx.block_signed_at).getTime(),
              from: primary.from,
              to: primary.to,
              value: primary.amount,
              assetType: 'ERC20',
              tokenAddress: primary.tokenAddress,
              tokenSymbol: primary.tokenSymbol,
              tokenDecimals: primary.tokenDecimals,
              nativeValue: safeBigIntString(nativeValue),
              tokenTransfers
            };
          }

          return {
            txHash: tx.tx_hash,
            blockNumber: tx.block_number,
            timestamp: new Date(tx.block_signed_at).getTime(),
            from: envelopeFrom,
            to: envelopeTo,
            value: safeBigIntString(nativeValue),
            assetType: tokenTransfers.length ? 'ERC20' : 'NATIVE',
            nativeValue: safeBigIntString(nativeValue),
            tokenTransfers
          };
        })()
      })),
      nextCursor: data?.pagination?.next_cursor
    };
  } catch (err) {
    const status = err?.response?.status;
    const code = err?.code;
    const serverMsg =
      err?.response?.data?.error_message ||
      err?.response?.data?.message ||
      err?.response?.data?.error ||
      null;

    console.error(
      `Goldrush API Error for ${address} on ${chain}: ${err.message}` +
        (status ? ` (status ${status})` : '') +
        (code ? ` (code ${code})` : '') +
        (serverMsg ? ` (server: ${serverMsg})` : '')
    );

    // Preserve axios metadata for retry decisions.
    const wrapped = new Error(
      `Failed to fetch transactions from Goldrush` +
        (status ? ` (status ${status})` : '') +
        (code ? ` (code ${code})` : '') +
        (serverMsg ? `: ${serverMsg}` : err?.message ? `: ${err.message}` : '')
    );
    wrapped.code = code;
    wrapped.response = err?.response;
    throw wrapped;
  }
}

export { fetchGoldrushTxs };
