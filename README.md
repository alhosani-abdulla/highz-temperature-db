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
# Create a new database
cd scripts
python ingest_ibutton_csv.py /path/to/temperature.db dummy.csv \
    --deployment init --site init --init-db
```

Or initialize manually:
```bash
sqlite3 /path/to/temperature.db < schema/temperature.sql
```

### 2. Ingest Temperature Data

```bash
python ingest_ibutton_csv.py /path/to/temperature.db \
    /path/to/raw_data/Adak/2025Dec/*.csv \
    --deployment "Adak_2025Dec" \
    --site "Adak" \
    --timezone "America/New_York"
```

### 3. Query Data in Python

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
    ├── data_model.md            # Database schema details
    └── timezone_handling.md     # Timezone conversion details
```

## Data Organization

### Raw Data
- Store raw CSV files separately from this repository
- Organize by site and deployment (e.g., `Data/temp_raw/Adak/2025Dec/`)
- **Never modify** these files
- Database references these files by path

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

## Workflows

### After a New Deployment

1. Extract CSV files from sensors
2. Store raw CSVs in organized directory
3. Run ingestion script with deployment metadata
4. Verify ingestion with queries

See [docs/workflow.md](docs/workflow.md) for detailed steps.

## License

[Specify your license]

## Contact

[Your contact information]
