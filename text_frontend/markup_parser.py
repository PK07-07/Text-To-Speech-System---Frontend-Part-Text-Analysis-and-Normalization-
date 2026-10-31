r"""Markup preprocessing stage (HTML/Markdown/SSML).

Handles:
- Fenced code block dropping with CODE_BLOCK_DROPPED info warning (or preserved via code_block_policy="keep")
- HTML comments stripping: <!-- comment -->text -> text
- Closed <script> and <style> block and content stripping
- Unclosed <script> / <style> tag stripping with UNCLOSED_SCRIPT_TAG warning, keeping remaining text
- Allowlisted HTML tag stripping / converting block tags & <br> to space boundaries
- Inline tags stripped (including <b>unclosed -> unclosed, <img alt="x"> stripped)
- HTML entity decoding (&amp;, &lt;, &gt;, &#39;, &quot;, &nbsp;, numeric) with exact coordinate tracking
- Markdown link extraction: [anchor](url) -> anchor
- Markdown heading prefix stripping: ^#{1,6}\s+
- Inline backtick code spans: `code` -> code
- Paired Markdown emphasis stripping: *text* and _text_ (excluding whitespace-padded)
- SSML preservation in ssml_mode=True; tag stripping in ssml_mode=False
- Strict monotonic coordinate mapping back to original text
"""

from __future__ import annotations

import html
import re

from text_frontend.config import NormalizerConfig
from text_frontend.unicode_utils import MonotonicCoordinateMapper
from text_frontend.validation import NormalizationWarning, PreprocessingEdit

ALLOWLIST_BLOCK_TAGS: frozenset[str] = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
    "blockquote", "section", "article", "header", "footer",
})
ALLOWLIST_BREAK_TAGS: frozenset[str] = frozenset({"br", "hr"})
ALLOWLIST_INLINE_TAGS: frozenset[str] = frozenset({
    "span", "b", "strong", "i", "em", "a", "u", "s", "small", "code", "kbd", "img", "input",
})
DROP_CONTENT_TAGS: frozenset[str] = frozenset({"script", "style"})
SSML_TAGS: frozenset[str] = frozenset({
    "speak", "break", "emphasis", "prosody", "say-as", "voice", "sub",
    "phoneme", "p", "s", "audio", "mark", "lang",
})

HTML_TAG_REGEX = re.compile(r"</?([a-zA-Z][a-zA-Z0-9_-]*)(?:\s+[^>]*)?/?>")
ENTITY_REGEX = re.compile(r"&([a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);")
MD_LINK_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MD_EMPHASIS_ASTERISK_REGEX = re.compile(r"(?<!\w)\*([^\s*](?:.*?[^\s*])?)\*(?!\w)")
MD_EMPHASIS_UNDERSCORE_REGEX = re.compile(r"(?<!\w)_([^\s_](?:.*?[^\s_])?)_(?!\w)")
MD_HEADING_REGEX = re.compile(r"(?m)^#{1,6}\s+")
DROP_TAG_REGEX = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
UNCLOSED_SCRIPT_REGEX = re.compile(r"<(script|style)\b[^>]*>", re.IGNORECASE)
HTML_COMMENT_REGEX = re.compile(r"<!--.*?-->", re.DOTALL)
FENCED_CODE_REGEX = re.compile(r"```[^\n`]*\n?.*?```\n?", re.DOTALL)
INLINE_CODE_REGEX = re.compile(r"`([^`\n]+)`")


def preprocess_markup(
    text: str,
    mapper: MonotonicCoordinateMapper,
    ssml_mode: bool = False,
    config: NormalizerConfig | None = None,
) -> tuple[str, MonotonicCoordinateMapper, tuple[PreprocessingEdit, ...], tuple[NormalizationWarning, ...]]:
    """Strips markup and decodes entities, preserving strict monotonic coordinate mapping."""
    # Fast path: skip processing if no markup triggers exist
    if not any(c in text for c in ("<", "&", "`", "[", "*", "_", "#")):
        return text, mapper, (), ()

    chars: list[str | None] = list(text)
    spans: list[tuple[int, int]] = list(mapper._raw_indices)
    edits: list[PreprocessingEdit] = []
    warnings: list[NormalizationWarning] = []

    # 1. Fenced Code Blocks (``` ... ```)
    if config is None or config.code_block_policy == "drop":
        for m in FENCED_CODE_REGEX.finditer(text):
            s_idx, e_idx = m.start(), m.end()
            raw_s = spans[s_idx][0]
            raw_e = spans[e_idx - 1][1]
            edits.append(
                PreprocessingEdit(
                    original_span=(raw_s, raw_e),
                    output_span=(s_idx, s_idx),
                    category="strip_markup",
                    description="Dropped fenced code block.",
                )
            )
            warnings.append(
                NormalizationWarning(
                    code="CODE_BLOCK_DROPPED",
                    message="Fenced code block dropped by policy.",
                    severity="info",
                    original_span=(raw_s, raw_e),
                )
            )
            for i in range(s_idx, e_idx):
                chars[i] = None

        new_chars: list[str] = []
        new_spans: list[tuple[int, int]] = []
        for c, sp in zip(chars, spans):
            if c is not None:
                new_chars.append(c)
                new_spans.append(sp)
        text = "".join(new_chars)
        spans = new_spans
        chars = list(text)

    # 2. HTML Comments (<!-- comment -->)
    for m in HTML_COMMENT_REGEX.finditer(text):
        s_idx, e_idx = m.start(), m.end()
        raw_s = spans[s_idx][0]
        raw_e = spans[e_idx - 1][1]
        edits.append(
            PreprocessingEdit(
                original_span=(raw_s, raw_e),
                output_span=(s_idx, s_idx),
                category="strip_markup",
                description="Stripped HTML comment.",
            )
        )
        for i in range(s_idx, e_idx):
            chars[i] = None

    new_chars = []
    new_spans = []
    for c, sp in zip(chars, spans):
        if c is not None:
            new_chars.append(c)
            new_spans.append(sp)
    text = "".join(new_chars)
    spans = new_spans
    chars = list(text)

    # 3. Closed Script and Style blocks
    for m in DROP_TAG_REGEX.finditer(text):
        s_idx, e_idx = m.start(), m.end()
        raw_s = spans[s_idx][0]
        raw_e = spans[e_idx - 1][1]
        edits.append(
            PreprocessingEdit(
                original_span=(raw_s, raw_e),
                output_span=(s_idx, s_idx),
                category="strip_markup",
                description=f"Dropped <{m.group(1)}> block and contents.",
            )
        )
        for i in range(s_idx, e_idx):
            chars[i] = None

    new_chars = []
    new_spans = []
    for c, sp in zip(chars, spans):
        if c is not None:
            new_chars.append(c)
            new_spans.append(sp)
    text = "".join(new_chars)
    spans = new_spans
    chars = list(text)

    # 4. Unclosed Script/Style tags (drop only the tag, keep text, emit warning)
    for m in UNCLOSED_SCRIPT_REGEX.finditer(text):
        s_idx, e_idx = m.start(), m.end()
        raw_s = spans[s_idx][0]
        raw_e = spans[e_idx - 1][1]
        edits.append(
            PreprocessingEdit(
                original_span=(raw_s, raw_e),
                output_span=(s_idx, s_idx),
                category="strip_markup",
                description=f"Dropped unclosed <{m.group(1)}> tag.",
            )
        )
        warnings.append(
            NormalizationWarning(
                code="UNCLOSED_SCRIPT_TAG",
                message="Unclosed script tag detected; dropped tag and preserved content.",
                severity="warning",
                original_span=(raw_s, raw_e),
            )
        )
        for i in range(s_idx, e_idx):
            chars[i] = None

    new_chars = []
    new_spans = []
    for c, sp in zip(chars, spans):
        if c is not None:
            new_chars.append(c)
            new_spans.append(sp)
    text = "".join(new_chars)
    spans = new_spans

    # 5. HTML Tag Processing (Allowlisted tags)
    tag_chars: list[str] = []
    tag_spans: list[tuple[int, int]] = []
    last_end = 0

    for m in HTML_TAG_REGEX.finditer(text):
        tag_name = m.group(1).lower()
        start, end = m.start(), m.end()

        # Copy text before tag
        if start > last_end:
            tag_chars.extend(text[last_end:start])
            tag_spans.extend(spans[last_end:start])

        # Validate that single-character tags with space inside contain '=' (not plain English prose like <b and c>)
        tag_inner = text[start + 1 : end - 1].strip()
        if len(tag_name) == 1 and " " in tag_inner and "=" not in tag_inner:
            tag_chars.extend(text[start:end])
            tag_spans.extend(spans[start:end])
            last_end = end
            continue

        raw_tag_span = (spans[start][0], spans[end - 1][1])

        # Check if SSML tag in SSML mode -> preserve as text so it becomes protected span
        if ssml_mode and tag_name in SSML_TAGS:
            tag_chars.extend(text[start:end])
            tag_spans.extend(spans[start:end])
        elif tag_name in ALLOWLIST_BLOCK_TAGS or tag_name in ALLOWLIST_BREAK_TAGS:
            # Block or break tag -> becomes space boundary if not already spaced and not at boundary of text
            remainder = text[end:].strip()
            if tag_chars and not tag_chars[-1].isspace() and remainder:
                tag_chars.append(" ")
                tag_spans.append(raw_tag_span)
                edits.append(
                    PreprocessingEdit(
                        original_span=raw_tag_span,
                        output_span=(len(tag_chars) - 1, len(tag_chars)),
                        category="strip_markup",
                        description=f"Converted <{tag_name}> to space boundary.",
                    )
                )
            else:
                edits.append(
                    PreprocessingEdit(
                        original_span=raw_tag_span,
                        output_span=(len(tag_chars), len(tag_chars)),
                        category="strip_markup",
                        description=f"Stripped <{tag_name}> block boundary.",
                    )
                )
        elif tag_name in ALLOWLIST_INLINE_TAGS or (not ssml_mode and tag_name in SSML_TAGS):
            # Inline tag -> stripped, inner text kept
            edits.append(
                PreprocessingEdit(
                    original_span=raw_tag_span,
                    output_span=(len(tag_chars), len(tag_chars)),
                    category="strip_markup",
                    description=f"Stripped inline <{tag_name}> tag.",
                )
            )
        else:
            # Not in allowlist -> keep as text
            tag_chars.extend(text[start:end])
            tag_spans.extend(spans[start:end])

        last_end = end

    if last_end < len(text):
        tag_chars.extend(text[last_end:])
        tag_spans.extend(spans[last_end:])

    text = "".join(tag_chars)
    spans = tag_spans

    # 6. Entity Decoding
    ent_chars: list[str] = []
    ent_spans: list[tuple[int, int]] = []
    last_end = 0
    for m in ENTITY_REGEX.finditer(text):
        start, end = m.start(), m.end()
        if start > last_end:
            ent_chars.extend(text[last_end:start])
            ent_spans.extend(spans[last_end:start])

        raw_ent_span = (spans[start][0], spans[end - 1][1])
        decoded = html.unescape(m.group(0))
        for ch in decoded:
            ent_chars.append(ch)
            ent_spans.append(raw_ent_span)

        edits.append(
            PreprocessingEdit(
                original_span=raw_ent_span,
                output_span=(len(ent_chars) - len(decoded), len(ent_chars)),
                category="decode_entity",
                description=f"Decoded HTML entity {m.group(0)} to {decoded}.",
            )
        )
        last_end = end

    if last_end < len(text):
        ent_chars.extend(text[last_end:])
        ent_spans.extend(spans[last_end:])

    text = "".join(ent_chars)
    spans = ent_spans

    # 7. Markdown Links: [anchor](url) -> anchor
    md_chars: list[str] = []
    md_spans: list[tuple[int, int]] = []
    last_end = 0
    for m in MD_LINK_REGEX.finditer(text):
        start, end = m.start(), m.end()
        if start > last_end:
            md_chars.extend(text[last_end:start])
            md_spans.extend(spans[last_end:start])

        anchor_len = len(m.group(1))
        anchor_start = start + 1
        anchor_end = anchor_start + anchor_len

        md_chars.extend(text[anchor_start:anchor_end])
        md_spans.extend(spans[anchor_start:anchor_end])

        raw_link_span = (spans[start][0], spans[end - 1][1])
        edits.append(
            PreprocessingEdit(
                original_span=raw_link_span,
                output_span=(len(md_chars) - anchor_len, len(md_chars)),
                category="strip_markdown",
                description="Extracted anchor text from Markdown link.",
            )
        )
        last_end = end

    if last_end < len(text):
        md_chars.extend(text[last_end:])
        md_spans.extend(spans[last_end:])

    text = "".join(md_chars)
    spans = md_spans

    # 8. Markdown Headings: ^#{1,6}\s+
    head_chars: list[str] = []
    head_spans: list[tuple[int, int]] = []
    last_end = 0
    for m in MD_HEADING_REGEX.finditer(text):
        start, end = m.start(), m.end()
        if start > last_end:
            head_chars.extend(text[last_end:start])
            head_spans.extend(spans[last_end:start])
        raw_head_span = (spans[start][0], spans[end - 1][1])
        edits.append(
            PreprocessingEdit(
                original_span=raw_head_span,
                output_span=(len(head_chars), len(head_chars)),
                category="strip_markdown",
                description="Stripped Markdown heading prefix.",
            )
        )
        last_end = end

    if last_end < len(text):
        head_chars.extend(text[last_end:])
        head_spans.extend(spans[last_end:])

    text = "".join(head_chars)
    spans = head_spans

    # 9. Inline Code Spans (`code` -> code)
    code_chars: list[str] = []
    code_spans: list[tuple[int, int]] = []
    last_end = 0
    for m in INLINE_CODE_REGEX.finditer(text):
        start, end = m.start(), m.end()
        if start > last_end:
            code_chars.extend(text[last_end:start])
            code_spans.extend(spans[last_end:start])

        inner_start = start + 1
        inner_end = end - 1
        inner_len = inner_end - inner_start
        code_chars.extend(text[inner_start:inner_end])
        code_spans.extend(spans[inner_start:inner_end])

        raw_span = (spans[start][0], spans[end - 1][1])
        edits.append(
            PreprocessingEdit(
                original_span=raw_span,
                output_span=(len(code_chars) - inner_len, len(code_chars)),
                category="strip_markdown",
                description="Stripped inline code backticks.",
            )
        )
        last_end = end

    if last_end < len(text):
        code_chars.extend(text[last_end:])
        code_spans.extend(spans[last_end:])

    text = "".join(code_chars)
    spans = code_spans

    # 10. Markdown Emphasis: *text* and _text_
    # Asterisk emphasis
    ast_chars: list[str] = []
    ast_spans: list[tuple[int, int]] = []
    last_end = 0
    for m in MD_EMPHASIS_ASTERISK_REGEX.finditer(text):
        start, end = m.start(), m.end()
        if start > last_end:
            ast_chars.extend(text[last_end:start])
            ast_spans.extend(spans[last_end:start])
        inner_start = start + 1
        inner_end = end - 1
        inner_len = inner_end - inner_start
        ast_chars.extend(text[inner_start:inner_end])
        ast_spans.extend(spans[inner_start:inner_end])
        raw_span = (spans[start][0], spans[end - 1][1])
        edits.append(
            PreprocessingEdit(
                original_span=raw_span,
                output_span=(len(ast_chars) - inner_len, len(ast_chars)),
                category="strip_markdown",
                description="Stripped Markdown asterisk emphasis.",
            )
        )
        last_end = end

    if last_end < len(text):
        ast_chars.extend(text[last_end:])
        ast_spans.extend(spans[last_end:])

    text = "".join(ast_chars)
    spans = ast_spans

    # Underscore emphasis
    und_chars: list[str] = []
    und_spans: list[tuple[int, int]] = []
    last_end = 0
    for m in MD_EMPHASIS_UNDERSCORE_REGEX.finditer(text):
        start, end = m.start(), m.end()
        if start > last_end:
            und_chars.extend(text[last_end:start])
            und_spans.extend(spans[last_end:start])
        inner_start = start + 1
        inner_end = end - 1
        inner_len = inner_end - inner_start
        und_chars.extend(text[inner_start:inner_end])
        und_spans.extend(spans[inner_start:inner_end])
        raw_span = (spans[start][0], spans[end - 1][1])
        edits.append(
            PreprocessingEdit(
                original_span=raw_span,
                output_span=(len(und_chars) - inner_len, len(und_chars)),
                category="strip_markdown",
                description="Stripped Markdown underscore emphasis.",
            )
        )
        last_end = end

    if last_end < len(text):
        und_chars.extend(text[last_end:])
        und_spans.extend(spans[last_end:])

    text = "".join(und_chars)
    spans = und_spans

    new_mapper = MonotonicCoordinateMapper(spans)
    return text, new_mapper, tuple(edits), tuple(warnings)
