# Scopey

<div align="center">
  <img src="assets/logo_1.png" alt="Scopey Logo" width="200"/>

  <!-- Language Toggle Buttons -->
  <div style="margin: 20px 0;">
    <button onclick="showLanguage('en')" id="btn-en" style="background-color: #007acc; color: white; border: none; padding: 8px 16px; margin: 5px; border-radius: 5px; cursor: pointer; font-weight: bold;">English</button>
    <button onclick="showLanguage('zh')" id="btn-zh" style="background-color: #6c757d; color: white; border: none; padding: 8px 16px; margin: 5px; border-radius: 5px; cursor: pointer;">中文</button>
  </div>
</div>

<script>
function showLanguage(lang) {
  // Hide all language sections
  const enContent = document.getElementById('content-en');
  const zhContent = document.getElementById('content-zh');
  const enBtn = document.getElementById('btn-en');
  const zhBtn = document.getElementById('btn-zh');

  if (lang === 'en') {
    enContent.style.display = 'block';
    zhContent.style.display = 'none';
    enBtn.style.backgroundColor = '#007acc';
    zhBtn.style.backgroundColor = '#6c757d';
  } else {
    enContent.style.display = 'none';
    zhContent.style.display = 'block';
    enBtn.style.backgroundColor = '#6c757d';
    zhBtn.style.backgroundColor = '#dc3545';
  }
}

// Set default language to English
document.addEventListener('DOMContentLoaded', function() {
  showLanguage('en');
});
</script>

---

<!-- English Content -->
<div id="content-en">

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

</div>

<!-- Chinese Content -->
<div id="content-zh" style="display: none;">

## 中文

**Scopey** 是一个强大的 Python 配置管理库，提供基于作用域的配置参数管理。它支持不同作用域（全局、本地、嵌套）的参数处理，同时支持 TOML 文件加载和验证。

### 🚀 快速开始

#### 安装

```bash
pip install scopey
```

#### 基本用法

```python
import scopey as sc
from dataclasses import dataclass

@dataclass
class MyConfig(sc.BaseConfig):
    # 全局参数 - 必须在全局配置段中
    database_url: str = sc.global_param()

    # 本地参数 - 必须在模块配置段中
    batch_size: int = sc.local_param(default=32)

    # 全局优先参数 - 优先使用全局值，其次本地值
    timeout: float = sc.global_first_param(default=30.0)

    # 本地优先参数 - 优先使用本地值，其次全局值
    debug: bool = sc.local_first_param(default=False)

# 从 TOML 文件加载
config = MyConfig.from_toml("config.toml", module_section="myapp")

# 或从字典创建
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

### 📋 功能特性

- **🎯 作用域参数**: 支持全局、本地、嵌套和优先级参数作用域
- **📁 TOML 集成**: 原生支持 TOML 配置文件的加载和保存
- **✅ 参数验证**: 内置参数验证和必填字段检查
- **🔧 灵活加载**: 支持从文件或字典加载配置
- **🏗️ 嵌套配置**: 支持复杂的嵌套配置结构
- **🔄 配置合并**: 将多个配置合并为单个对象
- **⚠️ 覆盖警告**: 参数值被覆盖时的可选警告

### 🎛️ 参数作用域

| 作用域 | 描述 | 用法 |
|-------|------|------|
| `global_param()` | 仅能在全局配置段中 | `sc.global_param()` |
| `local_param()` | 仅能在模块配置段中 | `sc.local_param()` |
| `global_first_param()` | 全局优先于本地 | `sc.global_first_param()` |
| `local_first_param()` | 本地优先于全局 | `sc.local_first_param()` |
| `nested_param()` | 嵌套配置对象 | `sc.nested_param(NestedConfig)` |

### 🏗️ 高级用法

#### 嵌套配置

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

#### 配置合并

```python
# 合并多个配置
config1 = DatabaseConfig.from_toml("db.toml", "database")
config2 = CacheConfig.from_toml("cache.toml", "cache")
merged = sc.BaseConfig.merge([config1, config2], "CombinedConfig")
```

### 📄 TOML 文件格式

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

### 🔧 API 参考

#### 核心类
- `BaseConfig`: 所有配置对象的基类
- `ParamScope`: 参数作用域类型枚举

#### 装饰器
- `global_param(required=True, default=None)`: 全局作用域参数
- `local_param(required=True, default=None)`: 本地作用域参数
- `global_first_param(required=True, default=None)`: 全局优先参数
- `local_first_param(required=True, default=None)`: 本地优先参数
- `nested_param(nested_class, required=True, default=None)`: 嵌套配置

### 📝 许可证

本项目采用 Apache License 2.0 许可证 - 详情请参见 [LICENSE](LICENSE) 文件。

### 🤝 贡献

欢迎贡献代码！请随时提交 Pull Request。

</div>

---

<div align="center">
  <p>Made with ❤️ by C4C-Dev</p>
  <p>
    <a href="mailto:jerry.sy.bai@gmail.com">📧 Contact</a> |
    <a href="https://github.com/C4C-Dev/scopey">🐙 GitHub</a>
  </p>
</div>