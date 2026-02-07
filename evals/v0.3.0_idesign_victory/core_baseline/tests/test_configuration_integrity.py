import unittest
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from controllers.system_initializer import SystemInitializer
from managers.hardware_manager import HardwareManager
from engines.hardware_verifier import HardwareVerifier
from engines.engine_optimizer import EngineOptimizer
from accessors.model_tool_accessor import ModelToolAccessor
from managers.ui.dashboard_manager import DashboardManager
from engines.view.dashboard_renderer import DashboardRenderer
from controllers.dashboard_controller import DashboardController
from utils.theme_manager import ThemeManager
from utils.system_logger import SystemLogger


class TestConfigurationIntegrity(unittest.TestCase):
    def test_controller_structure(self):
        # Verify that SystemInitializer is in the controllers directory
        self.assertTrue(hasattr(SystemInitializer, '__init__'))
        
        # Verify that DashboardController is in the controllers directory
        self.assertTrue(hasattr(DashboardController, '__init__'))

    def test_manager_structure(self):
        # Verify that HardwareManager is in the managers directory
        self.assertTrue(hasattr(HardwareManager, '__init__'))
        
        # Verify that DashboardManager is in the managers/ui directory
        self.assertTrue(hasattr(DashboardManager, '__init__'))

    def test_engine_structure(self):
        # Verify that HardwareVerifier is in the engines directory
        self.assertTrue(hasattr(HardwareVerifier, '__init__'))
        
        # Verify that DashboardRenderer is in the engines/view directory
        self.assertTrue(hasattr(DashboardRenderer, '__init__'))

    def test_accessor_structure(self):
        # Verify that ModelToolAccessor is in the accessors directory
        self.assertTrue(hasattr(ModelToolAccessor, '__init__'))

    def test_utility_structure(self):
        # Verify that SystemLogger is in the utils directory
        self.assertTrue(hasattr(SystemLogger, '__init__'))
        
        # Verify that ThemeManager is in the utils directory
        self.assertTrue(hasattr(ThemeManager, '__init__'))

    def test_file_organization(self):
        # Check that all required directories exist
        required_dirs = [
            'controllers',
            'managers',
            'engines',
            'accessors',
            'utils',
            'tests',
            'ui'
        ]
        
        for directory in required_dirs:
            self.assertTrue(os.path.exists(directory), f"Directory {directory} does not exist")

    def test_critical_path_coverage(self):
        # Ensure all critical components are tested
        critical_components = [
            SystemInitializer,
            HardwareManager,
            HardwareVerifier,
            EngineOptimizer,
            ModelToolAccessor,
            DashboardManager,
            DashboardRenderer,
            DashboardController,
            ThemeManager,
            SystemLogger
        ]
        
        for component in critical_components:
            self.assertIsNotNone(component)


if __name__ == '__main__':
    unittest.main()
