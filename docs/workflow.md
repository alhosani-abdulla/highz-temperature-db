# Workflows

## After a Field Deployment

### 1. Extract Data from Sensors

**Physical process:**
1. Connect iButton sensor to USB reader
2. Use manufacturer software to download CSV file
3. Save CSV with descriptive name (e.g., `sensor_ABC123_adak_dec2025.csv`)

**Organize files:**
```bash
Data/temp_raw/
├── Adak/
│   └── 2025Dec/
│       ├── deployment_metadata.json  # Optional metadata file
│       ├── Antenna_iButton_Dec2025.csv
│       ├── DigitalSpec_iButton_Dec2025.csv
│       └── RFBox_iButton_Dec2025.csv
```

### 2. Create Deployment Metadata (Optional but Recommended)

Create a `deployment_metadata.json` file in the same directory as your CSV files:

```json
{
  "deployment_notes": "December 2025 deployment - cold weather testing",
  "sensors": {
    "Antenna": {
      "location": "Antenna mount, north face, 2m above ground",
      "notes": "Exposed to wind and precipitation"
    },
    "DigitalSpec": {
      "location": "Digital spectrometer enclosure, center shelf",
      "notes": "Temperature controlled environment"
    },
    "RFBox": {
      "location": "RF box, upper compartment",
      "notes": "Near power supply"
    }
  }
}
```

The sensor labels (like "Antenna", "DigitalSpec") are extracted from the CSV filenames.

See `examples/deployment_metadata_template.json` for a template.

### 3. Prepare Command-Line Metadata

Gather:
- **Deployment name**: Unique identifier (e.g., `Adak_2025Dec`)
- **Site name**: Location (e.g., `Adak`)
- **Timezone**: Where sensors were deployed (`America/New_York` for Pittsburgh)
- **Notes** (optional): Can be provided via command line or in `deployment_metadata.json`

### 4. Ingest Data

```bash
cd highz-temperature-db/scripts

# Ingest all CSV files for this deployment
# The script will automatically find and load deployment_metadata.json if it exists
python ingest_ibutton_csv.py /path/to/temperature.db \
    /path/to/Data/temp_raw/Adak/2025Dec/*.csv \
    --deployment "Adak_2025Dec" \
    --site "Adak" \
    --timezone "America/New_York"
```

**What happens:**
- ✅ Script finds `deployment_metadata.json` in the CSV directory
- ✅ Extracts sensor labels from filenames (e.g., "Antenna" from "Antenna_iButton_Dec2025.csv")
- ✅ Looks up each sensor in the metadata file
- ✅ Sets sensor location notes and deployment-specific notes
- ✅ Stores everything in the database

**Expected output:**
```
📊 Deployment: Adak_2025Dec (ID: 1)
📍 Site: Adak
🕐 Timezone: America/New_York

📄 Parsing: sensor_ABC123.csv
✓ Ingested 45,230 readings from sensor_ABC123.csv

📄 Parsing: sensor_DEF456.csv
✓ Ingested 45,198 readings from sensor_DEF456.csv

📄 Parsing: sensor_GHI789.csv
✓ Ingested 45,215 readings from sensor_GHI789.csv

✅ Ingestion complete!
```

### 4. Verify Ingestion

```bash
# List all deployments
python query_temperature.py /path/to/temperature.db --list-deployments

# List all sensors
python query_temperature.py /path/to/temperature.db --list-sensors

# Check file summary
python query_temperature.py /path/to/temperature.db --file-summary
```

### 5. Spot-Check Data

```python
from query_temperature import load_deployment_data

# Load first 100 readings
df = load_deployment_data('temperature.db', 'Adak_2025Dec')
print(df.head(100))

# Check for reasonable values
print(f"Temperature range: {df['value_c'].min():.1f}°C to {df['value_c'].max():.1f}°C")
print(f"Total readings: {len(df)}")
print(f"Unique sensors: {df['sensor_registration'].nunique()}")
```

---

## Adding New Sensors to Database

### When adding a previously unused sensor:

The ingestion script automatically creates new sensor records when it encounters a new registration number.

**To update sensor metadata after ingestion:**

```python
import sqlite3

conn = sqlite3.connect('temperature.db')

# Update sensor label
conn.execute("""
    UPDATE sensors 
    SET label = 'Antenna Mount Top',
        location_notes = 'Mounted on north face of antenna, 2m above ground'
    WHERE registration_number = 'ABC123'
""")

conn.commit()
conn.close()
```

---

## Analyzing Data

### Load Data into Pandas

```python
from query_temperature import (
    load_deployment_data,
    load_sensor_data,
    load_time_range_data
)

# All data from a deployment
df = load_deployment_data('temperature.db', 'Adak_2025Dec')

# All data from one sensor (across all deployments)
df = load_sensor_data('temperature.db', 'ABC123')

# Data from a specific time range (UTC epoch seconds)
import datetime
start = int(datetime.datetime(2025, 12, 1).timestamp())
end = int(datetime.datetime(2025, 12, 31).timestamp())
df = load_time_range_data('temperature.db', start, end)
```

### Convert UTC to Local Time for Plotting

```python
import pandas as pd
from zoneinfo import ZoneInfo

# Convert UTC epoch to timezone-aware datetime
df['time_local'] = pd.to_datetime(df['time_utc'], unit='s', utc=True)
df['time_local'] = df['time_local'].dt.tz_convert('America/New_York')

# Plot in local time
import matplotlib.pyplot as plt
plt.plot(df['time_local'], df['value_c'])
plt.xlabel('Time (Pittsburgh Local)')
plt.ylabel('Temperature (°C)')
plt.show()
```

### Compare Sensors

```python
import matplotlib.pyplot as plt

df = load_deployment_data('temperature.db', 'Adak_2025Dec')

for sensor in df['sensor_registration'].unique():
    sensor_data = df[df['sensor_registration'] == sensor]
    label = sensor_data['sensor_label'].iloc[0] or sensor
    plt.plot(sensor_data['time_utc'], sensor_data['value_c'], label=label)

plt.legend()
plt.xlabel('Time (UTC)')
plt.ylabel('Temperature (°C)')
plt.title('Temperature Comparison - Adak Dec 2025')
plt.show()
```

---

## Re-ingesting Data (If Needed)

### If you need to re-ingest a file:

The database uses SHA256 hashing to prevent duplicate ingestion. To re-ingest:

**Option 1: Delete file record and readings**
```python
import sqlite3

conn = sqlite3.connect('temperature.db')

# Find file_id
cursor = conn.execute("SELECT file_id FROM files WHERE path LIKE ?", ('%sensor_ABC123.csv',))
file_id = cursor.fetchone()[0]

# Delete readings
conn.execute("DELETE FROM temperature_readings WHERE file_id = ?", (file_id,))

# Delete file record
conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))

conn.commit()
conn.close()
```

Then re-run ingestion script.

**Option 2: Create new database**
```bash
# Start fresh
rm /path/to/temperature.db
sqlite3 /path/to/temperature.db < ../schema/temperature.sql

# Re-ingest all files
python ingest_ibutton_csv.py /path/to/temperature.db \
    /path/to/Data/temp_raw/*/*.csv \
    --deployment "..." --site "..."
```

---

## Exporting Data

### Export to CSV

```bash
# Export entire deployment
python query_temperature.py temperature.db \
    --deployment "Adak_2025Dec" \
    --output adak_2025dec.csv

# Export single sensor
python query_temperature.py temperature.db \
    --sensor "ABC123" \
    --output sensor_abc123.csv
```

### Export from Python

```python
from query_temperature import load_deployment_data

df = load_deployment_data('temperature.db', 'Adak_2025Dec')

# Save to CSV
df.to_csv('adak_temps.csv', index=False)

# Save to Excel (requires openpyxl)
df.to_excel('adak_temps.xlsx', index=False)

# Save to HDF5 (for large datasets)
df.to_hdf('adak_temps.h5', key='temperatures', mode='w')
```

---

## Database Maintenance

### Check Database Integrity

```bash
sqlite3 temperature.db "PRAGMA integrity_check;"
```

### Compact Database (Reclaim Space)

```bash
sqlite3 temperature.db "VACUUM;"
```

### View Database Size

```bash
du -h temperature.db
```

### Backup Database

```bash
# Simple copy
cp temperature.db temperature_backup_$(date +%Y%m%d).db

# SQLite backup command (safer for active databases)
sqlite3 temperature.db ".backup temperature_backup.db"
```

---

## Troubleshooting

### File won't ingest

**Check file format:**
```bash
head -20 sensor_file.csv
```

Expected format:
- Header block with metadata
- Data section starting with `Date/Time,Unit,Value`

**Check for errors:**
```bash
python ingest_ibutton_csv.py temperature.db sensor.csv \
    --deployment "test" --site "test" 2>&1 | tee ingest.log
```

### Timestamp conversion errors

Check that timestamps match expected format:
- MM/DD/YY HH:MM:SS AM/PM
- MM/DD/YYYY HH:MM:SS AM/PM

If different format, update `local_to_utc()` in `utils.py`.

### Missing sensors in query

```bash
# List all sensors
python query_temperature.py temperature.db --list-sensors

# Check specific sensor
sqlite3 temperature.db "SELECT * FROM sensors WHERE registration_number = 'ABC123';"
```

### Data looks wrong

```python
# Check raw data
import sqlite3
conn = sqlite3.connect('temperature.db')
df = pd.read_sql_query("""
    SELECT * FROM temperature_readings 
    WHERE sensor_id = (SELECT sensor_id FROM sensors WHERE registration_number = 'ABC123')
    LIMIT 10
""", conn)
print(df)
```

Compare with original CSV file to verify parsing.
