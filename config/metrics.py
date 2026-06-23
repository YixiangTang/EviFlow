node_metrics = {
    "system.cpu.pct_usage": "Overall CPU utilization percentage of the node.",
    "system.cpu.system": "Percentage of CPU time spent in kernel (system) mode.",
    "system.cpu.user": "Percentage of CPU time spent in user mode.",
    "system.disk.pct_usage": "Percentage of disk capacity currently in use.",
    "system.mem.pct_usage": "Percentage of memory currently in use.",
    "system.io.r_await": "Average time (in milliseconds) for read requests to be served, including queue time and service time.",
    "system.io.r_s": "Number of read requests completed per second (read IOPS).",
    "system.io.w_await": "Average time (in milliseconds) for write requests to be served, including queue time and service time.",
    "system.io.w_s": "Number of write requests completed per second (write IOPS)."
}

pod_metrics = {
    "container_cpu_system_seconds": "Total CPU time spent in kernel mode by the container (in seconds).",
    "container_cpu_user_seconds": "Total CPU time spent in user mode by the container (in seconds).",
    "container_cpu_usage_seconds": "Total CPU time consumed by the container (in seconds), including both user and system time.",
    "container_memory_failures": "Number of memory allocation failures or OOM (Out Of Memory) events encountered by the container.",
    "container_memory_usage_MB": "Amount of memory currently used by the container (in megabytes).",
    "container_fs_reads": "Total number of filesystem read operations performed by the container.",
    "container_fs_reads_MB": "Total amount of data read from the filesystem by the container (in megabytes).",
    "container_fs_writes": "Total number of filesystem write operations performed by the container.",
    "container_fs_writes_MB": "Total amount of data written to the filesystem by the container (in megabytes).",
    "container_network_transmit_packets": "Total number of network packets transmitted by the container.",
    "container_network_transmit_MB": "Total amount of data transmitted over the network by the container (in megabytes).",
    "container_network_receive_packets": "Total number of network packets received by the container.",
    "container_network_receive_MB": "Total amount of data received over the network by the container (in megabytes)."
}

service_metrics = {
    "rr": "Receive request success rate of the service over the sampling interval.",
    "sr": "Send request success rate of the service over the sampling interval.",
    "mrt": "Mean response time of the service requests.",
    "count": "Total number of service requests in the sampling interval.",
}

nezha_metric_descriptions = {
    "CpuUsage(m)": "CPU usage of the service container in millicores.",
    "CpuUsageRate(%)": "CPU usage percentage of the service container.",
    "MemoryUsage(Mi)": "Memory usage of the service container in MiB.",
    "MemoryUsageRate(%)": "Memory usage percentage of the service container.",
    "SyscallRead": "Number of read syscalls observed for the service.",
    "SyscallWrite": "Number of write syscalls observed for the service.",
    "NetworkReceiveBytes": "Bytes received by the service over the network.",
    "NetworkTransmitBytes": "Bytes transmitted by the service over the network.",
    "PodClientLatencyP90(s)": "P90 latency when this service acts as a client.",
    "PodServerLatencyP90(s)": "P90 latency when this service acts as a server.",
    "PodClientLatencyP95(s)": "P95 latency when this service acts as a client.",
    "PodServerLatencyP95(s)": "P95 latency when this service acts as a server.",
    "PodClientLatencyP99(s)": "P99 latency when this service acts as a client.",
    "PodServerLatencyP99(s)": "P99 latency when this service acts as a server.",
    "PodWorkload(Ops)": "Observed service workload in operations per interval.",
    "PodSuccessRate(%)": "Request success rate percentage for the service.",
    "NodeCpuUsageRate(%)": "CPU usage percentage of the hosting node.",
    "NodeMemoryUsageRate(%)": "Memory usage percentage of the hosting node.",
    "NodeNetworkReceiveBytes": "Network receive bytes observed on the hosting node.",
    "SuccessRate(%)": "Request success rate percentage of the frontend service.",
    "LatencyP50(s)": "P50 request latency in seconds.",
    "LatencyP90(s)": "P90 request latency in seconds.",
    "LatencyP95(s)": "P95 request latency in seconds.",
    "LatencyP99(s)": "P99 request latency in seconds.",
}

rcaeval_metric_descriptions = {
    "cpu": "CPU usage of the service container.",
    "mem": "Memory usage of the service container.",
    "diskio": "Disk I/O activity of the service container.",
    "socket": "Socket usage or socket activity of the service container.",
    "workload": "Observed service workload over the sampling interval.",
    "error": "Observed service error signal over the sampling interval.",
    "latency-50": "P50 request latency of the service.",
    "latency-90": "P90 request latency of the service.",
}
