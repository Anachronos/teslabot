# -*- coding: utf-8 -*-

from __future__ import division
from math import ceil

from pluginbase import PluginBase
from questions import load_questions

import logging
import re
import random
import os.path
from config import Config, ConfigParser


class Trivia(PluginBase):
    """Trivia plays a trivia game in the trivia channel. It asks questions in the
    channel and keeps tracks of everyone's scores.

    To start: .trivia
    To stop: .strivia
    """
    def __init__(self):
        PluginBase.__init__(self)
        self.name = 'Trivia'
        self.logger = logging.getLogger('teslabot.plugin.trivia')
        self.alive = True

        try:
            self.channel = Config().get(self.name.lower(), 'channel')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.logger.warn('Unable to load trivia plugin. Channel name is missing.')
            # This ensures this plugin is never called
            self._callbacks = []
            return

        # Number of 5 second intervals between asking a question or giving a hint
        self.askpause = 2
        # Default number of questions to ask in a round
        self.defaultnumquestions = 10

        self.startingmsg = u"Trivia starting. Questions: {0}"
        self.stoppingmsg = u"Trivia stopping."
        self.questionmsg = u"Q{2}. [{0}] {1}"
        self.okanswermsg = u"{0} got it for {1} points. Total: {2}, streak: {3}. " \
                           + u"Answer: {4}"
        self.noanswermsg = u"No one got it. The answer was: {0}"
        self.rankingsmsg = u"{0} wins! Final scores: {1}"
        self.skippingmsg = u'Skipping this terrible question.'
        self.nextvotemsg = u'{0} voted to skip this question. {1} more votes needed.'
        self.roundendmsg = u"Round of trivia complete. '.trivia [number]' to start " \
                           + u"playing again."

        self.questions = load_questions(os.path.abspath('plugins/trivia'))
        self.logger.info("Loaded {0} trivia questions.".format(len(self.questions)))

        self.reset()

    def reset(self):
        self.gamerunning = False
        self.remainingq = self.defaultnumquestions
        self.q = random.choice(self.questions)
        self.qcount = 0
        self.hintlevel = 0
        self.scores = {}  # Key: nick, value: points scored this round
        self.streak = [None, 0]  # [nick, streak] (Would be a tuple but they're immutable)
        self.nextvotes = []  # List of nicks who've voted to skip the current question

    def on_load(self):
        # This function is called before the bot connects to the server
        if self.channel and self.channel != "":
            self.irch._init_channels.append(self.channel)

    def say(self, msg):
        self.irch.say(msg, self.channel)

    def scores_strs(self, limit=None):
        """ Returns a tuple containing the winner's nick and a string with the scores
        of the all players in descending order. """
        sortedscores = sorted(self.scores, key=self.scores.get, reverse=True)
        winner = sortedscores[0] if sortedscores else None

        scoresstr = ""
        for idx, nick in enumerate(sortedscores):
            if not limit or idx < limit:
                scoresstr += "{0} {1}; ".format(nick, self.scores[nick])

        return (winner, scoresstr)

    def end_round(self):
        self.unhook(self.ask)

        (winner, scores) = self.scores_strs()

        if winner:
            self.say(self.rankingsmsg.format(winner, scores))
        self.say(self.roundendmsg)

        self.reset()

    def next_q(self):
        self.hintlevel = 0
        self.nextvotes = []
        self.q = random.choice(self.questions)

        self.remainingq -= 1

        if self.remainingq == 0:
            self.end_round()

    def ask(self):
        """Asks a question or shows a hint."""
        if self.hintlevel == 0:
            self.qcount += 1
            self.hintlevel += 1

            self.logger.debug(u"Asking trivia question: {0}".format(self.q.question))
            self.say(self.questionmsg.format(self.q.category, self.q.question, self.qcount))
        elif self.hintlevel <= 3:
            # Strip all non-alphanum. TODO: handle non-ascii?
            chars = re.sub(r'\W', '', self.q.answer)

            # Show 1/4th, 1/3rd, etc. of the answer
            #numhintchars = ceil(len(chars) / (5 - self.hintlevel))

            # Use custom ratios
            if self.hintlevel == 1:
                numhintchars = ceil(len(chars) * 0.1)
            elif self.hintlevel == 2:
                numhintchars = ceil(len(chars) * 0.35)
            elif self.hintlevel == 3:
                numhintchars = ceil(len(chars) * 0.65)

            hint = ""
            for char in self.q.answer.replace('#', ''):
                if char.isalnum():
                    if numhintchars > 0:
                        hint += char
                        numhintchars -= 1
                    else:
                        hint += '*'
                else:
                        hint += char

            self.say(u"Hint: {0}".format(hint))

            self.hintlevel += 1
        else:
            self.streak = [None, 0]
            self.say(self.noanswermsg.format(self.q.answer.replace('#', '')))
            self.next_q()

    def is_correct_answer(self, guess):
        guess = guess.lower().strip()
        answer = self.q.answer.lower().strip()

        # For answers like "The #Lion# King". (Accept both "Lion" and "The Lion
        # King".)
        if (guess == answer
                or ('#' in answer and guess == answer.split('#')[1])
                or guess == answer.replace('#', '')):
            return True

        if self.q.regex and self.q.regex.match(guess):
            return True

        return False

    def on_channel_message(self, user, channel, msg):
        """Checks all channel msgs to see if they're correct answers."""
        if not self.gamerunning or channel.name.lower() != self.channel.lower():
            return

        if self.is_correct_answer(msg):
            points = 10 - self.hintlevel * 2

            if user.nick == self.streak[0]:
                self.streak[1] += 1
                points = int(ceil(points * (1 + (self.streak[1] - 1) / 2)))
            else:
                self.streak = [user.nick, 1]

            if user.nick in self.scores:
                self.scores[user.nick] += points
            else:
                self.scores[user.nick] = points

            self.say(self.okanswermsg.format(user.nick,
                                             points,
                                             self.scores[user.nick],
                                             self.streak[1],
                                             self.q.answer.replace('#', '')))
            self.next_q()

    # TODO: subcommand for ping

    def command_next(self, user, dst, args):
        """Allows users to vote to skip a question."""
        if (self.gamerunning
                and dst.lower() == self.channel.lower()
                and not user.nick in self.nextvotes
                and self.hintlevel > 0):
            self.nextvotes.append(user.nick)

            votesneeded = min(max(ceil(len(self.scores) / 2), 2), 6)

            if len(self.nextvotes) >= votesneeded:
                self.say(self.skippingmsg)
                self.next_q()
            else:
                votesleft = votesneeded - len(self.nextvotes)
                self.say(self.nextvotemsg.format(user.nick, votesleft))

    def command_tt(self, user, dst, args):
        """Prints top 10 scores."""
        if self.gamerunning and dst.lower() == self.channel.lower():
            scores = self.scores_strs(limit=10)[1]
            if scores != "":
                self.say(scores)

    def command_trivia(self, user, dst, args):
        """Starts the game."""
        # TODO: can't run games in multiple channels. would be a pain to write
        if not self.gamerunning and dst.lower() == self.channel.lower():
            self.gamerunning = True

            try:
                self.remainingq = int(args)

                if self.remainingq < 1:
                    raise
            except:
                self.remainingq = self.defaultnumquestions

            self.say(self.startingmsg.format(self.remainingq))

            self.ask()
            self.hook(self.ask, self.askpause)

    def command_strivia(self, user, dst, args):
        """Stops the current game."""
        if self.gamerunning and dst.lower() == self.channel.lower():
            self.say(self.stoppingmsg)
            self.end_round()
