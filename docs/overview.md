# System Overview

## Purpose

The highz-temperature-db system manages temperature sensor data from physics experiments with these goals:

1. **Centralized storage**: All temperature data from all deployments in one queryable database
2. **Data integrity**: Raw CSV files remain completely unchanged; database is an indexed copy
3. **Scientific auditability**: Full metadata tracking for provenance and reproducibility
4. **Analysis-ready**: Easy integration with Python data analysis workflows

## Design Principles

### Simplicity First
- Single SQLite file (no server required)
- Minimal dependencies (Python + pandas)
- No complex abstractions
- Human-readable structure

### Data Preservation
- Raw CSV files are **never modified**
- Original local timestamps preserved exactly as recorded
- File hashing prevents accidental duplicate ingestion
- All metadata from sensor headers captured in JSON

### Timezone Safety
- Sensors record in Pittsburgh local time
- Both local and UTC timestamps stored
- Daylight saving transitions handled explicitly
- Conversion policy documented for audit

### Future-Proof
- Schema designed to add spectrum data later
- Extensible metadata storage (JSON)
- Quality flags for data filtering
- Foreign key relationships maintain integrity

## System Components

### Database (`temperature.sqlite`)
- **Single file** containing all indexed data
- Lives anywhere convenient (not in git)
- Can be backed up, copied, archived
- ~1 MB per 50,000 readings (varies with metadata)

### Raw Data Files
- CSV files from sensors
- Stored separately in organized directories
- Never modified after extraction
- Database tracks path and hash

### Scripts
- **ingest_ibutton_csv.py**: Import CSV data
- **query_temperature.py**: Extract data for analysis
- **utils.py**: Common functions (hashing, timestamps, DB init)

### Documentation
- Design rationale (this file)
- Workflow guides
- Schema reference
- Timezone handling details

## Data Flow

```
┌─────────────────┐
│  iButton Sensor │
│  (Local Time)   │
└────────┬────────┘
         │ USB extraction
         ▼
┌─────────────────┐
│  Raw CSV File   │◄──── Store in organized
│  (Unchanged)    │      directory structure
└────────┬────────┘
         │
         │ ingest_ibutton_csv.py
         │ (parse header, convert timestamps)
         ▼
┌─────────────────┐
│ SQLite Database │
│  - deployments  │
│  - sensors      │
│  - files        │
│  - readings     │
└────────┬────────┘
         │
         │ query_temperature.py
         │ (load into pandas)
         ▼
┌─────────────────┐
│ Analysis Script │
│  (matplotlib,   │
│   scipy, etc.)  │
└─────────────────┘
```

## Non-Goals

This system explicitly **does not**:

- ❌ Perform live logging (post-deployment only)
- ❌ Downsample or aggregate data (store all points)
- ❌ Manage spectrum data (future addition)
- ❌ Provide web interfaces (command-line only)
- ❌ Support concurrent writes (ingest is sequential)
- ❌ Validate physical sensor readings (trust sensor QC)

## Use Cases

### Primary: Post-Deployment Analysis
After collecting sensors from the field:
1. Extract CSV files
2. Ingest into database
3. Query data for analysis
4. Generate plots and statistics

### Secondary: Cross-Deployment Comparison
Compare temperature behavior across:
- Multiple deployments at same site
- Different sensors at different sites
- Seasonal variations
- Sensor calibration drift

### Future: Spectrum-Temperature Correlation
When spectrum data is added:
- Time-align temperature with spectrum timestamps
- Analyze temperature effects on spectrum
- Filter data by environmental conditions

## Scalability Considerations

### Current Scale
- ~2 deployments per year
- ~10-20 sensors per deployment
- ~1 reading per minute
- ~500,000 readings per year

### Database Size Estimates
- 500K readings: ~10-20 MB
- 5M readings (10 years): ~100-200 MB
- Still well within SQLite sweet spot (<1 GB)

### Performance
- Queries on indexed columns: milliseconds
- Full table scans: seconds (even at 5M rows)
- Ingestion: ~1000 rows/second
- No optimization needed at this scale

## Extension Points

### Adding New Sensor Types
- Extend `parse_ibutton_header()` function
- Add sensor-specific parsing logic
- Update metadata extraction
- Same database schema works

### Adding Spectrum Data
- New tables: `spectrum_files`, `spectrum_readings`
- Foreign keys to existing `deployments`, `sensors`
- Time-based joins on UTC timestamps

### Adding Data Quality Checks
- Implement validation in ingestion script
- Set `quality_flag` on suspicious readings
- Add `quality_notes` to readings table
- Filter in queries

### Adding Calibration Corrections
- New table: `calibrations` (sensor_id, valid_from, valid_to, offset, scale)
- Apply corrections in query functions
- Preserve raw values in database
- Document correction provenance

## Technology Choices

### SQLite
**Why?**
- Single file, no server
- Excellent for read-heavy workloads
- Built into Python
- Reliable, well-tested
- Easy to backup/archive

**Limitations?**
- No concurrent writes (fine for our use)
- Limited to single machine (fine for our use)
- Not ideal for >1 TB (we're at ~100 MB)

### Python
**Why?**
- Standard in scientific computing
- Excellent data analysis libraries (pandas, numpy, matplotlib)
- Easy to learn and maintain
- Cross-platform

### Pandas
**Why?**
- Natural format for time series data
- Integrates with plotting libraries
- Familiar to scientists
- Handles missing data gracefully

## Maintenance

### Backups
- Database: Regular backups of `.sqlite` file
- Raw data: Keep CSV files indefinitely
- Can rebuild database from CSVs if needed

### Updates
- Schema changes: Create new database, re-ingest
- Script updates: Git version control
- Python upgrades: Pin compatible versions

### Validation
- Periodically check row counts match CSV line counts
- Verify no duplicate file hashes
- Spot-check timestamp conversions
- Compare sensor counts to physical inventory
