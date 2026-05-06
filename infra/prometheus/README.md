# prometheus

Mounted into the `prom/prometheus:v3.1.0` container at
`/etc/prometheus/prometheus.yml`. One scrape job points at the
collection-agent, plus a self-scrape so Prometheus's own `up` and
`scrape_duration_seconds` are visible.

Validate locally before committing:

```
docker run --rm \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  --entrypoint promtool \
  prom/prometheus:v3.1.0 \
  check config /etc/prometheus/prometheus.yml
```
