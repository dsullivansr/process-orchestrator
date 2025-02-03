# Process Orchestrator

A flexible process orchestration system that manages and monitors the execution of file processing jobs.

## Features

- YAML-based job configuration
- Parallel process execution
- Process monitoring and management
- Configurable input/output handling
- Safety checks to prevent accidental file overwrites

## Job Configuration

Jobs are defined using YAML configuration files. Each job configuration specifies:

1. The binary (executable) to run
2. Command-line flags and arguments
3. Input and output directory settings

### Basic Configuration Structure

```yaml
job_name:
  binary:
    path: /path/to/binary
    flags:
      - "-flag1"
      - "{input_file}"  # Will be replaced with actual input file
      - "{output_file}" # Will be replaced with actual output file
  directories:
    input_dir: /path/to/input
    output_dir: /path/to/output
    output_suffix: .processed  # Optional suffix for output files
```

### Output File Handling

The system provides flexible output file naming through the optional `output_suffix` configuration:

1. **With Suffix**: If `output_suffix` is specified, it will be appended to each output filename
   ```yaml
   directories:
     input_dir: /data/input
     output_dir: /data/output
     output_suffix: .processed
   ```
   Example: `input.txt` → `input.txt.processed`

2. **Without Suffix**: If `output_suffix` is omitted, output files keep their original names
   ```yaml
   directories:
     input_dir: /data/input
     output_dir: /data/output
   ```
   Example: `input.txt` → `input.txt`

### Safety Features

1. **Same Directory Protection**: When input and output directories are the same, an output suffix is required to prevent file overwrites
   ```yaml
   # This is valid - files will be suffixed
   directories:
     input_dir: /data/workspace
     output_dir: /data/workspace
     output_suffix: .new

   # This will raise an error - no suffix to prevent overwrites
   directories:
     input_dir: /data/workspace
     output_dir: /data/workspace
   ```

2. **Path Normalization**: The system normalizes paths to handle different path formats and prevent confusion
   ```yaml
   # These are treated as the same directory
   input_dir: /data/workspace
   output_dir: /data/workspace/../workspace
   ```

## Example Configurations

### 1. File Copy Job
```yaml
file_copy_job:
  binary:
    path: /bin/cp
    flags:
      - "-v"
      - "{input_file}"
      - "{output_file}"
  directories:
    input_dir: /data/input
    output_dir: /data/output
    output_suffix: .copy
```

### 2. Compression Job
```yaml
compression_job:
  binary:
    path: /bin/gzip
    flags:
      - "-c"
      - "{input_file}"
      - ">"
      - "{output_file}"
  directories:
    input_dir: /data/input
    output_dir: /data/compressed
    output_suffix: .gz
```

### 3. In-Place Processing
```yaml
inplace_job:
  binary:
    path: /bin/sed
    flags:
      - "-i"
      - "s/old/new/g"
      - "{input_file}"
      - ">"
      - "{output_file}"
  directories:
    input_dir: /data/workspace
    output_dir: /data/workspace  # Same as input
    output_suffix: .processed    # Required for in-place processing
```

## Usage

1. Create a job configuration file:
   ```yaml
   my_job:
     binary:
       path: /bin/process
       flags: [...]
     directories:
       input_dir: /path/to/input
       output_dir: /path/to/output
       output_suffix: .processed
   ```

2. Load and use the configuration in your code:
   ```python
   from orchestrator.config import Config
   from orchestrator.process_manager import ProcessManager

   # Load configuration
   config = Config(config_path='job_config.yaml')

   # Create process manager
   manager = ProcessManager(config)

   # Process a file
   process_info = manager.start_process('input_file.txt')
   ```

## Installation

```bash
pip install -r requirements.txt
```

## Testing

```bash
python -m pytest tests/
