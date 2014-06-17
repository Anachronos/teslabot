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

    logger.info('Started logger with {} level.'.format(logging.getLevelName(level)))

    return logger

if __name__ == '__main__':
    c = Config()
    c.read_all()

    logger = start_logging(c.logging)
                
    irch = IRCClient(c.nick, c.realname, c.channels, c.admins, c.trigger,
                     c.plugins, c.password, c.ssl, c.reconnect,
                     c.oper_user, c.oper_pass)
    irch.load_plugins()
    irch.connect(c.host, c.port)

    try:
        irch.run()
    except Exception as e:
        logger.exception(e)
        logger.critical("Teslabot has encountered an error that it cannot "\
                        "recover from.")