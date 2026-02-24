# Deploy to Free Staging (Render)

Deploy your Resume ATS Checker as a free demo preview on [Render](https://render.com).

## Prerequisites

- [GitHub](https://github.com) account
- [Render](https://render.com) account (free)

## Steps

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Deploy on Render

1. Go to [render.com](https://render.com) and sign up (free).
2. Click **New** → **Web Service**.
3. Connect your GitHub repo (authorize if needed).
4. Configure:
   - **Name:** `resume-ats-checker` (or any name)
   - **Region:** Choose closest
   - **Runtime:** Python 3
   - **Build Command:** `./build.sh`
   - **Start Command:** `gunicorn config.wsgi:application`
   - **Instance Type:** Free

5. **Environment Variables** (add these):
   | Key              | Value                          |
   |------------------|--------------------------------|
   | `DJANGO_SECRET_KEY` | (auto-generated or create a long random string) |
   | `DEBUG`          | `False`                        |
   | `PYTHON_VERSION` | `3.12`                         |

6. Click **Create Web Service**.

### 3. After First Deploy

1. Render will assign a URL like `https://resume-ats-checker-xxxx.onrender.com`.
2. Add a superuser (optional, for admin access):
   - Go to **Shell** tab in Render dashboard.
   - Run: `python manage.py createsuperuser`

### Notes

- **Free tier**: Service sleeps after ~15 min of no traffic; first visit may take 30–60 seconds to wake up.
- **Database**: Uses SQLite; data is ephemeral and may reset on redeploy or sleep.
- **Uploaded files**: Stored in `media/`; also ephemeral on free tier.
- **Alternative**: [PythonAnywhere](https://www.pythonanywhere.com) offers a free tier if you prefer a different host.
