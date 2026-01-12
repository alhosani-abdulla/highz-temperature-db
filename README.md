# highz-temperature-db

**Lightweight temperature data management for physics experiments**

This repository provides tools to manage temperature sensor data from infrequent deployments (≈ twice a year) in a searchable SQLite database, while keeping raw CSV files unchanged.

## Purpose

- **Store** temperature data from multiple sensors and deployments in one place
- **Preserve** original raw CSV files exactly as recorded
- **Enable** efficient queries from Python analysis scripts
- **Track** metadata and provenance for scientific auditability

## What This System Does

✅ Ingest temperature CSV files into an indexed SQLite database  
✅ Convert local timestamps (Pittsburgh time) to UTC while preserving originals  
✅ Track sensor metadata and deployment information  
✅ Provide Python helper functions for data analysis  
✅ Prevent duplicate ingestion via file hashing  

## What This System Does NOT Do

❌ Live logging or real-time data collection  
❌ Data downsampling or aggregation  
❌ Spectrum data management (not yet)  
❌ Web interfaces or remote access  
❌ Modification of raw CSV files  

## Quick Start

### 1. Initialize the Database

```bash
# Create a new database and ingest first deployment
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

Simply point to the deployment directory - the script automatically finds CSV files and reads metadata:

```bash
python ingest_ibutton_csv.py ~/temperature.db ~/Data/temp_raw/Adak/2025Dec
```

The script will:
- Find all CSV files in the directory
- Read deployment info from `deployment_metadata.json`
- Extract sensor labels from filenames
- Apply fixed timezone offset (no DST issues!)
- Store deployment-specific sensor locations

### 3. Query Data  (without locations)
python query_temperature.py temperature.db --list-sensors

# List sensors for a specific deployment (with locations)
python query_temperature.py temperature.db --list-deployment-sensors Adak_2025Dec
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
    plt.plot(sensor_data['time_utc'], sensor_data['value_c'], 
             label=sensor)
plt.legend()
plt.show()
```

### 4. Query from Command Line

```bash
# List all deployments
python query_temperature.py temperature.db --list-deployments

# List all sensors
python query_temperature.py temperature.db --list-sensors

# Export deployment data to CSV
python query_temperature.py temperature.db \
    --deployment "Adak_2025Dec" \
    --output adak_temps.csv
```

## Repository Structure

```
highz-temperature-db/
├── schema/
│   └── temperature.sql          # Database schema definition
├── scripts/
│   ├── ingest_ibutton_csv.py    # Ingest CSV files
│   ├── query_temperature.py     # Query and export data
│   └── utils.py                 # Common utilities
├── examples/
│   ├── ingest_example.sh        # Example ingestion workflow
│   └── query_example.ipynb      # Jupyter notebook examples
└── docs/
    ├── overview.md              # System design overview
    ├── workflow.md              # Step-by-step workflows
    ├── data_model.md            # Database schema details, but remain unsynced to world clocks during deployment.

- **Fixed timezone offsets** prevent DST transition issues
- Original local timestamps are **preserved exactly** as recorded
- UTC timestamps are computed using the fixed offset specified in deployment metadata
- Each deployment can have its own timezone offset (e.g., `-04:00` for EDT, `-05:00` for EST)
- See [docs/timezone_handling.md](docs/timezone_handling.md) for details

## Database Schema

Five main tables:
- **deployments**: Deployment metadata (site, timezone, notes)
- **sensors**: Sensor catalog (type, part number, registration, label)
- **sensor_deployments**: Deployment-specific sensor metadata (location, notes
### Database
- Single `.sqlite` file (e.g., `temperature.db`)
- Store outside this repository (not tracked in git)
- Contains indexed copies of temperature data
- Tracks file hashes to prevent duplicate ingestion

## Requirements

- Python 3.9+
- pandas
- sqlite3 (included in Python standard library)

Install dependencies:
```bash
pip install pandas
```

## Timezone Handling

All sensor clocks are initialized in **Pittsburgh local time** (`America/New_York`).

- Original local timestamps are **preserved exactly** as recorded
- UTC timestamps are computed for consistent analysis
- Daylight saving time transitions are handled automatically
- See [docs/timezone_handling.md](docs/timezone_handling.md) for details

## Database Schema

Four main tables:
- **deployments**: Deployment metadata (site, timezone, notes)
- **sensors**: Sensor catalog (type, part number, registration)
- **files**: Ingested CSV files (path, hash, metadata)
- **temperature_readings**: Individual measurements (time, value)

See [docs/data_model.md](docs/data_model.md) for complete schema documentation.
 to organized directory (e.g., `Data/temp_raw/SiteName/YYYYMMM/`)
2. Create `deployment_metadata.json` in the same directory
3. Run ingestion: `python ingest_ibutton_csv.py temperature.db /path/to/deployment/dir`
4. Verify: `python query_temperature.py temperature.db --list-deployment-sensors DeploymentName`

### Sharing Data with Team

The database file is self-contained and includes all temperature data:

1. Upload `temperature.db` to Google Drive (typically ~7MB for 80k readings)
2. Team members download just the database file (no CSV files needed)
3. They can query, analyze, and export data using `query_temperature.py`
4. To add new deployments, maintain database centrally or share updated version

1. Extract CSV files from sensors
2. Store raw CSVs in organized directory
3. Run ingestion script with deployment metadata
4. Verify ingestion with queries

See [docs/workflow.md](docs/workflow.md) for detailed steps.