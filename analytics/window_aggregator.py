from elasticsearch import Elasticsearch
from datetime import datetime, timedelta
import numpy as np

ES_INDEX = "soc-logs*"
WINDOW_MINUTES = 5

es = Elasticsearch("http://localhost:9200")


def get_window(start, end):
    query = {
        "size": 0,
        "query": {
            "range": {
                "@timestamp": {
                    "gte": start.isoformat(),
                    "lt": end.isoformat()
                }
            }
        },
        "aggs": {
            "request_count": { "value_count": { "field": "request_id" } },
            "avg_latency": { "avg": { "field": "latency_ms" } },
            "p95_latency": {
                "percentiles": {
                    "field": "latency_ms",
                    "percents": [95]
                }
            },
            "unique_ips": {
                "cardinality": { "field": "client_ip" }
            },
            "errors_4xx": {
                "filter": {
                    "range": { "status_code": { "gte": 400, "lt": 500 } }
                }
            },
            "errors_5xx": {
                "filter": {
                    "range": { "status_code": { "gte": 500 } }
                }
            },
            "bytes_in": { "sum": { "field": "request_size_bytes" } },
            "bytes_out": { "sum": { "field": "response_size_bytes" } }
        }
    }

    res = es.search(index=ES_INDEX, body=query)
    aggs = res["aggregations"]

    total = aggs["request_count"]["value"] or 1

    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "request_count": total,
        "avg_latency": aggs["avg_latency"]["value"] or 0,
        "p95_latency": aggs["p95_latency"]["values"]["95.0"],
        "unique_ips": aggs["unique_ips"]["value"],
        "rate_4xx": aggs["errors_4xx"]["doc_count"] / total,
        "rate_5xx": aggs["errors_5xx"]["doc_count"] / total,
        "bytes_in": aggs["bytes_in"]["value"],
        "bytes_out": aggs["bytes_out"]["value"],
    }

def store_metrics(doc):
    es.index(index="soc-metrics", document=doc)


def run():
    end = datetime.utcnow()
    start = end - timedelta(minutes=WINDOW_MINUTES)

    features = get_window(start, end)
    store_metrics(features)
    print("Stored window metrics:", features)

    print(features)
    from anomaly_rules import detect_anomaly

    alerts = detect_anomaly(features)
    if alerts:
        print("ALERTS:", alerts)



if __name__ == "__main__":
    run()

