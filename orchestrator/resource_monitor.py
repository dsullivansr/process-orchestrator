"""Resource monitor for tracking system resources with dynamic throttling."""

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from typing import Dict, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    start_time: datetime
    memory_usage: float  # In bytes
    cpu_usage: float  # Percentage


class ResourceMonitor:
    """Resource monitor for tracking system resources with dynamic throttling."""

    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        *,
        output_dir: Optional[str] = None,
        monitoring_interval: int = 5,  # seconds
        throttle_threshold: float = 0.9,  # 90% of max
        recovery_threshold: float = 0.7,  # 70% of max
    ) -> None:
        """Initialize resource monitor.

        Args:
            thresholds: Optional resource thresholds
            output_dir: Output directory to monitor disk usage for
            monitoring_interval: How often to update metrics (seconds)
            throttle_threshold: When to start throttling (percentage of max)
            recovery_threshold: When to stop throttling (percentage of max)
        """
        self.thresholds = thresholds or {
            'cpu_percent': 80.0,
            'memory_percent': 80.0,
            'disk_percent': 90.0,
            'max_processes': 2
        }
        self.output_dir = output_dir or os.getcwd()
        self.monitoring_interval = monitoring_interval
        self.throttle_threshold = throttle_threshold
        self.recovery_threshold = recovery_threshold
        self.last_check = datetime.now()
        self.running_processes: Dict[str, ProcessInfo] = {}
        self.throttled = False
        self.original_max_processes = self.thresholds['max_processes']

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

    def update_process_metrics(self) -> None:
        """Update metrics for all running processes."""
        current_time = datetime.now()
        if (current_time -
                self.last_check).total_seconds() < self.monitoring_interval:
            return

        self.last_check = current_time
        metrics = self.get_system_metrics()

        # Check if we need to throttle or can recover
        resource_usage = max(
            metrics['cpu_percent'] / self.thresholds['cpu_percent'],
            metrics['memory_percent'] / self.thresholds['memory_percent'],
            metrics['disk_percent'] / self.thresholds['disk_percent']
        )

        if not self.throttled and resource_usage > self.throttle_threshold:
            self._apply_throttling(metrics)
        elif self.throttled and resource_usage < self.recovery_threshold:
            self._remove_throttling()

        # Update metrics for each running process
        for file_id, proc_info in list(self.running_processes.items()):
            try:
                proc = psutil.Process(proc_info.pid)
                with proc.oneshot():
                    cpu_percent = proc.cpu_percent()
                    memory_info = proc.memory_info()
                    self.running_processes[file_id] = ProcessInfo(
                        pid=proc_info.pid,
                        start_time=proc_info.start_time,
                        memory_usage=memory_info.rss,
                        cpu_usage=cpu_percent
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.warning(
                    "Process %d no longer exists or is inaccessible",
                    proc_info.pid
                )
                del self.running_processes[file_id]

    def _apply_throttling(self, metrics: Dict[str, float]) -> None:
        """Apply throttling based on current resource usage."""
        self.throttled = True
        current_processes = len(self.running_processes)

        # Calculate new max processes based on resource usage
        cpu_ratio = self.thresholds['cpu_percent'] / max(
            metrics['cpu_percent'], 1
        )
        memory_ratio = self.thresholds['memory_percent'] / max(
            metrics['memory_percent'], 1
        )
        disk_ratio = self.thresholds['disk_percent'] / max(
            metrics['disk_percent'], 1
        )

        # Use the most constraining ratio
        ratio = min(cpu_ratio, memory_ratio, disk_ratio)
        new_max = max(1, int(current_processes * ratio * 0.8))  # 20% buffer

        logger.info(
            "Applying throttling: Reducing max processes from %d to %d due to resource usage"
            " (CPU: %.1f%%, Memory: %.1f%%, Disk: %.1f%%)",
            self.thresholds['max_processes'], new_max, metrics['cpu_percent'],
            metrics['memory_percent'], metrics['disk_percent']
        )

        self.thresholds['max_processes'] = new_max

    def _remove_throttling(self) -> None:
        """Remove throttling and restore original max processes."""
        self.throttled = False
        logger.info(
            "Removing throttling: Restoring max processes to %d",
            self.original_max_processes
        )
        self.thresholds['max_processes'] = self.original_max_processes

    def can_start_new_process(self) -> bool:
        """Check if new process can be started.

        Returns:
            True if new process can be started, False otherwise
        """
        # Update metrics before making decision
        self.update_process_metrics()

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

    def add_process(self, file_id: str, process: psutil.Process) -> None:
        """Add a new process to monitor.

        Args:
            file_id: Unique identifier for the process (e.g., input file path)
            process: Process object to monitor
        """
        try:
            with process.oneshot():
                self.running_processes[file_id] = ProcessInfo(
                    pid=process.pid,
                    start_time=datetime.now(),
                    memory_usage=process.memory_info().rss,
                    cpu_usage=process.cpu_percent()
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(
                "Failed to add process %d for monitoring: %s", process.pid, e
            )

    def remove_process(self, file_id: str) -> None:
        """Remove a process from monitoring.

        Args:
            file_id: Unique identifier for the process
        """
        if file_id in self.running_processes:
            del self.running_processes[file_id]
