from pluginbase import PluginBase
import logging
from HTMLParser import HTMLParser
import requests
import urllib
import re
import time
import json
from datetime import datetime
from ircconstants import *
try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup
    
class Paulcon(PluginBase):
    def __init__(self):
        PluginBase.__init__(self)
        self.name = 'Paulcon'
        self.logger = logging.getLogger('teslabot.plugin.paulcon')
        
        self.LEVEL_MSG = [["IT'S OVER", C_BLACK],
                       ["IT'S HAPPENING", C_RED],
                       ["IT'S TOO LATE", C_RED],
                       ["YOU CAN'T STOP IT", C_BROWN],
                       ["YOU ASKED FOR THIS", C_BROWN],
                       ["YOU COULD HAVE PREVENTED THIS", C_YELLOW],
                       ["WHY DIDN'T YOU LISTEN?", C_YELLOW],
                       ["YOU DIDN'T LISTEN", C_YELLOW],
                       ["IT BEGINS", C_YELLOW],
                       ["IT HASN'T EVEN BEGUN", C_GREEN]]
        self.cur_level = 9
        self.cur_time = datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M')
        
    def command_paulcon(self, user, dst, args):
        """PAULCON Warning System. Displays the current PAULCON condition.
        Subcommands: set"""
        if not args:
            msg, color = self.LEVEL_MSG[self.cur_level]
            ann = '\x02{1}PAULCON {2}\x02\x03: \x0311{3}'.format(self.cur_time, color, self.cur_level, msg)
            self.irch.say(ann, dst)
        else:
            if len(args.split()) != 2:
                raise PluginBase.InvalidSyntax
            
            subcmd, args = args.split(' ', 1)
            if subcmd == 'set':
                self.subcommand_paulcon_set(user, dst, args)
            
    def subcommand_paulcon_set(self, user, dst, args):
        """PAULCON levels range from 0 to 9.
        Syntax: {0}paulcon set <number>"""
        try:
            number = int(args)
        except ValueError:
            raise PluginBase.InvalidArgs

        if number < 0 or number > 9:
            raise PluginBase.InvalidArguments
        
        self.cur_level = number
        self.cur_time = datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M')
        
        self.irch.say('PAULCON has been set to {0}{1}{0}'.format(BOLD, number), dst)
        
    def command_earthquake(self, user, dst, args):
        """Returns the most recent high magnitude earthquake."""
        url = 'http://www.seismi.org/api/eqs?limit=1'
        try:
            r = requests.get(url)
            
            data = json.loads(r.text)
            
            for eq in data['earthquakes']:
                self.irch.say('\x02\x034(EARTHQUAKE)\x02\x03 Magnitude \x02{1}\x02 earthquake in ' \
                              '{2} \x0311[{0}]\x03.'.format(eq['timedate'], eq['magnitude'], eq['region']), dst)
            
            #self.irch.say('\x02\x034(EARTHQUAKE) \x02\x03{0}'.format(title), dst)
        except requests.ConnectionError:
            return
        
    def command_happening(self, user, dst, args):
        """Checks if there's any happening."""
        if args:
            args = args.split()
            if len(args) < 2:
                raise PluginBase.InvalidSyntax
            if args[0] == 'monitor':
                self.subcommand_happening_monitor(user, dst, args[1])
        else:
            reply = self.get_happening()
            if not reply:
                reply = '\x0311Nothing is happening.\x03'
            self.irch.say(reply, dst)
        
    def subcommand_happening_monitor(self, user, dst, args):
        """Monitors and notifies of new happenings.
        Syntax: <on|off>"""
        if args == 'on':
            self.happening_dst = dst
            self.happening_last = ''
            self.hook(self.monitor_happening, 12)
            self.irch.say('\x0311Happening monitor enabled.', dst)
        elif args == 'off':
            self.unhook(self.monitor_happening)
            self.irch.say('\x0311Happening monitor disabled.', dst)
        else:
            raise PluginBase.InvalidSyntax
    
    def monitor_happening(self):
        reply = self.get_happening()
        if self.happening_last == reply:
            return
        if reply:
            self.irch.say(reply, self.happening_dst)
            self.happening_last = reply
    
    def get_happening(self):
        try:
            reply = False
            url = 'http://rt.com'
            
            req = requests.get(url)
            req.encoding = 'utf-8'
            
            soup = BeautifulSoup(req.text)
            btag = soup.find('div', attrs={'class': 'rubric breaking_news mainhw'})
            
            if btag:
                btag = btag.find('div', attrs={'class': 'marquee'})
                path = btag.contents[1]['href']
                hline = btag.contents[1].string
                
                reply = u'\x02\x034(HAPPENING)\x03\x02 {0} | \x0311{1}'.format(hline, url + path)
            
            return reply
        except requests.ConnectionError:
            return False