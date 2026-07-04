# 🚀 Deploy to Render - Quick Guide

## One-Click Deploy (5 minutes)

### Step 1: Go to Render
Visit: **https://render.com**

### Step 2: Sign Up/Login
- Sign up with GitHub (recommended)
- This allows direct repository access

### Step 3: Create New Web Service
1. Click **"New +"** button (top right)
2. Select **"Web Service"**

### Step 4: Connect Repository
1. Click **"Connect a repository"**
2. Search for: **`Vishtheendodoc/modern-EMR`**
3. Click **"Connect"**

### Step 5: Configure Service
Render will auto-detect settings, but verify:

**Basic Settings:**
- **Name**: `endocrinology-emr` (or your choice)
- **Region**: Choose closest to you
- **Branch**: `main`
- **Root Directory**: (leave blank)

**Build & Deploy:**
- **Runtime**: `Python 3`
- **Build Command**: `./build.sh`
- **Start Command**: `gunicorn app:app`

**Instance Type:**
- Select: **Free** (perfect for demo/testing)

### Step 6: Environment Variables (Auto-configured)
Render will automatically generate:
- `SECRET_KEY` (auto-generated secure key)
- `PYTHON_VERSION` (3.12.3)
- `FLASK_ENV` (production)

### Step 7: Deploy!
1. Click **"Create Web Service"**
2. Wait 3-5 minutes for deployment
3. Watch the build logs (it will run `populate_sample_data.py` automatically)

### Step 8: Get Your URL
Once deployed, you'll see:
```
Your service is live at https://endocrinology-emr-xxxx.onrender.com
```

---

## 📱 Access on Mobile

**Your Live URL will be:**
`https://endocrinology-emr-[your-unique-id].onrender.com`

**Login Credentials:**
- Username: `demo_doctor`
- Password: `password123`

---

## ✅ What Happens During Deployment

1. **Build Phase** (2-3 minutes):
   - Installs all Python packages
   - Creates database
   - Populates sample data (7 drugs, 15 brands, 3 patients)

2. **Deploy Phase** (30 seconds):
   - Starts Gunicorn server
   - App becomes live!

3. **Result**:
   - ✅ 7 Generic Drugs
   - ✅ 15 Brand Medications
   - ✅ 10 Drug-Comorbidity Rules
   - ✅ 3 Sample Patients
   - ✅ Ready to use!

---

## 🔧 Troubleshooting

### If build fails:
1. Check build logs in Render dashboard
2. Verify `build.sh` has execute permissions (already done)
3. Ensure all dependencies install correctly

### If app doesn't start:
1. Check "Logs" tab in Render dashboard
2. Verify environment variables are set

### Database issues:
- Render's free tier uses ephemeral storage
- Database persists during app lifetime
- For production, consider upgrading to persistent disk

---

## 🎯 After Deployment

### Test These Features:
1. ✅ Login page loads
2. ✅ Dashboard shows statistics
3. ✅ View sample patients
4. ✅ Search for drugs
5. ✅ Add prescription with warnings
6. ✅ Generate PDF

### Share Your App:
Send the Render URL to colleagues/users:
`https://your-app-name.onrender.com`

---

## 💡 Pro Tips

1. **Free Tier Limitations**:
   - App sleeps after 15 min inactivity
   - Takes 30 sec to wake up on first request
   - Perfect for demo/testing!

2. **Custom Domain** (Optional):
   - Add your own domain in Render settings
   - e.g., `emr.yourdomain.com`

3. **Upgrade Options**:
   - Paid plans ($7/month) keep app always running
   - No sleep time
   - More resources

---

## 📊 Expected Deployment Time

- **Total**: ~5 minutes
- Repository connection: 30 seconds
- Build process: 3 minutes
- Service start: 1 minute
- First access: Ready!

---

## 🆘 Need Help?

If deployment fails:
1. Check the "Logs" section in Render dashboard
2. Common issues:
   - Build script permissions (already fixed ✅)
   - Missing dependencies (all included ✅)
   - Database initialization (automated ✅)

Everything is pre-configured and ready to deploy! 🚀

---

**Start deploying now at: https://render.com**
