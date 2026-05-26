# Starting the App

## On the server (digitization)

Open two terminals.

**Terminal 1 — API:**
```bash
cd /digitization/Metadata-Generator-App
source .venv/bin/activate
uvicorn api.main:app --port 8000 --reload
```
Wait for: `Application startup complete.`

**Terminal 2 — Frontend:**
```bash
cd /digitization/Metadata-Generator-App/ui
npm run dev
```
Wait for: `VITE ready` — note the port (usually 5173).

---

## On your local machine

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 digitization
```
(Replace 5173 if Vite picked a different port.)

Then open: **http://localhost:5173**

---

## Troubleshooting

**Port already in use:**
```bash
# Kill whatever's on those ports (run on local Mac)
sudo lsof -ti :5173 -ti :8000 | xargs kill -9

# Kill stale server processes (run on digitization)
pkill -f "uvicorn api.main:app"
pkill -f "vite dev"
pkill -f "npm run dev"
```

**Photos not showing / proxy errors:**
- Make sure uvicorn is running (Vite logs will show `ECONNREFUSED 127.0.0.1:8000` if not)
- Check both terminals are still alive

---

## Processing a collection

```bash
cd /digitization/Metadata-Generator-App
source .venv/bin/activate

# Ingest images (fast, just registers files)
python -m app.cli ingest /digitization/Metadata-Generator-App/images/incoming/Chicago_Cafe_Photos --collection "Chicago Cafe Photos"

# Generate metadata (runs VLM — slow)
python -m app.cli generate --collection "Chicago Cafe Photos"

# Test with just one item first
python -m app.cli generate --collection "Chicago Cafe Photos" --limit 1
```

Items are saved to the DB as they complete — you can review in the UI while generation is still running.
