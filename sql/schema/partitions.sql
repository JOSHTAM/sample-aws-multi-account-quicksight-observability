-- ================================================================
-- Weekly Partitions for cloudwatch_metrics table
-- Creates 12 weekly partitions covering the current quarter (Q3 2025)
-- and provides a helper function for ongoing partition management.
-- ================================================================

-- Helper function: create_weekly_partitions
-- Creates N weekly partitions starting from a given date.
-- Usage: SELECT create_weekly_partitions('2025-07-01'::date, 12);
CREATE OR REPLACE FUNCTION create_weekly_partitions(
    start_date DATE,
    num_weeks INTEGER DEFAULT 12
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    week_start DATE;
    week_end DATE;
    partition_name TEXT;
    year_week TEXT;
    i INTEGER;
BEGIN
    -- Align start_date to the Monday of its week
    week_start := start_date - (EXTRACT(ISODOW FROM start_date)::int - 1) * INTERVAL '1 day';

    FOR i IN 0..(num_weeks - 1) LOOP
        week_end := week_start + INTERVAL '7 days';
        year_week := TO_CHAR(week_start, 'IYYY') || TO_CHAR(week_start, 'IW');
        partition_name := 'cloudwatch_metrics_w' || year_week;

        -- Only create if partition does not already exist
        IF NOT EXISTS (
            SELECT 1 FROM pg_class WHERE relname = partition_name
        ) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF cloudwatch_metrics FOR VALUES FROM (%L) TO (%L)',
                partition_name,
                week_start::text,
                week_end::text
            );
            RAISE NOTICE 'Created partition: % (% to %)', partition_name, week_start, week_end;
        ELSE
            RAISE NOTICE 'Partition already exists: %', partition_name;
        END IF;

        week_start := week_end;
    END LOOP;
END;
$$;

-- ================================================================
-- Create Q3 2025 partitions (July 1 - September 22, 2025 = 12 weeks)
-- ================================================================
SELECT create_weekly_partitions('2025-06-30'::date, 12);
-- Note: 2025-06-30 is Monday of ISO week 27, covering:
--   Week 27: 2025-06-30 to 2025-07-07
--   Week 28: 2025-07-07 to 2025-07-14
--   Week 29: 2025-07-14 to 2025-07-21
--   Week 30: 2025-07-21 to 2025-07-28
--   Week 31: 2025-07-28 to 2025-08-04
--   Week 32: 2025-08-04 to 2025-08-11
--   Week 33: 2025-08-11 to 2025-08-18
--   Week 34: 2025-08-18 to 2025-08-25
--   Week 35: 2025-08-25 to 2025-09-01
--   Week 36: 2025-09-01 to 2025-09-08
--   Week 37: 2025-09-08 to 2025-09-15
--   Week 38: 2025-09-15 to 2025-09-22

-- ================================================================
-- MAINTENANCE GUIDE
-- ================================================================
-- To create partitions for the next quarter, run:
--   SELECT create_weekly_partitions('2025-09-22'::date, 13);
--
-- To create partitions dynamically from the current date:
--   SELECT create_weekly_partitions(CURRENT_DATE, 12);
--
-- Recommended: Schedule partition creation ahead of time (e.g., monthly)
-- so that new partitions exist before data arrives. The function is
-- idempotent — calling it again for existing partitions is safe.
--
-- To drop old partitions beyond the 90-day retention window:
--   DROP TABLE IF EXISTS cloudwatch_metrics_w202527;
--
-- Or use a maintenance query to find and drop expired partitions:
--   SELECT schemaname, tablename
--   FROM pg_tables
--   WHERE tablename LIKE 'cloudwatch_metrics_w%'
--   ORDER BY tablename;
