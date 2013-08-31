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
from config import Config
import datetime

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

        self.imageboard_urls = Config().get(self.name.lower(), 'imageboard').split()

    def on_channel_message(self, user, channel, msg):
        for word in msg.split():
            if word[:7] == 'http://' or word[:8] == 'https://':
                domain = self.get_domain(word)
                pattern = '{0}/{1}/res/{1}'.format(domain, '.+')

                if domain in self.imageboard_urls and re.findall(pattern, word):
                    self.handle_imgboard_url(user, channel, word, domain)
                else:
                    title = self.url_title(word)
                    if title:
                        self.irch.say(title, channel.name)

    def handle_imgboard_url(self, user, channel, url, domain):
        """Parses an imageboard url."""
        url = url.split('/')
        board = url[3]
        post = None

        # If the URL points to a post inside the thread
        if url[-1].find('#') != -1:
            thread = url[-1].split('#')[0].split('.')[0]
            post = int(''.join([x for x in url[-1].split('#')[1] if x.isdigit()]))
        else:
            thread = url[-1].split('.')[0]

        api = 'http://{0}/{1}/res/{2}.json'.format(domain, board, thread)
        r = requests.get(api)
        r.encoding = 'utf-8'

        if r.text:
            try:
                items = json.loads(r.text)
            except ValueError:
                self.irch.say('404 - Not found.', channel.name)
                return

            item = None

            if not post:
                item = items['posts'][0]
            else:
                for p in items['posts']:
                    if int(p['no']) == post:
                        item = p
                if item is None:
                    self.irch.say('404 - Post Not found.', channel.name)
                    return

            if item:
                reply = '\x032[/{0}/]\x03 \x0310{1}\x03 \x02\x037{2}:\x03\x02 {3}'

                preview = self.format_text(item['com'])
                time = datetime.datetime.fromtimestamp(item['time'])
                time = datetime.datetime.today() - time
                if time.days > 0:
                    time = '{0} days ago'.format(time.days)
                else:
                    if time.seconds < 60:
                        time = '{0} seconds ago'.format(time.seconds)
                    elif time.seconds < 60*60:
                        time = '{0} minutes ago'.format(time.seconds / 60)
                    else:
                        time = '{0} hours ago'.format(time.seconds / (60*60))

                reply = reply.format(board, time, item['name'], preview)

                self.irch.say(reply, channel.name)

        else:
            self.irch.say('404 - Not found.', channel.name)
                
    def get_domain(self, url):
        """Returns the full domain of a given URL."""
        if url[:7] == 'http://':
            spos = 7
        elif url[:8] == 'https://':
            spos = 8

        pos = url[spos:].find('/')

        if pos != -1:
            return url[spos:spos+pos]
        else:
            return url
        
    def url_title(self, url):
        """Extracts the HTML title of a given URL.
        
        Args:
            url: a valid HTTP url
        
        Returns:
            An escaped title. 
            If the title was not found, it returns None.
        """
        try:
            req = requests.get(url)
        except requests.ConnectionError:
            return 'Connection error. Invalid URL or host is down.'
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
        
        text = text.replace('<br>', ' ')
        text = text.replace('<br/>', ' ')
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
            
        ans = soup.find('div', attrs={'class': 'guts active'})
        source = ''
        for h3 in ans.findAll('h3'):
            source = h3.string

            ul = h3.findNextSiblings('ul')
            defList = ul[0].find_all('li')
            for item in defList:
                abbr = item.contents[0].string
                definition = item.contents[1].string

                if abbr is not None and definition is not None:
                    word_type = abbr.replace('.', '')
                    if type_count[word_type] == 0:
                        result = u'{0}.{1}'.format(word_type, definition)
                        reply.append(result)
                        type_count[word_type] = 1
            break
        if reply:
            self.irch.say(u'\x038[Dict]\x03 \x02\x032{0}:\x03\x02 {1}'.format(phrase, u' | '.join(reply), source), dst)
        else:
            self.irch.say(u'\x038[Dictionary]\x03 Definition for \x02{0}\x02 not found.'.format(phrase), dst)

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
