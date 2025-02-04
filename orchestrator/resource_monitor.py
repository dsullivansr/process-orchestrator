"""Resource monitor for tracking system resources."""

from typing import Dict, Optional
import os

import psutil


class ResourceMonitor:
    """Resource monitor for tracking system resources."""

    def __init__(self,
                 thresholds: Optional[Dict[str, float]] = None,
                 output_dir: Optional[str] = None) -> None:
        """Initialize resource monitor.

        Args:
            thresholds: Optional resource thresholds
            output_dir: Output directory to monitor disk usage for
        """
        self.thresholds = thresholds or {
            'cpu_percent': 80.0,
            'memory_percent': 80.0,
            'disk_percent': 90.0,
            'max_processes': 2
        }
        self.output_dir = output_dir or os.getcwd()
        self.running_processes = set()

    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics.

        Returns:
            Dictionary of system metrics
        """
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage(self.output_dir).percent
        }

    def can_start_new_process(self) -> bool:
        """Check if new process can be started.

        Returns:
            True if new process can be started, False otherwise
        """
        if len(self.running_processes) >= self.thresholds['max_processes']:
            return False

        metrics = self.get_system_metrics()
        resource_checks = {
            'cpu_percent':
                metrics['cpu_percent'] < self.thresholds['cpu_percent'],
            'memory_percent':
                metrics['memory_percent'] < self.thresholds['memory_percent'],
            'disk_percent':
                metrics['disk_percent'] < self.thresholds['disk_percent']
        }
        return all(resource_checks.values())
