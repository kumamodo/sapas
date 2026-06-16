# 01 Quick Start

This guide will help you quickly set up the Sapas development environment and run your first test flow using the built-in `Alishan` example project.

## Environment Requirements

- Python 3.8 or higher
- pip (Python package management tool)

## Installation Steps

1. Enter the project directory:

   ```bash
   cd sapas
   ```
2. Install dependencies in development mode:

   ```bash
   pip install -e .
   ```

## Project Structure Example (Alishan)

The `example` directory in Sapas contains a complete project called `Alishan`. Its structure is as follows:

```
sapas/
├── site_infra.yaml          # Global environment settings
└── example/                 # Example workspace
    ├── site_infra.yaml      # (Recommended) Place configuration file in the workspace
    └── Alishan/             # Alishan Project (Project Name)
        ├── configs/         # Project-level variables
        ├── criteria/        # Test specifications (CSV format)
        ├── flows/           # Test flow definitions
        ├── prompt_pictures/ # Images for operator GUI prompts (e.g. usb_disk.png)
        ├── scripts/         # Python test scripts
        └── stations/        # Station-specific settings (Function, Wireless)
```

## Running the Example Test

For ease of operation, it is recommended to first switch to the working directory (e.g., `example`):

```bash
cd example

# Start the Function station of the Alishan project
sapas --project Alishan --station Function
```

### Automated Execution (Quick Start)

If you have already specified commonly used projects and stations in `site_infra.yaml`:

```yaml
# Example site_infra.yaml content
PROJECT_NAME: Alishan
STATION_NAME: Function
```

Then you only need to enter the following command to start:

```bash
# Start directly (CLI mode)
sapas

# Or start the TUI (Graphical User Interface)
sapas --tui
```

### Common Parameters

- `--project`: Specify the project directory name.
- `--station`: Specify the station name (corresponding to folders under `stations/`).
- `--test_flow`: Force specify a specific `.flow` file.
- `--tui`: Start the graphical terminal interface (Dashboard).
