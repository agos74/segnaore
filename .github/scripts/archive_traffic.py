"""Archivia le statistiche Traffico di GitHub in stats/ (CSV + riepilogo).

Uso: GH_TOKEN=... REPO=owner/repo python3 archive_traffic.py [root_repo]
Legge le API /traffic/views, /traffic/popular/referrers e /popular/paths,
accoda solo le righe nuove e rigenera stats/RIEPILOGO.md.
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import date, timedelta

API = "https://api.github.com"


def fetch(path):
    token = os.environ["GH_TOKEN"]
    repo = os.environ["REPO"]
    req = urllib.request.Request(
        f"{API}/repos/{repo}/traffic/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def load_rows(csv_path):
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def append_new(csv_path, fieldnames, rows, key):
    existing = {r[key] for r in load_rows(csv_path)}
    fresh = [r for r in rows if r[key] not in existing]
    if not fresh and existing:
        return 0
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            w.writeheader()
        w.writerows(fresh)
    return len(fresh)


def sum_last(rows, days):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    sel = [r for r in rows if r["data"] >= cutoff]
    return (
        sum(int(r["visite"]) for r in sel),
        sum(int(r["unici"]) for r in sel),
        len(sel),
    )


def top(rows, run, n=5):
    sel = [r for r in rows if r["rilevazione"] == run]
    sel.sort(key=lambda r: int(r["visite"]), reverse=True)
    return [(r.get("referrer") or r.get("pagina"), r["visite"]) for r in sel[:n]]


def main(root="."):
    stats = os.path.join(root, "stats")
    views = fetch("views?per=day")
    refs = fetch("popular/referrers")
    paths = fetch("popular/paths")
    today = date.today().isoformat()

    n = append_new(
        os.path.join(stats, "visite.csv"),
        ["data", "visite", "unici"],
        [
            {
                "data": v["timestamp"][:10],
                "visite": v["count"],
                "unici": v["uniques"],
            }
            for v in views.get("views", [])
        ],
        "data",
    )
    append_new(
        os.path.join(stats, "referrer.csv"),
        ["rilevazione", "referrer", "visite", "unici"],
        [
            {
                "rilevazione": today,
                "referrer": r["referrer"],
                "visite": r["count"],
                "unici": r["uniques"],
            }
            for r in refs
        ],
        "referrer",
    )
    append_new(
        os.path.join(stats, "pagine.csv"),
        ["rilevazione", "pagina", "visite", "unici"],
        [
            {
                "rilevazione": today,
                "pagina": p["path"],
                "visite": p["count"],
                "unici": p["uniques"],
            }
            for p in paths
        ],
        "pagina",
    )

    visite = load_rows(os.path.join(stats, "visite.csv"))
    v7, u7, g7 = sum_last(visite, 7)
    v30, u30, g30 = sum_last(visite, 30)
    ref_rows = load_rows(os.path.join(stats, "referrer.csv"))
    runs = sorted({r["rilevazione"] for r in ref_rows})
    last = runs[-1] if runs else today
    pag_rows = load_rows(os.path.join(stats, "pagine.csv"))

    def lines(pairs):
        return "\n".join(f"- {name}: {c} visite" for name, c in pairs) or "- nessun dato"

    md = f"""# Traffico landing — riepilogo

_Aggiornato il {today} (giro settimanale automatico, fonte: API Traffico GitHub)._

## Ultimi 7 giorni ({g7} gg con dati)
- Visite: **{v7}** — visitatori unici: **{u7}**

## Ultimi 30 giorni ({g30} gg con dati)
- Visite: **{v30}** — visitatori unici: **{u30}**

## Top referrer (rilevazione {last})
{lines(top(ref_rows, last))}

## Top pagine (rilevazione {last})
{lines(top(pag_rows, last))}

_Nota: le API GitHub coprono 14 giorni; nuove righe aggiunte all'ultimo giro: {n}._
"""
    with open(os.path.join(stats, "RIEPILOGO.md"), "w") as f:
        f.write(md)
    print(f"OK: {n} giorni aggiunti, riepilogo al {today}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
