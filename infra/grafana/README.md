# grafana

`provisioning/` is mounted at `/etc/grafana/provisioning` and is read on
container start:

- `datasources/prometheus.yml` — registers Prometheus with a fixed
  `uid: prometheus` so dashboards can reference it deterministically.
- `dashboards/provider.yml` — points a file-based dashboard provider at
  `/var/lib/grafana/dashboards`, which is where `dashboards/` is mounted.

`dashboards/` holds the dashboard-as-code JSONs:

- `fleet-overview.json` — fleet-wide stat panels and time series.
- `per-gpu.json` — uses a `$gpu_id` template variable to slice into one GPU.

Anonymous Admin access is enabled via env vars in `docker-compose.yml`, so
`http://localhost:3000` opens straight into the dashboards.
