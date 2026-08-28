#!/usr/bin/env python3
"""
The last day's play in the four World Cup qualifiers, as an embeddable page.

    python gr_fiba_page.py
    python gr_fiba_page.py --as-of 2026-08-27      # force a day, for checking

Writes out/fiba-qualifiers.html: four tables, one per confederation, each showing
that day's players with their Global Rating, their line, the result and the flag of
who they played.

THE DAY IT SHOWS, AND WHEN IT MOVES

Settled rather than live. On the 28th it shows the 27th, and it moves to the 28th at
nine in the morning New York time on the 29th -- so a table never changes under a
reader during the day, and a game finishing late at night is never half-counted.

    9am ET on the 29th ---> shows the 28th
    8am ET on the 29th ---> still shows the 27th

If nothing was played on that date it falls back to the most recent day that had
games, rather than showing an empty table: these are tournaments with rest days, and
an empty page reads as a fault.

WHY NOT SIMPLY YESTERDAY

Because "yesterday" changes at midnight, in whichever timezone the reader happens to
be in, and a European reader would see a day appear while games were still being
played in the Americas. One boundary, one timezone, stated.
"""

import os
import csv
import sys
import argparse
import datetime
import collections

VERSION = "v1.6.0-our-names"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "nba_rgm_gr")
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

try:
    import rgm_flags as FL
except ImportError:
    FL = None

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                                            # noqa: BLE001
    ET = None

COMPETITIONS = [
    ("FIBA AfroBasket Qualifier", "Africa"),
    ("African World Cup Qualifier", "Africa"),
    ("European World Cup Qualifier", "Europe"),
    ("Americas World Cup Qualifier", "Americas"),
    ("Asian World Cup Qualifier", "Asia"),
]


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def show_date(now=None):
    """
    -> the date the page should show, by the nine-o'clock rule.

    The anchor is today in New York, moved back a day if it is before nine in the
    morning; the page shows the day before that anchor. Two steps rather than one
    because the rule has two parts -- when the day flips, and how far behind it
    sits -- and folding them into a single subtraction hides both.
    """
    now = now or (datetime.datetime.now(ET) if ET else datetime.datetime.now())
    anchor = now.date()
    if now.hour < 9:
        anchor -= datetime.timedelta(days=1)
    return anchor - datetime.timedelta(days=1)


def names():
    """
    player_id -> the name to print, in the platform's order of preference.

    1. hh_name from players_nba.csv -- the HoopsHype spelling, which is the one the
       rest of the platform publishes.
    2. players_manual.csv, hand-edited, which outranks anything fetched.
    3. players.csv, RealGM's own.

    The name in the box score is the last resort and is what this page used to
    show, which is why some read differently from everywhere else: RealGM writes
    what the federation gave it, and the federations are not consistent.
    """
    out = {}
    for name in ("players.csv", "players_national.csv", "players_dict.csv",
                 "players_manual.csv"):
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    pid = (r.get("player_id") or "").strip()
                    nm = (r.get("name") or "").strip()
                    if pid and nm and nm != "-":
                        out[pid] = nm
        except OSError:
            continue
    p = os.path.join(OUT, "players_nba.csv")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    rid = (r.get("realgm_id") or "").strip()
                    hh = (r.get("hh_name") or "").strip()
                    if rid and hh:
                        out[rid] = hh
        except OSError:
            pass
    return out


def team_names():
    """RealGM's team name -> the name we publish, from teams_manual.csv."""
    path = os.path.join(OUT, "teams_manual.csv")
    if not os.path.exists(path):
        return {}
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t = (r.get("team") or "").strip()
                hh = (r.get("hh_name") or "").strip()
                if t and hh and hh != "-":
                    out[t] = hh
    except OSError:
        return {}
    return out


def flag(name, label=None):
    """
    The flag is looked up on RealGM's name and LABELLED with ours.

    Two different jobs: the code map was built against RealGM's spellings and still
    has to be, while the tooltip is what a reader sees and should match the rest of
    the platform.
    """
    code = ""
    if FL is not None:
        try:
            code = FL.code_for(name) or ""
        except Exception:                                    # noqa: BLE001
            code = ""
    shown = label or name
    if not code:
        return ""
    return (f'<img src="https://flagcdn.com/w40/{code}.png" alt="{esc(shown)}" '
            f'title="{esc(shown)}" loading="lazy">')


def load(leagues, upto):
    """
    -> {league: {date: [rows]}} for the games on or before `upto`.

    Read from gr_all.csv, which is what the ratings themselves are built from, so a
    line on this page and the same line in the viewer cannot disagree.
    """
    src = os.path.join(OUT, "gr_all.csv")
    if not os.path.exists(src):
        return {}
    want = {lg for lg, _ in leagues}
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    with open(src, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lg = (r.get("league") or "").strip()
            if lg not in want:
                continue
            d = (r.get("date") or "")[:10]
            if not d or d > upto:
                continue
            out[lg][d].append(r)
    return out


def scores(rows):
    """-> {(game, team): points}, so a result can be shown without a scores file."""
    tot = collections.Counter()
    for r in rows:
        tot[(r.get("game_id"), (r.get("team") or "").strip())] += int(fnum(r.get("pts")))
    return tot


HEAD = """<colgroup><col class="c-rk"><col class="c-fl"><col class="c-pl">
<col class="c-rat"><col class="c-n"><col class="c-n"><col class="c-n"><col class="c-n">
<col class="c-res"><col class="c-fl"></colgroup>
<thead><tr><th></th><th></th><th class="l">Player</th>
<th>Rat</th><th>Min</th><th>Pts</th><th>Reb</th><th>Ast</th>
<th>Result</th><th>vs</th></tr></thead>"""


def table(rows, top, nm=None, tm=None):
    if not rows:
        return ""
    sc = scores(rows)
    best = sorted(rows, key=lambda r: -fnum(r.get("gr")))[:top]
    body = []
    for i, r in enumerate(best, 1):
        team = (r.get("team") or "").strip()
        opp = (r.get("opp") or "").strip()
        shown_team = (tm or {}).get(team) or team
        shown_opp = (tm or {}).get(opp) or opp
        gid = r.get("game_id")
        us, them = sc.get((gid, team), 0), sc.get((gid, opp), 0)
        # The opponent's total is only there when both sides of the game were
        # fetched. Without it the result is unknown, and a blank says so rather
        # than a score that is half a game.
        if us and them:
            # THE LETTER IN A BOX OF ITS OWN, because W is wider than L in this
            # font and the cell is right-aligned: the difference lands between the
            # letter and the score, so every loss sat a fraction left of every win
            # and the column looked crooked down the page.
            won_it = us > them
            # ONE STRING, right-aligned in the column. Three attempts at lining
            # the letters up in their own boxes each fixed a real fault and none
            # was the one being asked for; right-aligned text needs none of it.
            res = f'<b>{"W" if won_it else "L"}</b> {us}-{them}'
            cls = "w" if won_it else "l"
        else:
            res, cls = "&ndash;", ""
        body.append(
            "<tr>"
            f'<td class="rk">{i}</td>'
            f'<td class="fl">{flag(team, shown_team)}</td>'
            f'<td class="l pl">'
            f'{esc((nm or {}).get((r.get("player_id") or "").strip()) or r.get("player", ""))}'
            f'</td>'
            f'<td class="rat">{fnum(r.get("gr")):.1f}</td>'
            f'<td>{int(fnum(r.get("min")))}</td>'
            f'<td>{int(fnum(r.get("pts")))}</td>'
            f'<td>{int(fnum(r.get("reb")))}</td>'
            f'<td>{int(fnum(r.get("ast")))}</td>'
            f'<td class="res {cls}">{res}</td>'
            f'<td class="fl">{flag(opp, shown_opp)}</td>'
            "</tr>")
    return "<table>" + HEAD + "<tbody>" + "\n".join(body) + "</tbody></table>"


CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;padding:0;background:#fff;color:#1a1a2e;
  font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,
  sans-serif}
.wrap{max-width:680px;margin:0 auto;padding:2px}
h3{margin:18px 0 2px;font-size:15px;letter-spacing:-.2px}
h3:first-child{margin-top:2px}
p.day{margin:0 0 8px;color:#8a8aa0;font-size:12px}
table{border-collapse:collapse;width:100%;table-layout:fixed;margin-bottom:4px}
col.c-rk{width:26px}
col.c-fl{width:28px}
col.c-pl{width:auto}
col.c-rat{width:46px}
col.c-n{width:38px}
col.c-res{width:86px}
th,td{padding:5px 4px;border-bottom:1px solid #ecedf3;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
th{font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#6a6a80;
  text-align:right;border-bottom:1px solid #d8d9e3}
th.l,td.l{text-align:left}
td{text-align:right;font-variant-numeric:tabular-nums}
td.rk{color:#9a9ab0;font-size:12px}
td.fl{padding:0 2px}
td.fl img{display:block;width:22px;height:auto;border-radius:2px;margin:0 auto}
td.pl{font-weight:600;white-space:normal;overflow:visible;text-overflow:clip;
  line-height:1.25}
td.rat{font-weight:700;color:#8a5a00}
td.res{font-size:12px;color:#5a5a72;white-space:nowrap;text-align:right;
  font-variant-numeric:tabular-nums}
td.res.w b{color:#1a7f37}
td.res.l b{color:#a33}
tr:nth-child(even) td{background:#fafafd}
.none{color:#8a8aa0;font-size:12px;margin:2px 0 10px}
@media(max-width:560px){
  th,td{padding:5px 2px;font-size:13px}
  col.c-rk{width:20px}
  col.c-fl{width:24px}
  col.c-rat{width:40px}
  col.c-n{width:30px}
  col.c-res{width:76px}
  td.fl img{width:19px}
}
"""

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>World Cup qualifiers</title>
<style>{css}</style></head><body><div class="wrap">
{sections}
</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--as-of", default="",
                    help="show this date instead of working it out")
    ap.add_argument("--out", default=os.path.join(HERE, "out",
                                                  "fiba-qualifiers.html"))
    a = ap.parse_args()

    print(f"gr_fiba_page {VERSION}")
    upto = a.as_of.strip() or show_date().isoformat()
    now_et = (datetime.datetime.now(ET) if ET else datetime.datetime.now())
    print(f"  {now_et.strftime('%Y-%m-%d %H:%M')} in New York"
          f"  ->  showing {upto}" + ("  (forced)" if a.as_of else ""))
    if ET is None:
        print("  !! no timezone database, so this is local time, not New York")

    nm, tm = names(), team_names()
    print(f"  {len(nm):,} name(s) from the database, {len(tm)} club name(s)")
    data = load(COMPETITIONS, upto)
    if not data:
        print(f"  nothing found in {os.path.join(OUT, 'gr_all.csv')}")
        return 1

    secs = []
    for lg, label in COMPETITIONS:
        days = data.get(lg) or {}
        if not days:
            print(f"    {label:<10} {lg:<32} no games at all")
            continue
        # The most recent day ON OR BEFORE the target, so a rest day shows the last
        # night that was played rather than an empty table.
        day = max(days)
        rows = days[day]
        t = table(rows, a.top, nm, tm)
        if not t:
            continue
        stale = "" if day == upto else f" &middot; last played"
        secs.append(f"<h3>{esc(label)}</h3>"
                    f'<p class="day">{esc(day)}{stale}</p>{t}')
        print(f"    {label:<10} {lg:<32} {day}  {len(rows):>4} line(s),"
              f" top {min(a.top, len(rows))} shown"
              + ("" if day == upto else "   (nothing on the target day)"))

    if not secs:
        print("  no competition has any games -- nothing written")
        return 1

    html = PAGE.format(css=CSS, sections="\n".join(secs))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"  -> {a.out}  ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
