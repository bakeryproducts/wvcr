from __future__ import annotations

from loguru import logger
from google import genai
from google.genai import types

MODEL = "gemini-3.7-flash"

_BASE = """You are a live assistant listening to a conversation.
The audio mixes my voice with other participants.

FOCUS: I pressed the hint button, this instant, because I need
help with what is being said AT LAST!!! REST OF THE AUDIO IS JUST A CONTEXT.  I NEED ASSISTANCE AT THE END OF AUDIO.
Anchor entirely on the last sentence or phrase at the very end of the clip. 
If the topic changed partway through the audio, ignore the earlier topic completely - only the
final moment matters, no matter how brief it was.
"""

_FORMAT = """
FORMAT:
- No preamble, no restating what was said, no meta-commentary about the audio.
- Russian only.
- Plain text, no markdown.
- Short sentences, one per line, separated by \\n.
"""

PROMPTS: dict[str, str] = {
    "hint": _BASE
    + """TASK: Give me one immediately useful hint about that exact topic - a fact,
number, name, definition, risk, counterargument, or next step I can act on.
Always surface something useful, even with no explicit question asked.
Never just ask a question back, and never say there is nothing to add - if
the topic is unclear, give the most useful info about the closest thing you
can identify from the last moment of audio.
"""
    + _FORMAT,
    "gps": _BASE
    + """TASK: I gave you a GOAL for this conversation (see CONTEXT below, if
provided). Judge where the conversation currently stands relative to that
goal. If it has drifted, tell me how to steer it back and through which
topic. If it is on track, tell me the next concrete step toward the goal.
Be directive, like a navigator giving the next turn.
"""
    + _FORMAT,
    "bestmove": _BASE
    + """TASK: Infer the most useful next thing for me to say right now, without
any predefined goal - infer the implicit objective from what has been said
so far (what the other participant seems to want or need). Give me the
single best next move: a question, a statement, or an offer.
"""
    + _FORMAT,
    "explain": _BASE
    + """TASK: I just tried to explain something and did it poorly - my
explanation was confusing, circular, or incomplete. Rewrite that
explanation properly: break it down into a short numbered list of clear
steps or points, and include one concrete analogy if it helps.
"""
    + _FORMAT,
    "spravochnik": _BASE
    + """TASK: Identify the last concrete term, name, or fact mentioned and give
a thorough, encyclopedia-style reference entry on it, like a detailed wiki
article - what it is, its origin or background, key numbers/dates/names,
how it relates to the surrounding conversation, and any other factual
detail a well-read person would know. Prioritize being information-dense
and factual over being brief; several lines are expected, not just one or
two.
"""
    + _FORMAT,
    "factcheck": _BASE
    + """TASK: Take the last concrete factual claim or statement made (mine or
the other participant's) and fact-check it using search. State clearly
whether it is TRUE, FALSE, or PARTLY TRUE/MISLEADING, then give the
correct facts with sources of information (numbers, dates, names) that support
your verdict. If no checkable factual claim was made, say so and fact-check
the closest verifiable claim in the recent audio instead.
"""
    + _FORMAT,
    "question": _BASE
    + """TASK: I don't fully understand what the other participant just said or
meant. Give me one sharp clarifying question I could ask them right now to
better understand their point.
"""
    + _FORMAT,
}

MODE_META: dict[str, tuple[str, str]] = {
    "hint": ("\U0001F4A1", "Hint"),
    "gps": ("\U0001F9ED", "GPS"),
    "bestmove": ("\u265F", "BestMove"),
    "explain": ("\U0001F4CB", "BetterExplain"),
    "spravochnik": ("\U0001F4D6", "Spravochnik"),
    "factcheck": ("\U0001F50D", "FactCheck"),
    "question": ("\u2753", "Question"),
}


def get_hint(
    mode: str,
    audio_bytes: bytes,
    api_key: str,
    context: str | None = None,
    mime_type: str = "audio/mp3",
) -> str:
    prompt = PROMPTS.get(mode, PROMPTS["hint"])
    if context:
        prompt = f"{prompt}\nCONTEXT (provided by me ahead of time):\n{context}\n"
    client = genai.Client(api_key=api_key)
    tools = [types.Tool(google_search=types.GoogleSearch())]

    logger.debug(f"HINT PROMPT:\n{prompt}")

    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MEDIUM,
            ),
            tools=tools,
        ),
        contents=[
            prompt,
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ],
    )
    text = getattr(response, "text", None) or ""
    logger.debug(f"hint[{mode}] received {len(text)} chars")
    return text.strip()
