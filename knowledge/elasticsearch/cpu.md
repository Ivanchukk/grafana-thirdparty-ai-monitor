# CPU usage and performance bottlenecks
Source: https://www.elastic.co/docs/troubleshoot/elasticsearch/high-cpu-usage

CPU saturation can accompany expensive searches, background indexing, and garbage collection. A coincident CPU and latency increase does not identify a cause. Compare CPU with request throughput, GC activity and node workload distribution. Recommended investigations include Elasticsearch hot threads, slow query logs, shard balance and host resource contention. These are read-only follow-up checks for an operator; the assistant cannot execute them against infrastructure.
