from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg import Error as PsycopgError

from .db import query

app = FastAPI(title="FactoryPulse API", version="1.0.0", description="Manufacturing operations analytics API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in __import__("os").getenv("CORS_ORIGINS", "http://localhost:5173").split(",")],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

DateFrom = Annotated[date | None, Query(description="Inclusive start date (YYYY-MM-DD)")]
DateTo = Annotated[date | None, Query(description="Inclusive end date (YYYY-MM-DD)")]


def date_range(date_from: DateFrom, date_to: DateTo) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or end - timedelta(days=29)
    if start > end:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    if (end - start).days > 365:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days")
    return start, end


def filters(plant_id: int | None, machine_id: int | None, start: date, end: date) -> tuple[str, tuple]:
    clauses = ["v.production_date BETWEEN %s AND %s"]
    params: list = [start, end]
    if plant_id is not None:
        clauses.append("p.id = %s")
        params.append(plant_id)
    if machine_id is not None:
        clauses.append("v.machine_id = %s")
        params.append(machine_id)
    return " AND ".join(clauses), tuple(params)


@app.exception_handler(PsycopgError)
async def database_error_handler(_, exc: PsycopgError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": "Analytics database is unavailable", "code": "database_unavailable"})


@app.get("/health")
def health():
    query("SELECT 1 AS ok")
    return {"status": "ok", "database": "connected"}


@app.get("/api/v1/filters")
def get_filters():
    plants = query("SELECT id, code, name, region FROM plants ORDER BY name")
    machines = query("SELECT id, plant_id, code, name, line FROM machines ORDER BY plant_id, code")
    return {"plants": plants, "machines": machines}


@app.get("/api/v1/summary")
def summary(date_from: DateFrom = None, date_to: DateTo = None, plant_id: int | None = None, machine_id: int | None = None):
    start, end = date_range(date_from, date_to)
    where, params = filters(plant_id, machine_id, start, end)
    rows = query(f"""
        WITH selected AS (
            SELECT v.* FROM v_production_daily v
            JOIN machines m ON m.id = v.machine_id JOIN plants p ON p.id = m.plant_id
            WHERE {where}
        ), totals AS (
            SELECT SUM(units_produced) produced, SUM(defect_units) defects,
                   SUM(target_units) target, SUM(downtime_minutes) downtime,
                   SUM(planned_minutes) planned, SUM(production_cost) cost,
                   COUNT(DISTINCT machine_id) machines, COUNT(DISTINCT production_date) days
            FROM selected
        )
        SELECT produced, defects, target, downtime, planned, cost, machines, days,
          ROUND(100.0 * (planned - downtime) / NULLIF(planned, 0), 2) availability_pct,
          ROUND(100.0 * defects / NULLIF(produced, 0), 2) defect_rate_pct,
          ROUND(100.0 * produced / NULLIF(target, 0), 2) target_achievement_pct
        FROM totals
    """, params)
    row = rows[0]
    for key, value in row.items():
        if isinstance(value, Decimal):
            row[key] = float(value)
    return {"period": {"from": start, "to": end}, "kpis": row, "data_label": "Synthetic training data"}


@app.get("/api/v1/trends")
def trends(date_from: DateFrom = None, date_to: DateTo = None, plant_id: int | None = None, machine_id: int | None = None):
    start, end = date_range(date_from, date_to)
    where, params = filters(plant_id, machine_id, start, end)
    rows = query(f"""
        WITH daily AS (
          SELECT v.production_date, SUM(v.units_produced) produced, SUM(v.defect_units) defects,
                 SUM(v.target_units) target, SUM(v.downtime_minutes) downtime,
                 SUM(v.planned_minutes) planned, SUM(v.production_cost) cost
          FROM v_production_daily v JOIN machines m ON m.id=v.machine_id JOIN plants p ON p.id=m.plant_id
          WHERE {where} GROUP BY v.production_date
        ), rolling AS (
          SELECT *, SUM(produced) OVER (ORDER BY production_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS produced_7d,
                    SUM(target) OVER (ORDER BY production_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS target_7d
          FROM daily
        )
        SELECT production_date, produced, defects, target, downtime, planned, cost,
          ROUND(100.0 * (planned-downtime)/NULLIF(planned,0),2) availability_pct,
          ROUND(100.0 * defects/NULLIF(produced,0),2) defect_rate_pct,
          ROUND(100.0 * produced_7d/NULLIF(target_7d,0),2) rolling_7d_target_pct
        FROM rolling ORDER BY production_date
    """, params)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {"items": []}
    frame["production_date"] = frame["production_date"].astype(str)
    return {"items": frame.to_dict(orient="records")}


@app.get("/api/v1/machines")
def machines(date_from: DateFrom = None, date_to: DateTo = None, plant_id: int | None = None):
    start, end = date_range(date_from, date_to)
    params: list = [start, end]
    plant_clause = ""
    if plant_id is not None:
        plant_clause = "AND p.id = %s"
        params.append(plant_id)
    rows = query(f"""
        WITH perf AS (
          SELECT machine_id, SUM(units_produced) produced, SUM(defect_units) defects,
                 SUM(target_units) target, SUM(downtime_minutes) downtime, SUM(planned_minutes) planned,
                 SUM(production_cost) cost
          FROM v_production_daily WHERE production_date BETWEEN %s AND %s GROUP BY machine_id
        ), ranked AS (
          SELECT p.*, RANK() OVER (ORDER BY 100.0*p.produced/NULLIF(p.target,0) DESC) AS output_rank
          FROM perf p
        )
        SELECT m.id, m.code, m.name, m.line, pl.id plant_id, pl.name plant_name,
          COALESCE(r.produced,0) produced, COALESCE(r.defects,0) defects, COALESCE(r.target,0) target,
          COALESCE(r.downtime,0) downtime_minutes,
          COALESCE(ROUND(100.0*(r.planned-r.downtime)/NULLIF(r.planned,0),2),0) availability_pct,
          COALESCE(ROUND(100.0*r.defects/NULLIF(r.produced,0),2),0) defect_rate_pct,
          COALESCE(ROUND(100.0*r.produced/NULLIF(r.target,0),2),0) target_achievement_pct,
          COALESCE(r.cost,0) production_cost, COALESCE(r.output_rank,0) output_rank
        FROM machines m JOIN plants pl ON pl.id=m.plant_id LEFT JOIN ranked r ON r.machine_id=m.id
        WHERE TRUE {plant_clause} ORDER BY target_achievement_pct DESC, m.code
    """, tuple(params))
    for row in rows:
        for key, val in row.items():
            if isinstance(val, Decimal):
                row[key] = float(val)
    return {"items": rows, "period": {"from": start, "to": end}}


@app.get("/api/v1/machines/{machine_id}")
def machine_detail(machine_id: int, date_from: DateFrom = None, date_to: DateTo = None):
    start, end = date_range(date_from, date_to)
    machine = query("SELECT m.id,m.code,m.name,m.line,p.name plant_name FROM machines m JOIN plants p ON p.id=m.plant_id WHERE m.id=%s", (machine_id,))
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    daily = query("""
      SELECT production_date, units_produced, defect_units, target_units, downtime_minutes,
             availability_pct, defect_rate_pct, target_achievement_pct, production_cost
      FROM v_production_daily WHERE machine_id=%s AND production_date BETWEEN %s AND %s ORDER BY production_date
    """, (machine_id, start, end))
    return {"machine": machine[0], "daily": daily}


@app.get("/api/v1/alerts")
def alerts(status: str | None = None, severity: str | None = None, plant_id: int | None = None):
    allowed_status = {"open", "acknowledged", "resolved"}
    allowed_severity = {"critical", "warning", "info"}
    if status and status not in allowed_status:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(sorted(allowed_status))}")
    if severity and severity not in allowed_severity:
        raise HTTPException(status_code=422, detail=f"severity must be one of {', '.join(sorted(allowed_severity))}")
    clauses, params = [], []
    if status:
        clauses.append("a.status=%s"); params.append(status)
    if severity:
        clauses.append("a.severity=%s"); params.append(severity)
    if plant_id is not None:
        clauses.append("p.id=%s"); params.append(plant_id)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = query(f"""
      SELECT a.id,a.alert_type,a.severity,a.status,a.message,a.first_seen_at,a.last_seen_at,
             m.id machine_id,m.code machine_code,m.name machine_name,m.line,p.name plant_name
      FROM operational_alerts a JOIN machines m ON m.id=a.machine_id JOIN plants p ON p.id=m.plant_id
      {where} ORDER BY CASE a.severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END, a.last_seen_at DESC
    """, tuple(params))
    return {"items": rows, "count": len(rows), "data_label": "Seeded rule-based examples"}
