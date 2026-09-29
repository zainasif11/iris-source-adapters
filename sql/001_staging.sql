-- Run once against PostgreSQL 16+ with PostGIS 3.4+ using psql -v ON_ERROR_STOP=1.
BEGIN;
CREATE SCHEMA IF NOT EXISTS iris;
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS iris.staging_records (
    batch_id UUID NOT NULL,
    country_code TEXT NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
    source_id TEXT NOT NULL CHECK (length(source_id) > 0),
    record_id TEXT NOT NULL CHECK (length(record_id) > 0),
    region_code TEXT,
    source_date DATE NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    attributes JSONB NOT NULL CHECK (jsonb_typeof(attributes) = 'object'),
    geom geometry(Geometry, 4326),
    crs TEXT,
    completeness TEXT NOT NULL CHECK (completeness IN ('complete', 'partial')),
    units JSONB NOT NULL CHECK (jsonb_typeof(units) = 'object'),
    uncertainty JSONB NOT NULL CHECK (jsonb_typeof(uncertainty) = 'object'),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, country_code, source_id, record_id),
    CHECK ((geom IS NULL AND crs IS NULL) OR (geom IS NOT NULL AND crs = 'EPSG:4326')),
    CHECK (geom IS NULL OR ST_IsValid(geom))
);

CREATE INDEX IF NOT EXISTS staging_records_country_source_idx
    ON iris.staging_records (country_code, source_id, source_date);
CREATE INDEX IF NOT EXISTS staging_records_geom_idx
    ON iris.staging_records USING GIST (geom);
COMMIT;
