#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import Dict, List, Tuple

import argcomplete
import tqdm


def get_all_packages() -> Dict[str, Path]:
    """
    Retrieve all packages by scanning the 'install' directory.

    Returns:
        A dictionary mapping package names to their respective package.xml paths.

    Raises:
        FileNotFoundError: If the 'install' directory does not exist.
    """
    packages_to_paths: Dict[str, Path] = {}
    install_directory = Path("install")
    if not install_directory.exists():
        raise FileNotFoundError(
            "The 'install' directory was not found. Please navigate to the root of the workspace."
        )

    for package_directory in install_directory.iterdir():
        if package_directory.is_dir():
            package_name = package_directory.name
            package_xml_path = (
                package_directory / "share" / package_name / "package.xml"
            )
            if not package_xml_path.exists():
                continue
            packages_to_paths[package_name] = package_xml_path.resolve().parent

    return packages_to_paths


def filter_packages_by_base_path(
    packages: Dict[str, Path], base_path: str
) -> Dict[str, Path]:
    """
    Filter packages based on a specified base path.

    Args:
        packages: A dictionary of package names and their paths.
        base_path: The base directory to filter packages against.

    Returns:
        A dictionary of packages that are relative to the base path.
    """
    base_directory = Path(base_path).resolve()
    filtered_packages = {
        name: path
        for name, path in packages.items()
        if path.resolve().is_relative_to(base_directory)
    }
    return filtered_packages


def find_cpp_files(package_path: Path) -> List[Path]:
    """
    Recursively find all C++ source and header files within a package, excluding 'test' directories.

    Args:
        package_path: The root path of the package.

    Returns:
        A list of Paths to C++ source and header files.
    """
    cpp_files: List[Path] = []

    for root, dirs, files in os.walk(package_path):
        current_root = Path(root)

        # Exclude 'test' directories from traversal
        dirs[:] = [directory for directory in dirs if directory.lower() != "test"]

        for file_name in files:
            file_path = current_root / file_name

            if file_path.suffix.lower() in [".cpp", ".cc", ".c"]:
                cpp_files.append(file_path)

    return cpp_files


def filter_cpp_files_by_compile_commands(cpp_files: List[Path], package_name: str):
    """
    Filter source files by the compile_commands.json file.
    """
    compile_commands_json = json.load(
        open(f"build/{package_name}/compile_commands.json")
    )
    builded_files = [Path(entry["file"]) for entry in compile_commands_json]
    cpp_files = [path for path in cpp_files if path in builded_files]
    return cpp_files


class ClangTidyPackageScanner:
    """
    Scans and manages C++ packages for running clang-tidy checks.
    """

    def __init__(self):
        self.package_paths: Dict[str, Path] = {}
        self.package_cpp_files: Dict[str, List[Path]] = {}

        all_packages = get_all_packages()
        for package_name, package_path in all_packages.items():
            cpp_files = find_cpp_files(package_path)
            if len(cpp_files) == 0:
                continue
            cpp_files = filter_cpp_files_by_compile_commands(cpp_files, package_name)
            if cpp_files:
                self.package_paths[package_name] = package_path
                self.package_cpp_files[package_name] = cpp_files

    def apply_base_path_filter(self, base_path: str):
        """
        Apply a base path filter to include only packages within the specified base path.

        Args:
            base_path: The base directory to filter packages.
        """
        self.package_paths = filter_packages_by_base_path(self.package_paths, base_path)
        self.package_cpp_files = {
            pkg: sources
            for pkg, sources in self.package_cpp_files.items()
            if pkg in self.package_paths
        }

    def select_packages(self, selected_packages: List[str]):
        """
        Select a subset of packages to process.

        Args:
            selected_packages: A list of package names to include.
        """
        for package_name in list(self.package_paths.keys()):
            if package_name not in selected_packages:
                self.package_paths.pop(package_name)
                self.package_cpp_files.pop(package_name)

    def list_available_packages(self) -> List[str]:
        """
        List all available package names.

        Returns:
            A list of package names.
        """
        return list(self.package_paths.keys())


def build_clang_tidy_command(
    clang_tidy_cmd: str,
    package_name: str,
    package_path: str,
    source_file: str,
    config: str,
    config_file: str,
    fix_errors: bool,
    export_fixes_path: str,
    use_color: bool,
) -> List[str]:
    """
    Construct the clang-tidy command with the provided parameters.

    Args:
        package_name: Name of the package being processed.
        package_path: Path to the package directory.
        source_file: Path to the C++ source or header file.
        config: Clang-tidy configuration string.
        config_file: Path to the clang-tidy configuration file.
        fix_errors: Flag to enable automatic fixing of errors.
        export_fixes_path: Path to export the fixes to a file.

    Returns:
        A list of command-line arguments for clang-tidy.
    """
    command = [clang_tidy_cmd]
    command += ["-p", f"build/{package_name}"]
    command += [f"--header-filter={package_path}/.*"]

    if config:
        command += [f"--config={config}"]

    if config_file:
        command += [f"--config-file={config_file}"]

    if fix_errors:
        command += ["--fix-errors"]

    if export_fixes_path:
        command += [f"--export-fixes={export_fixes_path}"]

    if use_color:
        command += ["--use-color"]

    command += [source_file]

    return command


def parse_result(result: subprocess.CompletedProcess) -> str:
    return f"Command: {' '.join(result.args)}\n{result.stderr}\n{result.stdout}\n"


def process_packages(scanner: ClangTidyPackageScanner, args):
    """
    Process all packages using a shared thread pool for parallel execution.

    Args:
        scanner: Instance of ClangTidyPackageScanner with package information.
        args: Command-line arguments.
    """
    from concurrent.futures import ThreadPoolExecutor

    total_errors = 0
    total_warnings = 0
    clang_tidy_commands = []
    package_file_map = {}

    # Collect all clang-tidy commands across all packages
    for package_name in scanner.list_available_packages():
        package_path = scanner.package_paths[package_name]
        cpp_files = scanner.package_cpp_files[package_name]
        package_file_map.update({str(file): package_name for file in cpp_files})

        for source_file in cpp_files:
            command = build_clang_tidy_command(
                clang_tidy_cmd=args.clang_tidy_cmd,
                package_name=package_name,
                package_path=str(package_path),
                source_file=str(source_file),
                config=args.config,
                config_file=args.config_file,
                fix_errors=args.fix_errors,
                export_fixes_path=args.export_fixes,
                use_color=args.use_color,
            )
            clang_tidy_commands.append((package_name, command))

    def execute_command(
        cmd_info: Tuple[str, List[str]]
    ) -> Tuple[str, subprocess.CompletedProcess[str]]:
        """
        Execute a single clang-tidy command.

        Args:
            cmd_info: A tuple containing package name and the command to execute.

        Returns:
            A tuple of package name, combined output, and the error count.
        """
        package_name, cmd = cmd_info
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,  # Continue even if clang-tidy reports issues
            )

            has_some_output = len(result.stdout) > 0 or len(result.stderr) > 0

            if args.output_dir:
                os.makedirs(args.output_dir, exist_ok=True)
                if args.output_all or has_some_output:
                    log_file_path = os.path.join(args.output_dir, f"{package_name}.log")
                    with open(log_file_path, "a") as log_file:
                        log_file.write(parse_result(result))

            return package_name, result

        except Exception as error:
            return (
                package_name,
                subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr=str(error)
                ),
            )

    # Use a shared thread pool to execute all commands
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        results = list(
            tqdm.tqdm(
                executor.map(execute_command, clang_tidy_commands),
                total=len(clang_tidy_commands),
                desc="Running clang-tidy",
            )
        )

    # Collect and process results
    package_errors = {}
    for package_name, result in results:
        error_count = result.stdout.count("error: ")
        warning_count = result.stdout.count("warning: ")
        total_errors += error_count
        total_warnings += warning_count
        if package_name not in package_errors:
            package_errors[package_name] = 0
        package_errors[package_name] += error_count

        if args.output_all or len(result.stdout) > 0 or len(result.stderr) > 0:
            print(parse_result(result))

        if args.output_all or error_count > 0 or warning_count > 0:
            print(f"{package_name}: {error_count} errors, {warning_count} warnings")

    return total_errors, total_warnings


def main():
    """
    Main function to parse arguments and execute clang-tidy across selected packages.
    """
    scanner = ClangTidyPackageScanner()

    parser = argparse.ArgumentParser(
        description="Analyze C++ code style using clang-tidy.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--clang-tidy-cmd",
        type=str,
        default="clang-tidy",
        help="Clang-tidy command to use.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Clang-tidy configuration string.",
    )
    parser.add_argument(
        "--config-file",
        type=str,
        default=None,
        help="Path to the clang-tidy configuration file.",
    )
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=1,
        help="Number of clang-tidy jobs to run in parallel.",
    )
    parser.add_argument(
        "--explain-config",
        action="store_true",
        help="Explain the enabled clang-tidy checks.",
    )
    parser.add_argument(
        "--export-fixes",
        type=str,
        default=None,
        help="Path to export the recorded fixes (DAT file).",
    )
    parser.add_argument(
        "--fix-errors",
        action="store_true",
        help="Automatically fix the suggested changes.",
    )
    parser.add_argument(
        "--packages-select",
        nargs="*",
        metavar="PACKAGE_NAME",
        choices=scanner.list_available_packages(),
        help="Only process the specified subset of packages.",
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default=None,
        help="Base directory path to filter packages.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory where clang-tidy outputs will be stored.",
    )
    parser.add_argument(
        "--use-color",
        action="store_true",
        help="Use color in the output.",
    )
    parser.add_argument(
        "--output-all",
        action="store_true",
        help="Output all even if no errors or warnings.",
    )

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.packages_select:
        scanner.select_packages(args.packages_select)

    if args.base_path:
        scanner.apply_base_path_filter(args.base_path)

    total_packages = len(scanner.package_cpp_files)
    print(f"Processing {total_packages} package(s)")

    total_errors, total_warnings = process_packages(scanner, args)

    if total_warnings > 0:
        print(f"Total warnings encountered: {total_warnings}")

    if total_errors > 0:
        print(f"Total errors encountered: {total_errors}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
