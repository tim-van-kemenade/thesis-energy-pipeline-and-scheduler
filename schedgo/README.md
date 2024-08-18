# KubePowerSched

Adapted scheduler from [GitHub kelseyhightower/scheduler](https://github.com/kelseyhightower/scheduler.git).

## Run the Scheduler on Kubernetes

```cmd
kubectl create -f deployments/deployment.yaml
```

## Schedule pods using KubePowerSched

To schedule the pod using a specific scheduler use `spec:schedulerName`:
```yaml
spec:
  schedulerName: escheduler
```

## Energy based pod selection

- GET/POST `http://<node-ip>/api/v1/query`: POST to prevent a server-side URL character limits.
    - `query=<string>`: Prometheus expression query string.
- GET/POST `http://<node-ip>/api/v1/query_range`: POST to prevent a server-side URL character limits.
    - `query=<string>`: Prometheus expression query string.
    - `start=<rfc3339 | unix_timestamp>`: Start timestamp, inclusive.
    - `end=<rfc3339 | unix_timestamp>`: End timestamp, inclusive.
    - `step=<duration | float>`: Query resolution step width in duration format or float number of seconds.