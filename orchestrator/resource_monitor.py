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
            'disk_percent': 90.0
        }
        self.output_dir = output_dir or os.getcwd()

    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics.

        Returns:
            Dictionary of system metrics
        """
        # Get disk usage for the device containing the output directory
        disk_usage = psutil.disk_usage(self.output_dir)

        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': disk_usage.percent
        }

    def can_start_new_process(self) -> bool:
        """Check if new process can be started.

        Returns:
            True if new process can be started, False otherwise
        """
        metrics = self.get_system_metrics()
        return all(metrics[k] < v for k, v in self.thresholds.items())
