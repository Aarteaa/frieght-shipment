# Shipment Analytics — Business Answers

I want to front-load one thing before the actual answers: about half the "obvious" findings in this dataset don't survive a significance test, and one column (`status`) turned out to be almost useless. That shaped how I approached all five questions below — I'd rather tell you what's actually real than hand you five confident-sounding stories, three of which would fall apart the moment someone asks "how sure are you?"

**Methodology, once, so I don't repeat it five times:** 5,000 unique shipments (15 duplicate `shipment_id`s dropped). I don't trust the `status` column for delay math — see Q4 for why — so every on-time/late figure below is computed directly from `actual_delivery_date` vs. `promised_delivery_date`, on the 3,446 shipments where that comparison is actually possible and valid.

---

### Q1 — Which region has the worst on-time delivery performance, and what's actually driving it?

Honestly? None of them. Here's the on-time rate by region:

| Region | On-time rate | n |
|---|---|---|
| Central | 48.3% | 836 |
| North | 49.6% | 811 |
| East | 50.4% | 820 |
| West | 51.3% | 855 |
| South | 52.4% | 124 |

Central looks worst by four points, but I ran a chi-square test on region vs. on-time and got **p = 0.75** — that gap is comfortably explainable by chance. I'm not going to write a paragraph about "why Central underperforms" when the honest answer is that it doesn't, statistically. Same story for shipping mode (FTL/LTL/PTL): p = 0.69, no signal.

The one place a test actually comes back significant is **carrier** (p = 0.035) — weak, but real, and it's the only dimension in this whole question that clears the bar. CARR_02, CARR_07, and CARR_13 sit lowest on time-performance (40–45% on-time vs. a 50% average), while CARR_11 and CARR_14 sit highest (54–55%). If ops wants to move the needle on delivery performance, that's a carrier conversation, not a regional one.

One caveat on South specifically: its 124-shipment sample isn't just small — I dug into why, and it's not random (see Q4, point 1). Treat South's number as unreliable rather than "best-performing."

---

### Q2 — Is there a relationship between freight cost and distance? Which carrier(s) deviate, and by how much?

Yes, distance genuinely drives cost — but only once you take one carrier out of the picture. Fit a straight line through cost vs. distance for the whole dataset and you get a weak-looking R² of 0.09, which would normally make me say "not much of a relationship here." But that's misleading: **one carrier is so far off the pricing curve that it drags the whole regression down.**

Exclude CARR_07 and the relationship snaps into focus — correlation 0.73, R² 0.54, and a clean **₹16.4 per km** marginal cost. That's the real market rate. I'd trust this version of the number, not the pooled one, because a single extreme outlier shouldn't get to define what "normal" pricing looks like for the other 14 carriers.

CARR_07 itself: average cost of **₹159/km**, against a ₹16–17/km range for every other carrier — **roughly 9.6x the market rate**, and I checked this holds separately within FTL, LTL, and PTL, so it isn't an artifact of CARR_07 happening to run more expensive loads. This is either a real pricing/contract problem, a unit or decimal error somewhere upstream, or a carrier worth a direct conversation before renewing anything with them.

---

### Q3 — Which customer(s) are experiencing the most delays? Is that carrier-, region-, or something-else-driven?

Top of the list by delay rate (minimum 20 shipments so a couple of unlucky trips don't distort things):

| Customer | Delay rate | n |
|---|---|---|
| CUST_026 | 73.9% | 23 |
| CUST_050 | 71.0% | 31 |
| CUST_116 | 70.6% | 34 |
| CUST_063 | 69.7% | 33 |

CUST_026 stands out, but when I looked at *why*, I couldn't find one: their shipments run across roughly ten different carriers and all four regions with no concentration in any single one. Their most-used carrier delays them at almost exactly the same rate it delays everyone else. That tells me this isn't a carrier problem or a regional problem for this customer — it's either genuinely bad luck on a sample of 23, or something about this customer's shipments themselves (lane, product type, delivery window) that isn't captured in this dataset. I'd flag it for the ops team to watch over the next month rather than presenting it as a solved mystery.

---

### Q4 — What data quality issues did you find, and how did you handle them?

Four things worth calling out, roughly in order of how much they matter:

**1. South region has a near-total data gap that isn't random.** Every other region has an `actual_delivery_date` recorded for 100% of its Delivered/Delayed shipments. South has it for **15.5%** — 125 out of 807. That's not "South is a smaller region," that's "something in South's data pipeline isn't writing delivery dates." I didn't try to explain or impute this; I just excluded the unfilled rows and flagged South's numbers everywhere as low-confidence.

**2. The `status` column doesn't reliably describe what actually happened.** I cross-checked it against the dates directly: **50.2% of shipments labeled "Delivered" were actually late**, and **51.4% labeled "Delayed" were actually on-time**. That's a coin flip. Whatever process assigns this label isn't reading from the same dates that are sitting right next to it in the same row. Every delay calculation in this document ignores `status` as a signal and uses the dates only.

**3. 72 shipments show delivery before pickup.** `actual_delivery_date` is earlier than `pickup_date` — logically impossible. I treated these as invalid and excluded them from delay math rather than guessing which date was wrong.

**4. Smaller stuff:** `delivery_date` is a byte-for-byte duplicate of `promised_delivery_date` (dropped, no information). 15 duplicate `shipment_id`s (kept first occurrence). 71 missing `booking_date` and 87 missing `pickup_date` values, spread with no pattern across statuses — plain gaps, not systematic.

---

### Q5 — One metric to track weekly to catch delivery problems early?

**Share of currently in-transit shipments already past their promised delivery date.**

On-time rate tells you about shipments that already finished — by the time it moves, the damage is done. This metric catches a shipment while it's still fixable: you can expedite it, get ahead of the customer call, or swap carriers mid-route. I'd pair it with one more thing given what I found above — a weekly check of how often `status` disagrees with the dates. If that gap doesn't close, it means nobody can trust the operational dashboard built on top of `status`, and that's worth fixing before anything else on this list.
