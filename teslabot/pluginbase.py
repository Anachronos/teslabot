import sys
import Queue
import logging

class PluginBase:
    """Base class for a plugin.
    
    By default, it runs as a single thread and communicates via Queue. The Queue times out
    every self._qtimeout and calls any hooked function. 
    
    Attributes:
        name: The name of the plugin.
        irch: The IRC client object
    """
    def __init__(self):
        self.name = 'PluginBase'
        self.logger = logging.getLogger('teslabot.pluginbase')
        self.irch = None
        self.alive = True
        
        self._callbacks = []
        self.chat_commands = []
        
        self.INV_ARGS = 'Invalid arguments.'
        self.INV_SYNTAX = 'Invalid syntax.'
        self.INV_PERMS = 'Invalid permission.'
        
        self.PERM_USER = 0
        self.PERM_ADMIN = 1
        
        # The message type (or source) that a given command will only accept.
        self.CMD_ALL = 0
        self.CMD_CHANNEL = 1
        self.CMD_PRIVATE = 2
        
        self._commands_permissions = {}
        
        # Build callbacks from defined class methods
        self._build_callbacks()
        # Build commands from defined class methods
        self._build_commands()
        self.admin_commands = []
        
        self._hooks = []
        self._qtimeout = 5
        self._qcount = 0
        
    class InvalidSyntax(Exception):
        pass
    
    class InvalidArguments(Exception):
        pass
    
    class InvalidPermission(Exception):
        pass
        
    def get_permission(self, cmd):
        return self._commands_permissions[cmd]
        
    def _build_callbacks(self):
        for name in dir(self):
            if name[:3] == 'on_':
                self._callbacks.append(name)
                
    def _build_commands(self):
        """By default, commands are accessible from channel and private messages (CMD_ALL)."""
        for method in dir(self):
            if method[:8] == 'command_':
                self.chat_commands.append([method[8:], self.CMD_ALL])
                
    def set_cmd(self, method, ctype):
        """Sets the command type of a given command.
        Args:
            method: A command method's string name
            ctype: A command's type (either CMD_ALL, CMD_CHANNEL, or CMD_PRIVATE) 
        """
        for n, i in enumerate(self.chat_commands):
            if i[0] == method:
                self.chat_commands[n] = [method, ctype]
                
    def run(self, q, irc):
        """Listens for events and executes the appropriate callback.
        
        It is called once when the plugin's thread is not active and/or an
        event that the plugin listens to is called.
        """
        self.irch = irc
        while self.alive:
            try:
                event, args = q.get(True, self._qtimeout)
                
                callback = getattr(self, event)
                callback(*args)
            except self.InvalidSyntax:
                self.irch.notice(self.INV_SYNTAX, args[0].nick)
            except PluginBase.InvalidArguments:
                self.irch.notice(self.INV_ARGS, args[0].nick)
            except PluginBase.InvalidPermission:
                self.irch.notice(self.INV_PERMS, args[0].nick)
            except Queue.Empty:
                self.call_hooks()
                
    def hook(self, method, interval):
        """Adds a callback that will be called every (multiple * timeout), where timeout 
        is run()'s Queue.get() timeout in seconds. (Queue timeouts every 5 seconds by default.)"""
        self._hooks.append([method, interval])
        
    def unhook(self, method):
        """Removes a given callback from the hook list."""
        for h in self._hooks:
            if h == method:
                self._hooks.remove(h)
        
    def call_hooks(self):
        """Calls a hooked function every (_qtimeout * multiple seconds), where _qtimeout are
        the seconds for Queue.get() to timeout."""
        self._qcount += 1
            
        for h in self._hooks:
            if self._qcount % h[1] == 0:
                h[0]()
        
    def on_exit(self):
        """Cleanly terminate the plugin's execution."""
        self.alive = True
        sys.exit()
        
    def on_chat_command(self, user, dst, cmd, args):
        """Calls the appropriate command and displays docstring when help is requested.
        
        Every argument, except for type, is passed unchanged to the appropriate callback.
        
        Args:
            user: A User class object.
            dst: The name of the channel or user where the command originated.
            cmd: The command's name
            args: The command's arguments
        """
        method = 'command_{0}'.format(cmd)
        callback = getattr(self, method)
        
        if args and args.split()[-1] == 'help':
            if len(args.split()) == 2:
                subcmd = args.split()[0]
                method = 'subcommand_{0}_{1}'.format(cmd, subcmd)
                callback = getattr(self, method)
            
            if callback.__doc__:
                docstr = (callback.__doc__.format(self.irch.trigger)).split('\n')
                docstr = [x.lstrip() for x in docstr]
            else:
                docstr = ''

            if docstr:
                self.irch.notice(docstr, user.nick)
            else:
                self.irch.notice('No documentation available.', user.nick)
        else:
            callback(user, dst, args)