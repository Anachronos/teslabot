from irc import IRC
import threading
import Queue
import config
import random

class IRCClient(IRC):
    """IRCClient inherits the IRC core and expands it into a multi-threaded IRC
    client with dynamic plugins.
    
    Plugins share the same IRCClient object and can call *some* public
    methods in a thread safe manner.
    """
    def __init__(self, nick, realname, channels, admin, trigger, plugins,
                  password = False, _ssl = False, reconnect = False):
        IRC.__init__(self, nick, realname, channels, admin, _ssl, reconnect, password)

        self.plugins = plugins
        self.send_lock = threading.Lock()
        self.trigger = trigger
        self._password = password
        
        # Stores the class instance of a plugin inside the key of any
        # event the plugin has chosen to listen for.
        # A plugin will not be able to listen to an event that is not
        # defined in the dictionary.
        self._plugin_callbacks = {
                                  'on_connect': [],
                                  'on_quit': [],
                                  'on_quit': [],
                                  'on_whois': [],
                                  'on_channel_message': [],
                                  'on_chat_command': [],
                                  'on_channel_join': [],
                                  'on_channel_part': [],
                                  'on_private_message': [],
                                  
                                  # Plugin specific events
                                  'on_exit': [],
                                  'on_load': [],
                                  }
        self._plugin_threads = {}
        self._plugin_objects = []
        
        # Constants for command types: CMD_CHANNEL is a channel command,
        # CMD_PRIVATE is a private message command, and CMD_ALL is both
        self.CMD_ALL = 0
        self.CMD_CHANNEL = 1
        self.CMD_PRIVATE = 2
        
    def _import_plugins(self, Reload = False):
        """Imports (or reloads) modules from the list of plugins and returns a 
        list of plugin (class) objects."""
        if Reload:
            self._plugin_objects = []
        elif len(self._plugin_objects) > 0:
            return self._plugin_objects
            
        for plugin in self.plugins:
            module = 'plugins.{0}.{0}'.format(plugin.lower())
            try:
                module_obj = __import__(module, fromlist=[plugin.lower()])
            except ImportError as e:
                self.logger.warning(e)
                continue
            
            if Reload:
                reload(module_obj)
                
            class_obj = getattr(module_obj, plugin)
            self._plugin_objects.append(class_obj())
        
        return self._plugin_objects

    def load_plugins(self, Reload = False):
        """
        Creates an instance of each plugin and loads it into the _plugin_callbacks
        dictionary.
        
        A plugin's class object is appended to the list of an event (on_connect, etc.)
        if the plugin has chosen to listen for that specific event. The class object
        is essentially a callback for _on_event().
        """
        plugins = self._import_plugins(Reload)
        
        for p in plugins:            
            self.logger.debug('Loaded plugin [{0}].'.format(p.name))
            
            for event in p._callbacks:
                try:
                    self._plugin_callbacks[event].append(p)
                except KeyError:
                    self.logger.warning('Callback [{0}] for plugin [{1}] cannot be loaded.' \
                                       ' Event doesn\'t exist.'.format(event, p.name))
                    
            if Reload:
                # Terminate any existing plugin threads
                try:
                    if self._plugin_threads[p.name]:
                        t, q = self._plugin_threads[p.name]
                        alive = t.is_alive()
                        
                        if alive:
                            q.put(['on_exit', ''])
                        
                        del self._plugin_threads[p.name]
                except KeyError:
                    pass
        self._on_event('on_load', [])
        
    def reload_plugins(self):
        """Reloads every plugin. In the process, it will load any new plugin added to the config
        file, and it will also unload any plugin that was removed in the config file."""
        # Reset the list of callbacks
        for key, value in self._plugin_callbacks.items():
            self._plugin_callbacks[key] = []
        c = config.Config()
        self.plugins = c.read_plugins()
        self.load_plugins(Reload=True)
        
    def _plugin_has_command(self, cmd, type, plugin):
        """Returns true if the plugin has a command for the given type."""
        for pcmd, ptype in plugin.chat_commands:
            if cmd == pcmd and (ptype == self.CMD_ALL or type == ptype):
                return True
        return False

    def _on_event(self, event, args):
        """
        Calls every plugin that is listening to the given event and feeds them
        the appropriate arguments.
        
        For a given event, it will extract the plugin's callback (the class object)
        and execute its run() in a new thread if the plugin isn't already active. The 
        event and its corresponding arguments are fed sent to the plugin's thread 
        via a Queue. 
        """
        for plugin in self._plugin_callbacks[event]:
            name, callback = plugin.name, plugin.run
            
            # We create an exception for on_channel_command event to prevent every thread that
            # listens to a command event from being called. We only want to call the plugin
            # that has this command.
            if event == 'on_chat_command':
                has_cmd = self._plugin_has_command(args[2], args[4], plugin)
                
                if not has_cmd:
                    continue

            # Check if the plugin thread has already been initialized and alive
            try:
                if self._plugin_threads[name]:
                    t, q = self._plugin_threads[name]
                    alive = t.is_alive()
                    
                    if alive:
                        # Communicate with the plugin thread
                        q.put([event, args[:4]])
                        self.logger.debug('New message for [{0}] triggered by [{1}].'.format(name, event))
                    else:
                        raise KeyError
            # If both conditions are false, create a new thread and run it
            except KeyError:
                self.logger.debug('New thread for [{0}] triggered by [{1}].'.format(name, event))
                
                q = Queue.Queue()
                thread = threading.Thread(target=callback, args=(q, self))
                thread.daemon = True
                thread.start()
                self._plugin_threads[name] = [thread, q]
                
                # Communicate with the plugin thread
                q.put([event, args[:4]])

    def send(self, msg):
        """Sends a message to the IRC server."""
        self.send_lock.acquire()
        IRC.send(self, msg)
        self.send_lock.release()
        
    def on_connect(self):
        IRC.on_connect(self)
        self._on_event('on_connect', [])
    
    def on_quit(self):
        raise NotImplementedError
    
    def on_chat_command(self, src, dst, msg):
        """Handles chat command event."""
        args = ''
        if len(msg.split(' ', 1)) > 1:
            cmd, args = msg.split(' ', 1)
        else:
            cmd = msg.split(' ', 1)[0]
            
        if dst[0] == '#':
            type = self.CMD_CHANNEL
        else:
            type = self.CMD_PRIVATE
        
        self._on_event('on_chat_command', [src, dst, cmd[1:], args, type])

    def on_channel_message(self, user, channel, msg):
        self.logger.info('[{0}] <{1}> {2}'.format(channel, user.nick, msg))
        
        if msg[:1] == self.trigger:
            self.on_chat_command(user, channel, msg)
        else:
            self._on_event('on_channel_message', [user, channel, msg])

    def on_whois(self, whois):
        pass

    def on_channel_mode(self, user, channel, modes, args = None):
        self.logger.info('[{0}] {1} sets mode: {2} {3}'.format(channel, user, modes, args))

    def on_channel_join(self, user, channel):
        IRC.on_channel_join(self, user, channel)
        self.logger.info('[{0}] {1} has joined the channel.'.format(channel.name, user.nick))
        # Temporarily pass channel.name until we finish the whole Channel/User object transition
        self._on_event('on_channel_join', [user, channel])

    def on_channel_part(self, user, channel, reason = None):
        IRC.on_channel_part(self, user, channel, reason)
        self.logger.info('[{0}] {1} has left the channel.'.format(channel.name, user.nick, reason))
        self._on_event('on_channel_part', [user, channel, reason])

    def on_channel_topic(self, user, channel, topic):
        print channel.topic
        #log_msg = '[{0}] {1} changes the channel topic to: {2}'
        #self.logger.info(log_msg.format(channel, user.nick, topic))

    def on_channel_invite(self, user, channel):
        raise NotImplementedError

    def on_channel_kick(self):
        raise NotImplementedError

    def on_channel_quit(self):
        raise NotImplementedError

    def on_private_message(self, user, msg):
        if msg[:1] == self.trigger:
            self.on_chat_command(user, user.nick, msg)

    def on_private_notice(self):
        raise NotImplementedError
    
    def on_nickinuse(self):
        self.nick = self.nick + str(random.randint(0, 10))
        
    def on_exit(self):
        """on_exit is called before the bot is shut down. Plugins should listen to this
        event if they need to do any checks or clean ups before the bot exits.
        
        The event itself is also called when the bot reloads the plugins, though not this method."""
        pass
