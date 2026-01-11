# Contributing to Artemis Language

Thank you for your interest in contributing to ARX! We welcome contributions from developers of all skill levels.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Issue Reporting](#issue-reporting)
- [Community Guidelines](#community-guidelines)

## Getting Started

Artemis (ARX) is a programming language with its own compiler and standard library. Before contributing, please:

1. Read our [documentation](https://mira-xt.github.io/artemis-language/)
2. Try running some examples from the `testing/` directory
3. Familiarize yourself with the codebase structure

## Development Setup

### Prerequisites

- **Python 3.7 or higher**
- **C Compiler**: GCC 7.0+ or Clang 10.0+
- **LLVM Tools**:
  - `llc` (LLVM static compiler)
- **Git**

### Setup Instructions

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/artemis-language.git
   cd artemis-language
   ```

3. Install Python dependencies probably in a virtual environment:
   ```bash
   pip install -r requirements.txt
   ```

4. Test the installation:
   ```bash
   python arx.py build testing/hello_world.arx
   ./out/hello_world
   ```


## How to Contribute

### Areas for Contribution

- **Language Features**: Syntax, operators, or language constructs suggestions
- **Standard Library**: Built-in functions and modules
- **Documentation**: User guides, API documentation, & examples
- **Testing**: Unit tests, integration tests, & example programs
- **Tooling**: IDE extensions, debugging tools, formatters

### Types of Contributions

1. **Bug Fixes**: Fix existing issues or unexpected behavior
2. **Feature Additions**: Suggest new language features or library functions
3. **Performance Improvements**: Runtime performance
4. **Documentation**: Improve existing docs or add new content
5. **Tests**: Add test cases for better coverage

## Code Style Guidelines

### Python Code (Compiler)

- Read the code style
- Use full and meaningful variable and function names
- Classes are Pascal Case
- Functions and variables ar Snake Case
- Constants are Screaming Snake Case
- Imports should be grouped in categories
- Use type hints and return types
- Whenever possible strings will have single quotes
- Unused variables start with underscore

Example:
```python
def parse_expression(self, tokens: List[Token]) -> ExpressionNode:
    # Implementation here
```

### C Code (Runtime Library)

- Use Kernighan & Ritchie brace style
- Classes are Pascal Case
- Functions and variables ar Snake Case
- Constants are Screaming Snake Case
- Use full meaningful variable & function names
- Follow existing naming conventions
- Include proper header guards
- Unused variables start with underscore

Example:
```c
char* string_concat(const char* a, const char* b) {
    // Implementation here
}
```

### ARX Test Code

- Use descriptive test names
- Include comments explaining what is being tested
- Test both positive and negative cases
- Keep tests simple and focused

## Testing

### Running Tests

Test your changes using the example programs:

```bash
python arx.py build testing/fibonacci.arx
# Or any under testing/
```

### Adding Tests

1. **Language Tests**: Add `.arx` files to the `testing/` directory
2. **Unit Tests**: Add Python test files for compiler components
3. **Integration Tests**: Test complete compilation and execution workflows

### Test Coverage

Ensure your changes include appropriate tests:
- New language features should have example programs
- Bug fixes should include regression tests
- API changes should have unit tests
- LLVM IR generation tests for backend changes

### Debugging Compilation Issues

When working on compiler improvements, use these debugging techniques:

```bash
python arx.py build testing/debug_example.arx --debug
# --debug argument enables debug prints
```

## Submitting Changes

### Pull Request Process

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**:
   - Write code following the style guidelines
   - Add tests for your changes
   - Update documentation if needed

3. **Test Your Changes**:
   ```bash
   # Test your specific changes
   python arx.py build your_test_file.arx
   ```

4. **Commit Your Changes**:
   ```bash
   git add .
   git commit -m "feat: brief description"
   ```

5. **Push and Create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

### Commit Message Guidelines

- Something not annoying
- Reference issues and pull requests liberally after the first line

Examples:
```
Add support for nested function calls

- Implement function call parsing in parser.py
- Add test cases for nested scenarios
- Update documentation

Fixes #123
```

### Pull Request Requirements

Your PR should:
- [ ] Have a clear title and description
- [ ] Include tests for new functionality
- [ ] Pass all existing tests
- [ ] Follow code style guidelines
- [ ] Update documentation if needed
- [ ] Reference related issues

## Issue Reporting

### Before Creating an Issue

1. Check if the issue already exists
2. Try to reproduce the issue with a minimal example
3. Check the documentation for expected behavior

### Bug Reports

Include:
- ARX version or commit hash
- Operating system and version
- Python version
- C version
- LLVM version
- Python library versions
- Minimal code example that reproduces the issue
- Expected vs actual behavior
- Error messages or stack traces

### Feature Requests

Include:
- Clear description of the proposed feature
- Use cases and examples
- How it fits with existing language design
- Potential implementation approach (if known)

## Community Guidelines

### Code of Conduct

- Be respectful
- Provide constructive feedback
- You can contribute
- If you have a suggestion ask & I'll see

### Getting Help

- Create an issue for questions about contributing
- Check existing documentation and issues first
- Be patient when waiting for responses
- Provide context and examples when asking for help

### Recognition

You can find yourself in the Git commit history or other contributors will be recognized in:
- Release notes for significant contributions
- Contributors section ?

## Development Workflow

### Working on Issues

1. Comment on the issue to indicate you're working on it
2. Ask questions if requirements are unclear
3. Provide regular updates on progress
4. Request help if you get stuck

### Code Review Process

1. All changes must be reviewed before merging
2. Address reviewer feedback promptly
3. Be open to suggestions and improvements
4. Update your PR based on feedback

### Release Process

- Contributions are merged to the `main` branch & are not meant to work other than development
- Releases are tagged with version numbers and should work

## Resources

- [Project Documentation](https://mira-xt.github.io/artemis-language/)
- [Language Examples](./testing/)
- [Issue Tracker](https://github.com/mira-xt/artemis-language/issues)

## License

By contributing to ARX, you agree that your contributions will be licensed under the GPLv3 License. This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

Thanks for contributing to ARX
