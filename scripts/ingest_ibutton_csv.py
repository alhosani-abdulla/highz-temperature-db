#!/usr/bin/env python3
"""
Ingest iButton DS1925 temperature CSV files into the database.

This script:
1. Reads iButton CSV files with header metadata
2. Extracts sensor information (part number, registration number)
3. Converts local timestamps to UTC
4. Stores all data in the SQLite database

Usage:
    python ingest_ibutton_csv.py DB_PATH CSV_FILE [CSV_FILE ...] \\
        --deployment DEPLOYMENT_NAME \\
        --site SITE_NAME \\
        [--timezone TIMEZONE_NAME]

Example:
    python ingest_ibutton_csv.py /path/to/temperature.db \\
        sensor1.csv sensor2.csv \\
        --deployment "Adak_2025Dec" \\
        --site "Adak" \\
        --timezone "America/New_York"
"""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    get_db_connection,
    initialize_database,
    compute_file_hash,
    local_to_utc,
    file_already_ingested
)


def load_deployment_metadata(csv_dir: str) -> Dict:
    """
    Load deployment metadata from deployment_metadata.json if it exists.
    
    Args:
        csv_dir: Directory containing CSV files
        
    Returns:
        Dictionary with deployment metadata, or empty dict if file doesn't exist
    """
    metadata_file = Path(csv_dir) / 'deployment_metadata.json'
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            return json.load(f)
    return {}


def parse_ibutton_header(csv_path: str) -> Tuple[Dict[str, str], int]:
    """
    Parse the header metadata block from an iButton CSV file.
    
    iButton files have a header block followed by a data section:
    - Header: Key-value pairs (e.g., "Part Number,DS1925L")
    - Data: Starts with "Date/Time,Unit,Value" or similar
    
    Args:
        csv_path: Path to the iButton CSV file
        
    Returns:
        Tuple of (metadata_dict, data_start_line)
    """
    metadata = {}
    data_start_line = 0
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig removes BOM
        reader = csv.reader(f)
        for i, row in enumerate(reader, start=1):
            if not row or len(row) == 0:
                continue
            
            # Check if this is the data header
            if row[0].strip().lower() in ['date/time', 'date time']:
                data_start_line = i
                break
            
            # Parse header key-value pairs
            # Handle both "Key,Value" and "Key: Value" formats
            if len(row) >= 2:
                # CSV format: "Key,Value"
                key = row[0].strip().rstrip(':')  # Remove trailing colon
                value = row[1].strip() if len(row) > 1 else ""
                metadata[key] = value
            elif len(row) == 1 and ':' in row[0]:
                # Colon-separated format: "Key: Value"
                parts = row[0].split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    metadata[key] = value
    
    if data_start_line == 0:
        raise ValueError(f"Could not find data section in {csv_path}")
    
    return metadata, data_start_line


def get_or_create_sensor(conn: sqlite3.Connection, metadata: Dict[str, str], 
                         label: str = None) -> int:
    """
    Get existing sensor or create new one from metadata.
    
    Args:
        conn: Database connection
        metadata: Metadata dictionary from iButton header
        label: Optional human-readable label for the sensor
        
    Returns:
        sensor_id
    """
    # Extract sensor information from metadata
    # Try multiple possible key names (different iButton software versions)
    part_number = (metadata.get('1-Wire/iButton Part Number') or 
                   metadata.get('Part Number') or 
                   metadata.get('Part') or '')
    registration_number = (metadata.get('1-Wire/iButton Registration Number') or
                          metadata.get('Registration Number') or 
                          metadata.get('Registration') or '')
    
    if not registration_number:
        raise ValueError("Registration number not found in metadata")
    
    # Check if sensor exists
    cursor = conn.execute(
        "SELECT sensor_id, label FROM sensors WHERE registration_number = ?",
        (registration_number,)
    )
    row = cursor.fetchone()
    
    if row:
        sensor_id = row[0]
        existing_label = row[1]
        
        # Update label if we have one and sensor doesn't have it
        if label and not existing_label:
            conn.execute(
                "UPDATE sensors SET label = ? WHERE sensor_id = ?",
                (label, sensor_id)
            )
            conn.commit()
        return sensor_id
    
    # Create new sensor
    cursor = conn.execute(
        """
        INSERT INTO sensors (sensor_type, part_number, registration_number, label)
        VALUES (?, ?, ?, ?)
        """,
        ('ibutton_ds1925', part_number, registration_number, label)
    )
    conn.commit()
    return cursor.lastrowid


def upsert_sensor_deployment(conn: sqlite3.Connection, sensor_id: int, 
                             deployment_id: int, location_notes: str = None,
                             notes: str = None) -> None:
    """
    Create or update sensor_deployment record with deployment-specific metadata.
    
    Args:
        conn: Database connection
        sensor_id: Sensor ID
        deployment_id: Deployment ID
        location_notes: Location of sensor in this deployment
        notes: Additional notes for this sensor in this deployment
    """
    # Check if record exists
    cursor = conn.execute(
        "SELECT 1 FROM sensor_deployments WHERE sensor_id = ? AND deployment_id = ?",
        (sensor_id, deployment_id)
    )
    exists = cursor.fetchone()
    
    if exists:
        # Update existing record
        conn.execute(
            """UPDATE sensor_deployments 
               SET location_notes = ?, notes = ? 
               WHERE sensor_id = ? AND deployment_id = ?""",
            (location_notes, notes, sensor_id, deployment_id)
        )
    else:
        # Insert new record
        conn.execute(
            """INSERT INTO sensor_deployments (sensor_id, deployment_id, location_notes, notes)
               VALUES (?, ?, ?, ?)""",
            (sensor_id, deployment_id, location_notes, notes)
        )
    conn.commit()


def get_or_create_deployment(conn: sqlite3.Connection, name: str, site: str, 
                             timezone_name: str, notes: str = None) -> int:
    """
    Get existing deployment or create new one. Updates notes if deployment exists.
    
    Args:
        conn: Database connection
        name: Deployment name (must be unique)
        site: Site name
        timezone_name: IANA timezone name
        notes: Optional notes
        
    Returns:
        deployment_id
    """
    cursor = conn.execute(
        "SELECT deployment_id FROM deployments WHERE name = ?",
        (name,)
    )
    row = cursor.fetchone()
    
    if row:
        deployment_id = row[0]
        # Update notes if provided
        if notes:
            conn.execute(
                "UPDATE deployments SET notes = ? WHERE deployment_id = ?",
                (notes, deployment_id)
            )
            conn.commit()
        return deployment_id
    
    cursor = conn.execute(
        """
        INSERT INTO deployments (name, site, timezone_name, notes)
        VALUES (?, ?, ?, ?)
        """,
        (name, site, timezone_name, notes)
    )
    conn.commit()
    return cursor.lastrowid


def ingest_csv_file(conn: sqlite3.Connection, csv_path: str, 
                    deployment_id: int, timezone_name: str,
                    deployment_metadata: Dict = None, fixed_offset: str = None) -> None:
    """
    Ingest a single iButton CSV file.
    
    Args:
        conn: Database connection
        csv_path: Path to CSV file
        deployment_id: Deployment ID
        timezone_name: IANA timezone name for timestamp conversion
        deployment_metadata: Optional deployment metadata dictionary
        fixed_offset: Optional fixed UTC offset (e.g., "-04:00") to bypass DST
    """
    if deployment_metadata is None:
        deployment_metadata = {}
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    # Parse header
    print(f"📄 Parsing: {csv_file.name}")
    metadata, data_start_line = parse_ibutton_header(csv_path)
    
    # Extract label from filename (e.g., "Antenna_iButton_Dec2025.csv" -> "Antenna")
    filename = csv_file.stem  # Remove extension
    label = None
    if '_iButton_' in filename or '_ibutton_' in filename:
        # Split on _iButton_ or _ibutton_ and take first part
        label = filename.split('_iButton_')[0].split('_ibutton_')[0]
    
    # Get sensor-specific metadata from deployment metadata
    sensor_metadata = deployment_metadata.get('sensors', {}).get(label, {})
    location_notes = sensor_metadata.get('location')  # Only use location field
    sensor_notes = sensor_metadata.get('notes')
    
    # Get or create sensor (do this before hash check to update labels)
    sensor_id = get_or_create_sensor(conn, metadata, label)
    
    # Create/update sensor_deployment record with deployment-specific metadata
    upsert_sensor_deployment(conn, sensor_id, deployment_id, location_notes, sensor_notes)
    
    # Compute file hash
    file_hash = compute_file_hash(csv_path)
    
    # Check if already ingested
    if file_already_ingested(conn, file_hash):
        print(f"⚠️  File already ingested (skipping): {csv_file.name}")
        return
    
    # Insert file record with enhanced metadata
    file_metadata = metadata.copy()
    if sensor_notes:
        file_metadata['deployment_sensor_notes'] = sensor_notes
    
    cursor = conn.execute(
        """
        INSERT INTO files (deployment_id, sensor_id, path, sha256, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (deployment_id, sensor_id, str(csv_path), file_hash, json.dumps(file_metadata))
    )
    file_id = cursor.lastrowid
    
    # Parse and insert temperature readings
    readings = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        
        # Skip to data section
        for i, row in enumerate(reader, start=1):
            if i < data_start_line:
                continue
            if i == data_start_line:
                # This is the header row
                continue
            
            # Parse data row
            if len(row) < 3:
                continue
            
            time_local_text = row[0].strip()
            unit = row[1].strip()
            value_str = row[2].strip()
            
            if not time_local_text or not value_str:
                continue
            
            try:
                # Convert timestamp
                time_utc = local_to_utc(time_local_text, timezone_name, fixed_offset)
                
                # Parse temperature value
                value_c = float(value_str)
                
                readings.append((
                    file_id, deployment_id, sensor_id,
                    time_local_text, time_utc, value_c, 0
                ))
            except (ValueError, Exception) as e:
                print(f"⚠️  Warning: Could not parse row {i}: {e}")
                continue
    
    # Bulk insert readings
    if readings:
        conn.executemany(
            """
            INSERT INTO temperature_readings 
            (file_id, deployment_id, sensor_id, time_local_text, time_utc, value_c, quality_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            readings
        )
        conn.commit()
        print(f"✓ Ingested {len(readings)} readings from {csv_file.name}")
    else:
        print(f"⚠️  No valid readings found in {csv_file.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest iButton temperature CSV files into database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('db_path', help='Path to SQLite database file')
    parser.add_argument('deployment_path', help='Path to deployment directory containing CSV files and deployment_metadata.json')
    parser.add_argument('--deployment', 
                       help='Deployment name (e.g., "Adak_2025Dec"). If not provided, reads from deployment_metadata.json')
    parser.add_argument('--site', 
                       help='Site name (e.g., "Adak"). If not provided, reads from deployment_metadata.json')
    parser.add_argument('--timezone', default='America/New_York',
                       help='IANA timezone name (default: America/New_York)')
    parser.add_argument('--notes', default=None,
                       help='Optional deployment notes (overrides deployment_metadata.json)')
    parser.add_argument('--init-db', action='store_true',
                       help='Initialize database with schema before ingesting')
    
    args = parser.parse_args()
    
    # Initialize database if requested
    if args.init_db:
        schema_path = Path(__file__).parent.parent / 'schema' / 'temperature.sql'
        initialize_database(args.db_path, str(schema_path))
    
    # Connect to database
    conn = get_db_connection(args.db_path)
    
    try:
        # Convert deployment path to Path object and validate
        deployment_dir = Path(args.deployment_path)
        if not deployment_dir.exists():
            print(f"❌ Error: Deployment directory does not exist: {deployment_dir}")
            sys.exit(1)
        if not deployment_dir.is_dir():
            print(f"❌ Error: Path is not a directory: {deployment_dir}")
            sys.exit(1)
        
        # Find all CSV files in the directory
        csv_files = sorted(deployment_dir.glob('*.csv'))
        if not csv_files:
            print(f"❌ Error: No CSV files found in {deployment_dir}")
            sys.exit(1)
        
        # Load deployment metadata
        deployment_metadata = load_deployment_metadata(str(deployment_dir))
        if deployment_metadata:
            print(f"📋 Loaded deployment metadata from {deployment_dir / 'deployment_metadata.json'}")
        
        # Get deployment name and site from args or metadata
        deployment_name = args.deployment or deployment_metadata.get('deployment')
        site_name = args.site or deployment_metadata.get('site')
        timezone_name = deployment_metadata.get('timezone') or args.timezone
        fixed_offset = deployment_metadata.get('timezone_fixed_offset')
        
        if not deployment_name or not site_name:
            print("❌ Error: deployment and site must be provided via --deployment/--site or in deployment_metadata.json")
            sys.exit(1)
        
        # Use deployment notes from metadata if not provided via command line
        deployment_notes = args.notes or deployment_metadata.get('deployment_notes')
        
        # Get or create deployment
        deployment_id = get_or_create_deployment(
            conn, deployment_name, site_name, timezone_name, deployment_notes
        )
        print(f"\n📊 Deployment: {deployment_name} (ID: {deployment_id})")
        print(f"📍 Site: {site_name}")
        print(f"🕐 Timezone: {timezone_name}{f' (fixed offset: {fixed_offset})' if fixed_offset else ''}\n")
        
        # Ingest each CSV file
        for csv_file in csv_files:
            try:
                ingest_csv_file(conn, str(csv_file), deployment_id, timezone_name, deployment_metadata, fixed_offset)
            except Exception as e:
                print(f"❌ Error processing {csv_file}: {e}")
                continue
        
        print("\n✅ Ingestion complete!")
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
