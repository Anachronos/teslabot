# -*- coding: utf-8 -*-

"""
Read and parse question data files.
"""

import os
import re
import codecs
import logging


class Question:
    def __init__(self, category, question, answer, regex):
        """ All args are strings. """
        self.logger = logging.getLogger('teslabot.plugin.trivia.questions')
        self.category = category
        self.question = question
        self.answer = answer

        if regex:
            try:
                self.regex = re.compile(regex, re.IGNORECASE)
            except Exception:
                self.logger.info('The regex answer ({0}) for the following question was'
                                 + 'uncompilable: {1}'.format(regex, question))
                self.regex = None
                pass
        else:
            self.regex = None


#TODO: make sure the questions are in UTF8 show useful error msg if not
def load_questions(dir, lang="en"):
    """
    Loads all question data files in dir with the extention specified by
    lang. Returns a list of Questions. The answer can have substrings accepted by
    surrounding them with #'s. E.g.

    Question: What is a guitar?
    Answer: An #instrument#

    Questions are expected to be in the format used by Moxquizz, which is a trivia
    bot found at http://moxquizz.de, because that's where our data comes from.

    For more details on the format see the headers of the question data files.

    Expects all question data files to be UTF-8 encoded.
    """
    questions = []

    for root, _, files in os.walk(dir):
        for name in files:
            if not name.endswith("." + lang):
                continue

            f = codecs.open(os.path.join(root, name), "r", "utf-8")

            category, question, answer, regex = (None, None, None, None)

            for line in f:
                if line.find("Category:") == 0:
                    category = line.split("Category: ")[1].strip()

                if line.find("Question:") == 0:
                    question = line.split("Question: ")[1].strip()

                if line.find("Answer:") == 0:
                    answer = line.split("Answer: ")[1].strip()

                if line.find("Regexp:") == 0:
                    regex = line.split("Regexp: ")[1].strip()

                if line.strip() == '':
                    if question and answer:
                        questions.append(Question(category, question, answer, regex))

                    category, question, answer, regex = (None, None, None, None)

            # Read last question
            if question and answer:
                questions.append(Question(category, question, answer, regex))

            f.close()

    return questions
