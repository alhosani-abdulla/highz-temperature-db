#!/bin/bash
#
# Example: Ingest temperature data from a deployment
#
# This script shows how to ingest CSV files from iButton sensors
# into the temperature database.
#

# Configuration - CUSTOMIZE THESE PATHS FOR YOUR SETUP
DB_PATH="/path/to/temperature.db"
DEPLOYMENT_NAME="Adak_2025Dec"
SITE_NAME="Adak"
TIMEZONE="America/New_York"
CSV_DIR="/path/to/Data/temp_raw/Adak/2025Dec"

# Initialize database (first time only)
echo "=== Initializing database ==="
cd "$(dirname "$0")/../scripts"
python ingest_ibutton_csv.py "$DB_PATH" \
    dummy.csv \
    --deployment "init" \
    --site "init" \
    --init-db 2>/dev/null || echo "Database already initialized"

# Ingest all CSV files from deployment
echo ""
echo "=== Ingesting CSV files ==="
python ingest_ibutton_csv.py "$DB_PATH" \
    "$CSV_DIR"/*.csv \
    --deployment "$DEPLOYMENT_NAME" \
    --site "$SITE_NAME" \
    --timezone "$TIMEZONE" \
    --notes "Winter deployment, 3 sensors on antenna mount"

# Verify ingestion
echo ""
echo "=== Deployment summary ==="
python query_temperature.py "$DB_PATH" --list-deployments

echo ""
echo "=== Sensor summary ==="
python query_temperature.py "$DB_PATH" --list-sensors

echo ""
echo "=== File summary ==="
python query_temperature.py "$DB_PATH" --file-summary

echo ""
echo "✅ Ingestion complete! Database: $DB_PATH"
