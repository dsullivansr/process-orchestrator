#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
import subprocess
from prometheus_client import start_http_server, Gauge
from typing import Optional

class ProcessOrchestrator:
    def __init__(self, binary_path: str, metrics_port: int = 8000):
        self.binary_path = binary_path
        self.process: Optional[subprocess.Popen] = None
        self.metrics_port = metrics_port
        
        # Initialize metrics
        self.cpu_usage = Gauge('process_cpu_percent', 'CPU usage in percent')
        self.memory_usage = Gauge('process_memory_bytes', 'Memory usage in bytes')
        self.disk_read_bytes = Gauge('process_disk_read_bytes', 'Disk read in bytes')
        self.disk_write_bytes = Gauge('process_disk_write_bytes', 'Disk write in bytes')
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def start_process(self):
        """Start the managed process."""
        if self.process is not None and self.process.poll() is None:
            self.logger.warning("Process is already running")
            return

        try:
            self.process = subprocess.Popen(
                self.binary_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            self.logger.info(f"Started process with PID: {self.process.pid}")
        except Exception as e:
            self.logger.error(f"Failed to start process: {e}")
            raise

    def collect_metrics(self):
        """Collect and update process metrics."""
        if self.process is None or self.process.poll() is not None:
            self.logger.warning("Process is not running")
            return

        try:
            proc = psutil.Process(self.process.pid)
            
            # CPU usage
            self.cpu_usage.set(proc.cpu_percent())
            
            # Memory usage
            memory_info = proc.memory_info()
            self.memory_usage.set(memory_info.rss)
            
            # Disk I/O
            io_counters = proc.io_counters()
            self.disk_read_bytes.set(io_counters.read_bytes)
            self.disk_write_bytes.set(io_counters.write_bytes)
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")

    def run(self):
        """Main run loop."""
        # Start Prometheus metrics server
        start_http_server(self.metrics_port)
        self.logger.info(f"Started metrics server on port {self.metrics_port}")

        # Start the process
        self.start_process()

        try:
            while True:
                if self.process.poll() is not None:
                    self.logger.error("Process has terminated unexpectedly")
                    self.start_process()  # Restart the process
                
                self.collect_metrics()
                time.sleep(1)  # Collect metrics every second
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down orchestrator...")
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python orchestrator.py <path_to_binary>")
        sys.exit(1)

    binary_path = sys.argv[1]
    orchestrator = ProcessOrchestrator(binary_path)
    orchestrator.run()
