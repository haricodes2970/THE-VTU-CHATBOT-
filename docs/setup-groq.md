# Get a Groq API Key

## 1. Sign Up
Go to [console.groq.com](https://console.groq.com) → Sign up (free)

## 2. Create API Key
Dashboard → API Keys → Create API Key → Copy it

## 3. Add to .env
```
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama3-8b-8192
```

## Available Models
| Model | Context | Speed | Best for |
|-------|---------|-------|----------|
| llama3-8b-8192 | 8K | Very fast | Default (recommended) |
| llama3-70b-8192 | 8K | Fast | Better accuracy |
| mixtral-8x7b-32768 | 32K | Fast | Long documents |

## Free Tier Limits
- 30 requests/minute
- 14,400 requests/day
- Sufficient for development and moderate production use
