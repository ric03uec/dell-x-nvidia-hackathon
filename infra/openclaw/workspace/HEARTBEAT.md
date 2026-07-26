# Heartbeat

Periodic heartbeat turns are currently disabled. Do not claim continuous
monitoring while they are disabled.

When an operator enables heartbeats and provides a traffic or findings
interface, each heartbeat should:

1. Check source, collector, detector, and dashboard health.
2. Query for new high-severity findings or meaningful baseline deviations.
3. Correlate new evidence without re-alerting unchanged findings.
4. Report actionable anomalies and verification evidence.
5. Never apply a blocking or destructive rule without explicit operator
   confirmation.
