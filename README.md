# IRIS source adapters

This project reads data from different sources and gives every row the same shape. Each source has a small adapter that reads and maps its own data. The shared code then checks the rows and saves them for later use.

You need Python 3.12 or newer. The basic run does not need a database or an internet connection.

## Run it

From the project folder, run:

~~~sh
sh run.sh
~~~

This reads the sample data and writes 24 checked records to output/normalized.jsonl. A saved copy is in [examples/normalized.jsonl](examples/normalized.jsonl). JSONL means one JSON record per line. Twenty sample records have a point on a map; four have no geometry.

You can also try the second, CSV-based adapter:

~~~sh
PYTHONPATH=src python3.12 -m iris_adapters --adapter csv --output output/csv-normalized.jsonl
~~~

## Run the tests

~~~sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
~~~

The tests cover both sample adapters, a new adapter made only in the test file, missing or wrong country codes, duplicate IDs, dates, units, and geometry. A bad row stops the whole batch before anything is saved.

## GitHub Actions

GitHub Actions runs the tests when code is pushed to `main` or a pull request is opened. You can also start the check from the Actions tab.

When you publish a GitHub Release, Actions builds a Python wheel and a source archive, then adds both files to that release. This project does not have a hosted service to deploy.

## How the code works

The work happens in four steps:

1. **Read:** An adapter reads rows from a file or another source.
2. **Convert:** The shared code puts each row into the same record format. It also changes fetch times to UTC and geometry to GeoJSON.
3. **Check:** The shared code checks required fields and rejects bad rows.
4. **Save:** The checked batch goes to a JSONL file or, if configured, to PostgreSQL/PostGIS staging.

To add a new source, make a class based on SourceAdapter and implement these two methods:

~~~python
def extract(self):                 # yield source rows
    ...

def map_record(self, raw):         # return a SourceRecord
    ...
~~~

The [JSONL adapter](src/iris_adapters/adapters/jsonl_fixture.py) and [CSV adapter](src/iris_adapters/adapters/csv_fixture.py) show how to do this. You do not need to change the shared [pipeline](src/iris_adapters/pipeline.py). The adapter maps its source fields into SourceRecord; the shared code handles the checks and saving.

## What each saved record contains

| Field | Meaning |
| --- | --- |
| **record_id** | The ID of the row in its source. |
| **country_code** | A required two-letter country code, such as DE. |
| **region_code** | A region code, or null if the source does not provide one. |
| **source_id** | The name or ID of the source. |
| **source_date** | The date the source data represents. |
| **fetched_at** | When the data was collected, saved as a UTC time. |
| **attributes** | The row's source values. |
| **geom** | GeoJSON geometry, or null for a row without geometry. |
| **crs** | EPSG:4326 for geometry, or null for a row without geometry. |
| **completeness** | Either complete or partial. |
| **units** | Units for numeric values in attributes, such as m2. |
| **uncertainty** | Notes or values about uncertainty; an empty object if none were supplied. |

The code never guesses a missing country code. It checks country codes against a fixed ISO list. It rejects geometry with missing or unsupported CRS information. For geometry, coordinates must be longitude and latitude in EPSG:4326. IDs are checked within their country and source, so two countries may use the same record ID.

The normalizer checks basic GeoJSON structure and coordinate ranges. It does not change coordinates from another CRS. When using PostGIS, the database also checks whether geometry is valid.

## Optional PostgreSQL/PostGIS staging

The local JSONL run is enough to try the project. If you have PostgreSQL 16+ and PostGIS 3.4+, set DATABASE_URL for your local database and run:

~~~sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/001_staging.sql
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[postgres]'
.venv/bin/iris-ingest --sink postgres
~~~

The SQL file creates the iris.staging_records table with a PostGIS column named geom. A database error rolls back the batch. The command prints a batch ID so you can find that import later. The database account must be allowed to create the schema and PostGIS extension; on a managed database, an administrator may need to install PostGIS first.

## Assumptions and limits

- The sample data is made up and always gives the same result. No production passwords or paid services are needed.
- Each record needs a source date and a fetch time. The fetch time must include a time zone.
- Map coordinates are already in EPSG:4326. A future version could add explicit CRS conversion.
- The JSONL path checks geometry shape and coordinates. PostGIS adds stronger geometry checks when loading into the database.
- This project saves checked rows to staging. Moving them into final business tables is a separate step. A production version would also report bad rows clearly and stream large imports instead of keeping a whole batch in memory.
