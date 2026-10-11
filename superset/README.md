# Superset workspace

The `bi` Compose profile starts an independent Apache Superset service. Follow the root README to add the PostgreSQL connection, register `v_production_daily`, build the analyst dashboard, configure scheduled rule alerts, and export a sanitized dashboard bundle. No prebuilt dashboard export is included because Superset assigns IDs and database metadata at creation time; build/export it in the target instance so its connection binding is valid.

Superset's local demo credentials are intentionally unsafe for shared environments. Configure a unique admin password, strong secret key, persistent metadata database, and outbound email before team or production use.
