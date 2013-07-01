from pluginbase import PluginBase
import logging

class CoreCommands(PluginBase):
    """Provides basic commands."""
    def __init__(self):
        PluginBase.__init__(self)
        
        self.name = 'CoreCommands'
        self.logger = logging.getLogger('teslabot.plugin.corecommands')
        
        self.set_cmd('kick', self.CMD_CHANNEL)
        self.set_cmd('kickban', self.CMD_CHANNEL)
        self.set_cmd('ban', self.CMD_CHANNEL)
        self.set_cmd('unban', self.CMD_CHANNEL)
        self.admin_commands = ['reload', 'say', 'action', 'join', 'leave', 'quit', 'nick', 'plugins']
        
        self.lang_001 = 'Plugins: {0}'
        self.lang_002 = 'Type \x0310{0}commands\x03 for a list of available commands. Type \x0310{0}(command) help\x03 ' \
                        'to view the help text of a specific command. Note that the parentheses should not be included.'
        self.lang_003 = 'Goodbye.'
        
        self.users = {}
        
    def command_plugins(self, user, dst, args):
        if user.admin:
            self.irch.notice(self.lang_001.format(', '.join([p.name for p in self.irch._import_plugins()])), user.nick)
        else:
            raise self.InvalidPermission

    def command_help(self, user, dst, args):
        self.irch.notice(self.lang_002.format(self.irch.trigger), user.nick)

    def command_commands(self, user, dst, args):
        """Displays a list of commands available through this medium."""
        pobjects = self.irch._import_plugins()
        cmds = []
        for p in pobjects:
            for cmd, ctype in p.chat_commands:
                if cmd in p.admin_commands and user.admin:
                    continue
                cmds.append(cmd)
        cmds = ', '.join(cmds)
        
        self.irch.notice('Commands: {0}'.format(cmds), user.nick)

    def command_reload(self, user, dst, args):
        """Reloads the plugin system. Requires admin privileges."""
        if user.admin:
            self.irch.reload_plugins()
            self.irch.say('Plugins reloaded.', dst)
        else:
            raise self.InvalidPermission

    def command_say(self, user, dst, args):
        """Syntax: {0}say <destination> <message>"""
        if user.admin:
            try:
                dst, msg = args.split(' ', 1)
                self.irch.say(msg, dst)
            except ValueError:
                raise self.InvalidSyntax
        else:
            raise self.InvalidPermission
            
    def command_action(self, user, dst, args):
        """Syntax: {0}action <destination> <message>"""
        if user.admin:
            if args and len(args.split()) >  2:
                dst, msg = args.split(' ', 1)
                self.irch.action(msg, dst)
            else:
                raise self.InvalidSyntax
        else:
            raise self.InvalidPermission

    def command_join(self, user, dst, args):
        """Syntax: {0}join <channel>"""
        if user.admin:
            if args:
                self.irch.join(args.split(' ', 1)[0])
            else:
                raise self.InvalidSyntax
        else:
            raise self.InvalidPermission
                
    def command_leave(self, user, dst, args):
        """Syntax: {0}leave <channel> [reason]"""
        if user.admin:
            arg_len = len(args.split())
            if arg_len < 1:
                raise self.InvalidSyntax
            else:
                if arg_len > 1:
                    chan, reason = args.split()
                else:
                    chan = args
                    reason = self.lang_003
                self.irch.leave(chan, reason)
        else:
            raise self.InvalidPermission

    def command_quit(self, user, dst, args):
        """Shuts down the bot. Requires admin privileges."""
        if user.admin:
            if args:
                reason = args
            else:
                reason = self.lang_003
            self.irch.quit(reason)
        else:
            raise self.InvalidPermission

    def command_nick(self, user, dst, args):
        """Changes the bot's user. Requires admin privileges."""
        if user.admin:
            if args and len(args.split()) > 1:
                raise self.InvalidSyntax
            self.irch.nick = args
            
    def command_ban(self, user, dst, args):
        """Syntax: {0}ban <user>"""
        if user.modes.is_owner(dst) or user.admin:
            if self.irch.channels[dst].is_oper(user):
                self.irch.mode(dst, '+b', args)
        else:
            raise self.InvalidPermission
        
    def command_unban(self, user, dst, args):
        """Syntax: {0}unban <user>"""
        if user.modes.is_owner(dst) or user.admin:
            if self.irch.channels[dst].is_oper(user):
                self.irch.mode(dst, '-b', args)
        else:
            raise self.InvalidPermission
                
    def command_kick(self, user, dst, args):
        """Kicks a given user.
        Syntax: {0}kick <user> <reason>"""
        if user.modes.is_owner(dst) or user.admin:
                num = len(args.split())
                if num > 1:
                    nick, reason = args.split(' ', 1)
                elif num == 1:
                    nick = args
                    reason = ''
                else:
                    raise self.InvalidSyntax
                
                self.irch.kick(nick, dst, reason)
        else:
            raise self.InvalidPermission
                
    def command_kickban(self, user, dst, args):
        """Kicks and bans a given user.
        Syntax: {0}kickban <user> [reason] [duration]"""
        if user.modes.is_owner(dst) or user.admin:
            num = len(args.split())
            if num > 1:
                nick, reason = args.split(' ', 1)
            elif num == 1:
                nick = args
                reason = ''
            else:
                raise self.InvalidSyntax
            
            self.irch.mode(dst, '+b', nick)
            self.irch.kick(nick, dst, reason)
        else:
            raise self.InvalidPermission
            
    def command_deop(self, user, dst, args):
        if user.modes.is_owner(dst) or user.admin:
            num = len(args.split())
            if num == 1:
                nick = args
            else:
                raise self.InvalidSyntax
            
            self.irch.mode(dst, '-o', nick)
        else:
            raise self.InvalidPermission
        
    def command_op(self, user, dst, args):
        if user.modes.is_owner(dst) or user.admin:
            num = len(args.split())
            if num == 1:
                nick = args
            else:
                raise self.InvalidSyntax
            
            self.irch.mode(dst, '+o', nick)
        else:
            raise self.InvalidPermission