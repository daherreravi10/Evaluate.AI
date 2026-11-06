# Pitch (45 s, ~110 words) and demo (3 min) scripts

Fill the [brackets] from outputs/metrics_*.json. Record with a screen recorder; keep each file < 95 MB
(1080p, 30 fps, H.264 is plenty).

## pitch.mp4 — 45 seconds

1. (0–8 s) Hook, on screen the map of car-space premiums: "In the City of Sydney, a car space adds
   [$X] a week to a flat's rent. In [suburb] it's [$Y]. Nobody tells tenants that."
2. (8–25 s) What we made: "We estimate the weekly rent of all 65,777 flats, with and without parking,
   and the sale value of all 181,711 addresses."
3. (25–38 s) Proof: "Tested on adverts we never trained on, we miss by [$Z] a week." Only compare
   with the organisers' $86 if you also score their baseline on OUR held-out set (the report table
   does); their $86 was measured on a different set of adverts.
4. (38–45 s) Close: "Type any address, get rent, value and the reason. [Team name]."

## demo.mp4 — 3 minutes

1. (0:00–0:20) The problem: two flats on one street, very different rents. Who is overpaying?
2. (0:20–0:50) The data: the supplied adverts and sales, by date. The rule: nothing after the task date.
3. (0:50–1:40) The clever step, on screen: snapshot features, the anchor (own advert, own last price
   moved by the index, building), and the model's correction. Show `report.html` held-out table.
4. (1:40–2:30) Kerbside, the app: open an example flat, the two parking bays (rent with and without a
   car space), the sale value and how we got it. Type a quoted rent into "Is this rent fair?".
   Scroll to "Around this flat": with and without a car, what is close, what is being built.
   Then the map tab: what a car space adds, building by building, checked against the raw adverts.
5. (2:30–3:00) What we found ([insight 1], [insight 2]) and what we'd do next.
