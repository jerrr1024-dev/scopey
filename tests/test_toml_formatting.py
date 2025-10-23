"""
Additional formatting and serialization regression tests for TOML output.
"""

from dataclasses import dataclass

from scopey.config import BaseConfig, global_param, local_param


@dataclass
class OptionalFieldConfig(BaseConfig):
    """Configuration used to inspect placeholder rendering."""

    service_name: str = global_param(required=False, default="demo")
    service_token: str = global_param(required=False, default=None)
    retries: int = local_param(required=False, default=3)


@dataclass
class ZeroDefaultsConfig(BaseConfig):
    """Configuration validating that falsy defaults remain documented."""

    enabled: bool = global_param(required=False, default=False)
    retry_limit: int = local_param(required=False, default=0)


def test_to_toml_no_duplicate_section_headers(temp_toml_file):
    """Ensure each section header appears only once in the generated TOML."""
    config = OptionalFieldConfig()
    config.to_toml(temp_toml_file, as_template=True, show_comments=True)

    content = temp_toml_file.read_text(encoding="utf-8")

    # Each section should be emitted exactly once.
    assert content.count("[global]") == 1
    assert content.count("[optionalfield]") == 1


def test_template_placeholders_are_separated_by_blank_line(temp_toml_file):
    """Valued entries should be separated from placeholder comments by a blank line."""
    config = OptionalFieldConfig()
    config.to_toml(temp_toml_file, as_template=True, show_comments=True)

    content = temp_toml_file.read_text(encoding="utf-8")
    global_section = content.split("[optionalfield]", maxsplit=1)[0]

    lines = [line.rstrip() for line in global_section.splitlines()]
    name_index = next(
        i for i, line in enumerate(lines) if line.startswith('service_name = "demo"')
    )

    assert lines[name_index].startswith('service_name = "demo"  # str | GLOBAL')
    assert lines[name_index + 1] == ""
    assert lines[name_index + 2].startswith('# service_token = ""  # str | GLOBAL')


def test_template_comments_include_falsey_defaults(temp_toml_file):
    """Falsy defaults (False/0) should still be mentioned in comments."""
    config = ZeroDefaultsConfig()
    config.to_toml(temp_toml_file, as_template=True, show_comments=True)

    content = temp_toml_file.read_text(encoding="utf-8")

    assert "enabled = false  # bool | GLOBAL | default: False" in content
    assert "retry_limit = 0  # int | LOCAL | default: 0" in content
