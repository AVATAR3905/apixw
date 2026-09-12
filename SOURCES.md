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
