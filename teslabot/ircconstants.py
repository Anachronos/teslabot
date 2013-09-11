"""Reply Numerics"""
RPL_WELCOME = '001'
RPL_YOURHOST = '002'
RPL_CREATED = '003'
RPL_MYINFO = '004'
RPL_BOUNCE = '005'

RPL_MOTD = '372'
RPL_MOTDSTART = '375'
RPL_ENDOFMOTD = '376'

RPL_HOSTHIDDEN = '396'
RPL_WHOISUSER = '311'

RPL_WHOISIDLE = '317'

"""Channel related reply numerics"""
RPL_CHANNELMODEIS = '324'
RPL_TOPIC = '332'
RPL_TOPICWHOTIME = '333'
RPL_NAMREPLY = '353'

RPL_WHOISHOST = '378' # Provides the user's real IP/hostname

RPL_YOUREOPER = '381'


ERR_BANNEDFROMCHAN = '474'
ERR_NICKNAMEINUSE = '433'

"""Error Numerics"""
ERR_NICKNAMEINUSE = '433'

"""Teslabot Constants"""
CHAT_NONE = 0
CHAT_CMD = 1
CHAT_URL = 2

"""IRC Chat Codes"""
BOLD = '\x02'
COLOR = '\x03'
ITALIC = '\x09'
STRIKETHRU = '\0x13'
C_WHITE = '\x030'
C_BLACK = '\x031'
C_BLUE = '\x032'
C_GREEN = '\x033'
C_RED = '\x034'
C_BROWN = '\x035'
C_PURPLE = '\x036'
C_ORANGE = '\x037'
C_YELLOW = '\x038'

lang_001 = '{user} has sent the command {command}.'