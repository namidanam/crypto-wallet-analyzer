import React from 'react';

export default function AboutFounders() {
  const founders = [
    { name: 'Raghav Maheshwari', role: 'Architect', email: 'b24cs1107@iitj.ac.in', details: 'System Architecture, API Gateway, Routing' },
    { name: 'Anmol Mishra', role: 'Integrator', email: 'b24cs1009@iitj.ac.in', details: 'External APIs, Data Retrieval, Aggregation Engine' },
    { name: 'Anhad Singh', role: 'Analyst', email: 'b24cs1007@iitj.ac.in', details: 'Risk Algorithms using ML, Scoring Logic, Analytics' },
    { name: 'Vijna Maradithaya', role: 'Guardian', email: 'b24cs1109@iitj.ac.in', details: 'QA, Optimization, Normalization, Deployment' },
  ];

  return (
    <div className="vault-page fade-in-up">
      <header>
        <h1 className="display-lg vault-text-primary">About the Founders</h1>
        <p className="body-lg">Engineering team driving the Crypto Wallet Risk Analyzer.</p>
      </header>

      <div className="fade-in-up stagger-1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem', marginTop: '2rem' }}>
        {founders.map((f, i) => (
          <div key={i} className="vault-card vflex gap-sm">
            <h2 className="display-md vault-text-accent">{f.name}</h2>
            <span className="label-sm">{f.role}</span>
            <p className="body-md" style={{ marginTop: '0.5rem' }}>{f.details}</p>
            <div className="body-sm vault-text-success" style={{ marginTop: 'auto', paddingTop: '1rem' }}>{f.email}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
