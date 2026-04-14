import React, { useState } from 'react';
import { walletService } from '../services/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar
} from 'recharts';

export default function Dashboard() {
  const SUPPORTED_CHAINS = [
    { id: 'eth-mainnet', name: 'Ethereum', icon: 'Ξ' },
    { id: 'matic-mainnet', name: 'Polygon', icon: '⬡' },
    { id: 'bsc-mainnet', name: 'BNB Chain', icon: '◆' },
    { id: 'btc-mainnet', name: 'Bitcoin', icon: '₿' },
    { id: 'doge-mainnet', name: 'Dogecoin', icon: 'Ð' },
    { id: 'ltc-mainnet', name: 'Litecoin', icon: 'Ł' },
  ];

  const [address, setAddress] = useState('0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045');
  const [chain, setChain] = useState('eth-mainnet');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await walletService.analyzeWalletRisk({ address, chain });
      
      const mappedData = {
        totalValue: new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(result.total_volume),
        riskScore: result.score,
        riskLevel: `${result.tier} RISK`,
        transactionCount: result.tx_count,
        exposure: `${((result.hhi || 0) * 100).toFixed(1)}%`,
        // Charts will stay empty or show 0 until backend provides timeseries data
        history: [], 
        chainDistribution: [
          { name: chain, value: 100 }
        ]
      };
      
      setData(mappedData);
    } catch (err: any) {
      console.error("Analysis Error:", err);
      if (err.response?.status === 202) {
        setError("Wallet synchronization in progress. Please retry in 10-20 seconds.");
      } else {
        setError(err.response?.data?.message || "Internal Vault Error. Check logs.");
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="vault-page fade-in-up">
      <header className="hflex" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="display-md vault-text-primary">Institutional Analytics</h1>
          <p className="body-md">Real-time risk assessment and asset monitoring.</p>
        </div>
        <div className="hflex gap-sm" style={{ flex: 1, minWidth: '300px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="vault-card"
            style={{ padding: '0.5rem 1rem', flex: 1, maxWidth: '400px' }}
            placeholder="Wallet address (0x... or base58)"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
          <select
            value={chain}
            onChange={(e) => setChain(e.target.value)}
            style={{
              padding: '0.5rem 1rem',
              background: 'var(--surface-container-highest)',
              color: 'var(--on-surface)',
              border: '1px solid var(--outline)',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-body)',
              fontSize: '0.875rem',
              cursor: 'pointer',
              minWidth: '160px',
              appearance: 'none',
              WebkitAppearance: 'none',
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%239CA3AF' d='M2 4l4 4 4-4'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 0.75rem center',
              paddingRight: '2rem',
            }}
          >
            {SUPPORTED_CHAINS.map(c => (
              <option key={c.id} value={c.id}>
                {c.icon} {c.name}
              </option>
            ))}
          </select>
          <button className="vault-btn vault-btn-primary" onClick={handleAnalyze} disabled={loading}>
            {loading ? 'Analyzing...' : 'Analyze Risk'}
          </button>
        </div>
      </header>

      {error && (
        <div className="vault-card" style={{ borderLeft: '4px solid var(--error)', marginTop: '1rem', color: 'var(--error)' }}>
          ⚠ {error}
        </div>
      )}

      {data ? (
        <>
          {/* Top Metrics Row */}
          <div className="fade-in-up stagger-1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', marginTop: '1.5rem' }}>
            <div className="vault-card vflex gap-sm">
              <span className="label-sm">Total Asset Value</span>
              <span className="display-md vault-text-primary">{data.totalValue}</span>
              <span className="body-sm">Aggregate Volume tracked</span>
            </div>
            <div className="vault-card vflex gap-sm">
              <span className="label-sm">Risk Score / 100</span>
              <span className="display-md vault-text-accent">{data.riskScore}</span>
              <span className="body-sm vault-text-primary">{data.riskLevel}</span>
            </div>
            <div className="vault-card vflex gap-sm">
              <span className="label-sm">Transaction Volume</span>
              <span className="display-md vault-text-primary">{data.transactionCount}</span>
              <span className="body-sm vault-text-primary">Cumulative count</span>
            </div>
            <div className="vault-card vflex gap-sm">
              <span className="label-sm">Concentration (HHI)</span>
              <span className="display-md vault-text-error">{data.exposure}</span>
              <span className="body-sm vault-text-error">Asset centralization</span>
            </div>
          </div>

          {/* Charts Row */}
          <div className="fade-in-up stagger-2" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginTop: '1rem' }}>
            <div className="vault-card vflex gap-md">
              <span className="label-sm">Chain Distribution</span>
              <div style={{ height: '300px', width: '100%' }}>
                <ResponsiveContainer>
                  <BarChart data={data.chainDistribution} layout="vertical">
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" stroke="var(--on-surface-variant)" axisLine={false} tickLine={false} width={80} />
                    <Tooltip cursor={{ fill: 'var(--surface-variant)' }} contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--outline)' }} />
                    <Bar dataKey="value" fill="var(--primary)" radius={[0, 4, 4, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="vault-card fade-in-up" style={{ marginTop: '2rem', textAlign: 'center', padding: '4rem' }}>
           <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📡</div>
           <h2 className="display-md vault-text-primary">Awaiting Uplink</h2>
           <p className="body-lg">Enter a wallet address above to begin institutional-grade risk analysis.</p>
        </div>
      )}
    </div>
  );
}
