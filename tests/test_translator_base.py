from gideons_uebersetzer.pdf_reader import Chapter, Paragraph
from gideons_uebersetzer.translator_base import (
    build_messages,
    load_glossary,
    quality_check,
    split_into_chunks,
)


def _chapter(paragraphs, title="Kapitel"):
    return Chapter(title=title, paragraphs=[Paragraph(t, i + 1) for i, t in enumerate(paragraphs)])


def test_chunks_respect_word_limit_and_chapters():
    paras = [" ".join(["wort"] * 100) for _ in range(10)]  # 100 Wörter je Absatz
    chapters = [_chapter(paras[:5]), _chapter(paras[5:], title="Zwei")]
    chunks = split_into_chunks(chapters, 250)
    assert all(c.word_count <= 350 for c in chunks)  # ein Absatz darf allein das Limit überschreiten
    assert {c.chapter_index for c in chunks} == {0, 1}
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].page == 1


def test_build_messages_contains_glossary_and_context():
    messages = build_messages(
        "Hello world.",
        context_paragraphs=["Bisheriger Absatz."],
        glossary=[("Sherlock Holmes", "Sherlock Holmes"), ("London", "London")],
    )
    assert messages[0]["role"] == "system"
    user = messages[1]["content"]
    assert "Sherlock Holmes = Sherlock Holmes" in user
    assert "Bisheriger Absatz." in user
    assert "Hello world." in user


def test_quality_check_detects_short_output():
    assert quality_check("a" * 1000, "kurz") is not None
    assert quality_check("a" * 100, "a" * 20) is not None


def test_quality_check_detects_prompt_residue():
    assert quality_check("Hello there friend", "Hier ist die Übersetzung: Hallo") is not None
    assert quality_check("Hello there friend", "Here is the translation: Hallo") is not None
    assert quality_check("Hello there friend", "```Hallo```") is not None


def test_quality_check_detects_untranslated_text():
    source = "The quick brown fox jumps over the lazy dog and runs away. " * 5
    assert quality_check(source, source) is not None  # reiner englischer Text


def test_quality_check_accepts_good_translation():
    source = "The quick brown fox jumps over the lazy dog. " * 5
    translation = "Der schnelle braune Fuchs springt über den faulen Hund. " * 5
    assert quality_check(source, translation) is None
    # deutsche Übersetzung mit einzelnen englischen Eigennamen bleibt ok
    mixed = "Sherlock Holmes ging durch London und dachte nach. " * 5
    assert quality_check(source, mixed) is None


def test_load_glossary(tmp_path):
    g = tmp_path / "glossar.txt"
    g.write_text(
        "# Kommentar\n"
        "Sherlock Holmes = Sherlock Holmes\n"
        "\n"
        "London = London\n"
        "Zeile ohne Gleichheitszeichen\n",
        encoding="utf-8",
    )
    entries = load_glossary(g)
    assert entries == [("Sherlock Holmes", "Sherlock Holmes"), ("London", "London")]
    assert load_glossary(None) == []
    assert load_glossary(tmp_path / "fehlt.txt") == []


def test_sanitize_strips_fences_markers_and_quotes():
    from gideons_uebersetzer.translator_base import sanitize_translation

    assert sanitize_translation('Translation:\n"""\nHallo Welt.\n"""') == "Hallo Welt."
    assert sanitize_translation("```de\nHallo Welt.\n```") == "Hallo Welt."
    assert sanitize_translation('"Hallo Welt."') == "Hallo Welt."
    assert sanitize_translation("Hier ist die Übersetzung: Hallo Welt.") == "Hallo Welt."
    assert sanitize_translation("Here is the translation: Hallo Welt.") == "Hallo Welt."
    assert sanitize_translation("Hallo Welt.<|im_end|>") == "Hallo Welt."
    assert sanitize_translation("Übersetzung:\nHallo Welt.") == "Hallo Welt."
    assert sanitize_translation("Hallo Welt.") == "Hallo Welt."
    assert sanitize_translation("Erster Absatz.\n\n\n\nZweiter Absatz.") == "Erster Absatz.\n\nZweiter Absatz."


def test_quality_check_passes_after_sanitize():
    from gideons_uebersetzer.translator_base import quality_check, sanitize_translation

    src = "The quick brown fox jumps over the lazy dog. " * 5
    good = "Der schnelle braune Fuchs springt über den faulen Hund. " * 5
    dirty = 'Translation:\n"""\n' + good + '\n"""'
    assert quality_check(src, sanitize_translation(dirty)) is None
