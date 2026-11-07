"""Narration for demo.mp4: one voice clip per sentence, then a timeline the recorder follows.

Every number below comes from outputs/metrics_*.json or the hand-in CSVs (see pitch/numbers.md).
`caption` is what appears on screen; `say` is the same sentence with numbers written out for the voice.

    python scripts/demo_narration.py            # all clips + videos/demo/timeline.json + narration.wav
    VOICE=default python scripts/demo_narration.py   # neutral stock voice instead of the owner's
    ELEVEN_VOICE=<voice id> python scripts/demo_narration.py   # ElevenLabs (cloud, uses credits)

Needs `voice-say` (local Chatterbox) and ffmpeg. Output goes to videos/demo/ (git-ignored).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "videos" / "demo"
GAP = 0.25          # seconds between sentences
SECTION_GAP = 0.6   # at least this much between sections
LIMIT = 179.0       # the video must stay under 3:00

# (name, earliest start in seconds, [(caption, say), ...]); sections run back to back to fit 3:00
SECTIONS = [
    ("problem", 0, [
        ("Two flats on the same street in the City of Sydney can rent for very different prices, and one of "
         "them might have a car space nobody puts a price on.", None),
        ("We're Evaluate.AI.", "We're Evaluate A I."),
        ("We built one model that answers two questions for every flat in the City: what should it rent for, "
         "and what is it worth?", None),
    ]),
    ("data", 0, [
        ("We estimated the weekly rent of all 65,777 flats, twice, with and without a car space, and the sale "
         "value of all 181,711 addresses.",
         "We estimated the weekly rent of all sixty-five thousand, seven hundred and seventy-seven flats, twice, "
         "with and without a car space, and the sale value of all one hundred and eighty-one thousand, "
         "seven hundred and eleven addresses."),
        ("One strict rule: for rents, nothing dated after the 31st of July; for values, nothing after the "
         "31st of August.",
         "One strict rule: for rents, nothing dated after the thirty-first of July; for values, nothing after "
         "the thirty-first of August."),
        ("Every table goes through a date filter first, so the model never sees the future.", None),
    ]),
    ("report", 0, [
        ("We built on everything before the 1st of May 2026, then tested on 3,866 later adverts and 547 later "
         "sales the model had never seen.",
         "We built on everything before the first of May, twenty twenty-six, then tested on three thousand, "
         "eight hundred and sixty-six later adverts and five hundred and forty-seven later sales the model "
         "had never seen."),
        ("Our clever step is the anchor: for each flat we start from what we already know (its own last "
         "advert, its last sale moved by the market index, or its building), and the model learns the "
         "correction on top.",
         "Our clever step is the anchor. For each flat we start from what we already know: its own last "
         "advert, its last sale moved by the market index, or its building. And the model learns the "
         "correction on top."),
        ("On rents we miss by a median of $43 a week, and 81% of estimates land within $100.",
         "On rents we miss by a median of forty-three dollars a week, and eighty-one percent of estimates "
         "land within a hundred dollars."),
        ("On sale values, 65% of held-out sales land within 10%.",
         "On sale values, sixty-five percent of held-out sales land within ten percent."),
        ("The organisers' valuations: $86 a week and 34 of 227 sales, on their own scoring set.",
         "The organisers' valuations: eighty-six dollars a week, and thirty-four of two hundred and "
         "twenty-seven sales, on their own scoring set."),
        ("And 227 sales is a small test: 227 of ours drawn at random score from 61% to 70%.",
         "And two hundred and twenty-seven sales is a small test: random draws of ours score from sixty-one to "
         "seventy percent."),
    ]),
    ("app", 0, [
        ("Here's the app.", None),
        ("I type a street, 73 Victoria Street, and pick Unit 906.",
         "I type a street, seventy-three Victoria Street, and pick Unit nine oh six."),
        ("Rent first: $1,112 a week with its car space, $992 without, so the car space is worth about $120 a "
         "week here.",
         "Rent first: one thousand, one hundred and twelve dollars a week with its car space, nine hundred and "
         "ninety-two without, so the car space is worth about a hundred and twenty dollars a week here."),
        ("Below that: what's within walking distance.", None),
        ("Each number says how we got it: this one started from the flat's own last advert.", None),
        ("Got a quote? Type it in and it tells you whether it's fair.", None),
        ("And similar flats nearby.", None),
        ("Switch to Sale: $1,797,000, starting from its last sale moved by the market.",
         "Switch to Sale: one million, seven hundred and ninety-seven thousand dollars, starting from its last "
         "sale moved by the market."),
        ("On the map tab, each dot is a building, coloured by what a car space adds.", None),
        ("Across the City the median is $76.50 a week; on 816 like-for-like pairs of raw adverts, it's $71.",
         "Across the City the median is seventy-six dollars fifty a week. On eight hundred and sixteen "
         "like-for-like pairs of raw adverts, it's seventy-one dollars."),
    ]),
    ("close", 0, [
        ("First, the starting guess does most of the work: take it away and the rent miss grows from $43 to "
         "$254 a week.",
         "First, the starting guess does most of the work. Take it away, and the rent miss grows from "
         "forty-three dollars to two hundred and fifty-four dollars a week."),
        ("Second, a recent For Sale advert is gold: when a flat had one, 137 of 142 test sales landed within "
         "10%.",
         "Second, a recent For Sale advert is gold. When a flat had one, a hundred and thirty-seven of a "
         "hundred and forty-two test sales landed within ten percent."),
        ("Next, we'd add live transport and development applications to explain where rents are heading.", None),
        ("Type any address, get rent, value and the reason.", None),
        ("We're Evaluate.AI. Thank you.", "We're Evaluate A I. Thank you."),
    ]),
]


def duration(wav: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(wav)], capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def render(voice: str) -> list[Path]:
    """All sentences in one voice-say run (the model loads once), split back into one clip per sentence.

    voice-say joins takes with exactly 0.35 s of digital silence (all-zero samples), so the joins are found
    exactly by looking for runs of zeros that long.
    """
    import wave

    import numpy as np

    lines = [say or caption for _, _, ls in SECTIONS for caption, say in ls]
    script, full = OUT / "script.txt", OUT / "all.wav"
    script.write_text("\n".join(lines) + "\n")
    if not full.exists():
        subprocess.run(["voice-say", "-f", str(script), "--voice", voice, "--verify", "2", "-o", str(full)],
                       check=False)
    sr = 24000
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(full), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    mono = np.frombuffer(pcm, dtype=np.int16)
    zero = np.concatenate([[False], mono == 0, [False]]).astype(int)
    starts, ends = np.flatnonzero(np.diff(zero) == 1), np.flatnonzero(np.diff(zero) == -1)
    joins = [(a, b) for a, b in zip(starts, ends) if b - a >= int(sr * 0.34)]
    if len(joins) != len(lines) - 1:
        sys.exit(f"Found {len(joins)} joins for {len(lines)} sentences; split by hand.")
    cuts = [0] + [x for a, b in joins for x in (a, b)] + [len(mono)]
    wavs = []
    for i in range(len(lines)):
        w = OUT / f"line_{i:02d}.wav"
        with wave.open(str(w), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(mono[cuts[2 * i]:cuts[2 * i + 1]].tobytes())
        wavs.append(w)
    return wavs


def render_eleven(voice_id: str) -> list[Path]:
    """One ElevenLabs take per sentence (cloud, spends account credits), as 24 kHz mono WAV."""
    from concurrent.futures import ThreadPoolExecutor

    lines = [say or caption for _, _, ls in SECTIONS for caption, say in ls]

    def one(i: int) -> Path:
        import hashlib

        key = hashlib.sha1(f"{voice_id}|{lines[i]}".encode()).hexdigest()[:10]
        mp3, wav = OUT / f"el_{key}.mp3", OUT / f"line_{i:02d}.wav"
        if not mp3.exists():  # cached by text, so editing one sentence re-buys only that one
            subprocess.run(["elevenlabs", "tts", lines[i], "--voice", voice_id, "-o", str(mp3)], check=True)
        trim = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                "silenceremove=start_periods=1:start_threshold=-45dB,areverse")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-af", trim, "-ac", "1", "-ar", "24000",
                        str(wav)], check=True)
        return wav

    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(one, range(len(lines))))


def main() -> None:
    voice = os.environ.get("VOICE", "sol")
    OUT.mkdir(parents=True, exist_ok=True)
    eleven = os.environ.get("ELEVEN_VOICE")
    wavs = iter(render_eleven(eleven) if eleven else render(voice))
    timeline, t = [], 0.0
    for name, planned, lines in SECTIONS:
        t = max(float(planned), t + SECTION_GAP if timeline else 0.0)
        sec = {"name": name, "start": round(t, 2), "lines": []}
        for caption, _ in lines:
            wav = next(wavs)
            d = duration(wav)
            sec["lines"].append({"caption": caption, "wav": str(wav), "start": round(t, 2), "dur": round(d, 2)})
            t += d + GAP
        t -= GAP
        sec["end"] = round(t, 2)
        timeline.append(sec)
        print(f"{name:8s} {sec['start']:6.1f} -> {sec['end']:6.1f}  ({sec['end'] - sec['start']:.1f} s)")
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1))

    # one narration track: each clip placed at its start time
    lines = [ln for s in timeline for ln in s["lines"]]
    inputs, filters = [], []
    for k, ln in enumerate(lines):
        inputs += ["-i", ln["wav"]]
        ms = int(ln["start"] * 1000)
        filters.append(f"[{k}:a]aresample=48000,adelay={ms}|{ms}[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(lines)))
    filters.append(f"{mix}amix=inputs={len(lines)}:normalize=0,apad=whole_dur={LIMIT + 1}[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
                    "-ac", "2", str(OUT / "narration.wav")], check=True)
    end = timeline[-1]["end"]
    print(f"narration ends at {end:.1f} s")
    if end > LIMIT:
        sys.exit(f"Too long: {end:.1f} s > {LIMIT} s. Shorten a sentence and run again.")


if __name__ == "__main__":
    main()
