"""System resource monitoring for the orchestrator."""

from typing import Dict
import psutil


class ResourceMonitor:
    """Monitors system resources and provides capacity information."""

    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system-wide metrics.

        Returns:
            Dictionary containing system metrics:
            - cpu_percent: CPU usage percentage
            - memory_percent: Memory usage percentage
            - disk_percent: Disk usage percentage
        """
        return {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }

    def can_start_new_process(self, thresholds: Dict[str, float]) -> bool:
        """Check if system has capacity for a new process.

        Args:
            thresholds: Dictionary containing resource thresholds:
                - cpu_percent: Maximum CPU usage percentage
                - memory_percent: Maximum memory usage percentage
                - disk_percent: Maximum disk usage percentage

        Returns:
            True if system has capacity for a new process, False otherwise.
        """
        metrics = self.get_system_metrics()

        return all(
            metrics[key] <= threshold for key, threshold in thresholds.items())
