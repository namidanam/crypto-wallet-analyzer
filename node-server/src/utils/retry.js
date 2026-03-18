function isRetriableError(err) {
  const status = err?.response?.status;
  if (typeof status === 'number') {
    if (status === 429) return true;
    if (status >= 500) return true;
    return false; // 4xx is usually a permanent request/config issue
  }

  const code = err?.code;
  // Common transient Node/axios codes.
  return (
    code === 'EAI_AGAIN' ||
    code === 'ENOTFOUND' ||
    code === 'ECONNRESET' ||
    code === 'ECONNREFUSED' ||
    code === 'ETIMEDOUT' ||
    code === 'ESOCKETTIMEDOUT' ||
    code === 'EPIPE'
  );
}

export async function retryWithBackoff(fn, retries = 5, options = {}) {
  const shouldRetry = options.shouldRetry || isRetriableError;
  const maxDelayMs = options.maxDelayMs ?? 30000;
  let delayMs = options.initialDelayMs ?? 1000;

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const retriable = shouldRetry(err);
      const status = err?.response?.status;
      const code = err?.code;

      if (!retriable || attempt === retries) throw err;

      const base = Math.min(delayMs, maxDelayMs);
      const jitter = Math.floor(Math.random() * 250); // keep logs readable
      const waitMs = base + jitter;

      console.log(
        `Retry attempt ${attempt}/${retries} in ${waitMs}ms` +
          (status ? ` (status ${status})` : '') +
          (code ? ` (code ${code})` : '') +
          (err?.message ? `: ${err.message}` : '')
      );

      await new Promise(res => setTimeout(res, waitMs));
      delayMs *= 2;
    }
  }
}

export default {
  retryWithBackoff
};
