On macOS, a process that ends while contraagent reads the host's processes no longer stops the read with a `SystemError` from psutil 7.2.2; that process is left out.
