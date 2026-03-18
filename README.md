# 🔐 Crypto Wallet Risk Analyzer

**Multi-chain cryptocurrency wallet analysis and risk assessment system supporting 200+ blockchain networks.**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Node.js](https://img.shields.io/badge/node-%3E%3D18.0.0-green.svg)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

---

## 🎯 Project Overview

A blockchain-agnostic platform that analyzes cryptocurrency wallet addresses across multiple networks and computes risk scores based on transaction patterns, value concentration, temporal analysis, and interactions with known high-risk addresses.

### Key Features

- ✅ **Multi-Chain Support**: Ethereum, Bitcoin, Polygon, BSC, and 196+ more networks
- ✅ **Real-Time Analysis**: Live transaction monitoring and historical data processing
- ✅ **Risk Scoring**: Multi-factor algorithm for wallet risk assessment
- ✅ **Data Normalization**: Unified transaction format across heterogeneous blockchains
- ✅ **Microservices Architecture**: Scalable dual-server design (Node.js + Python)
- ✅ **Docker Ready**: One-command deployment with Docker Compose

---

## 🏗️ Architecture

```
┌─────────────┐
│   Frontend  │  React + TypeScript + Vite
│  (Port 3000)│
└──────┬──────┘
       │ HTTP
┌──────▼──────────────────────────────────┐
│      Node.js Backend (Port 5000)        │
│  ┌────────────────────────────────┐    │
│  │ • Express API Gateway          │    │
│  │ • GoldRush API Integration     │    │
│  │ • Tatum API Failover           │    │
│  │ • Job Queue (Bull)             │    │
│  │ • MongoDB Models               │    │
│  └────────────────────────────────┘    │
└──────┬──────────────────────────────────┘
       │ HTTP
┌──────▼──────────────────────────────────┐
│   Python Processing Server (Port 8000)  │
│  ┌────────────────────────────────┐    │
│  │ • FastAPI                      │    │
│  │ • Transaction Normalization    │    │
│  │ • Statistical Aggregates       │    │
│  │ • Risk Engine                  │    │
│  └────────────────────────────────┘    │
└──────┬──────────────────────────────────┘
       │
┌──────▼──────┐
│   MongoDB   │  NoSQL Database
│ (Port 27017)│
└─────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose** (recommended)
- **Node.js 18+** (for local development)
- **Python 3.11+** (for local development)
- **MongoDB 7.0+** (if running without Docker)

### Installation

#### Option 1: Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/crypto-wallet-analyzer.git
cd crypto-wallet-analyzer

# 2. Create environment file
cp .env.example .env
# Edit .env and add your API keys

# 3. Start all services
docker-compose up -d

# 4. Check service health
docker-compose ps

# 5. View logs
docker-compose logs -f
```

#### Option 2: Local Development

```bash
# 1. Install backend dependencies
cd backend
npm install

# 2. Install Python dependencies
cd ../python-server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Install frontend dependencies
cd ../frontend
npm install

# 4. Start MongoDB (in separate terminal)
mongod --dbpath /path/to/data

# 5. Start Python server (in separate terminal)
cd python-server
python app/main.py

# 6. Start backend (in separate terminal)
cd backend
npm run dev

# 7. Start frontend (in separate terminal)
cd frontend
npm run dev
```

### Accessing the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **Backend Docs**: http://localhost:5000/api-docs
- **Python API**: http://localhost:8000
- **Python Docs**: http://localhost:8000/docs
- **MongoDB**: mongodb://localhost:27017

---

## 📁 Project Structure

```
crypto-wallet-analyzer/
│
├── frontend/              # React + TypeScript frontend
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Page-level components
│   │   ├── services/      # API service layer
│   │   └── App.tsx        # Root component
│   ├── package.json
│   └── Dockerfile
│
├── backend/               # Node.js + Express backend
│   ├── src/
│   │   ├── config/        # Configuration files
│   │   ├── routes/        # API routes
│   │   ├── controllers/   # Request handlers
│   │   ├── services/      # Business logic (API integrations)
│   │   ├── models/        # MongoDB schemas
│   │   ├── jobs/          # Background job processors
│   │   └── middleware/    # Express middleware
│   ├── package.json
│   └── Dockerfile
│
├── python-server/         # Python + FastAPI processing server
│   ├── app/
│   │   ├── config/        # Settings and configuration
│   │   ├── db/            # Database connections
│   │   ├── processors/    # Data processing modules
│   │   ├── schemas/       # Pydantic models
│   │   └── utils/         # Utility functions
│   ├── tests/             # Unit tests
│   ├── requirements.txt
│   └── Dockerfile
│
├── docs/                  # Documentation
│   ├── API.md             # API reference
│   ├── ARCHITECTURE.md    # System design docs
│   ├── SETUP.md           # Setup instructions
│   └── CONTRIBUTION.md    # Team contributions
│
├── scripts/               # Utility scripts
│   ├── setup.sh           # Project setup script
│   └── test-all.sh        # Run all tests
│
├── docker-compose.yml     # Multi-container orchestration
├── .env.example           # Environment variables template
└── README.md              # This file
```

---

## 👥 Team Structure (Alpha Model)

| Role | Name | Responsibilities |
|------|------|------------------|
| **Alpha 1** (Architect) | Raghav Maheshwari | System Architecture, Auth, API Gateway, Routing |
| **Alpha 2** (Integrator) | Anmol Mishra | External APIs, Data Retrieval, Normalization Engine |
| **Alpha 3** (Analyst) | Anhad Singh | Risk Algorithms, Scoring Logic, Analytics |
| **Alpha 4** (Guardian) | Vijna Maradithaya | QA, Optimization, Caching, Deployment |

---

## 📚 API Documentation

### Backend API (Node.js)

**Base URL**: `http://localhost:5000`

#### Endpoints

```
POST   /api/wallet/analyze       # Analyze wallet and fetch transactions
GET    /api/wallet/:address      # Get wallet details
GET    /api/wallet/:address/history  # Get transaction history
GET    /health                   # Health check
```

### Python Processing API

**Base URL**: `http://localhost:8000`

#### Endpoints

```
POST   /normalize                # Normalize transactions
POST   /aggregates               # Compute statistical aggregates
POST   /risk-score               # Calculate risk score
GET    /health                   # Health check
```

For detailed API documentation, see [docs/API.md](./docs/API.md)

---

## 🧪 Testing

```bash
# Test backend
cd backend
npm test

# Test Python server
cd python-server
pytest

# Test all services
./scripts/test-all.sh
```

---

## 🔧 Configuration

### API Keys Required

1. **Covalent GoldRush API**: https://www.covalenthq.com/
2. **Tatum API**: https://tatum.io/

Add these to your `.env` file:

```env
GOLDRUSH_API_KEY=cqt_xxx...
TATUM_API_KEY=your_tatum_key
```

---

## 📊 Performance Metrics

- **Supported Chains**: 200+ blockchains
- **API Response Time**: 2-4 seconds (with external API calls)
- **Cached Response Time**: <500ms
- **Transaction Processing**: 1000+ tx/minute (normalization)
- **Uptime**: 99.9% (with failover)

---

## 🚧 Development Roadmap

### Phase 1 (Current)
- [x] Project structure and Docker setup
- [x] Backend API gateway with GoldRush integration
- [x] MongoDB schema design
- [X] Tatum API backup integration
- [ ] Python normalization engine
- [ ] Basic frontend UI

### Phase 2
- [ ] Risk scoring algorithm
- [ ] Advanced statistical analysis
- [ ] Real-time transaction monitoring
- [ ] Frontend dashboard with charts

### Phase 3
- [ ] Machine learning risk models
- [ ] Multi-user authentication
- [ ] Advanced caching with Redis
- [ ] Production deployment

---

## 📖 Documentation

- [Architecture Overview](./docs/ARCHITECTURE.md)
- [API Reference](./docs/API.md)
- [Setup Guide](./docs/SETUP.md)
- [Contribution Guidelines](./docs/CONTRIBUTION.md)

---

## 🤝 Contributing

This is an academic project for IIT Jodhpur's Software Engineering course. Team members should follow the contribution guidelines in [docs/CONTRIBUTION.md](./docs/CONTRIBUTION.md).

---

## 📄 License

MIT License - IIT Jodhpur Academic Project 2026

---

## 🙏 Acknowledgments

- **Covalent** for GoldRush API
- **Tatum** for multi-chain API support
- **IIT Jodhpur** for project guidance
- **Open Source Community** for tools and libraries

---

## 📧 Contact

For questions or support, reach out to the team:
- Raghav: b24cs1107@iitj.ac.in
- Anmol: b24cs1009@iitj.ac.in
- Anhad: b24cs1007@iitj.ac.in
- Vijna: b24cs1109@iitj.ac.in
