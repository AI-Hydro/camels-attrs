# Contributing to camels-attrs

Thank you for your interest in contributing to `camels-attrs`! This document provides guidelines for contributing to the project.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue on [GitHub Issues](https://github.com/galib9690/camels-attrs/issues) with:

1. A clear, descriptive title
2. Steps to reproduce the bug
3. Expected behavior vs. actual behavior
4. Your environment (Python version, OS, package version)
5. Any relevant error messages or logs

### Suggesting Features

Feature requests are welcome! Please open an issue with:

1. A clear description of the feature
2. The use case or problem it solves
3. Any relevant examples or references

### Submitting Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```
3. **Make your changes** with clear, descriptive commits
4. **Add tests** for any new functionality
5. **Run the test suite:**
   ```bash
   pytest tests/
   ```
6. **Update documentation** if needed
7. **Submit a pull request** with a clear description

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/camels-attrs.git
cd camels-attrs

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines
- Use descriptive variable and function names
- Add docstrings to all public functions and classes
- Keep functions focused and modular

## Questions?

For questions or support, please:
- Open an issue on GitHub
- Contact the maintainers: mgalib@purdue.edu

Thank you for contributing!
