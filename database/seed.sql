INSERT INTO plants (code, name, region) VALUES
('BLR-01', 'Bengaluru Assembly', 'South'),
('PUN-02', 'Pune Components', 'West'),
('CHN-03', 'Chennai Fabrication', 'South');

INSERT INTO machines (plant_id, code, name, line)
SELECT p.id, 'M-' || p.code || '-' || n, labels.machine_name, labels.line_name
FROM plants p
CROSS JOIN generate_series(1, 4) AS n
CROSS JOIN LATERAL (SELECT
  (ARRAY['CNC Mill', 'Press Line', 'Welding Cell', 'Assembly Robot'])[((n - 1) % 4) + 1] AS machine_name,
  'Line ' || chr(64 + n) AS line_name
) labels;

-- Deterministic synthetic daily data, 90 days per machine. Values are fixtures, not telemetry.
INSERT INTO production_daily
  (machine_id, production_date, units_produced, defect_units, target_units,
   downtime_minutes, planned_minutes, unit_cost)
SELECT m.id,
       CURRENT_DATE - day_offset,
       GREATEST(0, (780 + ((m.id * 37 + day_offset * 19) % 360) -
         CASE WHEN (m.id + day_offset) % 13 = 0 THEN 180 ELSE 0 END)),
       GREATEST(0, ((m.id * 3 + day_offset * 2) % 22) +
         CASE WHEN (m.id + day_offset) % 17 = 0 THEN 24 ELSE 0 END),
       1000 + ((m.id % 3) * 80),
       CASE WHEN (m.id + day_offset) % 17 = 0 THEN 190 + (m.id % 70)
            ELSE 15 + ((m.id * 11 + day_offset * 7) % 105) END,
       480,
       ROUND((18.5 + (m.id % 6) * 3.25)::numeric, 2)
FROM machines m
CROSS JOIN generate_series(0, 89) AS day_offset;

INSERT INTO operational_alerts
  (machine_id, alert_type, severity, status, message, first_seen_at, last_seen_at)
SELECT m.id, 'high_downtime', 'critical', 'open',
       m.name || ' exceeded 30% downtime in the latest synthetic shift.',
       (CURRENT_DATE - INTERVAL '6 days')::timestamptz + INTERVAL '14 hours',
       (CURRENT_DATE - INTERVAL '5 days')::timestamptz + INTERVAL '16 hours'
FROM machines m JOIN production_daily d ON d.machine_id=m.id
WHERE d.production_date=CURRENT_DATE-5
  AND 100.0*d.downtime_minutes/NULLIF(d.planned_minutes,0) > 30;

INSERT INTO operational_alerts
  (machine_id, alert_type, severity, status, message, first_seen_at, last_seen_at)
SELECT m.id, 'quality', 'warning', 'acknowledged',
       m.name || ' defect rate is above the 2.5% rule threshold.',
       (CURRENT_DATE - INTERVAL '6 days')::timestamptz + INTERVAL '9 hours',
       (CURRENT_DATE - INTERVAL '5 days')::timestamptz + INTERVAL '11 hours'
FROM machines m JOIN production_daily d ON d.machine_id=m.id
WHERE d.production_date=CURRENT_DATE-5
  AND 100.0*d.defect_units/NULLIF(d.units_produced,0) > 2.5;
