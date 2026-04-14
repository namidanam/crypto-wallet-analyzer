import React, { useState } from 'react';
import { walletService, RiskAnalysisResult } from '../services/api';
import TickerTape from '../components/TickerTape';
import GlowButton from '../components/GlowButton';
import './WalletsComparison.css';

export default function WalletsComparison() {
  const SUPPORTED_CHAINS = [
    { id: 'eth-mainnet', name: 'Ethereum', icon: 'Ξ' },
    { id: 'matic-mainnet', name: 'Polygon', icon: '⬡' },
    { id: 'bsc-mainnet', name: 'BNB Chain', icon: '◆' },
    { id: 'btc-mainnet', name: 'Bitcoin', icon: '₿' },
    { id: 'doge-mainnet', name: 'Dogecoin', icon: 'Ð' },
    { id: 'ltc-mainnet', name: 'Litecoin', icon: 'Ł' },
  ];

  const [addr1, setAddr1] = useState('');
  const [addr2, setAddr2] = useState('');
  const [chain1, setChain1] = useState('eth-mainnet');
  const [chain2, setChain2] = useState('eth-mainnet');
  const [res1, setRes1] = useState<RiskAnalysisResult | null>(null);
  const [res2, setRes2] = useState<RiskAnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleBenchmark = async () => {
    if (!addr1 || !addr2) {
      setError('Please provide two wallet addresses to compare.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [r1, r2] = await Promise.all([
        walletService.analyzeWalletRisk({ address: addr1, chain: chain1 }),
        walletService.analyzeWalletRisk({ address: addr2, chain: chain2 })
      ]);
      setRes1(r1);
      setRes2(r2);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Comparison failed. Check API connectivity.');
    } finally {
      setLoading(false);
    }
  };

  const WalletCard = ({ title, res, address, type }: { title: string, res: RiskAnalysisResult | null, address: string, type: 'INT' | 'EXT' }) => (
    <div className="vault-card entity-card">
      <div className="entity-header">
        <div className={`entity-icon ${type === 'INT' ? 'primary-icon' : 'warning-icon'}`} 
             style={{ fontSize: '1rem', fontWeight: 'bold' }}>{type}</div>
        <div>
          <div className="label-sm">{title}</div>
          <h2 className="display-md vault-text-primary">
            {res ? `${res.tier} Account` : 'Awaiting Entry...'}
          </h2>
          <div className="body-sm font-mono">{address || '0x000...000'}</div>
        </div>
      </div>

      {res && (
        <>
          <div style={{ padding: '1rem', background: 'var(--surface)', borderRadius: 'var(--radius-md)', margin: '1rem 0' }}>
            <div className="label-sm">Security Score</div>
            <div className="score-display">
              <span className={`score-value ${res.score > 70 ? 'positive' : res.score > 40 ? 'warning' : 'negative'}`}>
                {res.score}
              </span>
              <span className="score-max">/100</span>
            </div>
            <div className={`status-badge ${res.score > 70 ? 'positive' : res.score > 40 ? 'warning' : 'negative'}`}>
              {res.score > 70 ? '✓ Optimized' : res.score > 40 ? '! Sub-optimal' : '⚠ Critical Alert'}
            </div>
          </div>

          <div className="asset-balance">
            <div className="label-sm">Cumulative Volume</div>
            <h3 className="display-md vault-text-primary">
              ${(res.total_volume || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </h3>
            <div className="body-sm">Total interaction volume at scan time.</div>
          </div>
          
          <div className="metrics-grid" style={{ marginTop: '1.5rem' }}>
             <div style={{ padding: '1rem', border: '1px solid var(--outline)', borderRadius: 'var(--radius-md)' }}>
                <div className="label-sm">Total TXs</div>
                <div className="vault-text-primary" style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{res.tx_count}</div>
             </div>
             <div style={{ padding: '1rem', border: '1px solid var(--outline)', borderRadius: 'var(--radius-md)' }}>
                <div className="label-sm">Gini Index</div>
                <div className="vault-text-primary" style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{res.gini?.toFixed(3) || '0.000'}</div>
             </div>
          </div>
        </>
      )}
    </div>
  );

  return (
    <div className="vault-page fade-in-up">
      <TickerTape />

      <header className="page-header">
        <h1 className="display-lg vault-text-primary">Wallet Benchmarking</h1>
        <p className="body-lg">
          Institutional-grade risk assessment and performance benchmarking between primary and counterparty entities.
        </p>
        
        <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '300px' }}>
            <label className="label-sm" style={{ display: 'block', marginBottom: '8px' }}>Primary Address</label>
            <input 
              className="vault-input" 
              placeholder="0x... or base58 address" 
              value={addr1} 
              onChange={(e) => setAddr1(e.target.value)} 
              style={{ width: '100%', marginBottom: '0.5rem' }}
            />
            <select
              value={chain1}
              onChange={(e) => setChain1(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem 1rem',
                background: 'var(--surface-container-highest)',
                color: 'var(--on-surface)',
                border: '1px solid var(--outline)',
                borderRadius: 'var(--radius-md)',
                fontFamily: 'var(--font-body)',
                fontSize: '0.875rem',
                cursor: 'pointer',
                appearance: 'none',
                WebkitAppearance: 'none',
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%239CA3AF' d='M2 4l4 4 4-4'/%3E%3C/svg%3E")`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 0.75rem center',
                paddingRight: '2rem',
              }}
            >
              {SUPPORTED_CHAINS.map(c => (
                <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
              ))}
            </select>
          </div>
          <div style={{ flex: 1, minWidth: '300px' }}>
            <label className="label-sm" style={{ display: 'block', marginBottom: '8px' }}>Counterparty Address</label>
            <input 
              className="vault-input" 
              placeholder="0x... or base58 address" 
              value={addr2} 
              onChange={(e) => setAddr2(e.target.value)} 
              style={{ width: '100%', marginBottom: '0.5rem' }}
            />
            <select
              value={chain2}
              onChange={(e) => setChain2(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem 1rem',
                background: 'var(--surface-container-highest)',
                color: 'var(--on-surface)',
                border: '1px solid var(--outline)',
                borderRadius: 'var(--radius-md)',
                fontFamily: 'var(--font-body)',
                fontSize: '0.875rem',
                cursor: 'pointer',
                appearance: 'none',
                WebkitAppearance: 'none',
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%239CA3AF' d='M2 4l4 4 4-4'/%3E%3C/svg%3E")`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 0.75rem center',
                paddingRight: '2rem',
              }}
            >
              {SUPPORTED_CHAINS.map(c => (
                <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
              ))}
            </select>
          </div>
          <GlowButton variant="primary" onClick={handleBenchmark} disabled={loading}>
            {loading ? 'Analyzing...' : 'Execute Benchmark'}
          </GlowButton>
        </div>
        {error && <div style={{ color: 'var(--error)', marginTop: '1rem' }} className="body-sm">⚠ {error}</div>}
      </header>

      <section className="comparison-section fade-in-up" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '2.5rem', marginTop: '2.5rem' }}>
        <WalletCard title="Primary Entity" res={res1} address={addr1} type="INT" />
        <WalletCard title="Comparison Target" res={res2} address={addr2} type="EXT" />
      </section>
      
      {res1 && res2 && (
        <div className="vault-card fade-in-up" style={{ borderLeft: '4px solid var(--primary)', marginTop: '3rem' }}>
           <div className="label-sm" style={{ color: 'var(--primary)' }}>Vault Recommendation</div>
           <h3 className="display-md vault-text-primary" style={{ fontSize: '1.5rem', margin: '8px 0'}}>
             {res2.score < res1.score ? 'CAUTION: RISK DISPARITY DETECTED' : 'BENCHMARK VERIFIED'}
           </h3>
           <p className="body-sm">
             The counterparty profile shows a security score of <strong className="vault-text-primary">{res2.score}/100</strong>. 
             {res2.score < 50 ? ' Interaction restricted based on automated institutional protocols.' : ' Within acceptable operational bounds.'}
           </p>
        </div>
      )}
    </div>
  );
}
