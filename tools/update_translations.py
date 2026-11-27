"""Extract English UI messages and compile the maintained German catalog."""

from pathlib import Path
from runpy import run_path

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1] / "octoprint_mqttforusbrelaycontrol"


def main():
    template = Catalog(
        project="OctoPrint-MQTTForUSBRelayControl",
        version=run_path(str(ROOT / "_version.py"))["__version__"],
        charset="utf-8",
        copyright_holder="",
    )
    for filename, line, message, comments, context in extract_from_dir(
        str(ROOT),
        method_map=[("**/*.jinja2", "jinja2.ext:babel_extract"), ("**/*.js", "javascript")],
        options_map={"**/*.jinja2": {"extensions": "jinja2.ext.i18n"}},
    ):
        template.add(message, locations=[(filename, line)], auto_comments=comments, context=context)
    directory = ROOT / "translations"
    directory.mkdir(exist_ok=True)
    with (directory / "messages.pot").open("wb") as handle:
        write_po(handle, template, omit_header=True, sort_output=True)
    po = directory / "de/LC_MESSAGES/messages.po"
    if not po.exists():
        raise RuntimeError("The maintained German catalog is missing")
    with po.open("rb") as handle:
        german = read_po(handle, locale="de")
    german.update(template, no_fuzzy_matching=True)
    german.version = template.version
    german.header_comment = "# German UI translation catalog."
    german.last_translator = ""
    german.language_team = ""
    german.msgid_bugs_address = ""
    german.revision_date = template.creation_date
    german.fuzzy = False
    missing = [message.id for message in german if message.id and not message.string]
    if missing:
        raise ValueError(f"Untranslated German messages: {missing}")
    with po.open("wb") as handle:
        write_po(handle, german, sort_output=True)
    with po.with_suffix(".mo").open("wb") as handle:
        write_mo(handle, german)
    print(f"Extracted and compiled {len(template)} translated UI messages")


if __name__ == "__main__":
    main()
