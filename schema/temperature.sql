-- Temperature Database Schema
-- Purpose: Store temperature sensor data from physics experiment deployments
-- with proper timezone handling and metadata tracking
--
-- Design principles:
--   - Raw CSV files are never modified
--   - Database is a searchable, indexed copy
--   - Both local and UTC timestamps are preserved
--   - Metadata stored for full auditability

-- =============================================================================
-- Table: deployments
-- Represents a single deployment of sensors at a site
-- =============================================================================
CREATE TABLE IF NOT EXISTS deployments (
    deployment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    site TEXT NOT NULL,
    timezone_name TEXT NOT NULL DEFAULT 'America/New_York',
    notes TEXT,
    created_at_utc INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- =============================================================================
-- Table: sensors
-- Catalog of all temperature sensors used across deployments
-- =============================================================================
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_type TEXT NOT NULL,  -- e.g., "ibutton_ds1925"
    part_number TEXT,
    registration_number TEXT UNIQUE,  -- Unique sensor identifier
    label TEXT,  -- Human-readable label (most recent)
    created_at_utc INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- =============================================================================
-- Table: sensor_deployments
-- Junction table linking sensors to deployments with deployment-specific metadata
-- =============================================================================
CREATE TABLE IF NOT EXISTS sensor_deployments (
    sensor_id INTEGER NOT NULL,
    deployment_id INTEGER NOT NULL,
    location_notes TEXT,
    notes TEXT,
    PRIMARY KEY (sensor_id, deployment_id),
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id),
    FOREIGN KEY (deployment_id) REFERENCES deployments(deployment_id)
);

-- =============================================================================
-- Table: files
-- Tracks all ingested CSV files with hash-based deduplication
-- =============================================================================
CREATE TABLE IF NOT EXISTS files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id INTEGER NOT NULL,
    sensor_id INTEGER NOT NULL,
    path TEXT NOT NULL,  -- Path to original CSV file
    sha256 TEXT NOT NULL UNIQUE,  -- File hash for deduplication
    parsed_at_utc INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    metadata_json TEXT,  -- JSON blob of header metadata
    FOREIGN KEY (deployment_id) REFERENCES deployments(deployment_id),
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);

-- =============================================================================
-- Table: temperature_readings
-- Individual temperature measurements from sensors
-- =============================================================================
CREATE TABLE IF NOT EXISTS temperature_readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    deployment_id INTEGER NOT NULL,
    sensor_id INTEGER NOT NULL,
    time_local_text TEXT NOT NULL,  -- Original timestamp string from CSV
    time_utc INTEGER NOT NULL,  -- Unix epoch seconds in UTC
    value_c REAL NOT NULL,  -- Temperature in Celsius
    quality_flag INTEGER DEFAULT 0,  -- 0=good, non-zero=flagged
    FOREIGN KEY (file_id) REFERENCES files(file_id),
    FOREIGN KEY (deployment_id) REFERENCES deployments(deployment_id),
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);

-- =============================================================================
-- Indexes for efficient querying
-- =============================================================================

-- Query temperatures for a specific sensor over time
CREATE INDEX IF NOT EXISTS idx_sensor_time 
ON temperature_readings(sensor_id, time_utc);

-- Query all temperatures for a deployment over time
CREATE INDEX IF NOT EXISTS idx_deployment_time 
ON temperature_readings(deployment_id, time_utc);

-- Trace readings back to source file
CREATE INDEX IF NOT EXISTS idx_file 
ON temperature_readings(file_id);

-- Fast lookup for file deduplication
CREATE INDEX IF NOT EXISTS idx_file_sha256 
ON files(sha256);

-- =============================================================================
-- Views for common queries
-- =============================================================================

-- View: All readings with full context
CREATE VIEW IF NOT EXISTS v_temperature_data AS
SELECT 
    tr.reading_id,
    d.name AS deployment_name,
    d.site,
    s.sensor_type,
    s.registration_number,
    s.label AS sensor_label,
    tr.time_local_text,
    datetime(tr.time_utc, 'unixepoch') AS time_utc_iso,
    tr.time_utc,
    tr.value_c,
    tr.quality_flag,
    f.path AS source_file
FROM temperature_readings tr
JOIN deployments d ON tr.deployment_id = d.deployment_id
JOIN sensors s ON tr.sensor_id = s.sensor_id
JOIN files f ON tr.file_id = f.file_id;

-- View: File ingestion summary
CREATE VIEW IF NOT EXISTS v_file_summary AS
SELECT 
    f.file_id,
    f.path,
    d.name AS deployment_name,
    s.registration_number,
    datetime(f.parsed_at_utc, 'unixepoch') AS ingested_at,
    COUNT(tr.reading_id) AS num_readings
FROM files f
JOIN deployments d ON f.deployment_id = d.deployment_id
JOIN sensors s ON f.sensor_id = s.sensor_id
LEFT JOIN temperature_readings tr ON f.file_id = tr.file_id
GROUP BY f.file_id;
