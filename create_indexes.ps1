# ------------------------------------------------------------
# create_indexes_auto.ps1
# - auto-detects Postgres container (image name containing 'postgres')
# - connects to DB and finds tables whose names match given patterns
# - creates recommended indexes only on tables that exist
# ------------------------------------------------------------

# Config - change if you need to
$DbName = "rfc_garments_001"
$DbUser = "postgres"
$DbPassword = "vps_postgres"   # used only if you want to pass env; not used inside docker exec

# Attempt to auto-detect a Postgres container by image name containing 'postgres'
$containers = docker ps --format "{{.Names}}||{{.Image}}"
$pgContainer = $null
foreach ($c in $containers) {
    $parts = $c -split "\|\|"
    if ($parts.Length -ge 2) {
        $name = $parts[0].Trim()
        $image = $parts[1].Trim().ToLower()
        if ($image -like "*postgres*") {
            $pgContainer = $name
            break
        }
    }
}

if (-not $pgContainer) {
    Write-Host "Could not auto-detect a Postgres container. Run `docker ps` and set `$ContainerName` manually." -ForegroundColor Red
    exit 1
}

Write-Host "Using Postgres container: $pgContainer"

# The SQL we will pipe into psql - this inspects pg_tables and creates indexes dynamically
$Sql = @"
-- This script searches for tables whose names look like productplant/product/bomheader/party
-- and creates indexes only on tables that exist. It is safe to re-run.

-- 1) productplant-style indexes: (plant_id, product_id) and (plant_id, code)
DO $$
DECLARE
  r RECORD;
  tbl regclass;
BEGIN
  FOR r IN
    SELECT schemaname AS sch, tablename AS tbl
    FROM pg_tables
    WHERE tablename ILIKE '%productplant%'
  LOOP
    tbl := quote_ident(r.sch) || '.' || quote_ident(r.tbl);
    -- composite index plant+product
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_plant_product ON %s (plant_id, product_id);',
                   replace(lower(r.tbl), '-', '_'), tbl);
    -- plant+code index
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_plant_code ON %s (plant_id, code);',
                   replace(lower(r.tbl), '-', '_'), tbl);
  END LOOP;
END$$;

-- 2) bomheader active index: WHERE is_active = TRUE
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT schemaname AS sch, tablename AS tbl
    FROM pg_tables
    WHERE tablename ILIKE '%bomheader%'
  LOOP
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_active ON %I.%I (product_plant_id) WHERE is_active = TRUE;',
                   lower(r.tbl), r.sch, r.tbl);
  END LOOP;
END$$;

-- 3) party case-insensitive unique functional index (LOWER(party_code))
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT schemaname AS sch, tablename AS tbl
    FROM pg_tables
    WHERE tablename ILIKE '%party%'
  LOOP
    -- Use an existence check for index name to avoid duplicate unique index errors
    IF NOT EXISTS (
      SELECT 1 FROM pg_indexes
      WHERE schemaname = r.sch AND indexname = 'idx_' || lower(r.tbl) || '_code_lower'
    ) THEN
      EXECUTE format('CREATE UNIQUE INDEX idx_%s_code_lower ON %I.%I (LOWER(party_code));',
                     lower(r.tbl), r.sch, r.tbl);
    END IF;
  END LOOP;
END$$;

-- 4) product active flag index
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT schemaname AS sch, tablename AS tbl
    FROM pg_tables
    WHERE tablename ILIKE '%product%'
      AND tablename NOT ILIKE '%productplant%'   -- avoid matching productplant again
  LOOP
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_active ON %I.%I (active);',
                   lower(r.tbl), r.sch, r.tbl);
  END LOOP;
END$$;

-- 5) print indexes we created or found (for visibility)
SELECT schemaname, indexname, tablename
FROM pg_indexes
WHERE indexname LIKE 'idx_%product%' OR indexname LIKE 'idx_%party%' OR indexname LIKE 'idx_%bom%'
ORDER BY schemaname, indexname;
"@

# Pipe SQL to psql inside the container
$Sql | docker exec -i $pgContainer psql -U $DbUser -d $DbName
