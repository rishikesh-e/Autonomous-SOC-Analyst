"""
Fluent Bit Configuration Service for Multi-Tenancy
Generates and manages per-tenant Fluent Bit configurations
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

try:
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

from config.settings import settings

logger = logging.getLogger("soc-fluent-bit")


class FluentBitService:
    """
    Service for generating and managing per-tenant Fluent Bit configurations.
    Uses Jinja2 templates to render configuration files.
    """

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / "fluent-bit" / "templates"
        self.tenants_path = self.base_path / "fluent-bit" / "tenants"

        # Initialize Jinja2 environment if available
        if JINJA2_AVAILABLE and self.templates_path.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.templates_path)),
                trim_blocks=True,
                lstrip_blocks=True
            )
        else:
            self.jinja_env = None
            if not JINJA2_AVAILABLE:
                logger.warning("Jinja2 not installed. Fluent Bit config generation will use fallback templates.")

    def ensure_tenants_directory(self) -> bool:
        """Ensure the tenants directory exists"""
        try:
            self.tenants_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create tenants directory: {e}")
            return False

    def get_tenant_config_path(self, org_id: str) -> Path:
        """Get the path to a tenant's configuration directory"""
        return self.tenants_path / f"org_{org_id}"

    def generate_tenant_config(
        self,
        org_id: str,
        org_name: str,
        config_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Generate Fluent Bit configuration files for a tenant.

        Args:
            org_id: The organization ID
            org_name: The organization name
            config_options: Optional configuration options to override defaults

        Returns:
            Dictionary mapping filename to rendered content
        """
        options = config_options or {}

        # Default configuration context
        context = {
            "org_id": org_id,
            "org_name": org_name,
            "generated_at": datetime.utcnow().isoformat(),
            "log_source_path": options.get("log_source_path", "/var/log/app/*.log"),
            "elasticsearch_host": options.get("elasticsearch_host", settings.ELASTICSEARCH_HOST.replace("http://", "").split(":")[0]),
            "elasticsearch_port": options.get("elasticsearch_port", 9200),
            "http_port": options.get("http_port", 2020),
            "debug_mode": options.get("debug_mode", False),
            "read_from_head": options.get("read_from_head", "true"),
            "refresh_interval": options.get("refresh_interval", 1),
            "rotate_wait": options.get("rotate_wait", 30),
            "logstash_format": options.get("logstash_format", "On"),
            "tls_enabled": options.get("tls_enabled", False),
            "tls_verify": options.get("tls_verify", "On"),
            "tls_ca_file": options.get("tls_ca_file"),
            "elasticsearch_user": options.get("elasticsearch_user"),
            "elasticsearch_password": options.get("elasticsearch_password"),
            "retry_limit": options.get("retry_limit", "False"),
            "buffer_size": options.get("buffer_size", "5M"),
            "additional_inputs": options.get("additional_inputs", []),
            "additional_outputs": options.get("additional_outputs", []),
            "custom_parsers": options.get("custom_parsers", []),
        }

        configs = {}

        if self.jinja_env:
            # Use Jinja2 templates
            template_files = [
                ("fluent-bit.conf.j2", "fluent-bit.conf"),
                ("inputs.conf.j2", "inputs.conf"),
                ("outputs.conf.j2", "outputs.conf"),
                ("parser.conf.j2", "parser.conf"),
            ]

            for template_name, output_name in template_files:
                try:
                    template = self.jinja_env.get_template(template_name)
                    configs[output_name] = template.render(**context)
                except TemplateNotFound:
                    logger.warning(f"Template not found: {template_name}")
                    configs[output_name] = self._generate_fallback_config(output_name, context)
                except Exception as e:
                    logger.error(f"Error rendering template {template_name}: {e}")
                    configs[output_name] = self._generate_fallback_config(output_name, context)
        else:
            # Use fallback templates
            configs["fluent-bit.conf"] = self._generate_fallback_config("fluent-bit.conf", context)
            configs["inputs.conf"] = self._generate_fallback_config("inputs.conf", context)
            configs["outputs.conf"] = self._generate_fallback_config("outputs.conf", context)
            configs["parser.conf"] = self._generate_fallback_config("parser.conf", context)

        return configs

    def _generate_fallback_config(self, config_name: str, context: Dict[str, Any]) -> str:
        """Generate fallback configuration without Jinja2"""
        org_id = context["org_id"]
        org_name = context["org_name"]

        if config_name == "fluent-bit.conf":
            return f"""# Fluent Bit Configuration for Organization: {org_name}
# Organization ID: {org_id}
# Generated: {context['generated_at']}

[SERVICE]
    Flush        1
    Daemon       off
    Log_Level    info
    Parsers_File parser.conf
    HTTP_Server  On
    HTTP_Listen  0.0.0.0
    HTTP_Port    {context['http_port']}

@INCLUDE inputs.conf
@INCLUDE outputs.conf
"""
        elif config_name == "inputs.conf":
            return f"""# Input Configuration for Organization: {org_name}
[INPUT]
    Name              tail
    Path              {context['log_source_path']}
    Tag               soc.logs.{org_id}
    Parser            json
    Read_from_Head    {context['read_from_head']}
    Refresh_Interval  {context['refresh_interval']}
"""
        elif config_name == "outputs.conf":
            return f"""# Output Configuration for Organization: {org_name}
[OUTPUT]
    Name              es
    Match             soc.logs.{org_id}*
    Host              {context['elasticsearch_host']}
    Port              {context['elasticsearch_port']}
    Index             soc-logs-{org_id}
    Logstash_Format   {context['logstash_format']}
    Logstash_Prefix   soc-logs-{org_id}
    Replace_Dots      On
    Suppress_Type_Name On
    Retry_Limit       {context['retry_limit']}
"""
        elif config_name == "parser.conf":
            return f"""# Parser Configuration for Organization: {org_name}
[PARSER]
    Name        json
    Format      json
    Time_Key    @timestamp
    Time_Format %Y-%m-%dT%H:%M:%S.%LZ
    Time_Keep   On
"""
        return ""

    def save_tenant_config(
        self,
        org_id: str,
        org_name: str,
        config_options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Generate and save Fluent Bit configuration files for a tenant.

        Args:
            org_id: The organization ID
            org_name: The organization name
            config_options: Optional configuration options

        Returns:
            True if successful, False otherwise
        """
        self.ensure_tenants_directory()

        tenant_path = self.get_tenant_config_path(org_id)
        try:
            tenant_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create tenant directory: {e}")
            return False

        configs = self.generate_tenant_config(org_id, org_name, config_options)

        try:
            for filename, content in configs.items():
                file_path = tenant_path / filename
                with open(file_path, 'w') as f:
                    f.write(content)
                logger.info(f"Saved tenant config: {file_path}")

            return True
        except Exception as e:
            logger.error(f"Failed to save tenant configs: {e}")
            return False

    def delete_tenant_config(self, org_id: str) -> bool:
        """
        Delete Fluent Bit configuration files for a tenant.

        Args:
            org_id: The organization ID

        Returns:
            True if successful, False otherwise
        """
        tenant_path = self.get_tenant_config_path(org_id)

        if not tenant_path.exists():
            logger.warning(f"Tenant config path does not exist: {tenant_path}")
            return True

        try:
            import shutil
            shutil.rmtree(tenant_path)
            logger.info(f"Deleted tenant config: {tenant_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete tenant configs: {e}")
            return False

    def get_tenant_config(self, org_id: str) -> Optional[Dict[str, str]]:
        """
        Read existing Fluent Bit configuration for a tenant.

        Args:
            org_id: The organization ID

        Returns:
            Dictionary mapping filename to content, or None if not found
        """
        tenant_path = self.get_tenant_config_path(org_id)

        if not tenant_path.exists():
            return None

        configs = {}
        config_files = ["fluent-bit.conf", "inputs.conf", "outputs.conf", "parser.conf"]

        try:
            for filename in config_files:
                file_path = tenant_path / filename
                if file_path.exists():
                    with open(file_path, 'r') as f:
                        configs[filename] = f.read()
            return configs
        except Exception as e:
            logger.error(f"Failed to read tenant configs: {e}")
            return None

    def list_tenant_configs(self) -> List[str]:
        """
        List all tenant configurations.

        Returns:
            List of organization IDs with configurations
        """
        if not self.tenants_path.exists():
            return []

        org_ids = []
        try:
            for item in self.tenants_path.iterdir():
                if item.is_dir() and item.name.startswith("org_"):
                    org_ids.append(item.name[4:])  # Remove "org_" prefix
            return org_ids
        except Exception as e:
            logger.error(f"Failed to list tenant configs: {e}")
            return []

    def validate_config(self, org_id: str) -> Dict[str, Any]:
        """
        Validate a tenant's Fluent Bit configuration.

        Args:
            org_id: The organization ID

        Returns:
            Validation result dictionary
        """
        configs = self.get_tenant_config(org_id)

        if not configs:
            return {
                "valid": False,
                "errors": ["Configuration not found"],
                "warnings": []
            }

        errors = []
        warnings = []

        # Check for required files
        required_files = ["fluent-bit.conf", "inputs.conf", "outputs.conf", "parser.conf"]
        for filename in required_files:
            if filename not in configs:
                errors.append(f"Missing required file: {filename}")

        # Basic content validation
        if "fluent-bit.conf" in configs:
            content = configs["fluent-bit.conf"]
            if "[SERVICE]" not in content:
                errors.append("fluent-bit.conf missing [SERVICE] section")
            if f"@INCLUDE inputs.conf" not in content:
                warnings.append("fluent-bit.conf may be missing inputs include")
            if f"@INCLUDE outputs.conf" not in content:
                warnings.append("fluent-bit.conf may be missing outputs include")

        if "inputs.conf" in configs:
            content = configs["inputs.conf"]
            if "[INPUT]" not in content:
                errors.append("inputs.conf missing [INPUT] section")
            if org_id not in content:
                warnings.append(f"inputs.conf may not be properly scoped to org {org_id}")

        if "outputs.conf" in configs:
            content = configs["outputs.conf"]
            if "[OUTPUT]" not in content:
                errors.append("outputs.conf missing [OUTPUT] section")
            if f"soc-logs-{org_id}" not in content:
                warnings.append(f"outputs.conf may not target correct index for org {org_id}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


# Singleton instance
fluent_bit_service = FluentBitService()
