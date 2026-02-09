"""Tests for configuration loading and validation.

This module tests:
- Config file loading
- Config structure validation
- Default values
- Required fields
- Config type checking
"""

import pytest
import os
import tempfile
import yaml
from odta.models.config import (
    load_config,
    AppConfig,
    LLMConfig,
    DatabaseConfig,
    BrokerConfig,
    GuardrailsConfig
)


class TestConfigLoading:
    """Test configuration file loading."""

    def test_load_config_from_default_path(self):
        """Should load config from default config.yaml."""
        config = load_config()

        assert isinstance(config, AppConfig)
        assert config is not None

    def test_config_has_llm_section(self):
        """Config should have LLM configuration."""
        config = load_config()

        assert hasattr(config, 'llm')
        assert isinstance(config.llm, LLMConfig)

    def test_config_has_database_section(self):
        """Config should have database configuration."""
        config = load_config()

        assert hasattr(config, 'database')
        assert isinstance(config.database, DatabaseConfig)

    def test_config_has_broker_section(self):
        """Config should have broker configuration."""
        config = load_config()

        assert hasattr(config, 'broker')
        assert isinstance(config.broker, BrokerConfig)

    def test_config_has_guardrails_section(self):
        """Config should have guardrails configuration."""
        config = load_config()

        assert hasattr(config, 'guardrails')
        assert isinstance(config.guardrails, GuardrailsConfig)

    def test_config_has_mode(self):
        """Config should have trading mode."""
        config = load_config()

        assert hasattr(config, 'mode')
        assert config.mode in ["paper", "live"]


class TestLLMConfig:
    """Test LLM configuration."""

    def test_llm_config_has_model(self):
        """LLM config should have model field."""
        config = load_config()

        assert hasattr(config.llm, 'model')
        assert isinstance(config.llm.model, str)
        assert len(config.llm.model) > 0

    def test_llm_config_model_value(self):
        """Model should be a valid LLM identifier."""
        config = load_config()

        # Should be a non-empty string
        assert config.llm.model
        assert isinstance(config.llm.model, str)


class TestDatabaseConfig:
    """Test database configuration."""

    def test_database_config_has_path(self):
        """Database config should have path field."""
        config = load_config()

        assert hasattr(config.database, 'path')
        assert isinstance(config.database.path, str)

    def test_database_path_not_empty(self):
        """Database path should not be empty."""
        config = load_config()

        assert len(config.database.path) > 0

    def test_database_path_ends_with_duckdb(self):
        """Database path should end with .duckdb."""
        config = load_config()

        assert config.database.path.endswith('.duckdb')

    def test_database_config_defaults(self):
        """Database config should have default value."""
        db_config = DatabaseConfig()

        assert db_config.path
        assert '.duckdb' in db_config.path


class TestBrokerConfig:
    """Test broker configuration."""

    def test_broker_config_has_mcp_server_path(self):
        """Broker config should have MCP server path."""
        config = load_config()

        assert hasattr(config.broker, 'mcp_server_path')
        assert isinstance(config.broker.mcp_server_path, str)

    def test_broker_mcp_server_path_not_empty(self):
        """MCP server path should not be empty."""
        config = load_config()

        assert len(config.broker.mcp_server_path) > 0

    def test_broker_config_defaults(self):
        """Broker config should have default value."""
        broker_config = BrokerConfig()

        assert broker_config.mcp_server_path
        assert 'angel-one-mcp-server' in broker_config.mcp_server_path


class TestGuardrailsConfig:
    """Test guardrails configuration."""

    def test_guardrails_has_max_daily_loss(self):
        """Guardrails should have max daily loss limit."""
        config = load_config()

        assert hasattr(config.guardrails, 'max_daily_loss')
        assert isinstance(config.guardrails.max_daily_loss, int)
        assert config.guardrails.max_daily_loss > 0

    def test_guardrails_has_max_open_positions(self):
        """Guardrails should have max open positions limit."""
        config = load_config()

        assert hasattr(config.guardrails, 'max_open_positions')
        assert isinstance(config.guardrails.max_open_positions, int)
        assert config.guardrails.max_open_positions > 0

    def test_guardrails_has_square_off_time(self):
        """Guardrails should have square off time."""
        config = load_config()

        assert hasattr(config.guardrails, 'square_off_time')
        assert isinstance(config.guardrails.square_off_time, str)
        # Should be in HH:MM format
        assert ':' in config.guardrails.square_off_time

    def test_guardrails_has_pre_market_start(self):
        """Guardrails should have pre-market start time."""
        config = load_config()

        assert hasattr(config.guardrails, 'pre_market_start')
        assert isinstance(config.guardrails.pre_market_start, str)
        assert ':' in config.guardrails.pre_market_start

    def test_guardrails_time_format(self):
        """Time fields should be in HH:MM format."""
        config = load_config()

        square_off = config.guardrails.square_off_time
        pre_market = config.guardrails.pre_market_start

        # Basic format check
        assert len(square_off.split(':')) == 2
        assert len(pre_market.split(':')) == 2

        # Hours and minutes should be numeric
        sq_hour, sq_min = square_off.split(':')
        pm_hour, pm_min = pre_market.split(':')

        assert sq_hour.isdigit() and sq_min.isdigit()
        assert pm_hour.isdigit() and pm_min.isdigit()

    def test_guardrails_defaults(self):
        """Guardrails should have sensible defaults."""
        guardrails = GuardrailsConfig()

        assert guardrails.max_daily_loss == 5000
        assert guardrails.max_open_positions == 2
        assert guardrails.square_off_time == "15:00"
        assert guardrails.pre_market_start == "08:45"


class TestConfigValidation:
    """Test configuration validation."""

    def test_config_with_custom_yaml(self):
        """Should load config from custom YAML file."""
        # Create a temporary config file
        config_data = {
            'llm': {'model': 'test-model'},
            'database': {'path': '/tmp/test.duckdb'},
            'broker': {'mcp_server_path': './test-server'},
            'guardrails': {
                'max_daily_loss': 3000,
                'max_open_positions': 1,
                'square_off_time': '14:30',
                'pre_market_start': '09:00'
            },
            'mode': 'paper'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_config(path=temp_path)

            assert config.llm.model == 'test-model'
            assert config.database.path == '/tmp/test.duckdb'
            assert config.guardrails.max_daily_loss == 3000
            assert config.mode == 'paper'

        finally:
            os.unlink(temp_path)

    def test_config_mode_values(self):
        """Config mode should be paper or live."""
        config = load_config()

        assert config.mode in ['paper', 'live']

    def test_config_guardrails_reasonable_values(self):
        """Guardrails should have reasonable values."""
        config = load_config()

        # Max daily loss should be reasonable
        assert 1000 <= config.guardrails.max_daily_loss <= 50000

        # Max open positions should be reasonable
        assert 1 <= config.guardrails.max_open_positions <= 10

    def test_config_missing_llm_model_raises_error(self):
        """Config without LLM model should raise error."""
        config_data = {
            'database': {'path': '/tmp/test.duckdb'},
            'mode': 'paper'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(Exception):
                load_config(path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_config_partial_guardrails_uses_defaults(self):
        """Partial guardrails should use defaults for missing values."""
        config_data = {
            'llm': {'model': 'test-model'},
            'guardrails': {
                'max_daily_loss': 7000
                # Other fields should use defaults
            },
            'mode': 'paper'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_config(path=temp_path)

            assert config.guardrails.max_daily_loss == 7000
            # Should use defaults for other fields
            assert config.guardrails.max_open_positions == 2
            assert config.guardrails.square_off_time == "15:00"

        finally:
            os.unlink(temp_path)


class TestConfigIntegration:
    """Test configuration integration with system."""

    def test_config_accessible_from_modules(self):
        """Config should be accessible from odta modules."""
        from odta.models.config import load_config

        config = load_config()
        assert config is not None

    def test_database_path_from_config(self):
        """Database connection should use config path."""
        from odta.models.config import load_config
        from odta.db.connection import get_db_connection

        config = load_config()
        conn = get_db_connection(config.database.path)

        assert conn is not None

    def test_config_reloadable(self):
        """Should be able to reload config multiple times."""
        config1 = load_config()
        config2 = load_config()

        # Both should be valid configs
        assert config1.llm.model == config2.llm.model
        assert config1.mode == config2.mode
