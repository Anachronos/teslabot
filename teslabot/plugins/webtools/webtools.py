from pluginbase import PluginBase
from HTMLParser import HTMLParser
from random import randint
import logging
import requests
import re
try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup
import json

class WebTools(PluginBase):
    """WebTools provides commands for quickly extracting information from websites such as
    dictionaries and encyclopedias.
    
    TODO:
        Replace REGEX with BeautifulSoup.
    """
    def __init__(self):
        PluginBase.__init__(self)
        self.name = 'WebTools'
        self.logger = logging.getLogger('teslabot.plugin.webtools')
        
    def on_channel_message(self, user, channel, msg):
        for word in msg.split():
            if word[:7] == 'http://' or word[:8] == 'https://':
                title = self.url_title(word)
                if title:
                    self.irch.say(title, channel.name)
        
    def url_title(self, url):
        """Extracts the HTML title of a given URL.
        
        Args:
            url: a valid HTTP url
        
        Returns:
            An escaped title. 
            If the title was not found, it returns None.
        """
        req = requests.get(url)
        req.encoding = 'utf-8'
        text = req.text
        
        tag_start = '<title>'
        tag_end = '</title>'
        
        start = text.find(tag_start)
        end = text.find(tag_end)
        
        if start != -1 and end != -1:
            title = req.text[start+len(tag_start):end]
            h = HTMLParser()
            return h.unescape(title).strip()
        else:
            return None
        
    def format_text(self, text):
        """Removes HTML and truncates the text for chat output."""
        h = HTMLParser()
        text = h.unescape(text)
        
        text = re.sub('<[^>]+?>', '', text)
        text = text.replace('\r\n', ' ')
        text = text.replace('\r', ' ')
        
        # Arbitrarily limit the message to 400 bytes to fit in one send.
        if len(text) > 400 and text.count('.') > 0:
            i = lastx = 0
            for x in text:
                if x == '.':
                    lastx = i
                if i > 400:
                    text = text[:lastx+1]
                    break
                i += 1
        return text
    
    def command_translate(self, user, dst, args):
        """Syntax: {0}translate <language> <text>, where <language> is the desired translation."""
        lang = text = ''
        
        try:
            lang, text = args.split(' ', 1)
        except (ValueError, AttributeError) as e:
            raise self.InvalidSyntax
            
        headers = {'user-agent': 'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET ' \
                   'CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.04506.30)'}
        url = u'http://translate.google.com/m?tl={0}&sl={1}&q={2}'.format(lang, 'auto', text.replace(' ', '+'))
        r = requests.get(url, headers=headers)
        
        start = '<div dir="ltr" class="t0">'
        end = '</div>'
        
        text = r.text.split(start, 1)[1].split(end, 1)[0]
        self.irch.say(self.format_text(text), dst)
        
    def command_geoip(self, user, dst, args):
        """Syntax: {0}geoip <ip|domain>"""
        if len(args.split()) > 1:
            raise PluginBase.InvalidSyntax
        
        req = requests.get('http://freegeoip.net/csv/{0}'.format(args))
        req.encoding = 'utf-8'
        text = req.text
        
        print text

        if text.find(',') != -1:
            country = text.split(',')[2]
            city = text.split(',')[4][1:][:-1]
            country = country[1:][:-1]
            
            if len(city):
                reply = u'IP address {0} originates from {1}, \x02{2}\x02.'.format(args, city, country)
            else:
                reply = u'IP address {0} originates from \x02{1}\x02.'.format(args, country)

            self.irch.say(reply, dst)
        else:
            self.irch.say(text, dst)
            
    def command_def(self, user, dst, args):
        """Syntax: {0}def [source] [word]
        Available sources: u (urban dictionary), d (dictionary)
        """
        if len(args.split()) < 2:
            raise PluginBase.InvalidSyntax
        
        source, phrase = args.split(' ', 1)
        if source == 'u':
            self.subcommand_def_urbdict(user, dst, phrase)
        elif source == 'd':
            self.subcommand_def_dict(user, dst, phrase)

    def subcommand_def_dict(self, user, dst, phrase):
        html = requests.get('http://www.wordnik.com/words/{0}'.format(phrase)).text
        soup = BeautifulSoup(html)
            
        reply = []
        type_count = {'n': 0, 'v': 0, 'adj': 0, 'pro': 0, 'interj': 0, 'adv': 0, 'idiom': 0}
            
        ans = soup.find('ol', attrs={'class': 'definitions'})
        if ans:
            for i in ans:
                if i == '\n':
                    continue
                wtype = i.contents[0].find('abbr').string[:-1]
                if wtype:
                    if type_count[wtype] > 0:
                        continue
                    desc = i.contents[0].find('em')
                    if desc:
                        newdef = []
                        lblock = i.contents[0].findAll(text=True)
                        for x in lblock:
                            if x != ' ':
                                newdef.append(x)
                        defin = u' '.join([x.strip() for x in newdef])
                        defin = defin.replace(desc.string, u'\x0312{0}\x03'.format(desc.string))
                        defin = defin.replace(wtype, u'\x038{0}\x03'.format(wtype), 1)
                        reply.append(defin)
                    else:
                        defin =  u''.join(i.findAll(text=True)[1:])
                        reply.append(u'\x038{0}\x03.{1}'.format(wtype, defin))
                    type_count[wtype] = 1
                
            self.irch.say(u'\x038[Dictionary] \x03\x02{0}\x02: {1}'.format(phrase, u' \x02\x0311|\x03\x02 '.join(reply)), dst)
        else:
            self.irch.say(u'Definition not for \x02{0}\x02 not found.'.format(phrase), dst)

    def subcommand_def_urbdict(self, user, dst, args):
        r = requests.get(u'http://api.urbandictionary.com/v0/define?term={0}'.format(args))
        r.encoding = 'utf-8'

        decoded = json.loads(r.text)
        ans = u'\x037[UrbDict]\x03 \x032{0}:\x03 {1} (\x0308{2}\x03\u2191\x0308{3}\x03\u2193)'

        if decoded.get('list'):
            for item in decoded['list']:
                definition = self.format_text(item['definition'])

                ans = ans.format(item['word'], definition, item['thumbs_up'],
                           item['thumbs_down'])
                break

        if decoded.get('result_type') == 'exact':
            self.irch.say(ans, dst)
        else:
            self.irch.say('\x038[UrbanDictionary]\x03 Definition not found.', dst)
    
    def command_news(self, user, dst, args):
        """Displays random news headlines from US newspapers.
        Optional syntax: [top]
        """
        # TODO: Replace REGEX with BeautifulSoup
        try:
            req = requests.get('http://google.com/news?vanilla=1').text

            match = re.findall(r'<span class="titletext">(.+?)</div>', req)
    
            if not args:
                rand = randint(0, len(match) - 1)
                match = match[rand]
    
                match2 = re.search(r'<label class="esc-[a-z]*-article-source">(.+?)</label>', match)
    
                if match2:
                    print match2.group()
                    match = match.replace(match2.group(), ' \x02[' + match2.group() + '\x02]')
    
                self.irch.say(self.format_text(match), dst)
            elif args == 'top':
                self.irch.say(self.format_text('\x037(LEADING)\x03 ' + match[0]), dst)
        except requests.ConnectionError:
            return