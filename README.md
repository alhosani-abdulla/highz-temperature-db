# highz-temperature-db

Temperature data management for physics experiments using SQLite.

## Overview

Ingest iButton sensor CSV files into a searchable database. Raw CSV files remain unchanged. Data can be queried for analysis in Python.

## Quick Start

### 1. Initialize the Database

```bash
cd scripts
python ingest_ibutton_csv.py ~/temperature.db ~/Data/temp_raw/Adak/2025Dec --init-db
```

Or initialize manually:
```bash
sqlite3 /path/to/temperature.db < schema/temperature.sql
```

### 2. Prepare Deployment Metadata

Create a `deployment_metadata.json` file in each deployment directory:

```json
{
  "deployment": "Adak_2025Dec",
  "site": "Adak",
  "timezone": "America/New_York",
  "timezone_fixed_offset": "-05:00",
  "deployment_notes": "December 2025 Adak deployment.",
  "sensors": {
    "Antenna": {
      "location": "Below Antenna Ground Plate",
      "notes": "Taped to ground plate"
    },
    "DigitalSpec": {
      "location": "Inside DS enclosure",
      "notes": "Taped on RF deck"
    }
  }
}
```

### 3. Ingest Temperature Data

```bash
python ingest_ibutton_csv.py ~/temperature.db ~/Data/temp_raw/Adak/2025Dec
```

### 4. Query Data

**From Python:**
```python
from query_temperature import load_deployment_data, list_deployments

# List all deployments
deployments = list_deployments('temperature.db')
print(deployments)

# Load data for analysis
df = load_deployment_data('temperature.db', 'Adak_2025Dec')

# Plot temperature over time
import matplotlib.pyplot as plt
for sensor in df['sensor_registration'].unique():
    sensor_data = df[df['sensor_registration'] == sensor]
    plt.plot(sensor_data['time_utc'], sensor_data['value_c'], label=sensor)
plt.legend()
plt.show()
```

**From command line:**
```bash
# List deployments
python query_temperature.py temperature.db --list-deployments

# List sensors in a deployment
python query_temperature.py temperature.db --list-deployment-sensors Adak_2025Dec

# Export to CSV
python query_temperature.py temperature.db --deployment Adak_2025Dec --output data.csv
```

## Timezone Handling

Sensors are initialized in Pittsburgh time (`America/New_York`) but don't sync with world clocks during deployment. Use **fixed timezone offsets** in `deployment_metadata.json` to prevent DST conversion errors:
- `-05:00` if sensors initialized in EST (Nov-Mar)
- `-04:00` if sensors initialized in EDT (Mar-Nov)

Original timestamps are preserved. UTC timestamps are computed using the fixed offset.

## Database Schema

- **deployments**: Site, timezone, deployment notes
- **sensors**: Sensor type, serial number, label
- **sensor_deployments**: Deployment-specific sensor locations
- **files**: CSV file tracking (deduplication via SHA256)
- **temperature_readings**: Individual measurements

See [docs/data_model.md](docs/data_model.md) for details.

## Requirements

```bash
pip install pandas
```

Python 3.9+ required (sqlite3 included).

## Documentation

- [docs/workflow.md](docs/workflow.md) - Step-by-step guide
- [docs/data_model.md](docs/data_model.md) - Database schema
- [docs/timezone_handling.md](docs/timezone_handling.md) - Timezone conversion details
- [examples/](examples/) - Shell scripts and Jupyter notebooks