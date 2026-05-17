PostgreSQL deployment and migration notes

1) Install driver in your deployment env (or add to requirements):

```bash
pip install -r requirements.txt
# or if installing manually
pip install psycopg2-binary
```

2) Create DB and user (example with psql):

```sql
-- connect as postgres superuser
CREATE DATABASE mydb;
CREATE USER myuser WITH PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE mydb TO myuser;
```

3) Set environment variables for your process/hosting platform:

- `POSTGRES_DB` — database name (e.g. mydb)
- `POSTGRES_USER` — DB user (e.g. myuser)
- `POSTGRES_PASSWORD` — DB password
- `POSTGRES_HOST` — DB host (default: localhost)
- `POSTGRES_PORT` — DB port (default: 5432)
- Optional: `DB_CONN_MAX_AGE` — seconds for persistent connections (default: 600)
- Optional: `DB_SSLMODE` — e.g. `require` or `prefer`

4) Migrate schema on the target Postgres instance:

```bash
python manage.py migrate --noinput
```

5) To migrate existing data from sqlite:

```bash
# PowerShell writes `>` output as UTF-16, so use UTF-8 explicitly.
# First dump from the old SQLite database by clearing the PostgreSQL env vars
# for this one command only.
Remove-Item Env:POSTGRES_DB, Env:POSTGRES_USER, Env:POSTGRES_PASSWORD, Env:POSTGRES_HOST, Env:POSTGRES_PORT, Env:DB_CONN_MAX_AGE, Env:DB_SSLMODE -ErrorAction SilentlyContinue
$json = py manage.py dumpdata --natural-primary --natural-foreign --exclude contenttypes --exclude auth.permission | Out-String
[System.IO.File]::WriteAllText('data.json', $json, (New-Object System.Text.UTF8Encoding $false))

# Then restore the PostgreSQL env vars and load the fixture into Postgres.
$env:POSTGRES_DB="mydb"
$env:POSTGRES_USER="myuser"
$env:POSTGRES_PASSWORD="strongpassword"
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
py manage.py loaddata data.json

# If the target Postgres database already has partial data from a failed load,
# clear it first and then reload the fixture.
py manage.py flush --noinput
py manage.py loaddata data.json
```

Notes & watchouts:

- Test the dump/load on a copy of your DB first.
- If you use raw SQL or SQLite-specific queries, adjust them for Postgres.
- For production, run behind a managed Postgres (Heroku, AWS RDS, DigitalOcean) and enable SSL (`DB_SSLMODE=require`).
- Keep `CONN_MAX_AGE` > 0 for connection re-use (improves throughput under load).

If you want, I can commit these changes and optionally run a dry migration locally (requires Postgres access).