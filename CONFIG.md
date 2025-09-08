# Vinted Parser Bot - Configuration Guide

## Environment Variables

### Application Settings
```bash
ENVIRONMENT=production          # development | staging | production
DEBUG=false                     # Never enable in production
LOG_LEVEL=INFO                  # DEBUG | INFO | WARNING | ERROR
```

### Telegram Bot Configuration
```bash
BOT_TOKEN=your_bot_token        # From @BotFather
WEBHOOK_DOMAIN=https://your.domain.com  # Must be HTTPS in production
WEBHOOK_PATH=/telegram          # Webhook endpoint path
WEBHOOK_SECRET=secure_secret    # Min 32 characters
```

### Database Configuration
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
DB_POOL_SIZE=10                # Connection pool size
DB_MAX_OVERFLOW=20             # Max overflow connections
DB_POOL_TIMEOUT=30             # Connection timeout
```

### Redis Configuration
```bash
REDIS_URL=redis://user:pass@host:6379/1
REDIS_POOL_SIZE=10             # Redis connection pool
```

### Payment Processing (YooKassa)
```bash
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
```

### Security Keys
```bash
SECRET_KEY=secure_random_32_chars
REFERRAL_SECRET=secure_random_32_chars
```

### Business Logic
```bash
DEFAULT_TRIAL_DAYS=7
REFERRAL_BONUS_DAYS=3
```

### Rate Limiting
```bash
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW=60
VINTED_RATE_LIMIT=30
MAX_CONCURRENT_REQUESTS=10
```

### Security Settings
```bash
DISABLE_SSL_VERIFICATION=false  # NEVER enable in production
ENABLE_SECURITY_HEADERS=true
ENABLE_CORS=true
```

### Monitoring
```bash
ENABLE_PROMETHEUS=true
ENABLE_HEALTH_CHECKS=true
```

## Development Configuration

For local development, use these settings:

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
WEBHOOK_DOMAIN=http://localhost:8000
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/vinted_bot
REDIS_URL=redis://localhost:6379/1
ENABLE_SECURITY_HEADERS=false
```

## Production Checklist

- [ ] ENVIRONMENT=production
- [ ] DEBUG=false
- [ ] HTTPS enabled for webhook
- [ ] Strong, unique secrets for all keys
- [ ] Secure database credentials
- [ ] Redis with authentication
- [ ] SSL verification enabled
- [ ] Security headers enabled
- [ ] Monitoring enabled
