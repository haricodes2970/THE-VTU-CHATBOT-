# Deploy Frontend to Vercel

## Prerequisites
- Vercel account
- GitHub repo connected

## Steps

### 1. Import Project
1. Go to [vercel.com](https://vercel.com) → New Project
2. Import `haricodes2970/THE-VTU-CHATBOT-`
3. Set **Root Directory** to `frontend`

### 2. Configure Build
- **Framework**: Vite
- **Build Command**: `npm run build`
- **Output Directory**: `dist`

### 3. Add Environment Variables
In Vercel → Settings → Environment Variables:
- `VITE_API_URL=https://your-backend.onrender.com/api/v1`

### 4. Deploy
Click Deploy. Vercel will build and deploy automatically on every push to `master`.

### 5. Custom Domain (optional)
Vercel → Settings → Domains → Add your domain.
