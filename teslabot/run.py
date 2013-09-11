import logging
from ircclient import IRCClient
from config import Config
import sys

def start_logging(level = logging.DEBUG):
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    
    # Log to file
    fh = logging.FileHandler('irc.log')
    fh.setLevel(level)
    
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    
    # Output log to console
    logger.addHandler(ch)
    logger.addHandler(fh)

if __name__ == '__main__':    
    start_logging()
    c = Config()
    c = Config()
    c.read_all()
                
    irch = IRCClient(c.nick, c.realname, c.channels, c.admins, c.trigger,
                     c.plugins, c.password, c.ssl, c.reconnect,
                     c.oper_user, c.oper_pass)
    irch.load_plugins()
    irch.connect(c.host, c.port)
    irch.run()