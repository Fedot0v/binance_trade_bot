# Binance Trade Bot - Novichok++

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)](https://github.com/your-repo)

🚀 **Production-ready automated cryptocurrency trading bot** 

## 🎯 What This Bot Does

This is a sophisticated **automated trading system** that:

### 🤖 **Automated Trading**
- **24/7 Market Monitoring**: Continuously analyzes cryptocurrency markets using real-time data from Binance
- **Signal Generation**: Uses technical analysis to identify profitable trading opportunities
- **Automatic Trade Execution**: Places buy/sell orders automatically based on strategy signals
- **Risk Management**: Implements stop-loss, take-profit, and position sizing to protect your capital

### 📊 **Advanced Analytics**
- **Technical Analysis**: EMA crossovers, trend detection, momentum indicators
- **Market Sentiment**: Analyzes volume, price action, and market structure
- **Performance Tracking**: Real-time P&L monitoring and trade history  

### 🛡️ **Risk Management**
- **Position Sizing**: Calculates optimal position size based on account balance and risk tolerance
- **Stop-Loss Protection**: Automatic stop-loss orders to limit potential losses
- **Leverage Control**: Configurable leverage settings for margin trading
- **Portfolio Diversification**: Support for multiple trading pairs simultaneously

### 🌐 **Web Dashboard**
- **Real-time Monitoring**: Live charts, trade status, and performance metrics
- **Strategy Configuration**: Easy-to-use interface for adjusting trading parameters
- **Trade History**: Detailed logs of all executed trades and performance
- **API Management**: Secure storage and management of Binance API credentials

### 🔧 **Core Components**
- **FastAPI 0.115+**: Modern, fast web framework with automatic API documentation
- **Pydantic**: Data validation and serialization
- **SQLAlchemy 2.0+**: Modern async ORM with type hints
- **Alembic**: Database migration tool

### **Database & Caching**
- **PostgreSQL 16**: Robust relational database for persistent storage
- **Redis 7**: In-memory data store for caching and message queuing
- **asyncpg**: High-performance async PostgreSQL driver

### **Trading & Analysis**
- **python-binance**: Official Binance API client
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computing
- **ta**: Technical analysis indicators (RSI, MACD, EMA, etc.)

### **Task Processing**
- **Celery**: Distributed task queue for background processing
- **Redis**: Message broker for Celery
- **celery-beat**: Database-backed scheduler

### **Security & Authentication**
- **FastAPI Users**: User management and authentication
- **JWT**: JSON Web Tokens for secure API access
- **Argon2**: Password hashing
- **cryptography**: API key encryption

### **Frontend & UI**
- **Jinja2**: Template engine for server-side rendering
- **Bootstrap/CSS**: Responsive web interface

### **Testing & Quality**
- **pytest**: Testing framework
- **pytest-asyncio**: Async testing support
- **pytest-cov**: Code coverage reporting
- **pytest-mock**: Mocking utilities

### **Deployment & DevOps**
- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration
- **GitHub Actions**: CI/CD pipeline
- **uvicorn**: ASGI server

## 📊 Trading Strategies

### **Novichok++ Strategy** 🎯

#### **Core Logic**
```python
if fast_ema > slow_ema and trend_strength > threshold:
    return "long"  # Buy signal
elif fast_ema < slow_ema and trend_strength > threshold:
    return "short"  # Sell signal
else:
    return "hold"  # No position
```

#### **Key Features**
- **EMA Crossover**: 7-period vs 21-period Exponential Moving Averages
- **Trend Strength**: Dynamic threshold based on market volatility
- **Volume Confirmation**: Validates signals with volume analysis
- **Momentum Filter**: RSI-based momentum confirmation

#### **Risk Parameters**
- **Position Size**: 10% of account balance per trade
- **Stop Loss**: 1.5% from entry price
- **Leverage**: Configurable (1x to 20x)
- **Max Positions**: 3 concurrent positions

### **Strategy Customization**
- **Indicator Parameters**: Adjust EMA periods, RSI levels, etc.
- **Risk Settings**: Modify position size, stop-loss, take-profit
- **Time Filters**: Set trading hours and market conditions
- **Pair Selection**: Choose specific trading pairs

## 📈 Performance & Monitoring

### **Real-time Metrics**
- **P&L Tracking**: Live profit/loss calculation
- **Win Rate**: Percentage of profitable trades
- **Sharpe Ratio**: Risk-adjusted returns
- **Drawdown**: Maximum peak-to-trough decline
- **Trade Frequency**: Number of trades per day/week

### **Analytics Dashboard**
- **Performance Charts**: Historical P&L visualization
- **Trade Analysis**: Individual trade breakdown
- **Strategy Comparison**: Multi-strategy performance
- **Risk Metrics**: VaR, maximum drawdown, etc.

### **Logging & Debugging**
- **Structured Logging**: JSON-formatted logs
- **Error Tracking**: Comprehensive error reporting
- **Performance Monitoring**: Response time tracking
- **Audit Trail**: Complete trade history

## 🚀 Quick Start (Production Ready)

### **Option 1: Docker Deployment (Recommended)**

```bash
# 1. Clone repository
git clone <repository-url>
cd binance_trade_bot

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Start all services
docker-compose up -d

# 4. Access dashboard
open http://localhost:8000
```

### **Option 2: Local Development**

```bash
# 1. Setup Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start database services
docker-compose up postgres redis -d

# 4. Run migrations
alembic upgrade head

# 5. Start application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## ⚙️ Configuration Guide

### **Environment Variables**
```env
# Database Configuration
POSTGRES_DB=trading_bot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password
DATABASE_URL=postgresql+asyncpg://postgres:secure_password@localhost:5432/trading_bot

# Redis Configuration
REDISPASSWORD=redis_password
REDIS_URL=redis://:redis_password@localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://:redis_password@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:redis_password@localhost:6379/1

# Security Settings
SECRET_KEY=your-super-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Binance API (Required for live trading)
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key

# Optional: Test Mode
TEST_MODE=true  # Use testnet instead of mainnet
```

### **Strategy Configuration**
```json
{
  "parameters": {
    "ema_fast": 7,
    "ema_slow": 21,
    "trend_threshold": 0.001,
    "stop_loss_pct": 0.015,
    "deposit_prct": 10
  }
}
```

## 🧪 Testing & Validation

### **Backtesting**
```bash
# Run backtest on historical data
python backtest_novichok.py

# Results include:
# - Total return
# - Sharpe ratio
# - Maximum drawdown
# - Win rate
# - Trade count
```

### **Unit Tests**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest app/tests/test_strategies.py
pytest app/tests/test_trading.py
```

### **Integration Tests**
- API endpoint testing
- Database integration
- Trading simulation
- Performance validation

## 🔒 Security Features

### **Data Protection**
- **API Key Encryption**: All Binance credentials are encrypted at rest
- **Secure Storage**: Database-level encryption for sensitive data
- **Access Control**: Role-based permissions and authentication
- **Audit Logging**: Complete access and action logging

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

*This bot is production-ready and actively maintained.* 