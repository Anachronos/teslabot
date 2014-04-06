# -*- coding: utf-8 -*-

"""
Run from 'teslabot' dir with
    python -m plugins.trivia.tests
"""

from trivia import Trivia
from questions import Question


class TriviaTests:
    def __init__(self):
        self.t = Trivia()

    def test_questions_loaded(self):
        assert(len(self.t.questions) > 0)

    def test_is_correct_answer_simple(self):
        self.t.q = Question("Test category",
                            "Test question?",
                            "Test answer",
                            None)
        assert(self.t.is_correct_answer("Test answer"))

    def test_is_correct_answer_substring(self):
        self.t.q = Question("Test category",
                            "Test question?",
                            "Test #answer#",
                            None)
        assert(self.t.is_correct_answer("answer"))

    def test_is_correct_answer_regex(self):
        self.t.q = Question("Test category",
                            "Test question?",
                            "Test regex answer",
                            "Test regex(p)? answer")

        assert(self.t.is_correct_answer("Test regex answer"))
        assert(self.t.is_correct_answer("test regexp answer"))


if __name__ == '__main__':
    tests = TriviaTests()

    tests.test_questions_loaded()
    tests.test_is_correct_answer_simple()
    tests.test_is_correct_answer_substring()
    tests.test_is_correct_answer_regex()
