# Set Up Pinecone Vector Database

## 1. Create Account
Go to [app.pinecone.io](https://app.pinecone.io) → Sign up (free tier available)

## 2. Get API Key
Dashboard → API Keys → Copy the default API key

## 3. Add to .env
```
PINECONE_API_KEY=your_key_here
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=vtu-circulars
PINECONE_DIMENSION=384
```

## 4. Index is Auto-Created
The app automatically creates the `vtu-circulars` index on first run
(dimension=384, metric=cosine). No manual setup needed.

## 5. Verify
Run the backend and check logs for:
```
Creating Pinecone index: vtu-circulars
```
Or check the Pinecone dashboard for the new index.
