# Timezone Handling

## Overview

Temperature sensors for the highz experiment record timestamps in **Pittsburgh local time**. This document explains how local timestamps are converted to UTC and why specific design decisions were made.

---

## Core Facts

### Sensor Clock Initialization

- All iButton sensors are initialized in **Pittsburgh, PA**
- Clocks are set to **local wall time** before deployment
- **Timezone:** `America/New_York` (IANA standard)
- **Not** `EST` or `EDT` (these are ambiguous abbreviations)

### What is America/New_York?

`America/New_York` is an **IANA timezone identifier** that:
- Automatically handles daylight saving time transitions
- Knows the history of timezone rules (past and future)
- Provides unambiguous timezone conversion

**DST rules for America/New_York:**
- **Spring forward:** Second Sunday in March at 2:00 AM → 3:00 AM
- **Fall back:** First Sunday in November at 2:00 AM → 1:00 AM
- **Standard time:** UTC-5 (EST)
- **Daylight time:** UTC-4 (EDT)

---

## Why Store Both Local and UTC?

### Original Local Timestamps (`time_local_text`)

**Stored exactly as written in CSV:**
```
12/01/25 08:00:00 AM
```

**Why preserve?**
1. **Scientific integrity:** Never modify raw data
2. **Audit trail:** Can verify conversion logic later
3. **Debugging:** Check for parsing errors
4. **Reproducibility:** Original data always available

### UTC Timestamps (`time_utc`)

**Converted to Unix epoch seconds:**
```
1733054400  (seconds since 1970-01-01 00:00:00 UTC)
```

**Why convert to UTC?**
1. **Consistent comparison:** All timestamps on same basis
2. **No DST ambiguity:** UTC never changes
3. **Future joins:** Will align with spectrum data (also UTC)
4. **Standard practice:** International standard for scientific data

---

## Daylight Saving Time Challenges

### The Spring Gap (Missing Hour)

**What happens:**
- At 2:00 AM on second Sunday in March, clocks jump to 3:00 AM
- Times between 2:00 AM and 3:00 AM **don't exist**

**Example:**
```
2025-03-09 01:59:59 EST (UTC-5)
2025-03-09 03:00:00 EDT (UTC-4)  ← no 2:30 AM!
```

**In our data:**
- If a sensor records "03/09/25 02:30:00 AM", this is **invalid**
- Python will either:
  - Raise an error (if strict)
  - Interpret as 03:30:00 EDT (our approach)

**Our policy:**
- Trust sensor clock (assume it jumped correctly)
- If timestamp exists in CSV, convert as-is
- Document any anomalies in quality_flag

### The Fall Overlap (Ambiguous Hour)

**What happens:**
- At 2:00 AM on first Sunday in November, clocks fall back to 1:00 AM
- Times between 1:00 AM and 2:00 AM **occur twice**

**Example:**
```
2025-11-02 01:30:00 EDT (UTC-4)  ← first occurrence
2025-11-02 01:30:00 EST (UTC-5)  ← second occurrence (1 hour later!)
```

**The problem:**
Given "11/02/25 01:30:00 AM", which occurrence is it?

**Our policy: FOLD=1 (second occurrence = standard time)**

Python's `datetime.replace(tzinfo=..., fold=1)`:
- `fold=0`: First occurrence (assume DST still in effect)
- `fold=1`: Second occurrence (assume standard time)

**We choose `fold=1` because:**
1. Sensors typically don't update clocks automatically during deployment
2. If clock "fell back", second occurrence is more likely
3. Consistent, documented policy for audit
4. Worst case: 1-hour offset during that specific hour
5. Can be corrected in post-processing if needed

---

## Fixed Timezone Offset Mode

### The Problem with DST Auto-Conversion

Sensor clocks are initialized in Pittsburgh local time, but they **do not sync with world time** after deployment. This creates issues when deployments span DST transitions:

**Example scenario:**
- Sensors initialized on Nov 1, 2025 at 10:00 AM EDT (UTC-4)
- DST ends Nov 2, 2025 at 2:00 AM → clocks "fall back" to EST (UTC-5)
- **But sensor clocks don't change** - they keep running in EDT
- If we assume EST after Nov 2, all timestamps are off by 1 hour!

### Solution: Fixed Timezone Offsets

Use a **fixed UTC offset** matching when sensors were initialized:

```json
{
  "timezone": "America/New_York",
  "timezone_fixed_offset": "-04:00"
}
```

This tells the ingestion script:
- Use `-04:00` (EDT) for **all** timestamps in this deployment
- Don't apply DST transition rules
- Convert timestamps as if they're always in EDT

### When to Use Fixed Offsets

**Use `-05:00` (EST) if:**
- Sensors initialized November - March
- Deployment entirely during EST period

**Use `-04:00` (EDT) if:**
- Sensors initialized March - November  
- Deployment entirely during EDT period

**Important:** Once sensors are initialized, they stay in that offset for the entire deployment.

### Implementation

In `utils.py::local_to_utc()`:

```python
def local_to_utc(local_time_str: str, 
                 timezone_name: str = "America/New_York",
                 fixed_offset: str = None) -> int:
    """
    If fixed_offset is provided (e.g., "-05:00"), use it instead of 
    timezone_name to prevent DST-related conversion errors.
    """
    dt = datetime.strptime(local_time_str, "%m/%d/%y %I:%M:%S %p")
    
    if fixed_offset:
        # Use fixed offset, ignore DST rules
        tz = timezone(timedelta(hours=int(fixed_offset.split(':')[0]),
                               minutes=int(fixed_offset.split(':')[1])))
        dt_aware = dt.replace(tzinfo=tz)
    else:
        # Use timezone with DST rules (original behavior)
        tz = ZoneInfo(timezone_name)
        dt_aware = dt.replace(tzinfo=tz, fold=1)
    
    return int(dt_aware.timestamp())
```

### Verification

```python
# Without fixed offset (WRONG for unsynced sensors)
local_to_utc("11/03/25 10:00:00 AM", "America/New_York")
# → Assumes EST after Nov 2, gives UTC-5 offset

# With fixed offset (CORRECT)
local_to_utc("11/03/25 10:00:00 AM", "America/New_York", "-04:00")
# → Uses EDT throughout, maintains UTC-4 offset
```

---

## Conversion Implementation

### Code: `utils.py::local_to_utc()`

```python
from datetime import datetime
from zoneinfo import ZoneInfo

def local_to_utc(local_time_str: str, timezone_name: str = "America/New_York") -> int:
    """
    Convert local timestamp string to UTC epoch seconds.
    
    During fall-back ambiguity, assumes standard time (fold=1).
    """
    # Parse string to datetime
    dt = datetime.strptime(local_time_str, "%m/%d/%y %I:%M:%S %p")
    
    # Localize to timezone with fold=1 policy
    tz = ZoneInfo(timezone_name)
    localized_dt = dt.replace(tzinfo=tz, fold=1)
    
    # Convert to UTC epoch
    return int(localized_dt.timestamp())
```

### Example Conversions

**Normal time (winter):**
```
Local:  12/15/25 02:30:00 PM (EST, UTC-5)
UTC:    1734282600
ISO:    2025-12-15 19:30:00+00:00
```

**Normal time (summer):**
```
Local:  07/15/25 02:30:00 PM (EDT, UTC-4)
UTC:    1752656400
ISO:    2025-07-15 18:30:00+00:00
```

**Spring gap (missing hour):**
```
Local:  03/09/25 02:30:00 AM (invalid!)
UTC:    (interpreted as 03:30:00 EDT)
```

**Fall overlap (ambiguous hour):**
```
Local:  11/02/25 01:30:00 AM (ambiguous!)
UTC:    (fold=1 → second occurrence, EST)
```

---

## Verification

### How to verify conversion is correct:

**1. Spot-check in Python:**
```python
from datetime import datetime
from zoneinfo import ZoneInfo

local_str = "12/15/25 02:30:00 PM"
dt = datetime.strptime(local_str, "%m/%d/%y %I:%M:%S %p")
dt_local = dt.replace(tzinfo=ZoneInfo("America/New_York"))
dt_utc = dt_local.astimezone(ZoneInfo("UTC"))

print(f"Local: {dt_local}")
print(f"UTC:   {dt_utc}")
print(f"Epoch: {int(dt_utc.timestamp())}")
```

**2. Compare with online converter:**
- https://www.epochconverter.com/
- https://www.timeanddate.com/worldclock/converter.html

**3. Check database:**
```sql
SELECT 
    time_local_text,
    datetime(time_utc, 'unixepoch') AS time_utc_iso,
    time_utc
FROM temperature_readings
LIMIT 10;
```

Compare `time_local_text` with `time_utc_iso` (should differ by 4 or 5 hours).

---

## Edge Cases

### Case 1: Sensor Clock Drift

**Problem:** Sensor clock gradually drifts from true time.

**Detection:**
- Compare sensor timestamps at start and end of deployment
- Check against known reference events

**Solution:**
- Apply linear correction in post-processing
- Document in `quality_flag` or separate calibration table

### Case 2: Wrong Timezone Setting

**Problem:** Sensor was actually deployed in different timezone.

**Solution:**
- Re-ingest data with correct timezone
- Or apply offset correction in analysis

### Case 3: Sensor Crosses DST Boundary

**Problem:** Deployment spans spring forward or fall back.

**Expected behavior:**
- Spring: Gap in data around 2:00 AM
- Fall: Data continues normally (fold=1 policy handles it)

**Verification:**
```sql
-- Check for suspicious gaps (>10 minutes)
SELECT 
    time_local_text,
    time_utc,
    LAG(time_utc) OVER (PARTITION BY sensor_id ORDER BY time_utc) AS prev_time_utc,
    (time_utc - LAG(time_utc) OVER (PARTITION BY sensor_id ORDER BY time_utc)) AS gap_seconds
FROM temperature_readings
WHERE gap_seconds > 600
ORDER BY time_utc;
```

---

## Best Practices

### For Data Collection

1. **Initialize sensor clocks accurately**
   - Use NTP-synchronized computer
   - Record initialization time for audit

2. **Label sensors clearly**
   - Timestamp when clock is set
   - Note timezone setting

3. **Document deployment times**
   - Record deployment start/end in UTC
   - Note any clock resets during deployment

### For Data Analysis

1. **Always use UTC for comparisons**
   - Time differences
   - Alignment with other data
   - Multi-sensor synchronization

2. **Convert to local only for display**
   - Plotting for human review
   - Reports and publications
   - User interfaces

3. **Be aware of DST transitions**
   - Gaps in spring
   - Overlaps in fall
   - Filter or flag if needed

### For Database Queries

1. **Filter on `time_utc`, not `time_local_text`**
   ```sql
   -- Good
   WHERE time_utc BETWEEN 1733054400 AND 1735689600
   
   -- Bad (slow, error-prone)
   WHERE time_local_text LIKE '12/01/25%'
   ```

2. **Convert epoch to ISO in queries**
   ```sql
   SELECT datetime(time_utc, 'unixepoch') AS readable_time
   ```

3. **Use indexed columns**
   - `time_utc` is indexed
   - `time_local_text` is not

---

## Future Considerations

### If Sensors Are Deployed Elsewhere

If future deployments occur in different timezones:

1. **Update deployment record:**
   ```sql
   UPDATE deployments 
   SET timezone_name = 'America/Anchorage'  -- or whatever
   WHERE name = 'NewDeployment';
   ```

2. **Use deployment timezone in queries:**
   ```python
   # Get timezone from deployment
   tz_name = get_deployment_timezone(db, deployment_name)
   
   # Convert using that timezone
   utc_time = local_to_utc(local_str, timezone_name=tz_name)
   ```

3. **Document timezone changes:**
   - In deployment `notes` field
   - In analysis documentation

### If UTC is Needed at Collection Time

For future deployments, consider:
- Sensors that record UTC directly
- Dual timestamps (local + UTC)
- GPS time synchronization

---

## References

- IANA Time Zone Database: https://www.iana.org/time-zones
- Python `zoneinfo` docs: https://docs.python.org/3/library/zoneinfo.html
- PEP 495 (fold parameter): https://peps.python.org/pep-0495/
- Daylight Saving Time: https://www.timeanddate.com/time/dst/

---

## Summary

✅ **Sensors record:** Pittsburgh local time (`America/New_York`)  
✅ **Database stores:** Both local text and UTC epoch  
✅ **Queries use:** UTC for filtering, local for display  
✅ **DST handling:** `fold=1` policy (prefer standard time)  
✅ **Audit trail:** Original timestamps never modified  
✅ **Future-proof:** Can handle timezone changes per deployment  
