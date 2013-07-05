from pluginbase import PluginBase
import sqlite3
import logging
import time
import os
import datetime
import re

class Statistics(PluginBase):
    """Statistics provides various user and channel statistics via commands.
    
    channels: A dictionary of cached channel IDs.
    users: A dictionary of cached user IDs.
    """
    def __init__(self):
        PluginBase.__init__(self)
        self.name = 'Statistics'
        self.logger = logging.getLogger('teslabot.plugin.statistics')
        self.conn = None
        self.alive = True
        
        self.path_schema = os.path.abspath('plugins/statistics/schema.sql')
        self.path_statsdb = os.path.abspath('plugins/statistics/stats.sqlite3')
        
        self.channels = {}
        self.users = {}
        
    def fmt_time(self, time):
        return datetime.datetime.fromtimestamp(int(time)).strftime('%H:%M:%S %Y-%m-%d')
    
    def on_load(self):
        if os.path.exists(self.path_statsdb):
            self.conn = sqlite3.connect(self.path_statsdb)
        else:
            self.logger.debug('stats.sqlite3 does not exist. Creating a new stats.sqlite3.')
            self.create_db()
        
    def create_db(self):
        self.conn = sqlite3.connect(self.path_statsdb)
        
        with open(self.path_schema, 'r') as f:
            try:
                c = self.conn.cursor()
                c.executescript(f.read())
                self.conn.commit()
            except Exception as e:
                self.logger.warning(e.message)
        
    def update_counter(self, chan, count):
        """Records the number of online users in a given channel (timestamped)."""
        c = self.conn.cursor()
        params = (self.get_channel_id(chan), count, int(time.time()))
        c.execute("INSERT INTO channel_visit (cid, count, time) VALUES (?, ?, ?)", params)
        self.conn.commit()
        
    def update_lastseen(self, user, channel):
        """Records when and where a user was last seen."""
        c = self.conn.cursor()
        params = (self.get_channel_id(channel), int(time.time()), self.get_user_id(user.nick))
        c.execute("UPDATE user " \
                  "SET lastseen_cid = ?, lastseen_time = ? WHERE id = ?", params)
        self.conn.commit()

    def update_user_statistics(self, user, chan, msg):
        """Updates fields of user_statistics. If they don't exist for a given user
        and channel, create row."""
        c = self.conn.cursor()
        params = (self.get_channel_id(chan), self.get_user_id(user.nick))
        c.execute('SELECT id FROM user_statistics ' \
                  'WHERE cid = ? and uid = ?', params)

        self.conn.commit()

        params = (len(msg.split()), self.get_user_id(user.nick), self.get_channel_id(chan))

        if not c.fetchone():
            c.execute('INSERT INTO user_statistics (word_count, uid, cid, line_count) ' \
                      'VALUES (?, ?, ?, 1)', params)
        else:
            c.execute('UPDATE user_statistics ' \
                      'SET word_count = word_count+?, line_count = line_count+1 ' \
                      'WHERE uid = ? AND cid = ?', params)
        self.conn.commit()
        
    def get_channel_id(self, name):
        """Retrieves the channel id from the database. If it's not present, it will create a new one."""
        c = self.conn.cursor()
        
        c.execute("SELECT id FROM channel WHERE name = ? LIMIT 1", (name,))
        self.conn.commit()

        id = c.fetchone()
        
        if not id:
            c.execute("INSERT INTO channel (name) VALUES (?)", (name,))
            self.conn.commit()
            id = self.get_channel_id(name)
            return id
        else:
            self.channels[id[0]] = name
            return id[0]
        
    def get_user_id(self, nick):
        """Retrieves the user's id. If not present, a new one will be created."""
        c = self.conn.cursor()
        
        c.execute('SELECT id FROM user WHERE LOWER(nick) = ? LIMIT 1', (nick.lower(),))
        self.conn.commit()
        
        id = c.fetchone()
        
        if not id:
            c.execute('INSERT INTO user (nick) VALUES (?)', (nick.lower(),))
            self.conn.commit()
            id = self.get_user_id(nick)
            return id
        else:
            self.users[id] = nick
            return id[0]
        
    def on_channel_part(self, user, channel, reason):
        if user.nick != self.irch.user.nick:
            self.update_counter(channel.name, channel.count())
        self.update_lastseen(user, channel.name)
        
    def on_channel_join(self, user, channel):
        if user.nick == self.irch.user.nick:
            for u in channel:
                self.update_lastseen(u, channel.name)
        self.update_counter(channel.name, channel.count())
        self.update_lastseen(user, channel.name)
        
    def on_channel_message(self, user, channel, msg):
        """Calls methods that use channel message for their statistics."""
        self.handle_wordlist(channel.name, msg.split())
        self.update_user_statistics(user, channel.name, msg)
        
    def handle_wordlist(self, chan, word_list):
        """Maintains a table of word frequencies for a given channel."""
        c = self.conn.cursor()
        cid = self.get_channel_id(chan)
        
        for word in word_list:
            word = re.sub(r'\W+', '', word).lower().decode('utf-8')
            
            c.execute(u'SELECT id FROM word_list WHERE cid = ? AND word = ?', (cid, word))
            self.conn.commit()

            id = c.fetchone()
            
            if not id:
                c.execute(u'INSERT INTO word_list (cid, word, count) VALUES (?, ?, ?)', (cid, word, 1))
            else:
                c.execute('UPDATE word_list SET count = count+1 WHERE id = ?', (id[0],))
            self.conn.commit()
            
    def command_seen(self, user, dst, args):
        """Displays where and when a given user was last seen by the bot."""
        if not args or len(args.split()) > 1 or len(args.split()) < 1:
            raise PluginBase.InvalidSyntax
        
        c = self.conn.cursor()
        
        query = 'SELECT channel.name, user.lastseen_time, user.nick ' \
                'FROM user INNER JOIN channel ' \
                'WHERE user.lastseen_cid = channel.id AND LOWER(user.nick) = ? ' \
                'LIMIT 1'
        c.execute(query, (args.lower(),))
        rows = c.fetchone()
        
        if rows:
            chan, time, nick = rows
            self.irch.say('{0} was last seen in {1} on {2}.'.format(nick, chan, self.fmt_time(time)), dst)
        else:
            self.irch.say('\x0311No information available.', dst)
        
    def command_stats(self, user, dst, args):
        """Provides the top statistical information about users and channels.
        Subcommands: words, peak, user
        """
        if len(args.split()) < 2:
            raise self.InvalidSyntax
        
        subcmd, subargs = args.split(' ', 1)
        
        if subcmd == 'words':
            self.subcommand_stats_words(user, dst, subargs)
        elif subcmd == 'peak':
            self.subcommand_stats_peak(user, dst, subargs)
        elif subcmd == 'reset':
            self.subcommand_stats_reset(user, dst, subargs)
        elif subcmd == 'user':
            self.subcommand_stats_user(user, dst, subargs)

    def subcommand_stats_user(self, user, dst, args):
        """Returns the stats of a given or top user.
        Syntax: {0}stats user [get|top] [<user>|words|lines]
        """
        subargs = args.split()

        if subargs[0] == 'get':
            target = subargs[1]

            c = self.conn.cursor()

            values = (self.get_channel_id(dst), self.get_user_id(target))

            c.execute('SELECT word_count, line_count ' \
                      'FROM user_statistics ' \
                      'WHERE cid = ? and uid = ?', values)
            self.conn.commit()

            for row in c.fetchall():
                reply = '{0} has written {1} words and {2} lines of text.'
                self.irch.say(reply.format(target, row[0], row[1]), dst)
                return
            self.irch.say('{0} not found.'.format(args), dst)
        elif subargs[0] == 'top':
            c = self.conn.cursor()

            try:
                type = subargs[1]
            except IndexError:
                raise self.InvalidSyntax

            if type == 'line' or type == 'word':
                values = (self.get_channel_id(dst),)
                c.execute('SELECT user.nick, user_statistics.{0}_count ' \
                          'FROM user INNER JOIN user_statistics ' \
                          'WHERE user_statistics.cid = ? ' \
                          'AND user.id = user_statistics.uid ' \
                          'ORDER BY user_statistics.{0}_count DESC LIMIT 1'.format(type),
                          values)
                self.conn.commit()
                
                row = c.fetchone()
                if row:
                    res = '{0} has the most {1} count ({2}) on {3}.'
                    self.irch.say(res.format(row[0], type, row[1], dst), dst)
        else:
            raise self.InvalidSyntax
            
    def subcommand_stats_peak(self, user, dst, args):
        """Returns the highest record of online users for a given channel.
        Returns peak online users information for channels.
        Syntax: {0}stats peak [get|top] <channel>
        """
        subargs = args.split()
        if subargs[0] == 'get':
            try:
                chan = subargs[1]
                
                c = self.conn.cursor()
                id = self.get_channel_id(chan)
                c.execute("SELECT count, time FROM channel_visit WHERE cid = {0} ORDER BY count DESC LIMIT 1".format(id))
                rows = c.fetchall()

                if not len(rows):
                    self.irch.say(u'No data available for channel {0}.'.format(chan), dst)
                    return
                
                for row in rows:
                    date = datetime.datetime.fromtimestamp(int(row[1])).strftime('%Y-%m-%d %H:%M:%S')
                    
                    if not id:
                        self.irch.say(u'No data available for channel {0}.'.format(chan), dst)
                    else:
                        self.irch.say(u'There were {0} users online (peak) in {1} on {2}.'.format(row[0], chan, date), dst)
            except IndexError:
                self.irch.notice(self.INV_SYNTAX, user.nick)
        elif subargs[0] == 'top':
            c = self.conn.cursor()
            c.execute("SELECT channel.name, channel_visit.count " \
                      "FROM channel_visit " \
                      "INNER JOIN channel " \
                      "WHERE channel.id = channel_visit.cid "
                      "ORDER BY channel_visit.count DESC LIMIT 1")
            self.conn.commit()
            row1 = c.fetchone()
            self.irch.say('Channel {0} has the highest peak at {1} users online.'.format(*row1), dst)
        else:
            raise self.InvalidSyntax()
            
    def subcommand_stats_words(self, user, dst, args):
        """Displays the most frequently used words in a given channel.
        Syntax: {0}stats words <channel>"""
        if not args:
            self.irch.notice(self.INV_SYNTAX, user.nick)
        else:
            subargs = args.split(' ', 1)
        
            c = self.conn.cursor()
            cid = self.get_channel_id(subargs[0])
            
            if len(subargs) > 1:
                c.execute('''SELECT word, count FROM word_list WHERE cid = ? 
                AND length(word) > ? ORDER BY count DESC LIMIT 5''', (cid, int(subargs[1])))
            elif len(subargs) > 0:
                c.execute('SELECT word, count FROM word_list WHERE cid = ? ' \
                          'ORDER BY count DESC LIMIT 5', (cid,))
            else:
                self.irch.say('No data available.', dst)
                
            self.conn.commit()
            rows = c.fetchall()
            
            if len(rows) > 0:
                msg = []
                i = 1
                for row in rows:
                    msg.append('{0}. {1} ({2} mentions)'.format(i, row[0], row[1]))
                    i += 1
                    
                self.irch.say('\r\n'.join(msg), dst)
            else:
                self.irch.say('No data available for channel {0}'.format(subargs[0]), dst)
                
    def subcommand_stats_reset(self, nick, dst, args):
        """Wipes the statistics database. Requires admin privileges."""
        if nick[0] in self.irch.admins:
            self.conn.close()
            os.remove(self.path_statsdb)
            self.create_db()
            self.irch.say('Statistics database reset.', dst)
            self.conn = sqlite3.connect(self.path_statsdb)
            
