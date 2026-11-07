"""Record demo.mp4: title cards, report.html and the app, following the narration timeline.

    streamlit run app/app.py --server.port 8501 --server.headless true   # in another terminal
    python scripts/demo_narration.py      # voice clips + videos/demo/timeline.json
    python scripts/record_demo.py         # -> demo.mp4 (1920x1080, 30 fps, H.264, under 3:00)

Needs Playwright (pip install playwright==1.59.0 && playwright install chromium) and ffmpeg.
Captions are drawn inside the page, so ffmpeg needs no subtitle filter. Raw video goes to videos/ (git-ignored).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEMO = Path(os.environ.get("DEMO_DIR", ROOT / "videos" / "demo"))
APP = os.environ.get("APP_URL", "http://localhost:8501")
W, H = 1920, 1080
TAIL = 1.5  # seconds kept after the last word

# ------------------------------------------------------------------ page helpers (captions, cover, scrolling)
OVERLAY_JS = """
(args) => {
  const [lines, now] = args;
  let bar = document.getElementById('__cap');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = '__cap';
    bar.style.cssText = 'position:fixed;left:50%;bottom:36px;transform:translateX(-50%);z-index:2147483647;' +
      'max-width:1500px;padding:16px 28px;border-radius:14px;background:rgba(18,22,21,.86);color:#fff;' +
      'font:500 30px/1.35 Barlow,"Helvetica Neue",Arial,sans-serif;text-align:center;pointer-events:none;' +
      'transition:opacity .25s;opacity:0';
    document.body.appendChild(bar);
    const tag = document.createElement('div');
    tag.textContent = 'Synthetic voice';
    tag.style.cssText = 'position:fixed;right:18px;top:14px;z-index:2147483647;font:500 15px Barlow,Arial,' +
      'sans-serif;color:rgba(255,255,255,.85);background:rgba(18,22,21,.55);padding:4px 10px;border-radius:6px;' +
      'pointer-events:none';
    document.body.appendChild(tag);
    // Playwright only records a frame when the page repaints; a still page would drop time from the video.
    const tick = document.createElement('div');
    tick.style.cssText = 'position:fixed;left:0;bottom:0;width:2px;height:2px;z-index:2147483647;pointer-events:none';
    document.body.appendChild(tick);
    let n = 0;
    const beat = () => { tick.style.background = (n++ % 2) ? 'rgba(0,0,0,.02)' : 'rgba(0,0,0,.03)';
                         requestAnimationFrame(beat); };
    requestAnimationFrame(beat);
  }
  (window.__capTimers || []).forEach(clearTimeout);
  window.__capTimers = [];
  const show = (t) => { bar.textContent = t; bar.style.opacity = t ? 1 : 0; };
  show('');
  for (const l of lines) {
    const a = (l.start - now) * 1000, b = (l.start + l.dur - now) * 1000;
    if (b <= 0) continue;
    window.__capTimers.push(setTimeout(() => show(l.caption), Math.max(0, a)));
  }
  const last = lines[lines.length - 1];
  window.__capTimers.push(setTimeout(() => show(''), Math.max(0, (last.start + last.dur + 0.6 - now) * 1000)));
}
"""

SCROLL_JS = """
async ([sel, text, nth, ms, offset]) => {
  let els = [...document.querySelectorAll(sel)];
  if (text) els = els.filter(e => e.textContent.includes(text));
  const el = els[nth];
  if (!el) return 'missing';
  let box = el.parentElement;
  while (box && !(box.scrollHeight > box.clientHeight + 5 && /auto|scroll/.test(getComputedStyle(box).overflowY)))
    box = box.parentElement;
  const sc = box || document.scrollingElement;
  const top = (box ? el.getBoundingClientRect().top - box.getBoundingClientRect().top : el.getBoundingClientRect().top)
              + sc.scrollTop - offset;
  const from = sc.scrollTop, t0 = performance.now();
  await new Promise(done => {
    const step = (t) => {
      const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      sc.scrollTop = from + (top - from) * e;
      k < 1 ? requestAnimationFrame(step) : done();
    };
    requestAnimationFrame(step);
  });
  return 'ok';
}
"""


def card(title: str, rows: list[str], small: str = "") -> str:
    items = "".join(f'<li>{r}</li>' for r in rows)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#16191B;color:#fff;
font-family:Barlow,"Helvetica Neue",Arial,sans-serif}}
.c{{max-width:1400px;padding:0 80px}} h1{{font-size:96px;line-height:1.05;margin:0 0 36px;letter-spacing:-.01em}}
ul{{list-style:none;padding:0;margin:0}} li{{font-size:46px;line-height:1.3;margin:0 0 22px;color:#E9ECE8}}
li b{{color:#EDBB2A;font-weight:600}} p{{font-size:28px;color:#AEB6B2;margin:30px 0 0}}
</style></head><body><div class="c"><h1>{title}</h1><ul>{items}</ul>{f'<p>{small}</p>' if small else ''}</div>
</body></html>"""


CARDS = {
    "problem": card("Evaluate.AI", ["Every flat in the City of Sydney:",
                                    "what should it <b>rent</b> for, with and without a car space,",
                                    "and what is it <b>worth</b>?"]),
    "data": card("The data and the rule", [
        "<b>65,777</b> flats: weekly rent, with and without a car space",
        "<b>181,711</b> addresses: sale value on 31 August 2026",
        "Rents: nothing dated after <b>31 July 2026</b>",
        "Values: nothing dated after <b>31 August 2026</b>"],
        "Every table goes through one date filter first (src/asof.py)."),
    "close": card("What we found", [
        "Without the starting guess, the rent miss grows from <b>$43</b> to <b>$254</b> a week",
        "Flats with a For Sale advert: <b>137 of 142</b> test sales within 10%",
        "Next: live transport and development applications"],
        "Type any address, get rent, value and the reason. Evaluate.AI"),
}


class Run:
    def __init__(self, page: Page, timeline: list[dict]):
        self.page, self.timeline = page, timeline
        self.lines = [ln for s in timeline for ln in s["lines"]]
        self.t0 = None

    def now(self) -> float:
        return time.monotonic() - self.t0

    def at(self, t: float) -> None:
        """Wait (letting Playwright work) until t seconds into the narration."""
        while self.now() < t:
            self.page.wait_for_timeout(min(200, max(1, (t - self.now()) * 1000)))

    def captions(self) -> None:
        self.page.evaluate(OVERLAY_JS, [self.lines, self.now()])

    def scroll(self, sel: str, text: str = "", nth: int = 0, ms: int = 1800, offset: int = 90) -> None:
        r = self.page.evaluate(SCROLL_JS, [sel, text, nth, ms, offset])
        if r != "ok":
            print(f"  scroll target not found: {sel} {text!r} #{nth}")

    def section(self, name: str) -> dict:
        return next(s for s in self.timeline if s["name"] == name)

    def line(self, name: str, i: int) -> float:
        return self.section(name)["lines"][i]["start"]


def show_card(run: Run, name: str) -> None:
    run.page.set_content(CARDS[name])
    run.captions()


def record(run: Run) -> None:
    p = run.page
    # 0:00 problem + 0:20 data: title cards
    show_card(run, "problem")
    run.at(run.section("data")["start"] - 0.3)
    show_card(run, "data")

    # 0:50 report.html, down to the held-out tables
    run.at(run.section("report")["start"] - 0.2)
    p.goto((ROOT / "report.html").as_uri())
    run.captions()
    run.at(run.line("report", 0) + 1.0)
    run.scroll("h2", "Method", ms=5000, offset=40)
    run.at(run.line("report", 2) - 0.5)
    run.scroll("h3", "Held-out check", nth=0, ms=2500, offset=40)
    run.at(run.line("report", 3) - 0.3)
    run.scroll("h3", "Held-out check", nth=1, ms=2500, offset=40)
    run.at(run.line("report", 5) - 0.3)
    run.scroll("h3", "Why 227 sales", ms=1500, offset=40)

    # 1:40 the app
    run.at(run.section("app")["start"] - 1.2)
    p.goto(APP)
    run.captions()
    box = p.get_by_placeholder("Start typing a street, like Powell Street")
    box.wait_for(timeout=30_000)
    run.at(run.line("app", 1) - 0.3)
    box.click()
    box.press_sequentially("73 Victoria Street", delay=35)
    box.press("Enter")
    p.get_by_text("Building: 73 Victoria Street").first.wait_for(timeout=20_000)
    p.wait_for_timeout(900)
    box.click()
    box.press("ControlOrMeta+a")
    box.press_sequentially("Unit 906, 73 Victoria Street", delay=30)
    box.press("Enter")
    p.locator(".bay").first.wait_for(timeout=20_000)
    run.at(run.line("app", 3) - 0.2)
    run.scroll("#around", ms=1600, offset=20)
    run.at(run.line("app", 4) - 0.2)
    run.scroll("#fair", ms=1600, offset=40)
    run.at(run.line("app", 5))
    q = p.get_by_label("Weekly rent quoted ($)")
    q.click()
    q.press("ControlOrMeta+a")
    q.press_sequentially("1200", delay=80)
    q.press("Enter")
    p.locator(".verdict").first.wait_for(timeout=15_000)
    run.at(run.line("app", 6) - 0.2)
    run.scroll("#similar", ms=1600, offset=60)
    run.at(run.line("app", 7) - 0.4)
    p.evaluate("document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0 })")
    p.get_by_role("radio", name="Sale", exact=True).click()
    p.locator(".bay.sale").first.wait_for(timeout=20_000)
    p.wait_for_timeout(2600)
    run.scroll("h3", "How we got the value", ms=1800, offset=120)
    run.at(run.line("app", 8) - 0.3)
    p.evaluate("document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0 })")
    p.get_by_role("tab", name="Car spaces across the city").click()
    p.get_by_text("Checked against the raw adverts").wait_for(timeout=20_000)

    # 2:30 close
    run.at(run.section("close")["start"] - 0.3)
    show_card(run, "close")
    run.at(run.timeline[-1]["end"] + TAIL)


def warm_up(browser) -> None:
    """Load the app once, unrecorded, so its caches are warm before the take."""
    ctx = browser.new_context(viewport={"width": W, "height": H})
    pg = ctx.new_page()
    pg.goto(APP)
    pg.get_by_placeholder("Start typing a street, like Powell Street").wait_for(timeout=120_000)
    box = pg.get_by_placeholder("Start typing a street, like Powell Street")
    box.fill("Unit 906, 73 Victoria Street")
    box.press("Enter")
    pg.locator(".bay").first.wait_for(timeout=120_000)
    pg.get_by_role("tab", name="Car spaces across the city").click()
    pg.get_by_text("Checked against the raw adverts").wait_for(timeout=120_000)
    ctx.close()


def main() -> None:
    timeline = json.loads((DEMO / "timeline.json").read_text())
    raw = DEMO / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--mute-audio"])
        warm_up(browser)
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(raw),
                                  record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        started = time.monotonic()
        run = Run(page, timeline)
        page.set_content(CARDS["problem"])
        run.t0 = time.monotonic()
        lead = run.t0 - started
        record(run)
        video = Path(page.video.path())
        ctx.close()
        browser.close()
    end = timeline[-1]["end"] + TAIL
    out = ROOT / "demo.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{lead:.3f}", "-i", str(video), "-i", str(DEMO / "narration.wav"),
        "-t", f"{end:.2f}", "-map", "0:v", "-map", "1:a", "-vf", f"fps=30,scale={W}:{H}:flags=lanczos",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    mb = out.stat().st_size / 1e6
    print(f"demo.mp4: {end:.1f} s, {mb:.1f} MB (video lead trimmed: {lead:.2f} s)")


if __name__ == "__main__":
    main()
