# Source Registry, Legal Compliance & Reliability

> Compliance, robots.txt management, and collection resilience documentation.

---

## 1. Ethical & Legal Compliance Framework

The observatory enforces a four-stage compliance state-machine on all collection feeds:

```
[DISCOVERED] ---> [REVIEW_REQUIRED] ---> [APPROVED] ---> [ACTIVE]
                         |
                         v
                    [REJECTED]
```

1. **State Machine Rule:** No collection job is ever dispatched for a source whose state is not `APPROVED` or `ACTIVE`.
2. **Robots.txt & Terms of Service Auditing:** Prior to promotion to `APPROVED`, sources undergo automated and manual inspection for terms of service permissions.
3. **Public Data Exemption:** Official datasets (DGCA passenger traffic, MoSPI CPI reports, IOCL fuel notices) are registered under `PUBLIC_DATASET` authorization.

---

## 2. Circuit Breaker & Resilience Taxonomy

To avoid placing undue load on airline endpoints, all connector requests are gated by a per-source `CircuitBreaker` (`services/collectors/circuit_breaker.py`):

- **Failure Threshold:** 5 consecutive failures.
- **Recovery Timeout:** 60.0 seconds.
- **Max Retries:** 3 with exponential backoff ($50\text{ ms} \times 2^{\text{attempt}-1}$).
- **Permanent Exceptions:** Fatal permissions (`PERMISSION_DENIED`) and HTML layout changes (`SCHEMA_CHANGED`) abort immediately without wasteful retries.
- **Telemetry States:** `HEALTHY` $\rightarrow$ `WARNING` $\rightarrow$ `DEGRADED` $\rightarrow$ `DOWN`.

---

## 3. Cryptographic Raw Payload Integrity

Every collected payload is written to disk under `data/raw/{year}/{month}/{day}/{sha256}.{json|html}`:
- The SHA-256 hash is verified on read.
- Any file tampering or corruption raises `PayloadIntegrityError`.
- Enables complete, undeniable scientific audit trails for MoSPI statisticians.

---

## 4. Official Partner API Tier (Licensed GDS Feeds)

The portals that reject programmatic access at the transport level (Air India,
IndiGo, MakeMyTrip, Yatra — `ERR_HTTP2_PROTOCOL_ERROR` / IP-range block) are
**not** circumvented. Their legitimate replacement is a licensed partner/GDS
API relationship, exactly as the README and `TASKS.md` conclude:

| Source (seed id) | Type | Access policy | License required | Coverage |
|---|---|---|---|---|
| Amadeus Enterprise API (13) | `GDS_API` | `PARTNER_ONLY` | `PARTNER_AGREEMENT` (**commercial only** — self-service portal decommissioned 2026-07-17) | Air India + IndiGo inventory (`/v2/shopping/flight-offers`); adapter code-ready for enterprise credentials |
| Sabre Developer Hub (14) | `GDS_API` | `PARTNER_ONLY` | self-service test account (username/password → OAuth token) | Flight Shop API (`/v1/offers/flightShop`), PLAY cert env — parser modeled on the documented schema; reconcile on first live response |
| RapidAPI "Sky Scrapper" (Skyscanner, 12) | `METASEARCH` | `CONDITIONAL` | free RapidAPI key (live-verified Sep 2026) | metasearch discovery — real DEL→MAA fares confirmed |

### Integration contract

- **Adapter shape:** subclass of `BaseOTAScraper` implementing `_execute_scrape`
  (live licensed call) + `_generate_calibrated_quotes` (fallback). Missing
  credentials raise a key-missing exception that the base class converts to the
  tagged calibrated fallback — see `ota/amadeus_scraper.py`,
  `ota/sabre_scraper.py` and `ota/skyscanner_scraper.py`.
- **Feed tagging:** licensed GDS quotes carry `feed_type=PARTNER_API`, weighted
  at 0.85 in `FEED_QUALITY_WEIGHTS` (below carrier-direct 1.0 because GDS prices
  are fee-bundled; above OTA 0.7 because the data is licensed). Calibrated
  fallbacks always keep `extraction_method=CALIBRATED_MODEL` and are flagged
  `is_synthetic=True` downstream — a real observation can never be fabricated.
- **Governance:** sources gate through `SourceRegistryService.can_collect`
  (`PARTNER_ONLY` ⇒ license must be `PARTNER_AGREEMENT`); rate limits are the
  documented partner-API budgets (30 req/min), never beaten via egress
  rotation or fingerprint spoofing.
- **Honest disclosure:** Amadeus retired its free self-service developer portal
  on 2026-07-17 — its adapter only produces real data with an Enterprise
  agreement. Sabre's Developer Hub is the self-service licensed path that
  remains (free test account, PLAY cert environment); the RapidAPI Sky Scrapper
  wrapper has been live-verified in this repo against the free tier and returns
  real metasearch fares. Until enterprise credentials exist, any fallback stays
  clearly tagged as model-generated, never promoted to real.
