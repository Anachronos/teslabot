from user import User
import logging
from ircconstants import *

class Channel(object):
    """
    Attributes:
        name: A string of the channel's name
        topic: A string of the channel's topic
        
        _users: A list of a list of User class and its respective channel flag.
        _modes: A list of channel modes
    """
    def __init__(self, name):
        self.name = name
        self.topic = ''
        self._users = []
        self._modes = []
        
        self._i = 0
        self._size = 0
        
    def count(self):
        """Returns the size of _users list."""
        return len(self._users)
    
    def add(self, user, flag = None):
        self._users.append([user, flag])
        self._size += 1
        
    def __iter__(self):
        return self
    
    def next(self):
        if self._i < self._size:
            self._i += 1
            return self._users[self._i - 1][0]
        else:
            self._i = 0
            raise StopIteration
        
    def __getitem__(self, nick):
        for i, item in enumerate(self._users):
            if item[0].nick == nick:
                return self._users[i][0]
            
    def get(self, nick):
        user = self.__getitem__(nick)
        if user:
            return user
    
    def __str__(self):
        user_list = [x[0].nick for x in self._users]
        return str(user_list)
        
    def remove(self, user):
        for i, item in enumerate(self._users):
            if item[0].nick == user.nick:
                self._users.pop(i)
                self._size += 1
        
    def is_oper(self, user):
        """Returns whether or not a given user has oper privileges."""
        for x in self._users:
            if x[0] is user and x[1] > 1:
                return True
        return False
    
    def is_owner(self, user):
        """Returns whether or not the user has owner (+q) privileges."""
        for x in self._users:
            if x[0] is user and x[1] == 5:
                return True
        return False

class ChannelList(object):
    """Stores a list of all currently joined channels and handles channel events."""
    def __init__(self, users):
        self._channels = []
        self.logger = logging.getLogger('teslabot.irc.channelist')
        self._flags = {'+': 1, '@': 2, '%': 3, '&': 4, '~': 5}
        self._prefixes = ['+', '@', '%', '&', '~']
        self._users = users

        self._i = 0
        self._size = 0
    
    def __iter__(self):
        return self
    
    def next(self):
        if self._i < self._size:
            self._i += 1
            return self._channels[self._i - 1]
        else:
            self._i = 0
            raise StopIteration
    
    def __getitem__(self, name):
        """Returns the unique Channel object of a given channel name."""
        for i, item in enumerate(self._channels):
            if item.name == name:
                return self._channels[i]
        raise KeyError
    
    def __str__(self):
        return str(self._channels)
    
    def add(self, chan):
        channel = Channel(chan)
        self._channels.append(channel)
        self._size += 1
        
        return channel
    
    def remove(self, name):
        for i, item in enumerate(self._channels):
            if item.name == name:
                self._channels.pop(i)
                self._size += 1
        
    def on_reply(self, rpl, args):
        if rpl == RPL_TOPIC:
            self.on_RPL_TOPIC(args)
            
        elif rpl == RPL_NAMREPLY:
            self.on_RPL_NAMREPLY(args)
        
    def on_RPL_TOPIC(self, args):
        nick, chan, topic = args.split(' ', 2)
        
        self.__getitem__(chan).topic = topic[1:]
        self.logger.info('Channel topic for {0}: {1}'.format(chan, topic[1:]))
        
    def on_RPL_NAMREPLY(self, args):
        """Populates the users dict of a channel object."""
        args = args.split(' ', 3)
        chan = args[2]
        nicks = args[3][1:].split(' ')
        nicks.pop() # Pop empty string
        
        for nick in nicks:
            if nick[0] in self._prefixes:
                user = self._users[nick[1:]]
                self.__getitem__(chan).add(user, self._flags[nick[0]])
            else:
                user = self._users[nick]
                self.__getitem__(chan).add(user, 0)