# Teslabot - YA Python IRC Bot #

About
-----
Teslabot is a modular, event-based IRC bot for Python 2.7 that can be extended with plugins.

Dependencies
---------------
Teslabot's core functionality does not depend on any third party modules. However, some of its plugins require the following third-party modules:

* requests
* BeautifulSoup4

Highlights
---------------
* IRC fantasy commands
* Plugins
* SSL support
* Automatic reconnection
* Reloadable plugins

License
---------------
Teslabot is released under the MIT License.

Installation
---------------
*teslabot.cfg* should be filled with the appropriate connection details. Afterwards, Teslabot can be started by running *run.py*.

Programming Notes
---------------
Teslabot derives its functionality from an IRC client class, which is further abstracted by a child class that implements support for plugins. 

Teslabot maintains a socket connection with an IRC server. It translates every server message into an event to be handled. Plugins listening to these events are called and executed in a separate thread.

### Plugins ###
Plugins are modules that provide most of the bot's functionality to users. They are derived from a base class template that provides the essential components of a plugin.

Plugins run in their own separate thread. They are called when an event occurs. Individual plugins can choose to run continuosly on a single thread and wait for input, or spawn new threads in the event of a command, *provided that there isn't more than one thread running for each plugin*. By default, plugins run in a single thread.

Plugin methods can be hooked so that they are called every x amount of seconds by a plugin's thread.

## Commands ##
Teslabot supports automatically defining commands by calling any function whose name matches a command (i.e. command_kick).

There is no advanced permissions system. For now, you can only define which commands are accessible by admins or/and by normal users.

### Recommendations for plugin design ###
You should derive your plugin from the PluginBase class. You should also use the standard logging module for monitoring and debugging. When using the logging module, use setLogger('teslabot.plugin.your_plugin'). Implement on_exit() if your plugin needs to clean up before shutdown.

Implement on_load() if your run plugin needs to run as soon as the bot is connected.