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
from config import Config, ConfigParser
import datetime, time
from urlparse import urlparse

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

        # Load imageboard URL parser settings
        try:
            self.imageboard_urls = Config().get(self.name.lower(), 'imageboard').split()
        except ConfigParser.NoSectionError:
            self.logger.debug('Imageboard settings not found.')
            self.imageboard_urls = []

        self.news = {
            'lupdate': None,
            'uinterval': 60*5,
            'cur_ed': 'us',
            'set': False,
        }
        self.strings.URL_GOOGLE = 'https://news.google.com/news?edchanged=1&ned={0}&authuser=0'
        self.strings.URL_GOOGLE_SEARCH = 'https://www.google.com/search?hl=en&gl=us&tbm=nws&authuser=0&q={0}'
        self.strings.NO_NEWS_SET = 'There is no news set currently selected. Type news help ' \
            'for more information.'
        self.strings.KEYWORD_NOT_FOUND = 'No news items found.'
        self.strings.NEWS_SET_REFRESHED = 'The news set has been updated!'

    def on_channel_message(self, user, channel, msg):
        """Provides meta information of URLs in a given channel message."""
        for word in msg.split():
            if word[:7] == 'http://' or word[:8] == 'https://':
                parsed_url = urlparse(word)
                domain = parsed_url.netloc
                pattern = '{0}/{1}/res/{1}'.format(domain, '.+')

                if domain in self.imageboard_urls and re.findall(pattern, word):
                    self.handle_imgboard_url(user, channel, word, domain)
                else:
                    desc = self.handle_http_url(word)
                    self.irch.say(desc, channel.name)

    def handle_http_url(self, url):
        r = requests.get(url)

        if r.status_code == 200:
            if r.headers['content-type'].count('text/html'):
                r.encoding = 'utf-8'
                soup = BeautifulSoup(r.text)
                title = soup.title.text

                return self.format_text(title)
            else:
                return u'Content-Type: {0} | Content Length: {1} KiB'.format(
                    r.headers['content-type'],
                    int(r.headers['content-length']) / 1024
                )
        else:
            return u'HTTP Error Code: {0}'.format(r.status_code)

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
        return text.strip()
    
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
        """Retrieves the latest news from around the world.
        Example: {0}news (Alias for {0}news next)
        Syntax: {0}news [random|refresh|metadata]
        Subcommands: filter, summary, next, find
        Type {0}news <subcommand> help for more information.
        """
        params = ['random', 'refresh', 'metadata']
        force_refresh = False

        if len(args.split()) > 0 and args.split()[0] not in params:
            s_args = args.split()

            if s_args[0] == 'find': # This subcommand requires no news set
                self.subcommand_news_find(user, dst, ' '.join(s_args[1:]))
            elif not self.news['set']:
                self.irch.say(self.strings.NO_NEWS_SET, dst)
            elif s_args[0] == 'filter':
                self.subcommand_news_filter(user, dst, ' '.join(s_args[1:]))
            elif s_args[0] == 'next':
                self.subcommand_news_next(user, dst, ' '.join(s_args[1:]))
            elif s_args[0] == 'summary':
                self.subcommand_news_summary(user, dst, ' '.join(s_args[1:]))
            else:
                raise PluginBase.InvalidSyntax
        else:
            if self.news['lupdate']:
                if time.time() - self.news['lupdate'] > self.news['uinterval']:
                    force_refresh = True

            if args == 'refresh' or not self.news['set'] or force_refresh:
                # Build an unfiltered news set from Google News HTML,
                # either when there is currently no news set, or
                # when the argument 'refresh' is given.
                try:
                    r = requests.get(
                        self.strings.URL_GOOGLE.format(self.news['cur_ed'])
                    )
                except requests.ConnectionError:
                    self.irch.say(self.strings.CONNECTION_ERROR, dst)
                    return

                self.news['lupdate'] = time.time()

                r.encoding = 'utf-8'
                soup = BeautifulSoup(r.text)

                titles = soup.find_all(class_='titletext')
                top_headlines = []
                side_headlines = []

                for item in titles:
                    url = item.parent['url']
                    title = item.text
                    summary = None
                    timestamp = None
                    source = None

                    # Filter out certain invalid titles
                    if u'sngltn' in item.parent.parent.parent['class']:
                        continue

                    if u'title' in item.parent.parent['class']:
                        source_tag = item.parent.parent.next_sibling
                        source = source_tag.contents[0].text
                        timestamp = source_tag.contents[2].text

                        side_headlines.append([title, timestamp, source, url])

                    elif u'esc-lead-article-title-wrapper' in item.parent.parent.parent['class']:
                        root = item.parent.parent.parent
                        source_tag = root.next_sibling
                        try:
                            summary = source_tag.next_sibling.text
                        except AttributeError:
                            pass

                        source = source_tag.find(class_='al-attribution-source').text
                        timestamp = source_tag.find(class_='al-attribution-timestamp').text[1:-1]

                        top_headlines.append([title, timestamp, source, url, summary])

                summaries = soup.find_all(class_='esc-lead-snippet-wrapper')

                for i in range(0, len(summaries)):
                    top_headlines[i][4] = summaries[i].text # Set summary to corresponding item

                self.news['set'] = NewsSet(name='US News', set_=top_headlines + side_headlines)

            if args == 'random':
                self.irch.say(self.news['set'].random(), dst)
            elif args == 'refresh':
                self.irch.say(self.strings.NEWS_SET_REFRESHED, dst)
            elif args == 'metadata' and self.news['set']:
                self.irch.say(unicode(self.news['set']), dst)
            elif not args:
                self.subcommand_news_next(user, dst, u'')

    def subcommand_news_filter(self, user, dst, args):
        """
        Filters the current news set by a given keyword and returns the
        first result of this news set.
        {0}news filter <keyword>
        """
        if not args:
            raise PluginBase.InvalidSyntax

        result = self.news['set'].filter(args)

        if len(result) > 0:
            self.news['set'] = result
            self.irch.say(self.news['set'].get(), dst)
        else:
            self.irch.say(self.strings.KEYWORD_NOT_FOUND, dst)


    def subcommand_news_find(self, user, dst, args):
        """Queries Google News for the first page of news results
        for a given keyword.
        Syntax: {0}news find <keyword>
        """
        if not user.admin:
            raise PluginBase.InvalidPermission
        try:
            # TODO: Consider the safety of directly placing user input
            r = requests.get(self.strings.URL_GOOGLE_SEARCH.format(args))
        except requests.ConnectionError:
            self.irch.say(self.strings.CONNECTION_ERROR, dst)
            return

        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text)

        titles = soup.find_all(class_='r')
        search_set = []

        for tag in titles:
            url = tag.contents[0].attrs['href'].split('=', 1)[1]
            title = tag.text
            parent = tag.parent
            source, timestamp = parent.find(class_='f').text.split(' - ')
            summary = parent.find(class_='st').text

            search_set.append([title, timestamp, source, url, summary])

        if len(search_set) > 0:
            self.news['set'] = NewsSet(name='Search: {0}'.format(args), set_=search_set)
            self.irch.say(self.news['set'].get(), dst)
        else:
            self.irch.say(self.strings.KEYWORD_NOT_FOUND, dst)

    def subcommand_news_next(self, user, dst, args):
        """Returns the next news item in the currently selected news set.
        Syntax: {0}news next
        """
        if args:
            raise PluginBase.InvalidSyntax

        if self.news['set']:
            self.news['set'].next()
            self.irch.say(self.news['set'].get(), dst)

    def subcommand_news_summary(self, user, dst, args):
        """Returns the summary of the currently selected news item.
        Syntax: {0}news summary
        """
        if args:
            raise PluginBase.InvalidSyntax

        if self.news['set']:
            self.irch.say(self.news['set'].get(True), dst)

class NewsSet:
    """A quasi-list with a cursor that points to an item in the list.
    Represents a set of news articles.
    """
    def __init__(self, name=None, set_=None):
        self._list = []
        self._name = name
        self._cursor = -1 # A "pointer" to a NewsItem

        if set_:
            for item in set_:
                self.push(NewsItem(*item))

    def __unicode__(self):
        return u'[{0} | {1} items]'.format(self._name, self.__len__())

    def filter(self, keyword):
        """Returns a NewsSet with items that match the given keyword."""
        result = NewsSet(u'Keyword: {0}'.format(keyword))

        for i in range(len(self._list)):
            if keyword.lower() in self._list[i].title.lower():
                result.push(self._list[i])

        return result

    def get(self, summary=False):
        """Returns the NewsItem pointed by the cursor."""
        if self.__len__():
            if summary:
                return self._list[self._cursor].summary
            else:
                return unicode(self._list[self._cursor])
        else:
            return u'[{0}] Empty news list.'.format(self._name)

    def random(self):
        """Returns a random item (unicode) from the list."""
        n = randint(0, self.__len__() - 1)
        self._cursor = n

        return self.get()

    def push(self, news_item):
        self._list.append(news_item)

    def pop(self, news_item):
        self._list.pop()

    def next(self):
        """Moves the cursor to the next item.
        If the cursor is already at the last time, the cursor will return
        to the first item."""
        if self._cursor < len(self._list) - 1:
            self._cursor += 1
        else:
            self._cursor = 0

    def __len__(self):
        return len(self._list)


class NewsItem:
    """Encapsulates a news item from Google News."""
    def __init__(self, title, timestamp, source, url, summary=None):
        self._title = title
        self._summary = summary
        self._timestamp = timestamp
        self._source = source
        self._url = url

        self.SUMMARY_FMT = u'\u275D{0}\u275E \u00AB {1} \u00BB \u2043\u2043 {2} \u2043\u2043 \x0315{3}'
        self.NONSUMMARY_FMT = u'\u275D{0}\u275E \u00AB {1} \u00BB | \x0315{2}'

    @property
    def summary(self):
        if self._summary:
            return self._summary
        else:
            return u'No summary available.'

    @summary.setter
    def summary(self, value):
        self._summary = value

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    def __unicode__(self):
        return self.NONSUMMARY_FMT.format(
            self._title, self._timestamp, self._url
        )

    def get(self, summary=True):
        return self.SUMMARY_FMT.format(
            self._title, self._timestamp, self._summary, self._url
        )

