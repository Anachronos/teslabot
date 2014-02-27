class User(object):
    """
    Attributes:
        nick: A string of the user's nickname
        real: A string of the user's realname
        host: A string of the user's hostname
        modes: A list of user modes
        idle: A integer of idle time in seconds
        sign: An integer of idle time in UNIX time
        
        server: A boolean to check if the User object is referring to the server
        
        _admin: A boolean whether or not to define a User object as admin
        _ahost and _areal: Two strings containing the hostname and realname that a User 
        must match in order to acquire privileges. If no host or real is specified, it defaults
        to the asterik mask.
    """
    def __init__(self, **kwargs):
        self.nick = kwargs.get('nick', '')
        self.real = kwargs.get('real', '')
        self.host = kwargs.get('host', '')
        self.modes = []
        self.server = kwargs.get('server', False)
        self.idle = 0
        self.signon = 0
        self._admin = kwargs.get('admin', False)
        self._ahost = kwargs.get('host', '*')
        self._areal = kwargs.get('real', '*')
        self.modes = UserModes()

        if 'src' in kwargs:
            self._parse(kwargs['src'])

    @property
    def admin(self):
        if self._admin:
            if self.host == self._ahost and self._areal == self.real:
                return True
            if self._ahost == '*' and self._areal == self.real:
                return True
            if self._ahost == self.host and self._areal == '*':
                return True
            if self._ahost == '*' and self._areal == '*':
                return True
        else:
            return False
        
    @admin.setter
    def admin(self, value):
        self.admin = value
    
    def _parse(self, name):
        delim1 = name.find('!')
        delim2 = name.find('@')
        
        if delim1 > -1 and delim2 > -1:
            self.nick = name[:delim1]
            self.real = name[delim1 + 1:delim2]
            self.host = name[delim2 + 1:]
        else:
            self.nick = name
            
    def __str__(self):
        return '{0}!{1}@{2}'.format(self.nick, self.real, self.host)
    

class UserModes(object):
    """Stores user modes for every channel."""
    def __init__(self):
        self._modes = {}
        self._privileges = {'v': 1, 'o': 2, 'h': 3, 'a': 4, 'q': 5}

    def __str__(self):
        output = "<UserModes: {0}>"
        output2 = ''

        for key, value in self._modes.items():
            output2 += '{0}:'.format(key)
            for mode in value:
                output2 += ' +{0}'.format(mode)
        return output.format(output2)
       
    def get(self, chan):
        return self._modes[chan]

    def add(self, chan, mode):
        """Appends a given mode to the user's channel mode list.
        Arguments:
            mode: A single ASCII/UTF-8 letter
        """
        try:
            mode_list = self._modes[chan]
            if mode in mode_list:
                return
            mode_list.append(mode)
        except KeyError:
            self._modes[chan] = [mode]

    def remove(self, chan, mode):
        """Removes a given mode from the user's channel mode list.
        Args:
            mode: A mode string. If -1, wipe the list of modes.
            chan: A channel name string
        """
        if mode == -1:
            self._modes[chan] = []
            print(self._modes)
        else:
            mode_list = self._modes[chan]
            for x in enumerate(mode_list):
                if x[1] == mode:
                    mode_list.pop(x[0])

    def is_owner(self, chan):
        mode_list = self.get(chan)
        if 'q' in mode_list:
            return True
        return False

    def is_op(self, chan):
        mode_list = self.get(chan)
        if 'o' in mode_list:
            return True
        return False

    def is_voice(self, chan):
        mode_list = self.get(chan)
        if 'v' in mode_list:
            return True
        return False
    
class UserList(object):
    def __init__(self):
        self._users = []
        
    def __getitem__(self, nick):
        for i, item in enumerate(self._users):
            if item.nick.lower() == nick.lower():
                return self._users[i]
        user = User(nick=nick)
        self._users.append(user)
        return user
            
    def get(self, src = False, user = False):
        """Returns the User reference of a given source.
        
        If it's not already in the list, create a new object.
        
        Args:
            src: A source string of the format [nickname]![realname]@[hostname]
            
        Returns:
            user: A User object        
        """
        if user:
            return self.__getitem__(user.nick)
        user = User(src=src)
        
        for i, item in enumerate(self._users):    
            if self._users[i].nick.lower() == user.nick.lower():
                if self._users[i].host != user.host:
                    self._users[i].host = user.host
                    
                if self._users[i].real != user.real:
                    self._users[i].real = user.real
                
                return self._users[i]
            
        self._users.append(user)
        return user
        
    def append(self, user):
        """Appends a User class to the list of users."""
        self._users.append(user)