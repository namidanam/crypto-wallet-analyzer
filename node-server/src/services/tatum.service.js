import axios from 'axios';
import { rateLimit } from '../utils/rateLimiter.js';

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

const UTXO_CHAINS = ['bitcoin', 'dogecoin', 'litecoin'];
const SUPPORTED_CHAINS = Object.keys(CHAIN_MAPPING);

async function fetchTatumTxs(address, chain, offset = 0) {
  // Validate chain is supported
  if (!CHAIN_MAPPING[chain]) {
    throw new Error(`Chain ${chain} is not supported by Tatum. Supported chains: ${SUPPORTED_CHAINS.join(', ')}`);
  }

  // Map the chain to correct Tatum format
  const mappedChain = CHAIN_MAPPING[chain];

  await rateLimit();

  const apiKey = process.env.TATUM_API_KEY;

  if (!apiKey) {
    throw new Error('TATUM_API_KEY is not set. Cannot fetch Tatum transactions.');
  }

  try {
    let response;
    const pageSize = 50;
    
    // Use different endpoints for UTXO vs EVM chains
    if (UTXO_CHAINS.includes(mappedChain)) {
      // Tatum UTXO address transactions endpoint varies across versions.
      // Prefer the paginated transaction endpoint; fall back on older paths on 404.
      const candidates = [
        {
          url: `https://api.tatum.io/v3/${mappedChain}/transaction/address/${address}`,
          params: { pageSize, offset },
        },
        {
          url: `https://api.tatum.io/v3/${mappedChain}/address/${address}/transactions`,
          params: {},
        },
        {
          url: `https://api.tatum.io/v3/${mappedChain}/address/${address}`,
          params: { pageSize, offset },
        },
      ];

      let lastErr;
      for (const candidate of candidates) {
        try {
          response = await axios.get(candidate.url, {
            params: candidate.params,
            headers: { 'x-api-key': apiKey },
            timeout: 30000,
          });
          lastErr = null;
          break;
        } catch (e) {
          // Try next candidate only on "route not found".
          if (e?.response?.status === 404) {
            lastErr = e;
            continue;
          }
          throw e;
        }
      }
      if (!response && lastErr) throw lastErr;
    } else {
      // EVM chains use /v3/ledger/transaction/address/
      response = await axios.get(
        `https://api.tatum.io/v3/ledger/transaction/address/${address}`,
        {
          params: {
            chain: mappedChain,
            pageSize,
            offset: offset,
            sort: 'DESC'
          },
          headers: {
            'x-api-key': apiKey
          },
          timeout: 30000
        }
      );
    }

    const data = response.data;

    if (!data) {
      throw new Error('Invalid response format from Tatum API');
    }

    // Handle different response formats for UTXO vs EVM
    let transactions = [];
    
    if (UTXO_CHAINS.includes(mappedChain)) {
      // UTXO response is typically an array or object with txs/transactions
      transactions = Array.isArray(data) ? data : (data.txs || data.transactions || data.result || []);
    } else {
      // EVM response structure
      transactions = data.result || (Array.isArray(data) ? data : []);
    }

    if (!Array.isArray(transactions)) {
      throw new Error('Invalid transactions format from Tatum API');
    }

    return {
      transactions: transactions.map(tx => ({
        txHash: tx.txid || tx.txId || tx.hash || tx.id,
        blockNumber: tx.blockNumber || tx.block || 0,
        timestamp: new Date(tx.created || tx.blockTime || tx.time || Date.now()).getTime(),
        from: tx.from || tx.sender || address,
        to: tx.to || tx.recipient || address,
        value: tx.amount || tx.value || '0',
        assetType: 'NATIVE'
      })),
      nextOffset: offset + pageSize // Return next offset for pagination
    };
  } catch (err) {
    const status = err?.response?.status;
    const code = err?.code;
    const serverMsg =
      err?.response?.data?.error_message ||
      err?.response?.data?.message ||
      err?.response?.data?.error ||
      null;
    
    // Log full response data for debugging
    const fullError = err?.response?.data;

    console.error(
      `Tatum API Error for ${address} on ${chain}: ${err.message}` +
        (status ? ` (status ${status})` : '') +
        (code ? ` (code ${code})` : '') +
        (serverMsg ? ` (server: ${serverMsg})` : '')
    );
    
    // Log full error response for debugging
    if (fullError) {
      console.error('Full error response:', JSON.stringify(fullError, null, 2));
    }

    // Preserve axios metadata for retry decisions.
    const wrapped = new Error(
      `Failed to fetch transactions from Tatum` +
        (status ? ` (status ${status})` : '') +
        (code ? ` (code ${code})` : '') +
        (serverMsg ? `: ${serverMsg}` : err?.message ? `: ${err.message}` : '')
    );
    wrapped.code = code;
    wrapped.response = err?.response;

    throw wrapped;
  }
}

export { fetchTatumTxs };
