def detect_anomaly(features):
    alerts = []

    if features["rate_4xx"] > 0.3:
        alerts.append("High 4xx rate (possible brute force)")

    if features["rate_5xx"] > 0.1:
        alerts.append("Service instability")

    if features["p95_latency"] > 1000:
        alerts.append("Latency spike")

    if features["unique_ips"] > 500:
        alerts.append("Possible scanning / DDoS")

    return alerts

