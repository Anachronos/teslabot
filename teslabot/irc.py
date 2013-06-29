from ircconstants import *
from user import User
from user import UserList
from channel import ChannelList
import socket
import sys
import time
import logging
import ssl
import select
import errno

__version__ = '1.0a'                
        
class IRC(object):
    """
    IRC protocol interface.
    
    Attributes:
        user: A User object to store the bot's user details
        logger: A Logger object
        channels: A ChannelList object
        admins: A list of User objects
        ssl: A boolean  to enable or disable SSL wrapper
        
        _init_channels: A list of channels that is joined when the client is connected
        _reconnect: Whether or not to reconnect when socket connection is lost
        _password: The connection password (if any)
        _buffer: A socket buffer string
    """
    def __init__(self, nick, realname, channels, admins, _ssl = False, reconnect = False, password = False):
        self.user = User(nick, realname)
        self.users = UserList()
        self.channels = ChannelList(self.users)
        
        self.logger = logging.getLogger('teslabot.irc')
        self._init_channels = channels
        self._ssl = _ssl
        self._reconnect = reconnect
        self._password = password
        self._buffer = ''
        
        self._msg_time = []
        self._msg_last_id = 0
        self._max_mps = 5
        self._throttle = False

        self.alive = 1
        
        # Define users with administrator privileges
        for src in admins:
            user = User(src, admin=True)
            self.users.append(user)

    def run(self):
        """
        Keeps the the connection alive by continuously calling _recv().
        It will attempt to reconnect if connection is lost and reconnect is enabled.
        """
        while self.alive:
            try:
                self._recv()
            except socket.error as e:
                if e.errno == errno.EBADF:
                    self.reconnect()

    def _get_headers(self):
        return ':' + self.user.nick + '!' + self.user.real + '@' + self.user.hostname

    def join(self, channel):
        self.send('JOIN :{0}'.format(channel))
        
    @property
    def nick(self):
        return self.user.nick

    @nick.setter
    def nick(self, value):
        self.send('NICK {0}'.format(value))
        self.user.nick = value
        
    def notice(self, msg, nick):
        """Accepts a string or a list of messages."""
        if type(msg) == list:
            for line in msg:
                if len(line) > 0:
                    self.send(u'NOTICE {0} :{1}'.format(nick, line))
                    self.logger.info('>{0}< {1}'.format(nick, line))
        else:
            msg = msg.split('\r\n')
            for line in msg:
                maxlen = 512 - len(self._get_headers()) - len(nick) - 12
                
                if len(line) < maxlen:
                    self.send('NOTICE {0} :{1}'.format(nick, line))
                    self.logger.info('>{0}< {1}'.format(nick, line))
                else:
                    self.send('NOTICE {0} :{1}'.format(nick, line[:maxlen-1]))
                    self.logger.info('>{0}< {1}'.format(nick, line[:maxlen-1]))
                    self.notice(line, line[maxlen-1:])
            
    def mode(self, modes, args, channel = False):
        msg = 'MODE {0} {1} {2}'
        if channel:
            self.send(msg.format(channel, modes, args))
        else:
            self.send(msg.format(self.user.nick, modes, args))
            
    def kick(self, nick, chan, reason = ''):
        self.send(u'KICK {0} {1} :{2}'.format(chan, nick, reason))
            
    def _get_avg_mps(self):
        """Returns the average rate of sent messages per second."""
        x1 = self._msg_last_id - self._max_mps
        t1 = self._msg_time[self._msg_last_id - self._max_mps]
        x2 = self._msg_last_id
        t2 = self._msg_time[self._msg_last_id]
        
        avg_mps = (x2 - x1) / (t2 - t1)
        
        return avg_mps
            
    def _is_throttling(self):
        """Returns true if the rate of messages per second has exceeded the limit.
        
        Formula:
            (x2 - x1)/(t2 - t1) = mps (average messages per second)
            where (x1, t1) and (x2, t2) represent amount of x messages covered in y seconds.
            
            The distance between (x1, t1) and (x2, t2) is determined by _max_mps (5 by default).
            
            If the average mps exceeds _max_mps, throttling occurs. When throttling, messages are
            sent every 1 second. When the average mps is equal to or less than 1, throttling stops.
            
        Data structure:
            _msg_time: a list of UNIX time values, whose index represents the number of messages.
            Although in practice, the difference between each index is the only relevant fact.
            As a result, we "pop" values from the beginning of the list that are no longer needed.
            
        """
        self._msg_time.append(time.time())
        throttle = False
        
        if self._throttle:    
            avg_mps = self._get_avg_mps()
            
            if self._msg_last_id % self._max_mps == 0:
                # In order to prevent the list from growing big, we drop values we no longer need.
                self._msg_time.pop(0)
                self._msg_last_id -= 1
            
            if avg_mps <= 1:
                self.logger.warning('Throttling disabled.')
                self._throttle = False
            else:
                self.logger.warning('Throttling.')
                throttle = True
        
        elif len(self._msg_time) > self._max_mps:
            avg_mps = self._get_avg_mps()
            
            # In order to prevent the list from growing large, we drop values we no longer need.
            if self._msg_last_id % self._max_mps == 0:
                self._msg_time.pop(0)
                self._msg_last_id -= 1
            
            if avg_mps >= self._max_mps:
                self.logger.warning('Throttling enabled.')
                self._throttle = throttle = True
            else:
                throttle = False
                
        self._msg_last_id += 1
        return throttle

    def send(self, msg):
        """msg should be 512 bytes or less"""
        
        if self._is_throttling():
            time.sleep(1)
            
        # Encode to bytes -- assuming it's a utf-8 string
        msg = msg.encode('utf-8')
        
        self.sock.send(msg + '\r\n')
        self.logger.debug('{0}'.format(msg))

    def leave(self, chan, reason = 'Leaving'):
        self.send('PART {0} :{1}'.format(chan, reason))
        self.channels.remove(chan)
        self.logger.info('Left channel {0} ({1}).'.format(chan, reason))

    def say(self, msg, dst):
        msg = msg.split('\r\n')

        for line in msg:
            maxlen = 512 - len(self._get_headers()) - len(dst) - 12
            
            if len(line) < maxlen:
                self.send(u'PRIVMSG {0} :{1}'.format(dst, line))
                self.logger.info(u'[{0}] <{1}> {2}'.format(dst, self.user.nick, line))
            else:
                self.send(u'PRIVMSG ' + dst + ' :' + line[:maxlen-1])
                self.logger.info(u'[{0}] <{1}> {2}'.format(dst, self.user.nick, line[:maxlen-1]))
                self.say(line[maxlen-1:], dst)
                
    def names(self, chan):
        self.send('NAMES {0}'.format(chan))

    def action(self, msg, dst):
        self.send('PRIVMSG ' + dst + ' :\x01ACTION ' + msg + '\x01')

    def whois(self, nick):
        self.send('WHOIS {0}'.format(nick))

    def _on_privmsg(self, user, args):
        """Calls the appropriate handler for a given PRIVMSG type.
        Either channel, private, or CTCP message.
        
        Args:
            user: A User class instance
            args: A string of arguments
        """
        dst, msg  = args.split(' ', 1)
        
        # CTCP message
        if msg[1] == '\x01' and msg[-1] == '\x01':
            msg = msg[2:-1]
            if len(msg.split()) > 1:
                cmd, subargs = msg[1:-1].split(' ', 1)
            else:
                cmd = msg
                subargs = None
            
            self.logger.info('>{0}< CTCP {1}'.format(user.nick, cmd))
            self.on_ctcp(user, cmd, subargs)
        
        # Channel message
        if dst[:1] == '#':
            self.on_channel_message(user, dst, msg[1:])

        # Private query
        elif dst.lower() == self.user.nick.lower():
            self.on_private_message(user, msg[1:])

    def quit(self, msg = 'Quitting', force = None):
        try:
            if force:
                sys.exit()
            
            self.send('QUIT :{0}'.format(msg))
            self.sock.close()
            self.alive = 0
        finally:
            self.logger.info('Disconnected from [{0}].'.format(self.user.host))

    def _set_hostname(self, args):
        self.user.host = args.split(' ')[1]
    
    def _recv(self, timeout = False):
        """Processes messages received from the IRC server and calls the
        appropriate handlers."""
        buffer = ''
        
        try:
            buffer = self._buffer + self.sock.recv(512)
        except (socket.error, socket.gaierror) as e:
            self.logger.critical(e.strerror)

        self._buffer = ''

        # Server has closed the socket connection
        if len(buffer) == 0:
            self.quit(force=True)
        
        data = buffer.split('\r\n')
        
        # If not empty, this is part of a new message. Add it to the buffer.
        self._buffer += data.pop()

        # Server didn't send CRLF
        if not len(data):
            return

        # Remove empty strings due to an \r\n in the beginning 
        if data[0] == '':
            data.pop(0)

        for msg in data:
            self.logger.debug('{0}'.format(msg))
            self._parse_message(msg)

    def _parse_message(self, msg):
        """Parses a given IRC message."""

        if msg[:4] == 'PING':
            self.send('PONG {0}'.format(msg[5:]))
            return

        if msg[:5] == 'ERROR':
            self.quit(force=True)
        
        src, cmd, args = msg.split(' ', 2)
        user = self.users.get(src[1:])

        if cmd == 'PRIVMSG':
            self._on_privmsg(user, args)
            
        elif cmd == 'NOTICE':
            self.on_notice(user, args)

        elif cmd == 'TOPIC':
            chan = args.split(' ', 1)[0]
            topic = args.split(' ', 1)[1][1:]

            self.on_channel_topic(user, self.channels[chan], topic)

        elif cmd == 'JOIN':
            if args[0] != ':':
                chan = args
            else:
                chan = args[1:]
            channel = self.channels.add(chan)
            self.on_channel_join(user, channel)
            
        elif cmd == 'NICK':
            self.users.get(user=user).nick = args
            print id(self.users[args])

        elif cmd == 'PART':
            subargs = args.split()
            
            if len(subargs) == 2:
                chan, reason = subargs
                self.on_channel_part(user, self.channels[chan], reason[1:])
            else:
                chan = args.split()[0]
                self.logger.warning('CHANNEL NAME: ' + chan)
                self.on_channel_part(user, self.channels[chan])

        elif cmd == RPL_WELCOME:
            self.on_connect()

        elif cmd == RPL_HOSTHIDDEN:
            self._set_hostname(args)

        elif cmd in (RPL_WHOISUSER, RPL_WHOISIDLE):
            self._on_whois(cmd, args)

        elif cmd == ERR_NICKNAMEINUSE:
            self.on_nickinuse()
        
        elif cmd in (RPL_TOPIC, RPL_TOPICWHOTIME, RPL_NAMREPLY):
            self.channels.on_reply(cmd, args)
            
        elif cmd in (RPL_MOTDSTART, RPL_MOTD, RPL_ENDOFMOTD):
            self.on_motd(args)
            
    def on_motd(self, msg):
        self.logger.info(msg.split(':', 1)[1])
            
    def _on_whois(self, cmd, args):
        if cmd == RPL_WHOISUSER:
            if args.split(' ')[1] == self.user.nick:   # Self-WHOIS
                self.user.hostname = args.split(' ')[3]    # Get the hostname
                self.logger.debug('Setting hostname to [{0}].'.format(self.user.hostname))
            else:
                pass
        elif cmd == RPL_WHOISIDLE:
            args = args.split()
            
            user = self.users.get(args[1])
            user.idle = int(args[2])
            user.signon = int(args[3])

    def connect(self, host, port):
        """Attempts to establish a socket connection with a given IRC server."""
        self._host = host
        self._port = port
        
        try:
            self.logger.info('Connecting to {0}:{1}.'.format(host, port))
            
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self._ssl:
                self.sock = ssl.wrap_socket(self.sock, cert_reqs=ssl.CERT_NONE)
            self.sock.connect((host, port))
            self.alive = 1
            
            if self._password:
                self.send('PASS {0}'.format(self._password))
        
            self.send('NICK {0}'.format(self.user.nick))
            self.send('USER {0} 0 * :{0}'.format(self.user.real))

        except (socket.timeout, socket.error) as e:
            self.logger.critical('Failed to connect to [{0}].'.format(host))
            
    def reconnect(self):
        if self._reconnect:
            self.connect(self._host, self._port)
            
    def on_connect(self):
        self.whois(self.user.nick)
            
        for channel in self._init_channels:
            self.join(channel)

    def on_channel_mode(self, user, channel, modes, args = None):
        raise NotImplementedError

    def on_channel_message(self, user, channel, msg):
        raise NotImplementedError

    def on_channel_join(self, user, channel):
        """on_channel_join is called whenever the bot or a user joins a channel.
        
        Args:
            channel: A Channel instance
            user: A user instance
        """
        pass

    def on_channel_part(self, user, channel, reason):
        if user.nick == self.user.nick:
            self.channels.remove(channel)
        else:
            channel.remove(user)

    def on_channel_topic(self, user, channel, topic):
        raise NotImplementedError

    def on_private_message(self, user, msg):
        raise NotImplementedError
    
    def on_notice(self, user, msg):
        self.logger.info('-{0}- {1}'.format(user.nick, msg))

    def on_nickinuse(self):
        raise NotImplementedError

    def ctcp_reply(self, msg, nick):
        self.send(u'PRIVMSG {2} :{0}{1}{0}'.format('\x01', msg, nick))
    
    def on_ctcp(self, user, cmd, args):
        global __version__
        
        if cmd == 'VERSION':
            self.ctcp_reply('VERSION Teslabot {0}'.format(__version__), user.nick)
        