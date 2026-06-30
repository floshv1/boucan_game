from scripts.bank import opentriviaqa
from scripts.bank.opentriviaqa import QuestionDraft

SAMPLE = """#Q What is the capital of Italy?
^ Rome
A Venice
B Rome
C Naples
D Milan

#Q What is the capital of Greece?
^ Athens
A Ankara
B Athens
C Sofia
D Thessaloniki
"""


def test_parse_returns_one_draft_per_valid_block():
    drafts = opentriviaqa.parse_category(SAMPLE, "geography", source_url="u")
    assert len(drafts) == 2
    assert drafts[0] == QuestionDraft(
        question="What is the capital of Italy?",
        answer="Rome",
        choices=["Venice", "Rome", "Naples", "Milan"],
        category="geography",
        source_url="u",
    )


def test_parse_skips_block_without_four_choices():
    text = "#Q Q1?\n^ A\nA A\nB B\nC C\n"  # only 3 choices
    assert opentriviaqa.parse_category(text, "general") == []


def test_parse_skips_block_when_answer_not_in_choices():
    text = "#Q Q1?\n^ Zzz\nA A\nB B\nC C\nD D\n"
    assert opentriviaqa.parse_category(text, "general") == []


def test_parse_joins_multiline_question():
    text = "#Q Line one\nstill the question\n^ A\nA A\nB B\nC C\nD D\n"
    drafts = opentriviaqa.parse_category(text, "general")
    assert len(drafts) == 1
    assert drafts[0].question == "Line one still the question"


def test_category_url():
    assert opentriviaqa.category_url("geography") == opentriviaqa.RAW_BASE + "/geography"
