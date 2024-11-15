# ROS2 Clang-Tidy

ROS2 Clang-Tidy is a command-line tool designed to analyze and enforce C++ code style using [clang-tidy](https://clang.llvm.org/extra/clang-tidy/). It scans C++ packages within a ROS2 workspace, runs clang-tidy checks in parallel, and provides detailed reports on code quality and potential issues.

## Installation

We recommend using [pipx](https://pipxproject.github.io/pipx/) to install ROS2 Clang-Tidy.
```bash
pipx install git+https://github.com/yhisaki/ros2-clang-tidy.git
```

You can verify the installation by running:
```bash
ros2-clang-tidy --help
```

## Usage

The `ros2-clang-tidy` command provides various options to customize the analysis of your C++ packages. Below is a guide to help you get started.

### Basic Command

Navigate to the root of your workspace (where the `install` directory is located) and run:

```bash
ros2-clang-tidy
```

This will analyze all detected C++ packages using default settings.

### Options

```bash
usage: ros2-clang-tidy [-h] [--config CONFIG] [--config-file CONFIG_FILE]
                           [--jobs JOBS] [--explain-config] [--export-fixes EXPORT_FIXES]
                           [--fix-errors] [--packages-select [PACKAGE_NAME ...]]
                           [--base-path BASE_PATH] [--verbose] [--output-dir OUTPUT_DIR]
```

#### Arguments

- `--config CONFIG`: Clang-tidy configuration string.
- `--config-file CONFIG_FILE`: Path to the clang-tidy configuration file.
- `--jobs JOBS`: Number of clang-tidy jobs to run in parallel. *(Default: 1)*
- `--explain-config`: Explain the enabled clang-tidy checks.
- `--export-fixes EXPORT_FIXES`: Path to export the recorded fixes (DAT file).
- `--fix-errors`: Automatically fix the suggested changes.
- `--packages-select [PACKAGE_NAME ...]`: Only process the specified subset of packages.
- `--base-path BASE_PATH`: Base directory path to filter packages.
- `--verbose`: Enable verbose output.
- `--output-dir OUTPUT_DIR`: Directory where clang-tidy outputs will be stored.

### Interactive Completion

ROS2 Clang-Tidy supports [argcomplete](https://github.com/kislyuk/argcomplete) for tab-completion of command-line arguments. To enable it, follow the [argcomplete installation instructions](https://kislyuk.github.io/argcomplete/#global-activation).

## License

This project is licensed under the [Apache License](LICENSE).

---

**Author**: Y. Hisaki  
**Contact**: [yhisaki31@gmail.com](mailto:yhisaki31@gmail.com)
