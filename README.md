<p align="center">
  <img width="240pt" src="./docs/arx-path.svg" alt="ARX Language Logo">
</p>

<div align="center">

# Artemis (ARX) Programming Language

**Some personal not bad looking programming language in Python compiled to LLVM**

[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://python.org)
[![Documentation](https://img.shields.io/badge/docs-online-green.svg)](https://mira-xt.github.io/arx-lang/)

[Documentation](https://mira-xt.github.io/arx-lang/) • [Getting Started](#quick-start) • [Contributing](CONTRIBUTING.md)

</div>

## Features

- **I Like My Syntax** - Readable code
- **LLVM Backend** - High-performance compilation with optimization
- **Type Safety** - Static typing with type inference
- **Modular Design** - Built-in module system with `using` imports
- **Cross-Platform** - Runs on Linux, Windows, not sure if anything else but just needs C and LLVM
- **On Going IDE Support** - Has VSCode extension

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/mira-xt/artemis-language.git
cd artemis-language

# Install
python arx_install.py -i

# Run your first ARX program
python arx.py build testing/hello_world.arx
./out/hello_world
```

### Hello World

```arx
using io

int _exec() {
    io.print('Hello, ARX!\n')
    return 0
}
```

### Fibonacci Example

```arx
using io

int fib(int n) {
    if (n <= 1) {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}

int _exec() {
    int result = fib(io.input_integer('Enter number > '))
    io.print(result)
    return 0
}
```

## Requirements

- **Python 3.7 or higher**
- **C Compiler**: GCC 7.0+ or Clang 10.0+
- **LLVM Tools**:
  - `llc` (LLVM static compiler)
- **Git**

## Architecture

```
ARX Source Code (.arx)
        ↓
    Lexer & Parser
        ↓
    Abstract Syntax Tree
        ↓
    Code Generator
        ↓
   LLVM IR / C Code
        ↓
    GCC / LLC Compiler
        ↓
    Native Binary
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

- **Bug Reports** - Help us improve reliability
- **Feature Requests** - Suggest new language features  
- **Documentation** - Improve guides and examples
- **Testing** - Add test cases and examples

## License

This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details. (Not changing it)

## Links

- [📖 **Documentation**](https://mira-xt.github.io/artemis-language/) - Complete language reference
- [🧩 **VS Code Extension**](https://github.com/mira-xt/arx-vscode/) - Not gonna update it
- [📁 **Examples**](testing/) - Sample ARX programs
- [🐛 **Issues**](https://github.com/mira-xt/artemis-language/issues) - Bug reports and feature requests

---

<div align="center">

**Made with boredom by the ARX Community (Me rn)**

Star this repo if you find ARX useful (Nah bro)

</div>
