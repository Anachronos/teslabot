import ConfigParser
import logging
import sys

class Config:
    """Extracts configuration settings from the default configuration file (teslabot.cfg)."""
    def __init__(self, cfg = 'teslabot.cfg'):
        self.logger = logging.getLogger('teslabot.config')
        self.parser = ConfigParser.ConfigParser()
        self._config = cfg

    def read_all(self, section='connection'):
        """Loads the default configuration file."""
        try:
            f = open(self._config)
            self.parser.readfp(f)
        except IOError:
            self.logger.critical('{0} is missing or inaccessible.'.format(self._config))
            sys.exit()
            
        self.host = self.parser.get('teslabot', 'host')
        self.port = self.parser.getint('teslabot', 'port')
        self.nick = self.parser.get('teslabot', 'nick')
        self.realname = self.parser.get('teslabot', 'realname')
        self.channels = self.parser.get('teslabot', 'channels').split()
        self.trigger = self.parser.get('teslabot', 'trigger')
        self.password = self.parser.get('teslabot', 'password')
        self.admins = self.parser.get('teslabot', 'admins').split()
        self.ssl = self.parser.getboolean('teslabot', 'ssl')
        self.reconnect = self.parser.getboolean('teslabot', 'reconnect')
        self.plugins = self.parser.get('teslabot', 'plugins').split()

    def read_plugins(self):
        """Extracts the list of plugins to be loaded by the IRC client."""
        try:
            fp = open(self._config)
            self.parser.readfp(fp)
        except IOError:
            self.logger.critical('{0} is missing or inaccessible.'.format(self._config))
            sys.exit()
        self.parser.read(self._config)

        self.plugins = self.parser.get('teslabot', 'plugins').split()
        
        return self.plugins
    
    def get(self, section, option):
        try:
            f = open(self._config)
            self.parser.readfp(f)
        except IOError:
            self.logger.critical('{0} is missing or inaccessible.'.format(self._config))
            sys.exit()

        return self.parser.get(section, option)