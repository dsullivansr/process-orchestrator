# Process Orchestrator

A flexible process orchestration system that manages and monitors the execution of commands across multiple files.

## Features

- Run commands on multiple input files with templated arguments
- Configure input/output handling with YAML configuration
- Monitor process execution and resource usage
- Support for output file suffixes
- Flexible command-line argument templating

## Configuration

The system uses YAML configuration files to define process execution parameters. Here's an example:

```yaml
binary:
  path: /usr/bin/ffmpeg  # Path to the binary to execute
  flags:  # Command line flags with templated variables
    - "-i"
    - "{input_file}"  # Will be replaced with actual input file
    - "-vf"
    - "scale=1280:720"
    - "{output_file}"  # Will be replaced with output file path

directories:
  input_file_list: /path/to/input_files.txt  # File containing list of input files to process
  output_dir: /path/to/output  # Directory where processed files will be saved
  output_suffix: _720p  # Optional suffix to add to output files
```

The `input_file_list` should contain one file path per line, for example:

```text
/path/to/video1.mp4
/path/to/video2.mp4
/path/to/video3.mp4
```

## Usage

1. Create a configuration file (e.g., `config.yaml`) with your desired settings
2. Create a text file listing the input files to process
3. Run the orchestrator:

```bash
python -m orchestrator.process_manager --config config.yaml
```

## Command Templates

The system supports variable substitution in command flags:

- `{input_file}`: Replaced with the current input file being processed
- `{output_file}`: Replaced with the generated output file path

For example, if processing `/data/video1.mp4` with output suffix `_720p`, the command:

```yaml
flags:
  - "-i"
  - "{input_file}"
  - "{output_file}"
```

Would expand to:

```bash
-i /data/video1.mp4 /path/to/output/video1_720p.mp4
```

## Error Handling

The system includes error handling for:
- Missing or invalid input files
- Command execution failures
- Resource monitoring issues

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

The project uses:
- YAPF for code formatting
- Pylint for code quality
- Pre-commit hooks for consistency

## License

MIT License
