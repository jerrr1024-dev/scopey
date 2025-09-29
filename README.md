# Scopey

<div align="center">
  <img src="assets/logo_1.png" alt="Scopey Logo" width="200"/>

  <!-- Language Toggle Badges -->
  <div style="margin: 20px 0;">
    <img src="https://img.shields.io/badge/Language-English-blue?style=for-the-badge&logo=googletranslate&logoColor=white" alt="English" />
    <a href="README.zh.md">
      <img src="https://img.shields.io/badge/Language-中文-red?style=for-the-badge&logo=googletranslate&logoColor=white" alt="中文" />
    </a>
  </div>
</div>

---

## English

**Scopey** is a powerful Python library for scope-based configuration management. It provides a flexible and intuitive way to handle configuration parameters with different scopes (global, local, nested) while supporting TOML file loading and validation.

### 🚀 Quick Start

#### Installation

```bash
pip install scopey
```

#### Basic Usage

```python
import scopey as sc
from dataclasses import dataclass

@dataclass
class MyConfig(sc.BaseConfig):
    # Global parameter - must be in global section
    database_url: str = sc.global_param()

    # Local parameter - must be in module section
    batch_size: int = sc.local_param(default=32)

    # Global-first parameter - prefers global, falls back to local
    timeout: float = sc.global_first_param(default=30.0)

    # Local-first parameter - prefers local, falls back to global
    debug: bool = sc.local_first_param(default=False)

# Load from TOML file
config = MyConfig.from_toml("config.toml", module_section="myapp")

# Or create from dictionary
data = {
    "global": {
        "database_url": "postgresql://localhost/mydb",
        "timeout": 60.0
    },
    "myapp": {
        "batch_size": 64,
        "debug": True
    }
}
config = MyConfig.from_dict(data, module_section="myapp")
```

### 📋 Features

- **🎯 Scope-based Parameters**: Support for global, local, nested, and priority-based parameter scopes
- **📁 TOML Integration**: Native support for loading and saving TOML configuration files
- **✅ Validation**: Built-in parameter validation with required field checking
- **🔧 Flexible Loading**: Load configurations from files or dictionaries
- **🏗️ Nested Configurations**: Support for complex nested configuration structures
- **🔄 Configuration Merging**: Merge multiple configurations into a single object
- **⚠️ Override Warnings**: Optional warnings when parameter values are overridden

### 🎛️ Parameter Scopes

| Scope | Description | Usage |
|-------|-------------|-------|
| `global_param()` | Must be in global section only | `sc.global_param()` |
| `local_param()` | Must be in module section only | `sc.local_param()` |
| `global_first_param()` | Global takes priority over local | `sc.global_first_param()` |
| `local_first_param()` | Local takes priority over global | `sc.local_first_param()` |
| `nested_param()` | Nested configuration object | `sc.nested_param(NestedConfig)` |

### 🏗️ Advanced Usage

#### Nested Configurations

```python
@dataclass
class DatabaseConfig(sc.BaseConfig):
    host: str = sc.local_param()
    port: int = sc.local_param(default=5432)

@dataclass
class AppConfig(sc.BaseConfig):
    name: str = sc.global_param()
    database: DatabaseConfig = sc.nested_param(DatabaseConfig)
```

#### Configuration Merging

```python
# Merge multiple configurations
config1 = DatabaseConfig.from_toml("db.toml", "database")
config2 = CacheConfig.from_toml("cache.toml", "cache")
merged = sc.BaseConfig.merge([config1, config2], "CombinedConfig")
```

### 📄 TOML File Format

```toml
[global]
database_url = "postgresql://localhost/mydb"
timeout = 60.0

[myapp]
batch_size = 64
debug = true

[myapp.nested_section]
host = "localhost"
port = 5432
```

### 🔧 API Reference

#### Core Classes
- `BaseConfig`: Base class for all configuration objects
- `ParamScope`: Enumeration of parameter scope types

#### Decorators
- `global_param(required=True, default=None)`: Global scope parameter
- `local_param(required=True, default=None)`: Local scope parameter
- `global_first_param(required=True, default=None)`: Global-priority parameter
- `local_first_param(required=True, default=None)`: Local-priority parameter
- `nested_param(nested_class, required=True, default=None)`: Nested configuration

### 📝 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

### 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<div align="center">
  <p>Made with ❤️ by C4C-Dev</p>
  <p>
    <a href="mailto:jerry.sy.bai@gmail.com">📧 Contact</a> |
    <a href="https://github.com/C4C-Dev/scopey">🐙 GitHub</a>
  </p>
</div>