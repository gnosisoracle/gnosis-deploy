# GNOSIS — Deploy Guide

## Option A: Manual Deploy via Render Dashboard (RECOMMENDED — no GitHub needed)

1. Go to https://dashboard.render.com
2. Click **New → Web Service**
3. Choose **"Deploy from existing code"** or **"Upload"**
4. Upload the `gnosis-oracle-deploy.zip` directly

## Option B: Fix GitHub → Render Connection

### Step 1: Make your GitHub repo Public (easiest)
1. Go to https://github.com/sicutdeusvult/gnosis
2. Settings → Danger Zone → Change visibility → **Make public**
3. Render will then be able to clone it automatically

### Step 2 (alternative): Add Render's Deploy Key to GitHub
1. In Render dashboard → Your service → Settings → **Deploy Key**
2. Copy the SSH public key shown
3. Go to GitHub repo → Settings → **Deploy Keys** → Add Key
4. Paste the key, check "Allow write access" → Add
5. Trigger a new deploy in Render

### Step 3 (alternative): Use GitHub App
1. Render dashboard → Account Settings → **GitHub**
2. Connect your GitHub account via OAuth
3. Grant access to the `gnosis` repository
4. Render will now have read access

## Option C: Push Code to GitHub First

```bash
# In your local terminal after unzipping gnosis-oracle-deploy.zip:
cd gnosis-deploy
git init
git add -A
git commit -m "GNOSIS v2"
git remote add origin https://github.com/sicutdeusvult/gnosis.git
git push -f origin main
```
Then Render will auto-deploy on next push.

## Environment Variables (set in Render Dashboard)
```
ANTHROPIC_API_KEY=sk-ant-...
TWITTER_user_name=GNOSIS1966282
TWITTER_email=omuwuwofe462@gmail.com
TWITTER_pwd=888777rtTT!!
TWITTER_phone=          ← add phone number if you have it
TWITTER_API_CONSUMER_KEY=ma1pYa7JJJ6Fdb9ImTYKr5050
TWITTER_API_CONSUMER_SECRET=fUyCqVCXzYuOyoOQDTPYLasaUnO1NyiA33ZpslD45Fzhimlj6h
TWITTER_API_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAOE68AE...
TWITTER_API_ACCESS_TOKEN=          ← regenerate with Read+Write
TWITTER_API_ACCESS_TOKEN_SECRET=   ← regenerate with Read+Write
DATA_DIR=/data
PORT=8000
PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/.playwright
```
