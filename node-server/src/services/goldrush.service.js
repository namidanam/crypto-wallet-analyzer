import axios from 'axios';
import { rateLimit } from '../utils/rateLimiter.js';
import https from 'https';

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
        txHash: tx.tx_hash,
        blockNumber: tx.block_number,
        timestamp: new Date(tx.block_signed_at).getTime(),
        from: tx.from_address,
        to: tx.to_address,
        value: tx.value,
        assetType: 'NATIVE'
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
