# 🎬 Video Splitter Pro — Deploy Guide

## ជំហានទី 1 — Upload ទៅ GitHub

1. ចូល https://github.com → "New repository"
2. Repository name: `video-splitter-pro`
3. Public ✅ → "Create repository"
4. Upload files ទាំង 4 នេះ:
   - `server.py`
   - `index.html`
   - `requirements.txt`
   - `render.yaml`

## ជំហានទី 2 — Deploy លើ Render

1. ចូល https://render.com → Sign up (free)
2. "New +" → **Web Service**
3. Connect GitHub → ជ្រើស repo `video-splitter-pro`
4. Render នឹង detect `render.yaml` ដោយស្វ័យប្រវត្តិ
5. ចុច **"Create Web Service"**
6. រង់ចាំ ~3-5 នាទី ដើម្បី build

## ជំហានទី 3 — ប្រើ

Render នឹងផ្តល់ URL ដូចជា:
```
https://video-splitter-pro.onrender.com
```

បើកតាម Browser → ប្រើបានភ្លាម! 🎉

---

## ⚠️ Free Tier Limitations

| លក្ខណៈ | Free | Paid ($7/ខែ) |
|--------|------|-------------|
| Sleep បន្ទាប់ 15 នាទី idle | ✅ | ❌ |
| Bandwidth | 100GB/ខែ | Unlimited |
| RAM | 512MB | 2GB+ |
| Video ធំ (>100MB) | 느린 | ⚡ Fast |

**Tips Free Tier:**
- Request ដំបូងអាច slow (~30s) ព្រោះ server wake up
- Video file ត្រូវ < 100MB សម្រាប់ free tier
- ប្រើ Custom Domain បានដោយឥតគិតថ្លៃ

---

## 🔧 Alternative: Railway

1. ចូល https://railway.app
2. "New Project" → "Deploy from GitHub"
3. ជ្រើស repo → Add variable: `NIXPACKS_APT_PACKAGES=ffmpeg`
4. Deploy!
