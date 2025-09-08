# Vinted Parser Bot

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/poetry-1.7+-blue.svg)](https://python-poetry.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![aiogram](https://img.shields.io/badge/aiogram-3.10+-blue.svg)](https://aiogram.dev/)

A sophisticated Telegram bot for searching and parsing Vinted listings with Austrian shipping. Built with modern Python async patterns, comprehensive monitoring, and production-grade reliability.

## 🚀 Features

- **Telegram Bot Integration**: Modern aiogram 3.x with webhook support
- **Vinted Search**: Advanced scraping with fallback strategies
- **Payment Processing**: YooKassa integration with secure webhooks
- **User Management**: Trial periods, referrals, and premium subscriptions
- **Monitoring & Observability**: Prometheus metrics, structured logging, health checks
- **Security**: Rate limiting, webhook validation, input sanitization
- **Scalability**: Async/await patterns, connection pooling, circuit breakers

## 🏗️ Architecture

```
vinted-parser-bot/
├── src/                          # Application source code
│   ├── main.py                   # FastAPI application entry point
│   ├── config.py                 # Configuration management
│   ├── monitoring.py             # Observability utilities
│   ├── bot/                      # Telegram bot components
│   │   ├── bot.py               # Bot initialization
│   │   ├── handlers/            # Message/command handlers
│   │   ├── services/            # Business logic services
│   │   ├── keyboards/           # Inline/reply keyboards
│   │   └── utils/               # Bot utilities
│   ├── db/                      # Database layer
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── crud.py              # CRUD operations
│   │   └── asyncpg_adapter.py   # Async database adapter
│   ├── middleware/              # FastAPI middleware
│   ├── tasks/                   # Background task processing
│   └── lib/                     # Shared utilities
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── e2e/                     # End-to-end tests
├── supabase/                    # Database migrations
└── docs/                        # Documentation
```

## 🛠️ Technology Stack

### Core Framework
- **Python 3.12** - Modern Python with advanced async features
- **FastAPI** - High-performance async web framework
- **aiogram 3.x** - Modern Telegram bot framework
- **Uvicorn** - ASGI server with automatic reload

### Database & Caching
- **PostgreSQL** - Primary database with asyncpg
- **Redis** - Caching, rate limiting, session management
- **SQLAlchemy** - ORM with async support

### External Integrations
- **Vinted API** - Custom scraper with cloudscraper
- **YooKassa** - Payment processing with webhooks
- **Supabase** - Database hosting and migrations

### Quality & Monitoring
- **Ruff** - Lightning-fast linting and formatting
- **MyPy** - Static type checking
- **pytest** - Comprehensive testing framework
- **Prometheus** - Metrics collection
- **Structured Logging** - Context-aware logging

## 📋 Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Poetry (dependency management)

## 🚀 Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/your-org/vinted-parser-bot.git
cd vinted-parser-bot
poetry install
```

### 2. Environment Setup

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Database Setup

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Run migrations
poetry run alembic upgrade head
```

### 4. Run the Application

```bash
# Development mode
poetry run uvicorn src.main:app --reload

# Production mode
poetry run gunicorn -k uvicorn.workers.UvicornWorker src.main:app
```

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test types
poetry run pytest tests/unit/
poetry run pytest tests/integration/ -m "not slow"
```

## 📊 Monitoring

### Health Checks
- `GET /health` - Basic health status
- `GET /healthz` - Detailed health with service status
- `GET /health/search` - Search functionality health
- `GET /metrics` - Prometheus metrics

### Logs
Structured logging with context:
```json
{
  "timestamp": "2025-01-01T12:00:00Z",
  "level": "INFO",
  "logger": "vinted_service",
  "message": "Search completed",
  "user_id": 12345,
  "query": "nike shoes",
  "items_count": 24,
  "duration_ms": 1250
}
```

## 🔧 Configuration

Key environment variables:

```bash
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
WEBHOOK_DOMAIN=https://your-domain.com
WEBHOOK_SECRET=your_webhook_secret

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/vinted_bot
REDIS_URL=redis://localhost:6379/1

# Payments
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false
```

## 🏭 Deployment

### Docker Deployment

```bash
# Build and run
docker-compose up --build

# Production deployment
docker build -t vinted-bot .
docker run -p 8000:8000 vinted-bot
```

### Manual Deployment

```bash
# Install dependencies
poetry install --only main

# Run with gunicorn
gunicorn -k uvicorn.workers.UvicornWorker \
  -c gunicorn_conf.py \
  src.main:app
```

## 📚 API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Write tests for your changes
4. Ensure all tests pass: `poetry run pytest`
5. Format code: `poetry run ruff format src tests`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

## 📝 Code Quality

### Linting & Formatting
```bash
# Check code quality
poetry run ruff check src tests

# Auto-fix issues
poetry run ruff check --fix src tests

# Format code
poetry run black src tests
```

### Type Checking
```bash
# Static type analysis
poetry run mypy src
```

## 🔒 Security

- **Webhook Validation**: HMAC signature verification
- **Rate Limiting**: Redis-based per-user limits
- **Input Validation**: Pydantic models with strict validation
- **SQL Injection Protection**: Parameterized queries
- **XSS Protection**: HTML escaping in responses
- **CSRF Protection**: Secure token validation

## 📈 Performance

- **Async/Await**: Full async stack from request to database
- **Connection Pooling**: Efficient database and Redis connections
- **Circuit Breakers**: Automatic failure detection and recovery
- **Caching**: Redis-based caching for frequent queries
- **Background Tasks**: Non-blocking task processing

## 🐛 Troubleshooting

### Common Issues

**Database Connection Failed**
```bash
# Check PostgreSQL status
docker-compose ps postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

**Redis Connection Failed**
```bash
# Check Redis status
docker-compose ps redis

# Flush Redis data
docker-compose exec redis redis-cli FLUSHALL
```

**Bot Webhook Issues**
```bash
# Check webhook status
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Reset webhook
curl https://api.telegram.org/bot<TOKEN>/setWebhook?url=<YOUR_URL>
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [aiogram](https://aiogram.dev/) - Modern Telegram bot framework
- [FastAPI](https://fastapi.tiangolo.com/) - High-performance async web framework
- [Vinted](https://www.vinted.at/) - Fashion marketplace
- [YooKassa](https://yookassa.ru/) - Payment processing

## 📞 Support

For support, please open an issue on GitHub or contact the development team.

---

**Built with ❤️ using modern Python practices**
