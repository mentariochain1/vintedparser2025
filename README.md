# Vinted Parser Bot

A Telegram bot that helps Austrian users discover and track Vinted listings that ship to Austria. The bot provides search functionality, item tracking, payment processing for premium features, and a referral system.

## Features

- 🔍 Search Vinted items that ship to Austria
- 💰 Premium subscription with YooKassa payments
- 👥 Referral system with trial extensions
- 📱 Telegram bot interface with inline keyboards
- 🚀 Async-first architecture with FastAPI and aiogram
- 🐳 Docker support with multi-stage builds
- 🔒 Security-first design with rate limiting and validation

## Tech Stack

- **Python 3.12** - Modern Python with type hints
- **aiogram 4.x** - Telegram Bot API framework
- **FastAPI** - Modern web framework for webhooks
- **Supabase** - PostgreSQL database with real-time features
- **Redis** - Caching and background job queue
- **Docker** - Containerized deployment
- **YooKassa** - Payment processing

## Quick Start

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- Docker and Docker Compose (optional)
- Telegram Bot Token
- Supabase project
- YooKassa account

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd vinted-parser-bot
```

2. Install dependencies:
```bash
make dev
```

3. Set up environment:
```bash
make setup-dev
# Edit .env file with your configuration
```

4. Run the application:
```bash
make run
```

### Docker Development

```bash
# Run with Docker Compose
make docker-run
```

## Configuration

Copy `.env.example` to `.env` and configure the following variables:

### Required Settings

- `BOT_TOKEN` - Your Telegram bot token
- `WEBHOOK_DOMAIN` - Your domain for webhooks
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `YOOKASSA_SHOP_ID` - YooKassa shop ID
- `YOOKASSA_SECRET_KEY` - YooKassa secret key
- `REFERRAL_SECRET` - Secret for signing referral links

### Optional Settings

- `DEFAULT_TRIAL_DAYS` - Trial period length (default: 7)
- `REFERRAL_BONUS_DAYS` - Referral bonus days (default: 3)
- `VINTED_RATE_LIMIT` - API rate limit per minute (default: 30)
- `REDIS_URL` - Redis connection URL
- `LOG_LEVEL` - Logging level (default: INFO)

## Development

### Code Quality

```bash
# Run linting
make lint

# Format code
make format

# Run tests
make test

# Run tests with coverage
make test-cov
```

### Project Structure

```
src/
├── bot/                 # Bot handlers and logic
│   ├── handlers/        # Command and callback handlers
│   ├── keyboards/       # Inline and reply keyboards
│   ├── middlewares/     # Bot middlewares
│   ├── services/        # Business logic services
│   └── utils/           # Utility functions
├── db/                  # Database models and connections
├── tasks/               # Background tasks
└── config.py           # Configuration management

tests/                   # Test suite
```

## Deployment

### Docker Production

```bash
# Build production image
docker build --target production -t vinted-parser-bot:latest .

# Run production container
docker run -d \
  --name vinted-bot \
  --env-file .env \
  -p 8000:8000 \
  vinted-parser-bot:latest
```

### Environment Variables for Production

Set the following additional variables for production:

- `ENVIRONMENT=production`
- `DEBUG=false`
- `WORKERS=4` (adjust based on your server)
- `PORT=8000`

## API Endpoints

- `GET /health` - Health check endpoint
- `POST /telegram` - Telegram webhook endpoint
- `POST /yookassa/webhook` - YooKassa payment webhook

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions, please open an issue on GitHub.# vintedparser2025
