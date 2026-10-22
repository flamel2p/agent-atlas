"""Host-owned grammar, state transition, and stable course-guide composition.

The gate recognizes a finite English grammar. It blocks unsupported or mixed
instructions before any store opens. The pure policy consumes a scoped snapshot.
The composer can render only a validated response plan and packaged facts.
"""

from dataclasses import dataclass
from importlib.resources import files
import json
import re

from .domain import (
    Choosing, Closed, Detail, Focused, Intent, LessonStyle, Ready, ResponsePlan, Snapshot,
)


@dataclass(frozen=True)
class Course:
    id: str
    title: str
    hours: int
    prerequisites: str
    description: str
    aliases: tuple[str, ...]


def _catalogue() -> tuple[Course, ...]:
    data = json.loads(files("conversational").joinpath("data/courses.json").read_text())
    return tuple(Course(**(row | {"aliases": tuple(row["aliases"])})) for row in data)


COURSES = _catalogue()
BY_ID = {course.id: course for course in COURSES}
ALIASES = {alias: course.id for course in COURSES for alias in course.aliases}
COURSE_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(a) for a in sorted(ALIASES, key=len, reverse=True)) + r")\b")
TRIGGERS = ("ignore previous", "change your persona", "act as", "system prompt", "weather", "stock price")
SIMPLE = {
    "help": "help", "hello": "help", "hi": "help",
    "list courses": "list", "courses": "list", "what courses are available": "list",
    "goodbye": "close", "bye": "close", "quit": "close", "recap": "recap",
}
FOLLOWUPS = {
    "tell me more": Detail.OVERVIEW, "tell me about it": Detail.OVERVIEW,
    "overview": Detail.OVERVIEW, "how long is it": Detail.DURATION,
    "how long does it take": Detail.DURATION, "duration": Detail.DURATION,
    "prerequisites": Detail.PREREQUISITES,
    "what are the prerequisites": Detail.PREREQUISITES,
    "what does it require": Detail.PREREQUISITES,
}
TEMPLATES = {
    "<courses>": Detail.OVERVIEW, "tell me about <courses>": Detail.OVERVIEW,
    "what is <courses>": Detail.OVERVIEW, "what are <courses>": Detail.OVERVIEW,
    "overview of <courses>": Detail.OVERVIEW,
    "how long is <courses>": Detail.DURATION, "how long are <courses>": Detail.DURATION,
    "how long does <courses> take": Detail.DURATION,
    "duration of <courses>": Detail.DURATION, "<courses> duration": Detail.DURATION,
    "what is the duration of <courses>": Detail.DURATION,
    "what are the prerequisites for <courses>": Detail.PREREQUISITES,
    "prerequisites for <courses>": Detail.PREREQUISITES,
    "<courses> prerequisites": Detail.PREREQUISITES,
    "what do i need for <courses>": Detail.PREREQUISITES,
}
STYLE = re.compile(r"(?:remember lesson style|set lesson style|use|actually use) (short|standard)(?: lessons)?\Z")
CHOICES = {"1": 1, "first": 1, "the first": 1, "2": 2, "second": 2, "the second": 2,
           "3": 3, "third": 3, "the third": 3, "4": 4, "fourth": 4}


def parse(text: str) -> Intent | None:
    """Return an authorized intent or gate rejection. No user text is retained."""
    text = " ".join(text.casefold().strip().split()).rstrip("?!.")
    if any(trigger in text for trigger in TRIGGERS):
        return None
    if text in SIMPLE:
        return Intent(SIMPLE[text])
    if text in FOLLOWUPS:
        return Intent("detail", detail=FOLLOWUPS[text])
    if text in CHOICES:
        return Intent("choice", choice=CHOICES[text])
    if match := STYLE.fullmatch(text):
        return Intent("style", style=LessonStyle(match[1]))
    courses = tuple(dict.fromkeys(ALIASES[match[0]] for match in COURSE_PATTERN.finditer(text)))
    substituted = COURSE_PATTERN.sub("<course>", text)
    substituted = re.sub(r"<course>(?:(?: (?:and|or) |, ?)<course>)*", "<courses>", substituted)
    if courses and substituted in TEMPLATES:
        return Intent("detail", courses=courses, detail=TEMPLATES[substituted], bare_course=substituted == "<courses>")
    return None


def transition(snapshot: Snapshot, intent: Intent) -> ResponsePlan:
    """Resolve focus and clarification without model authority or mutable state."""
    state = snapshot.state
    if isinstance(state, Closed):
        return ResponsePlan("already_closed", state, "already_closed")
    if intent.kind == "close":
        return ResponsePlan("session_closed", Closed(), "closed")
    if intent.kind == "style":
        return ResponsePlan("preference_updated", state, "style", save_style=intent.style)
    if intent.kind == "help":
        return ResponsePlan("answered", state, "help")
    if intent.kind == "list":
        return ResponsePlan("answered", Choosing(tuple(BY_ID), Detail.OVERVIEW), "list")
    if intent.kind == "recap":
        course_ids = tuple(dict.fromkeys(turn.course_id for turn in snapshot.recent if turn.course_id))
        return ResponsePlan("answered", state, "recap", recap=course_ids)
    if intent.kind == "choice":
        if isinstance(state, Choosing) and intent.choice and intent.choice <= len(state.candidates):
            course_id = state.candidates[intent.choice - 1]
            return ResponsePlan("answered", Focused(course_id), "detail", course_id, state.detail)
        return ResponsePlan("clarification", state, "invalid_choice" if isinstance(state, Choosing) else "no_choice",
                            candidates=state.candidates if isinstance(state, Choosing) else ())
    if len(intent.courses) > 1:
        return ResponsePlan("clarification", Choosing(intent.courses, intent.detail), "choose", candidates=intent.courses)
    if len(intent.courses) == 1:
        course_id = intent.courses[0]
        if isinstance(state, Choosing) and intent.bare_course and course_id in state.candidates:
            return ResponsePlan("answered", Focused(course_id), "detail", course_id, state.detail)
        # An explicit course always replaces old focus or a pending request.
        return ResponsePlan("answered", Focused(course_id), "detail", course_id, intent.detail)
    if isinstance(state, Focused):
        return ResponsePlan("answered", state, "detail", state.course_id, intent.detail)
    if isinstance(state, Choosing):
        return ResponsePlan("clarification", state, "choose", candidates=state.candidates)
    return ResponsePlan("clarification", Ready(), "no_focus")


def compose(plan: ResponsePlan, style: LessonStyle) -> str:
    """Render host facts only. Stable prefix defines this demo's course-guide persona."""
    titles = lambda ids: "; ".join(f"{index}. {BY_ID[cid].title}" for index, cid in enumerate(ids, 1))
    messages = {
        "help": "Ask about a course, duration, or prerequisites. You can list courses, save lesson style, recap, or say goodbye.",
        "list": titles(tuple(BY_ID)),
        "closed": "This session is closed. Start a new session to continue.",
        "already_closed": "This session is already closed. Start a new session to continue.",
        "style": "Your lesson style preference is saved.",
        "no_choice": "There is no pending choice. Name a course or list courses.",
        "no_focus": "Which course do you mean? Name a course or list courses.",
        "choose": "Choose one course by number or name. " + titles(plan.candidates),
        "invalid_choice": "Choose a number from the pending courses. " + titles(plan.candidates),
        "recap": "Recent course discussion: " + (", ".join(BY_ID[cid].title for cid in plan.recap) or "none in the last four completed turns") + ".",
    }
    if plan.kind == "detail":
        course = BY_ID[plan.course_id]
        if plan.detail == Detail.DURATION:
            message = f"{course.title} takes {course.hours} hours."
        elif plan.detail == Detail.PREREQUISITES:
            message = f"{course.title} prerequisites: {course.prerequisites}"
        elif style == LessonStyle.SHORT:
            message = f"{course.title}, {course.hours} hours."
        else:
            message = f"{course.title}: {course.description} Duration: {course.hours} hours. Prerequisites: {course.prerequisites}"
    else:
        message = messages[plan.kind]
    return "Course guide: " + message
