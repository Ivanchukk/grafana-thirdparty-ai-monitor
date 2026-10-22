# JVM heap and garbage collection
Source: https://www.elastic.co/docs/troubleshoot/elasticsearch/high-jvm-memory-pressure

High heap occupancy together with sustained garbage collection and increased latency is evidence to investigate memory pressure. Heap occupancy alone is not the old-generation memory-pressure indicator, and normal heap use may have a sawtooth pattern. The demo measures total JVM heap occupancy, so treat its 85% warning as a demonstration operating limit.

Compare affected nodes against their peers and inspect the old-generation pool, garbage collection duration, allocation rate and Elasticsearch GC logs over the same interval. Expensive aggregations and shard overhead are possible contributors; confirm them using query and shard evidence. Do not prescribe a heap size or change JVM flags based on these metrics alone.
