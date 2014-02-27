from pluginbase import PluginBase
import socket
import os
import logging
import struct
import select
import time
from config import Config
import ConfigParser

class DCCSocket:
    """A wrapper for the DCC socket connection.
    This class will be responsible for sending the object the
    file to the destination client.

    Initially the instance has no socket reference.
    """
    def __init__(self, user, port, file_name, file_handler, file_size):
        self.user = user
        self.port = port
        self.name = file_name

        self._file_name = file_name
        self._file_handler = file_handler
        self._file_size = file_size
        self._bytes_offset = 0

        self._file_buffer = ''
        self._bytes_sent = 0
        self._total_bytes_sent = self._bytes_offset

        self._socket = None
        self._addr = None

        # Signifies whether or not the object has a valid socket descriptor.
        self.ready = False
        self.done = False

        self._avg_speed = 0
        self._start_time = None

    def put_sd(self, socket, addr=False):
        self._socket = socket
        self._addr = addr
        self.ready = True

    @property
    def avg_speed(self):
        return round(self._avg_speed, 1)

    def __unicode__(self):
        return u'{0}: {1} KiB/s ({2} MiB - {3}%)'.format(
            self.name, self.avg_speed,
            round(float(self._file_size) / 1024 / 1024, 2),
            (self._bytes_offset + self._total_bytes_sent) / self._file_size * 100)

    def fileno(self):
        """Returns the socket descriptor. Necessary for
        compliance with the select.select() function."""
        return self._socket.fileno()

    def set_offset(self, offset):
        self._bytes_offset = offset
        self._file_handler.seek(self._bytes_offset)

    def send_chunk(self):
        """Sends a chunk of the file to the socket connection.
        Return True when the transfer is complete.
        Raises: DCCSocket.TransferFailure"""
        if not self._start_time:
            self._start_time = time.time()

        if self._total_bytes_sent < self._file_size:
            # If the current buffer hasn't been sent entirely, re-send
            # the remainder of the buffer
            if self._bytes_sent < len(self._file_buffer):
                prev_bytes_sent = self._bytes_sent
                bytes_sent = self._socket.send(self._file_buffer[self._bytes_sent:])

                self._total_bytes_sent += bytes_sent
                self._bytes_sent = prev_bytes_sent + bytes_sent

                self.avg_speed = time.time() - self._start_time

            else:
                self._file_buffer = self._file_handler.read(4096)
                if len(self._file_buffer) == 0:
                    return self._close()
                try:
                    self._bytes_sent = self._socket.send(self._file_buffer)

                except socket.error:
                    raise DCCSocket.TransferFailure

                self._total_bytes_sent += self._bytes_sent
                try:
                    self._avg_speed =\
                        (self._total_bytes_sent / (time.time() - self._start_time)) / 1024
                except ZeroDivisionError:
                    # At the beginning time differential may be small that it returns 0
                    pass
        else:
            return self._close()

    def _close(self):
        """Raises: DCCSocket.TransferFailure"""
        # The DCC SEND protocol specifies that the client should send
        # the number of bytes received. This is redundant and slows down
        # the connection. However, I need to at least acknowledge that I
        # received these packets or otherwise the transfer fails.
        try:
            while len(self._socket.recv(4096)) != 0:
                pass
        except socket.error:
            pass

        self._socket.close()
        self.done = True

        if self._total_bytes_sent != self._file_size - self._bytes_offset:
            raise DCCSocket.TransferFailure

    class TransferFailure(Exception):
        pass


class DCCSocketManager:
    """A manager of DCCSockets.
    Provides useful functions for managing concurrent file transfers.
    """
    def __init__(self):
        self._clients = []

    def add(self, socket):
        self._clients.append(socket)

    def remove(self, socket):
        self._clients.remove(socket)

    def dequeue(self):
        self._clients.pop(-1)

    def peek(self):
        return self._clients[-1]

    def load_sd(self, sd, addr=None):
        """Load socket descriptor to the lastly added DCCSocket."""
        self._clients[-1].put_sd(sd, addr)

    def __len__(self):
        return len(self._clients)

    def __unicode__(self):
        output = u''

        for c in self._clients:
            output += u'[' + unicode(c) + '] '
        return output[:-1]

    def active(self):
        """Returns the number of active clients."""
        return len(self.get_active_clients())

    def pending(self):
        """Returns the number of pending (inactive) clients."""
        return len(self._clients) - self.active()

    def get_active_clients(self):
        """Returns a list of active DCCSockets."""
        client_list = []
        for c in self._clients:
            if c.ready:
                client_list.append(c)
        return client_list


class FileSessionManager(object):
    """FileSessionManager contains a list of the current FileSessions
    in memory."""
    def __init__(self, working_dir):
        self._list = []
        self._working_dir = working_dir

    def get(self, user):
        """Returns the FileSession of a given user."""
        for i in range(len(self._list)):
            if self._list[i].user == user:
                return self._list[i]

        # No file session was found; create a new one
        session = FileSession(user, self._working_dir)
        self._list.append(session)
        return session


class FileSession(object):
    # TODO: Possibly redesign this class to generate list of files
    # more efficiently.
    def __init__(self, user, working_dir):
        """
        FileSession represent's an end-user's view of the XDCC files directory.
        It allows users to view the list of files in paginated chunks.
        It provides "pack" number, filename, and filesize information for each file.

        The list of files outputed to the end-user is divided in "pages",
        each of which will have a maximum number of lines given by _list_size.
        _list_size can be modified by the end-user, but cannot be less than
        one or greater than _list_limit.
        """
        self._working_dir = working_dir
        self._list_size = 10
        self._list_limit = 50
        self._current_page = 1
        self.user = user

    def set_list_size(self, value):
        if value > 1 and value <= self._list_limit:
            self._list_size = value

    def get(self, id_):
        filenames = self._dir(dir=self._working_dir)
        output = (os.path.join(self._working_dir, filenames[id_][1]),
            filenames[id_][1], filenames[id_][2])

        return output

    def _dir(self, page=None, limit=None, dir=None, filter=False):
        """Returns an iterable list of tuples which contain pack number,
         filename, and filesize of each directory file."""
        directory = os.walk(dir)
        for triple in directory:
            dirpath, dirnames, filenames = triple
            if dirpath != self._working_dir:
                break

            if filter:
                new_filenames = []
                for _file in filenames:
                    if _file.find(filter) != -1:
                        new_filenames.append(_file)
                filenames = new_filenames

            for i in range(len(filenames)):
                print(i)
                filenames[i] = (i, filenames[i])

            if not page:
                return self._fmt_size(filenames)
            elif page == 1:
                return self._fmt_size(filenames[0:self._list_size])
            else:
                start = (page-1) * self._list_size
                if start + self._list_size < len(filenames):
                    # Include the elements from start to the number of _list_size
                    return self._fmt_size(filenames[start:start + self._list_size])
                else:
                    # Last page
                    return self._fmt_size(filenames[start:len(filenames)])

    def _fmt_size(self, filenames):
        # TODO: Rename this function
        # TODO: Create a way to adjust the size to MiB for xdcc list only.
        """Appends filesize to each filename tuple.
        The resulting tuple should be formated as:
            (id, filename, filesize)
        """
        for i in range(len(filenames)):
            path = os.path.join(self._working_dir, filenames[i][1])
            size = os.path.getsize(path)

            # Reconstruct the tuple
            filenames[i] = (i, filenames[i][1], size)

        return filenames

    def first(self):
        self._current_page = 1
        return self._dir(1, self._list_size, self._working_dir)

    def next(self):
        self._current_page += 1
        return self._dir(self._current_page, self._list_size, self._working_dir)

    def filter(self, keyword):
        return self._dir(1, self._list_size, self._working_dir, keyword)


class XDCC(PluginBase):
    """An XDCC plugin for file-sharing. Supports concurrent connections.

    A note about _qtimeout: _qtimeout normally defaults to 5, but even 1 is too
    slow for file transfer. Setting it to 0 ensures a fast connection but at the
    cost of CPU cycles. This is a limitation of the plugin design.

    Has the following configuration options:
    [xdcc]
        ip: (Optional) This is the bot's IP address. Necessary to serve files via
        DCC SEND.

        port: (Optional) The server's port number. Note that this port must be
        open in order for the file transfer to work.

        directory: (Required) The file system directory where the files will be stored.
    """
    def __init__(self):
        PluginBase.__init__(self)

        self.name = 'XDCC'
        self.logger = logging.getLogger('teslabot.plugin.XDCC')
        self._qtimeout = 1

        self._dcc_port = 6500
        self._dcc_ip = None

        try:
            self._dcc_ip = Config().get(self.name.lower(), 'ip')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            pass

        try:
            self._dcc_port = Config().get(self.name.lower(), 'port')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            pass

        try:
            self.working_dir = Config().get(self.name.lower(), 'directory')
            if not os.path.isdir(self.working_dir):
                self.working_dir = None
                self.logger.debug('Provided directory path is not valid.')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            pass
        finally:
            if self.working_dir == None:
                # Cannot load directory path; disable XDCC commands
                self.chat_commands = []
                self.logger.debug('Cannot load directory path. XDCC commands disabled.')

        self._sessions = FileSessionManager(self.working_dir)
        self._server = None
        # A list of DCCSocket clients. They may or may not be active.
        self._manager = DCCSocketManager()
        # Number of activate file transfers
        self._transfers_active = 0
        # Maximum number of file transfers
        self.max_conns = 5
        # Time to wait (in secs) before closing the server to new connections
        self.new_conn_timeout = 10
        # Last time (in UNIX secs) that a new server connection was expected
        self._last_request = None

        self.strings.TRANSFER_FAILURE = u'[{0}] failed!'
        self.strings.TRANSFER_SUCCESS = u'[{0}] was successful!'
        self.strings.QUEUE_FULL = u'There is currently a file transfer ' \
            u'waiting to be accepted. Please try again in a few seconds.'
        self.strings.ACTIVE_CONN_PLURAL = u'There are currently {0} active ' \
            u'connections.'
        self.strings.ACTIVE_CONN_SINGULAR = u'There is currently one active ' \
            u'connection.'
        self.strings.ACTIVE_CONN_NONE = u'There are no active connections.'

        # TEMPORARY SESSION DATA -- SHOULD BE REPLACED WITH CLASS
        self.folder_map = {}
        self.file_map = {}

    def ipaddr(self):
        if not self._dcc_ip:
            return self.irch.ipaddr()
        else:
            return self._dcc_ip

    def on_ctcp(self, user, cmd, args):
        """Respond to DCC RESUME if a DCC SEND had already been requested."""
        if cmd == 'DCC':
            if args.split()[0] == 'RESUME':
                try:
                    name, port, position = args.split()[1:]
                    dcc = self._manager.peek()
                    if dcc.name == name and dcc.port == int(port):
                        dcc.set_offset(int(position))
                        self.irch.ctcp('DCC ACCEPT {0} {1} {2}'.format(
                            name, port, position), user.nick)
                except ValueError:
                    # Invalid DCC RESUME message
                    pass

    def command_xdcc(self, user, dst, args):
        """XDCC provides a set of subcommands for manipulating the XDCC module.
        Subcommands: send, state, list
        """
        if not args:
            raise PluginBase.InvalidSyntax

        subcmd = args.split()[0]
        subargs = ' '.join(args.split()[1:])

        if subcmd == 'send':
            self.subcommand_xdcc_send(user, dst, subargs)

        elif subcmd == 'state':
            self.subcommand_xdcc_state(user, dst, subargs)

        elif subcmd == 'list':
            self.subcommand_xdcc_list(user, dst, subargs)

    def subcommand_xdcc_state(self, user, dst, args):
        """Returns state information about the current DCC connections.
        Syntax: {0}dcc state"""
        count = self._manager.active()

        summary = u'\x02Active Conns:\x02 {0} \x02Inactive Conns:\x02 {1}'
        connections = unicode(self._manager)

        self.irch.say(summary.format(
            self._manager.active(), self._manager.pending()
        ), dst)
        self.irch.say(connections, dst)

    def subcommand_xdcc_list(self, user, dst, args):
        """
        Syntax: {0}xdcc list [filter|next] [filter-argument]
        """
        session = self._sessions.get(user)

        fmt = u'\x02#{0}\x02 [{2} MiB] {1}'

        if not args:
            for line in session.first():
                self.irch.notice(fmt.format(*line), user.nick)
        elif args.split()[0] == 'next':
            for line in session.next():
                self.irch.notice(fmt.format(*line), user.nick)
        elif args.split()[0] == 'filter':
            subargs = args.split()
            if len(subargs) > 1:
                filter = subargs[1]

                for line in session.filter(keyword=filter):
                    self.irch.notice(fmt.format(*line), dst)
            else:
                raise PluginBase.InvalidSyntax
        else:
            raise PluginBase.InvalidSyntax

    def subcommand_xdcc_send(self, user, dst, args):
        """
        A user has requested a file.
        """
        # TODO: Proper docstring
        self._last_request = time.time()

        session = self._sessions.get(user)
        try:
            file_path, file_name, file_size = session.get(id_=int(args[1:]))
        except ValueError:
            raise PluginBase.InvalidArguments

        file_handler = open(file_path, 'rb')

        self.create_server(self._dcc_port)

        # Only one "inactive" DCCSocket is allowed at a time. Otherwise,
        # the server may supply the wrong file to the clients.
        # TODO: Create a server for each connection.
        if self._manager.pending():
            self.irch.say(self.strings.QUEUE_FULL, dst)
        else:
            fuck = self.ipaddr()
            self.irch.say('\x01DCC SEND "{0}" {1} {2} {3}\x01'.format(
                file_name,
                struct.unpack('>L', socket.inet_aton(self.ipaddr()))[0],
                self._dcc_port,
                file_size
            ), user.nick)
            self._manager.add(DCCSocket(
                user, self._dcc_port, file_name, file_handler, file_size))
            self.hook(self.handle_new_conn)

    def handle_new_conn(self):
        """Checks if the user has connected to the temporary for file transfer.
        After a certain number of accept() attempts, close the server.
        """
        try:
            s, addr = self._server.accept()

            # Put the socket descriptor in the last DCCSocket
            self._manager.load_sd(s, addr)

            # Only hook when it is not currently hooked.
            if self.handle_dcc_conn not in self._hooks:
                self.hook(self.handle_dcc_conn)
        except socket.error:
            if not self._manager.pending():
                self.unhook(self.handle_new_conn)
            elif time.time() - self._last_request > self.new_conn_timeout:
                self._manager.dequeue()
                self.unhook(self.handle_new_conn)
                self.logger.debug('Unhooked [handle_new_conn] due to inactivity.')

    def handle_dcc_conn(self):
        """Polls every DCC transfer in progress to send a chunk."""
        client_list = self._manager.get_active_clients()
        if client_list:
            conns = select.select([], client_list, [], 0)

            for dcc_socket in conns[1]:
                try:
                    dcc_socket.send_chunk()
                    if dcc_socket.done:
                        self._manager.remove(dcc_socket)
                        self.irch.notice(
                            self.strings.TRANSFER_SUCCESS.format(
                                unicode(dcc_socket)), dcc_socket.user.nick)
                except DCCSocket.TransferFailure:
                    self._manager.remove(dcc_socket)
                    self.irch.notice(self.strings.TRANSFER_FAILURE.format(unicode(dcc_socket)),
                                  dcc_socket.user.nick)
        else:
            # All transfers have been completed. Unhook this method.
            self.unhook(self.handle_dcc_conn)
            self.close_server()

    def create_server(self, port):
        """Creates the DCC server socket."""
        self._qtimeout = 0
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind(('0.0.0.0', port))
        self._server.setblocking(0)
        self._server.listen(5)

    def close_server(self):
        """Closes the DCC server socket."""
        self._server.close()
        self._qtimeout = 1