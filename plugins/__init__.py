"""
Plugin system — Load and manage plugins from the plugins/ directory.
Plugins are subdirectories with a plugin.json manifest.
"""
import os
import json
import importlib
import logging

logger = logging.getLogger(__name__)

_plugins = {}  # slug -> {manifest, module, enabled}
_hooks = {}    # hook_name -> [modules]


def load_all(settings_getter=None):
    """Scan plugins/ directory and load enabled plugins.
    
    Args:
        settings_getter: Optional function to check if plugin is enabled.
                        Called as settings_getter(f"plugin_{slug}_enabled", False)
    """
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    loaded = 0
    
    for name in sorted(os.listdir(plugin_dir)):
        manifest_path = os.path.join(plugin_dir, name, "plugin.json")
        if not os.path.exists(manifest_path):
            continue
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Plugin {name}: invalid manifest — {e}")
            continue

        slug = manifest.get('slug', name)
        
        # Check if enabled
        enabled = True
        if settings_getter:
            try:
                enabled = bool(settings_getter(f"plugin_{slug}_enabled", False))
            except Exception:
                enabled = False

        _plugins[slug] = {
            'manifest': manifest,
            'module': None,
            'enabled': enabled,
            'dir': os.path.join(plugin_dir, name),
        }

        if enabled:
            try:
                module = importlib.import_module(f"plugins.{name}")
                _plugins[slug]['module'] = module
                # Register hooks
                for hook in manifest.get('hooks', []):
                    _hooks.setdefault(hook, []).append(module)
                loaded += 1
                logger.info(f"Plugin loaded: {manifest.get('name', slug)} v{manifest.get('version', '?')}")
            except Exception as e:
                logger.error(f"Plugin {slug} load error: {e}")
                _plugins[slug]['enabled'] = False

    logger.info(f"Plugins: {loaded} loaded, {len(_plugins)} discovered")


def trigger_hook(hook_name, **kwargs):
    """Trigger a hook across all plugins that listen to it."""
    results = []
    for module in _hooks.get(hook_name, []):
        handler_name = f"on_{hook_name.replace('.', '_')}"
        handler = getattr(module, handler_name, None)
        if handler:
            try:
                result = handler(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook {hook_name} error in {module.__name__}: {e}")
    return results


def list_plugins():
    """Return dict of all discovered plugins."""
    return _plugins


def get_plugin(slug):
    """Get plugin info by slug."""
    return _plugins.get(slug)


def get_plugin_categories():
    """Get unique categories."""
    return list(set(
        p['manifest'].get('category', 'other')
        for p in _plugins.values()
    ))


def enable_plugin(slug):
    """Enable a plugin (requires reload)."""
    if slug in _plugins:
        _plugins[slug]['enabled'] = True


def disable_plugin(slug):
    """Disable a plugin."""
    if slug in _plugins:
        _plugins[slug]['enabled'] = False
        _plugins[slug]['module'] = None
