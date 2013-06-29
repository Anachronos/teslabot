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
        must match in order to acquire privileges.
    """
    def __init__(self, name, realname = '', host = '', admin = False):
        self.nick = ''
        self.real = realname
        self.host = host
        self.modes = []
        self.server = False
        self.idle = 0
        self.signon = 0
        
        self._admin = admin
        self._ahost = ''
        self._areal = ''
        
        self._parse(name)
        
        if self._admin:
            self._ahost = self.host
            self._areal = self.real
        
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
    
    
class UserList(object):
    def __init__(self):
        self._users = []
        
    def __getitem__(self, nick):
        user = User(nick)
        for i, item in enumerate(self._users):
            if item.nick == nick:
                return self._users[i]
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
        user = User(src)
        
        for i, item in enumerate(self._users):    
            if self._users[i].nick == user.nick:
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