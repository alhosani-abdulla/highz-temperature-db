# Data Model

## Database Schema

The temperature database uses five core tables with foreign key relationships to maintain referential integrity and enable efficient queries.

## Tables

### `deployments`

Represents a single deployment period of sensors at a site.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `deployment_id` | INTEGER | PRIMARY KEY | Auto-incrementing unique identifier |
| `name` | TEXT | NOT NULL, UNIQUE | Human-readable deployment name |
| `site` | TEXT | NOT NULL | Site/location name |
| `timezone_name` | TEXT | NOT NULL | IANA timezone (e.g., "America/New_York") |
| `timezone_fixed_offset` | TEXT | | Fixed UTC offset (e.g., "-05:00") to prevent DST issues |
| `notes` | TEXT | | Optional deployment notes |
| `created_at_utc` | INTEGER | NOT NULL | Insertion timestamp (epoch seconds) |

**Purpose:**
- Group temperature readings by deployment campaign
- Track timezone for timestamp conversion
- Store deployment-level metadata
- Support fixed timezone offsets to prevent DST conversion errors

**Fixed Timezone Offsets:**

Sensor clocks remain unsynced after initialization and don't follow DST transitions. The `timezone_fixed_offset` field prevents incorrect conversions:
- If sensors initialized in EST: `-05:00`
- If sensors initialized in EDT: `-04:00`

This ensures timestamps are converted correctly even when deployments span DST transitions.

**Example rows:**
```
deployment_id | name            | site  | timezone_name       | notes
1            | Adak_2025Dec    | Adak  | America/New_York    | Winter deployment
2            | LunarDry_2025Nov| LDL   | America/New_York    | Fall test
```

---

### `sensors`

Catalog of all temperature sensors used across deployments.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `sensor_id` | INTEGER | PRIMARY KEY | Auto-incrementing unique identifier |
| `sensor_type` | TEXT | NOT NULL | Sensor model (e.g., "ibutton_ds1925") |
| `part_number` | TEXT | | Manufacturer part number |
| `registration_number` | TEXT | UNIQUE | Unique sensor serial number |
| `label` | TEXT | | Human-readable label |
| `created_at_utc` | INTEGER | NOT NULL | First appearance timestamp |

**Purpose:**
- Identify individual sensors across deployments
- Track sensor metadata
- Enable sensor-specific queries

**Why registration_number is unique:**
Each physical sensor has a permanent serial number that uniquely identifies it across all deployments.

**Example rows:**
```
sensor_id | sensor_type     | registration_number | label              
1         | ibutton_ds1925  | 0000ABC123         | Antenna Top
2         | ibutton_ds1925  | 0000DEF456         | Ground Level
```

---

### `sensor_deployments`

Junction table linking sensors to deployments with deployment-specific metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `sensor_id` | INTEGER | PRIMARY KEY, FK | References `sensors` |
| `deployment_id` | INTEGER | PRIMARY KEY, FK | References `deployments` |
| `location` | TEXT | | Deployment-specific sensor location |
| `notes` | TEXT | | Deployment-specific notes |

**Purpose:**
- Store deployment-specific sensor metadata
- Support sensor reuse across multiple deployments
- Track different locations for same sensor in different deployments

**Why this table exists:**
Sensors are often reused across deployments but placed in different locations each time. This table allows each sensor-deployment combination to have its own location and notes, while the `sensors` table tracks only permanent sensor properties.

**Example rows:**
```
sensor_id | deployment_id | location                          | notes
1         | 1            | Antenna mount, north face         | Exposed to wind
1         | 2            | RF box, upper compartment         | Temperature controlled
2         | 1            | Digital spec enclosure, center    | Near power supply
```

---

### `files`

Tracks all ingested CSV files with hash-based deduplication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `file_id` | INTEGER | PRIMARY KEY | Auto-incrementing unique identifier |
| `deployment_id` | INTEGER | NOT NULL, FK | References `deployments` |
| `sensor_id` | INTEGER | NOT NULL, FK | References `sensors` |
| `path` | TEXT | NOT NULL | Path to original CSV file |
| `sha256` | TEXT | NOT NULL, UNIQUE | SHA256 hash of file contents |
| `parsed_at_utc` | INTEGER | NOT NULL | Ingestion timestamp (epoch seconds) |
| `metadata_json` | TEXT | | JSON blob of header metadata |

**Purpose:**
- Prevent duplicate ingestion (same file twice)
- Track provenance (which CSV produced which readings)
- Store raw sensor metadata for audit

**Why SHA256 hash:**
Uniquely identifies file contents. If the same file is ingested twice (even with different paths), it will be detected and skipped.

**What's in metadata_json:**
All key-value pairs from the iButton CSV header:
```json
{
  "Part Number": "DS1925L",
  "Registration Number": "0000ABC123",
  "Mission Start Time": "12/01/25 08:00:00 AM",
  "Sample Rate": "1.0 Minute",
  "Resolution": "0.5 C",
  ...
}
```

**Example rows:**
```
file_id | deployment_id | sensor_id | path                    | sha256           | parsed_at_utc
1       | 1            | 1         | /Data/Adak/sensor1.csv  | a3f2b1...        | 1735689600
```

---

### `temperature_readings`

Individual temperature measurements from sensors.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `reading_id` | INTEGER | PRIMARY KEY | Auto-incrementing unique identifier |
| `file_id` | INTEGER | NOT NULL, FK | References `files` |
| `deployment_id` | INTEGER | NOT NULL, FK | References `deployments` (denormalized) |
| `sensor_id` | INTEGER | NOT NULL, FK | References `sensors` (denormalized) |
| `time_local_text` | TEXT | NOT NULL | Original timestamp string from CSV |
| `time_utc` | INTEGER | NOT NULL | Unix epoch seconds in UTC |
| `value_c` | REAL | NOT NULL | Temperature in Celsius |
| `quality_flag` | INTEGER | DEFAULT 0 | Data quality flag (0=good) |

**Purpose:**
- Store individual temperature measurements
- Enable time-based queries
- Track data quality

**Why denormalize deployment_id and sensor_id?**
- Faster queries without joins
- More efficient indexes
- Negligible storage cost (~8 bytes per row)
- Can verify consistency: `file.deployment_id == reading.deployment_id`

**Why store both time_local_text and time_utc?**

1. **time_local_text**: Original timestamp exactly as recorded by sensor
   - Scientific integrity: never modify raw data
   - Audit trail: can verify conversion later
   - Debugging: check for parsing issues

2. **time_utc**: Converted timestamp for analysis
   - Consistent comparison across sensors
   - Handles daylight saving time
   - Required for future spectrum joins
   - Efficient indexing and filtering

**quality_flag values:**
- `0`: Good data (default)
- `1`: Suspicious (e.g., sensor malfunction indicated in metadata)
- `2`: Out of range (future: automatic validation)
- `3`: User flagged (future: manual review)

**Example rows:**
```
reading_id | file_id | sensor_id | time_local_text      | time_utc   | value_c | quality_flag
1          | 1       | 1         | 12/01/25 08:00:00 AM | 1733054400 | -5.5    | 0
2          | 1       | 1         | 12/01/25 08:01:00 AM | 1733054460 | -5.4    | 0
```

---

## Indexes

Indexes dramatically speed up common queries at negligible storage cost.

### `idx_sensor_time` on `(sensor_id, time_utc)`
**Used for:**
- "Get all temperatures from sensor X between time A and B"
- Plotting single sensor over time
- Finding min/max/avg temperature for a sensor

### `idx_deployment_time` on `(deployment_id, time_utc)`
**Used for:**
- "Get all temperatures from deployment X between time A and B"
- Comparing all sensors in a deployment
- Deployment-wide statistics

### `idx_file` on `(file_id)`
**Used for:**
- Tracing readings back to source CSV
- Aggregating by file
- Verifying ingestion counts

### `idx_file_sha256` on `(sha256)`
**Used for:**
- Fast duplicate detection during ingestion
- Finding file by hash

---

## Views

Pre-defined views for common queries.

### `v_temperature_data`

All readings with full context (no joins needed).

**Columns:**
- `reading_id`
- `deployment_name`
- `site`
- `sensor_type`
- `registration_number`
- `sensor_label`
- `time_local_text`
- `time_utc_iso` (human-readable UTC)
- `time_utc` (epoch seconds)
- `value_c`
- `quality_flag`
- `source_file`

**Usage:**
```sql
SELECT * FROM v_temperature_data 
WHERE deployment_name = 'Adak_2025Dec'
AND time_utc BETWEEN 1733054400 AND 1735689600;
```

### `v_file_summary`

Summary of ingested files with reading counts.

**Columns:**
- `file_id`
- `path`
- `deployment_name`
- `registration_number`
- `ingested_at`
- `num_readings`

**Usage:**
```sql
SELECT * FROM v_file_summary 
WHERE deployment_name = 'Adak_2025Dec';
```

---

## Relationships

```
deployments (1) ──── (many) files
                │
                ├──── (many) temperature_readings
                │
                └──── (many) sensor_deployments

sensors (1) ──────── (many) files
           │
           ├──────── (many) temperature_readings
           │
           └──────── (many) sensor_deployments

files (1) ────────── (many) temperature_readings
```

**Foreign key constraints:**
- Ensure referential integrity
- Prevent orphaned readings
- Enable cascading operations (if configured)

---

## Data Types

### Why INTEGER for timestamps?

SQLite's `INTEGER` for Unix epoch seconds:
- ✅ Compact storage (8 bytes)
- ✅ Fast comparison
- ✅ Easy conversion to datetime
- ✅ No timezone ambiguity

vs. SQLite's `TEXT` datetime:
- ❌ Larger storage
- ❌ Slower comparison
- ❌ Timezone parsing issues

### Why REAL for temperatures?

SQLite's `REAL` (floating-point):
- ✅ Sufficient precision for sensor data (±0.5°C)
- ✅ Efficient storage
- ✅ Standard for scientific data

### Why TEXT for metadata_json?

SQLite has limited JSON support. Using `TEXT`:
- ✅ Store arbitrary metadata
- ✅ Future-proof (new sensor types)
- ✅ Human-readable
- ✅ Can parse with `json.loads()` in Python

---

## Design Decisions

### No Data Aggregation

**Decision:** Store every individual reading, no averaging or downsampling.

**Rationale:**
- Original data may reveal important transients
- Downsampling decisions should be analysis-specific
- Storage is cheap
- Can always aggregate in queries

### Denormalization in temperature_readings

**Decision:** Include `deployment_id` and `sensor_id` directly (even though they're in `files`).

**Rationale:**
- 90% of queries filter by deployment or sensor
- Eliminates one join
- Minimal storage cost
- Easier to maintain indexes

### Both Local and UTC Timestamps

**Decision:** Store both `time_local_text` and `time_utc`.

**Rationale:**
- Original data integrity (never modify raw timestamps)
- UTC for consistent analysis
- Audit trail for timezone conversion
- Handle DST edge cases

### JSON Metadata Storage

**Decision:** Store sensor header as JSON blob instead of structured columns.

**Rationale:**
- Different sensor types have different metadata
- Future sensors may add new fields
- Rarely queried (just for audit)
- Easy to parse in Python

---

## Future Extensions

### Adding Spectrum Data

```sql
CREATE TABLE spectrum_files (
    spectrum_file_id INTEGER PRIMARY KEY,
    deployment_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    FOREIGN KEY (deployment_id) REFERENCES deployments(deployment_id)
);

CREATE TABLE spectrum_readings (
    spectrum_id INTEGER PRIMARY KEY,
    spectrum_file_id INTEGER NOT NULL,
    deployment_id INTEGER NOT NULL,
    time_utc INTEGER NOT NULL,
    frequency_mhz REAL NOT NULL,
    power_dbm REAL NOT NULL,
    FOREIGN KEY (spectrum_file_id) REFERENCES spectrum_files(spectrum_file_id)
);

CREATE INDEX idx_spectrum_time ON spectrum_readings(time_utc);
```

**Join spectrum and temperature:**
```sql
SELECT 
    s.time_utc,
    s.frequency_mhz,
    s.power_dbm,
    t.value_c AS temperature
FROM spectrum_readings s
LEFT JOIN temperature_readings t 
    ON s.deployment_id = t.deployment_id
    AND ABS(s.time_utc - t.time_utc) < 60  -- within 1 minute
```

### Adding Calibration Data

```sql
CREATE TABLE calibrations (
    calibration_id INTEGER PRIMARY KEY,
    sensor_id INTEGER NOT NULL,
    valid_from_utc INTEGER NOT NULL,
    valid_to_utc INTEGER,
    offset_c REAL NOT NULL,
    scale_factor REAL NOT NULL DEFAULT 1.0,
    notes TEXT,
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);
```

Apply in query:
```python
df['value_c_calibrated'] = df['value_c'] * scale_factor + offset_c
```
