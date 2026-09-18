# 🌐 Global 24/7 Hosting Guide for Cognify (StudyMate AI)

Cognify is completely packaged and ready for free, 24/7 cloud hosting on **Render** (recommended) or **Railway**.

---

## 🚀 Option 1: Deploy on Render (Free 24/7)

Render offers a generous free tier for Python web services with automatic SSL (`https://...onrender.com`).

### Step 1: Push to GitHub
1. Open your terminal in `Cognify`:
   ```powershell
   git add .
   git commit -m "Configure production cloud deployment"
   git branch -M main
   ```
2. Create a new repository on [GitHub](https://github.com/new) (e.g. `cognify-studymate`).
3. Link and push:
   ```powershell
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/cognify-studymate.git
   git push -u origin main
   ```

### Step 2: Create Web Service on Render
1. Go to [render.com](https://render.com) and sign in (using your GitHub account).
2. Click **New +** (top right) and select **Web Service**.
3. Choose **Build and deploy from a Git repository** and connect your `cognify-studymate` repo.
4. Fill in the settings:
   - **Name**: `cognify-studymate` (or any name you choose)
   - **Region**: Closest to you (e.g., Singapore, Frankfurt, Oregon)
   - **Branch**: `main`
   - **Root Directory**: *(leave blank)*
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **Free**
5. Scroll down to **Environment Variables** and click **Add Environment Variable**:
   - **Key**: `GEMINI_API_KEY`
   - **Value**: *(your Gemini API key)*
6. Click **Deploy Web Service**!

Render will build the app and give you a permanent live URL like:
👉 **`https://cognify-studymate.onrender.com`**

---

## 🚆 Option 2: Deploy on Railway (Alternative)

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your `cognify-studymate` repository.
4. Go to **Variables** tab and add:
   - `GEMINI_API_KEY` = *(your Gemini API key)*
5. Go to **Settings** -> **Networking** -> click **Generate Domain**.
6. Your app is live with SSL!

---

## 🧪 Local Testing Before Deploying

To test the unified server locally (with the frontend served directly by FastAPI):
```powershell
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Then visit:
- From your PC: [http://localhost:8000](http://localhost:8000)
- From your phone (on the same Wi-Fi): `http://<YOUR_LOCAL_IP>:8000`
