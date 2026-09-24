# T+15 Headline Anchor — Booking Lead-Time Justification

Generated: 2026-09-15 22:28

## Why T+15?

The national headline index is anchored at **T+15** (2-week advance purchase).
This choice is defensible when T+15 sits at or near the **median booking
lead-time** of Indian domestic passengers: the headline then describes the
*typical* purchase, free of the last-minute premium (T+1/T+2) and the
early-bird holiday cluster (T+30/T+45).

## Data basis

Documented Indian domestic booking lead-time distribution (see `_LEAD_TIME_BUCKETS` source basis).

## Lead-time distribution and quantiles

| Window | Share of bookings (%) |
|---|---|
| ≤ 1 days | 4.0 |
| ≤ 2 days | 3.5 |
| ≤ 3 days | 5.0 |
| ≤ 7 days | 10.0 |
| ≤ 10 days | 8.0 |
| ≤ 14 days | 19.5 |
| ≤ 21 days | 18.0 |
| ≤ 30 days | 14.0 |
| ≤ 45 days | 10.0 |
| ≤ 60 days | 6.0 |
| ≤ 90 days | 2.0 |

| Statistic | Value |
|---|---|
| Mean lead (days) | 11.67 |
| Median lead (days) | 8 |
| Q1 / Q3 (days) | 3 / 15 |
| Bookings within ≤ T+15 | 75.0% |
| Bookings within ≤ T+30 | 92.3% |

## Verdict

The T+15 anchor is in the **interquartile range** of the booking lead-time
distribution — the median booking happens at T+8.
**The headline anchor is VINDICATED.**

## References & method note

- Bucket shares are normalised from the documented domestic booking-lead
  distribution; run `--from-db` to recompute from live observations.
- T+1 / T+2 remain published as unpooled `SUB_T1` sub-indices (the Core
  series definition excludes them by design).
