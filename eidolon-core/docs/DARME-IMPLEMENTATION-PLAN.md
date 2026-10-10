# DARME implementation plan

Status: development only; no network enforcement.

1. Fix and test R1-R5 in the event projection.
2. Add bounded durable SQLite event storage, append-only acknowledgements and integrity checks.
3. Add a read-only status API with authentication and freshness timestamps.
4. Implement passive journald and listening-port collectors, using synthetic test inputs first.
5. Integrate the compact DARME badge in the Windows dashboard.
6. Benchmark Qwen3 0.6B Q4 and 1.7B Q4 on CPU, using normalized events only.
7. Review deployment isolation, logging privacy, backup and rollback.

No automatic firewall changes, poweroff, offensive traffic or main branch merge.
