import os
import shutil
from mock import Mock, patch, ANY
from nose.tools import assert_raises, assert_equal

from zabby.tests import assert_is_instance
from zabby.core.utils import write_to_file
from zabby.core.six import string_types, integer_types
from zabby.config_manager import ConfigManager, ModuleLoader
from zabby.core.exceptions import ConfigurationError

CONFIG_DIR = '/tmp/zabby'
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.py')

ITEMS_DIR = os.path.join(CONFIG_DIR, 'items')

OVERRIDDEN_KEY = 'override_me'
ITEM_MODULES_COUNT = 2


class TestConfigManager():
    def setup(self):
        self.config_module = Mock()
        self.config_module.listen_host = '0.0.0.0'
        self.config_module.listen_port = 10052
        self.config_module.item_files = list()

        self._patcher = patch('logging.config')
        self.mock_logging_conf = self._patcher.start()

        self.config_module.logging_conf = os.path.join(CONFIG_DIR,
                                                       'logging.conf')

        self.modules = {CONFIG_PATH: self.config_module}

        for i in range(ITEM_MODULES_COUNT):
            item_module = Mock()
            item_module.items = {str(i): lambda: i, OVERRIDDEN_KEY: lambda: i}

            item_module_path = os.path.join(ITEMS_DIR, "{0}.py".format(i))
            self.config_module.item_files.append(item_module_path)
            self.modules[item_module_path] = item_module

        def return_module(module_path):
            return self.modules[module_path]

        self.config_loader = Mock()
        self.config_loader.load.side_effect = return_module
        self.config_manager = ConfigManager(CONFIG_PATH, self.config_loader)

    def teardown(self):
        self._patcher.stop()

    def test_update_config_loads_config_file(self):
        self.config_manager.update_config()
        self.config_loader.load.assert_any_call(CONFIG_PATH)

    def test_throws_exception_if_config_does_not_contain_attribute(self):
        self.config_loader.load.side_effect = None
        self.config_loader.load.return_value = Mock(spec=[])
        assert_raises(ConfigurationError, self.config_manager.update_config)

    def test_throws_exception_if_attribute_is_of_wrong_type(self):
        self.config_module.listen_host = 0
        assert_raises(ConfigurationError, self.config_manager.update_config)

    def test_contains_listen_address(self):
        self.config_manager.update_config()

        host, port = self.config_manager.listen_address
        assert_is_instance(host, string_types)
        assert_is_instance(port, integer_types)

    def test_loads_items_from_item_files(self):
        self.config_manager.update_config()

        for module_path, module in self.modules.items():
            if module_path == CONFIG_PATH:
                continue

            self.config_loader.load.assert_any_call(module_path)
            for item_key, item_value in module.items.items():
                if item_key == OVERRIDDEN_KEY:
                    continue
                assert_equal(self.config_manager.items[item_key], item_value)

    def test_overrides_item_definitions(self):
        self.config_manager.update_config()
        assert_equal(ITEM_MODULES_COUNT - 1,
                     self.config_manager.items[OVERRIDDEN_KEY]())

    def test_configures_logging(self):
        self.config_manager.update_config()
        self.mock_logging_conf.fileConfig.assert_called_once_with(
            ANY, disable_existing_loggers=False)


class TestModuleLoader():
    def setup(self):
        if os.path.exists(CONFIG_DIR):
            shutil.rmtree(CONFIG_DIR)
        os.mkdir(CONFIG_DIR)

        self.module_loader = ModuleLoader()

    def test_load_nonexistent_path(self):
        assert_raises(IOError, self.module_loader.load, CONFIG_PATH)

    def test_load_module_with_syntax_errors(self):
        write_to_file(CONFIG_PATH, 'a b c')
        assert_raises(SyntaxError, self.module_loader.load, CONFIG_PATH)

    def test_load_module_with_name_errors(self):
        write_to_file(CONFIG_PATH, 'a')
        assert_raises(NameError, self.module_loader.load, CONFIG_PATH)

    def test_load_module_with_type_errors(self):
        write_to_file(CONFIG_PATH, 'a = 1; a()')
        assert_raises(TypeError, self.module_loader.load, CONFIG_PATH)

    def test_load_module_with_value_errors(self):
        write_to_file(CONFIG_PATH, 'a,b = [1, 2, 3]')
        assert_raises(ValueError, self.module_loader.load, CONFIG_PATH)

    def test_load_working_module(self):
        write_to_file(CONFIG_PATH, 'a = 1')
        module = self.module_loader.load(CONFIG_PATH)
        assert_equal(1, module.a)
