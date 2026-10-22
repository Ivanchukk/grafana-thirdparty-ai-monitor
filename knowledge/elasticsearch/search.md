# Search latency and search thread pool rejections
Source: https://www.elastic.co/guide/en/elasticsearch/reference/8.19/rejected-requests.html

Search thread pool rejections indicate that work could not be accepted. Compare a rate of rejected tasks with search throughput and latency over aligned windows. Cumulative rejection counts should first be converted to rates so old incidents are not interpreted as a current rejection storm. A histogram quantile estimates a latency percentile from buckets; it is not an exact observed request duration.

An increase in request volume, latency and rejection rate is consistent with search overload. Other explanations include CPU or memory pressure and slow or expensive queries. Inspect slow logs, thread pool queues, request distribution and shard balance before concluding. Do not automatically increase thread pool or queue sizes, change configurations, or assert causation from correlation.
