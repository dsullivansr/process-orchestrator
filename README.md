# Process Orchestrator

A Python-based process orchestrator that manages and monitors a binary process, collecting metrics for CPU, memory, and disk usage.

## Features

- Process management with automatic restart on failure
- Real-time monitoring of:
  - CPU usage
  - Memory usage
  - Disk I/O
- Prometheus metrics endpoint for monitoring integration
- Logging system for process events

## Requirements

- Python 3.7+
- Dependencies listed in requirements.txt

## Installation

1. Clone the repository
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Unix/macOS
   # or
   .\venv\Scripts\activate  # On Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the orchestrator with your binary:
```bash
python orchestrator.py /path/to/your/binary
```

The orchestrator will:
1. Start your binary process
2. Monitor its resource usage
3. Automatically restart it if it crashes
4. Expose metrics on http://localhost:8000 for Prometheus scraping

## Metrics

Access metrics at http://localhost:8000. Available metrics:
- process_cpu_percent
- process_memory_bytes
- process_disk_read_bytes
- process_disk_write_bytes
