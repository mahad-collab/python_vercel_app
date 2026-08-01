# Jashn-e-Azadi Quiz — Vercel + Upstash Redis Edition

Same quiz as before (QR join, 20 MCQs, one overall timer, instant score, auto-ranked
leaderboard) — but hosted on a free public Vercel URL instead of your local network.
This fixes the WiFi/LAN-can't-reach-each-other problem entirely: any device with
internet (WiFi *or* mobile data) can reach it, since there's no local network
dependency at all anymore.

## 1. Add your own 20 questions

Same as before — edit `questions.json` in this folder. Keep the structure, just
change the text:

```json
{
  "id": 1,
  "question": "Who is known as the founder of Pakistan?",
  "options": {
    "a": "Quaid-e-Azam Muhammad Ali Jinnah",
    "b": "Allama Iqbal",
    "c": "Liaquat Ali Khan",
    "d": "Sir Syed Ahmad Khan"
  },
  "answer": "a"
}
```

`"answer"` is the correct option's letter. You can also change `"quiz_title"` and
`"duration_minutes"` at the top of the file.

## 2. Push this folder to a new GitHub repo

```bash
cd quiz_app_vercel
git init
git add .
git commit -m "Initial quiz app"
```

Then create a new **empty** repo on github.com (no README/gitignore), and push:

```bash
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git branch -M main
git push -u origin main
```

## 3. Create your Vercel account and import the repo

1. Go to vercel.com and sign up using your GitHub account (this makes importing repos a one-click step).
2. Click **Add New → Project**.
3. Select the GitHub repo you just pushed.
4. Leave all build settings as default (Vercel auto-detects the Python runtime from `vercel.json`).
5. Click **Deploy**. The first deploy will actually fail or error on `/display`/`/join` — that's expected, because the database isn't connected yet. Continue to step 4.

## 4. Add Upstash Redis (free) from the Vercel Marketplace

1. In your new Vercel project, go to the **Storage** tab.
2. Click **Create Database** → choose **Upstash** → **Redis**.
3. Pick the free tier, create it, and **connect it to your project**.
4. This automatically adds two environment variables to your project:
   `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` — the app reads these
   automatically, no code changes needed.
5. Go to **Deployments** → click the three-dot menu on the latest deployment →
   **Redeploy**, so the new environment variables take effect.

## 5. You're live

Vercel gives you a URL like `https://your-project-name.vercel.app`. That's your
permanent event link:

- **`https://your-project-name.vercel.app/display`** — open this on the projector.
  It shows the QR code (staff scan it with any phone, on any network, to join).
- **`https://your-project-name.vercel.app/leaderboard`** — live, auto-refreshing
  winner board. Open on a second screen, or switch to it after everyone's done.
- **`https://your-project-name.vercel.app/`** — the join page itself (this is what
  the QR code points to).

## 6. Rehearse, then reset

Test the whole flow yourself with a couple of dummy entries first. Once you're happy,
wipe them before the real event:

```
https://your-project-name.vercel.app/admin/reset?key=reset-me
```

**Important:** before the real event, change the reset key in `app.py`
(`admin_reset` function, the `"reset-me"` string) to something private, and change
`app.secret_key` at the top of `app.py` to a random string — then push the change
to GitHub (Vercel auto-redeploys on every push to `main`).

## How scoring & the winner work (unchanged)

- Each employee enters **name + employee ID** and gets exactly **one attempt** —
  re-scanning shows their existing score instead of a new attempt.
- The clock starts the moment they tap "Start the quiz" and runs for the full
  duration (10 minutes by default); the quiz auto-submits whatever's answered so
  far if time runs out.
- Ranking = **highest score first, then fastest completion time** as the tiebreaker.
- All results live in Upstash Redis (a small free cloud database) — free tier
  comfortably covers a few hundred submissions for a one-day event.

## Notes

- This needs internet on both ends (server + staff phones) — unlike the local
  version, it does NOT work with zero internet. Make sure the venue has usable
  WiFi or that staff can use mobile data.
- Free Vercel + free Upstash tier is plenty for a single-day internal company quiz
  (dozens to low hundreds of participants). No credit card required for either free tier.
- Want a custom domain instead of `*.vercel.app`? You can add one for free in the
  Vercel project's **Domains** tab if you already own one — otherwise the default
  `.vercel.app` link works fine and doesn't cost anything.
