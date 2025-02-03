"""Resource monitor for tracking system resources."""

from typing import Dict, Optional

import psutil


class ResourceMonitor:
    """Resource monitor for tracking system resources."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        """Initialize resource monitor.

        Args:
            thresholds: Optional resource thresholds
        """
        self.thresholds = thresholds or {
            'cpu_percent': 80.0,
            'memory_percent': 80.0,
            'disk_percent': 90.0
        }

    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics.

        Returns:
            Dictionary of system metrics
        """
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }

    def can_start_new_process(self) -> bool:
        """Check if new process can be started.

        Returns:
            True if new process can be started, False otherwise
        """
        metrics = self.get_system_metrics()
        return all(metrics[k] < v for k, v in self.thresholds.items())
