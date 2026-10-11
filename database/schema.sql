CREATE TABLE plants (
  id SERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  region TEXT NOT NULL
);

CREATE TABLE machines (
  id SERIAL PRIMARY KEY,
  plant_id INTEGER NOT NULL REFERENCES plants(id),
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  line TEXT NOT NULL,
  UNIQUE (plant_id, code)
);

CREATE TABLE production_daily (
  id BIGSERIAL PRIMARY KEY,
  machine_id INTEGER NOT NULL REFERENCES machines(id),
  production_date DATE NOT NULL,
  units_produced INTEGER NOT NULL CHECK (units_produced >= 0),
  defect_units INTEGER NOT NULL CHECK (defect_units >= 0 AND defect_units <= units_produced),
  target_units INTEGER NOT NULL CHECK (target_units > 0),
  downtime_minutes INTEGER NOT NULL CHECK (downtime_minutes BETWEEN 0 AND 1440),
  planned_minutes INTEGER NOT NULL CHECK (planned_minutes BETWEEN 1 AND 1440),
  unit_cost NUMERIC(10,2) NOT NULL CHECK (unit_cost >= 0),
  UNIQUE (machine_id, production_date)
);

CREATE TABLE operational_alerts (
  id BIGSERIAL PRIMARY KEY,
  machine_id INTEGER NOT NULL REFERENCES machines(id),
  alert_type TEXT NOT NULL CHECK (alert_type IN ('high_downtime', 'quality', 'target_gap')),
  severity TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
  status TEXT NOT NULL CHECK (status IN ('open', 'acknowledged', 'resolved')),
  message TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL,
  UNIQUE (machine_id, alert_type, first_seen_at)
);

CREATE INDEX idx_production_date_machine ON production_daily (production_date, machine_id);
CREATE INDEX idx_machine_plant ON machines (plant_id);
CREATE INDEX idx_alert_status_time ON operational_alerts (status, last_seen_at DESC);

CREATE VIEW v_production_daily AS
SELECT p.code AS plant_code, p.name AS plant_name, p.region,
       m.id AS machine_id, m.code AS machine_code, m.name AS machine_name, m.line,
       d.production_date, d.units_produced, d.defect_units, d.target_units,
       d.downtime_minutes, d.planned_minutes, d.unit_cost,
       ROUND(100.0 * (d.planned_minutes - d.downtime_minutes) / d.planned_minutes, 2) AS availability_pct,
       ROUND(100.0 * d.defect_units / NULLIF(d.units_produced, 0), 2) AS defect_rate_pct,
       ROUND(100.0 * d.units_produced / d.target_units, 2) AS target_achievement_pct,
       ROUND(d.units_produced * d.unit_cost, 2) AS production_cost
FROM production_daily d
JOIN machines m ON m.id = d.machine_id
JOIN plants p ON p.id = m.plant_id;
