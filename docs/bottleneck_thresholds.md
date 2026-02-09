# Bottleneck Threshold Configuration

## Overview

Orket's bottleneck detection uses configurable thresholds to distinguish **normal operation** from **real problems**. This prevents alert fatigue and helps you focus on actual bottlenecks.

## Why Thresholds Matter

**Without thresholds:**
- 3 cards waiting for VRAM → "CRITICAL ALERT!" (wrong - this is normal)
- High VRAM usage during work → "RESOURCE BOTTLENECK!" (wrong - this is expected)

**With thresholds:**
- 3 cards waiting → "OK: normal serial execution" (correct)
- >10 cards waiting → "WARNING: chronic bottleneck" (correct)

## Configuration

Thresholds are defined in your `organization.json` file:

```json
{
  "bottleneck_thresholds": {
    "resource_normal": 3,
    "resource_warning": 10,
    "resource_critical": 11,
    "dependency_warning_pct": 0.5,
    "human_attention_threshold": 1
  }
}
```

## Threshold Reference

### `resource_normal` (default: 3)

**Meaning:** Cards waiting for resources below this threshold = normal serial execution

**When to increase:**
- You have multiple LLM slots available
- You run tasks in parallel
- Example: 4 GPUs → set to 12 (3 per GPU)

**When to decrease:**
- You have very limited resources (1 small GPU)
- You want stricter alerting
- Example: Raspberry Pi → set to 1

### `resource_warning` (default: 10)

**Meaning:** Cards waiting 4-10 = mild backlog (monitor but don't alert)

**When to increase:**
- You're comfortable with larger queues
- You batch process work
- Example: Overnight processing → set to 50

**When to decrease:**
- You want faster feedback on queue growth
- You have strict SLAs
- Example: Real-time system → set to 5

### `resource_critical` (default: 11)

**Meaning:** Cards waiting >10 = chronic bottleneck (alert and take action)

**When to increase:**
- Large batch jobs are normal
- Queue depth is expected
- Example: CI/CD system → set to 100

**When to decrease:**
- You need immediate alerts
- Resources are scarce
- Example: Shared machine → set to 5

### `dependency_warning_pct` (default: 0.5)

**Meaning:** Alert if >50% of blocked cards are dependency-blocked

**When to increase:**
- Your workflows are naturally sequential
- Long dependency chains are normal
- Example: Waterfall process → set to 0.8

**When to decrease:**
- You want to catch dependency pile-ups early
- Parallel work is expected
- Example: Microservices → set to 0.3

### `human_attention_threshold` (default: 1)

**Meaning:** Alert if any cards need human review/input

**When to increase:**
- Human review is batched (daily/weekly)
- You don't want constant alerts
- Example: Weekly review cycle → set to 5

**When to decrease:**
- Never (1 is already the minimum)
- Human attention should always be flagged

## Hardware-Specific Examples

### Local Workstation (1 GPU, 24GB VRAM)

```json
{
  "resource_normal": 3,
  "resource_warning": 8,
  "resource_critical": 10
}
```

**Rationale:** Serial execution is normal, but queue shouldn't grow beyond ~10 cards.

### Server (4 GPUs, 96GB VRAM)

```json
{
  "resource_normal": 12,
  "resource_warning": 40,
  "resource_critical": 50
}
```

**Rationale:** Can run 4 parallel tasks, so ~3 queued per GPU is normal.

### Raspberry Pi (CPU only, 8GB RAM)

```json
{
  "resource_normal": 1,
  "resource_warning": 3,
  "resource_critical": 5
}
```

**Rationale:** Very limited resources, tight thresholds to prevent overload.

### Cloud (Auto-scaling)

```json
{
  "resource_normal": 10,
  "resource_warning": 50,
  "resource_critical": 100
}
```

**Rationale:** Can scale up, so larger queues are acceptable before alerting.

## Tuning Strategy

### Step 1: Start with defaults

Run Orket for a week with default thresholds and observe patterns.

### Step 2: Measure your baseline

- How many cards are typically queued during normal operation?
- What's your max observed queue depth during busy periods?
- How often do you see "CRITICAL" alerts?

### Step 3: Adjust thresholds

- If you see too many false alarms → increase thresholds
- If you miss real problems → decrease thresholds
- If alerts are actionable and accurate → keep current settings

### Step 4: Monitor and iterate

Bottleneck patterns change as your workload evolves. Review thresholds quarterly.

## Diagnostic Output Examples

### Normal Operation

```
** Status: 3 blocked, 1 active
   OK: 3 card(s) queued (normal serial execution)
```

**Action:** None - work is flowing as expected.

### Mild Backlog

```
** Status: 8 blocked, 1 active
   WARNING: Queue building up (8 cards)
   ACTION: Monitor queue depth, consider scaling if it persists
```

**Action:** Watch the trend. If queue keeps growing, investigate.

### Chronic Bottleneck

```
** Status: 15 blocked, 1 active
   CRITICAL: Large queue (15 cards) - chronic bottleneck!
   ACTION: Add more LLM capacity or reduce concurrency
```

**Action:** This is a real problem. Add resources or optimize workload.

### No Work Running

```
** Status: 5 blocked, 0 active
   CRITICAL: 5 blocked but nothing running!
   ACTION: Check resource allocation - cards blocked but no work in progress
```

**Action:** Something is misconfigured. Resources should be available but aren't being used.

## Best Practices

1. **Tune for YOUR hardware** - Default thresholds are for a typical local workstation
2. **Document your settings** - Explain why you chose specific values
3. **Review periodically** - Workload changes over time
4. **Test under load** - Simulate high load to validate thresholds
5. **Prefer false negatives over false positives** - Better to miss an alert than drown in noise

## Related

- [Wait Reason Documentation](wait_reason.md)
- [Priority System Documentation](priority.md)
- [Resource Declaration Documentation](resource_declaration.md)
