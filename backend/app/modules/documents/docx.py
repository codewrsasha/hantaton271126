import re
from collections.abc import Iterator
from io import BytesIO
from struct import unpack_from
from xml.etree.ElementTree import Element, ParseError
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile
from zlib import error as CompressionError

from defusedxml import ElementTree as safe_xml
from defusedxml.common import DefusedXmlException

from ...contracts import DocxLocation, UnknownLocation
from .models import DocumentIssue, Extraction, Fragment, RejectedUpload

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 1024
MAX_DIRECTORY_BYTES = 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
MAX_PARAGRAPHS = 25_000
MAX_HEADING_CHARS = 512
WORD_NAMESPACES = {
    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}",
    "{http://purl.oclc.org/ooxml/wordprocessingml/main}",
}
TYPES = "{http://schemas.openxmlformats.org/package/2006/content-types}"
RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAIN_PART = "word/document.xml"
MAIN_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
OFFICE_RELATIONSHIPS = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
}
STYLE_RELATIONSHIPS = {uri.rsplit("/", 1)[0] + "/styles" for uri in OFFICE_RELATIONSHIPS}
BLOCKS = ("body", "tbl", "tr", "tc", "sdt", "sdtContent", "customXml", "ins", "moveTo")
INLINE = ("p", "r", "hyperlink", "sdt", "sdtContent", "customXml", "smartTag", "ins", "moveTo", "fldSimple")
HEADING_NAME = re.compile(r"(?:heading|заголовок) ?[1-9]", re.IGNORECASE)


def verify_zip_directory(content: bytes) -> None:
    # Bound metadata before ZipFile allocates an object for every entry.
    end = len(content) - 22
    lower = max(0, end - 65535)
    while (end := content.rfind(b"PK\x05\x06", lower, end + 4)) >= 0:
        if end + 22 <= len(content):
            disk, start_disk, disk_entries, entries, size, offset, comment = unpack_from("<4H2IH", content, end + 4)
            if end + 22 + comment == len(content):
                if disk or start_disk or disk_entries != entries or offset + size != end:
                    raise BadZipFile("Unsupported ZIP directory layout")
                if entries > MAX_ENTRIES or size > MAX_DIRECTORY_BYTES:
                    raise RejectedUpload(422, "Служебные данные архива DOCX превышают допустимый размер.")
                return
        end -= 1
    raise BadZipFile("Missing ZIP directory")


def validate_archive(archive: ZipFile) -> set[str]:
    members = archive.infolist()
    if len(members) > MAX_ENTRIES or sum(member.file_size for member in members) > MAX_ARCHIVE_BYTES:
        raise RejectedUpload(422, "DOCX превышает предел распакованного размера или числа элементов.")
    names: set[str] = set()
    for member in members:
        name = member.filename
        key = name.casefold()
        if (
            key in names or "\\" in name or ":" in name
            or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))
            or member.flag_bits & 1 or member.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
        ):
            raise RejectedUpload(422, "DOCX содержит неподдерживаемые или небезопасные элементы архива.")
        if "vbaproject" in key:
            raise RejectedUpload(422, "Документы с макросами не поддерживаются.")
        names.add(key)
    return {member.filename for member in members}


def xml_part(archive: ZipFile, name: str) -> Element:
    if archive.getinfo(name).file_size > MAX_XML_BYTES:
        raise RejectedUpload(422, "Размер XML внутри DOCX превышает допустимый предел.")
    with archive.open(name) as file:
        content = file.read(MAX_XML_BYTES + 1)
    if len(content) > MAX_XML_BYTES:
        raise RejectedUpload(422, "Размер XML внутри DOCX превышает допустимый предел.")
    return safe_xml.fromstring(content, forbid_dtd=True, forbid_entities=True, forbid_external=True)


def verify_package(archive: ZipFile, names: set[str]) -> None:
    if not {"[Content_Types].xml", "_rels/.rels", MAIN_PART} <= names:
        raise RejectedUpload(415, "ZIP-файл не содержит обязательных частей DOCX.")
    types = xml_part(archive, "[Content_Types].xml")
    relationships = xml_part(archive, "_rels/.rels")
    if types.tag != TYPES + "Types" or relationships.tag != RELS + "Relationships":
        raise RejectedUpload(422, "Нарушена структура пакета DOCX.")
    if any("macroenabled" in item.get("ContentType", "").casefold() for item in types):
        raise RejectedUpload(422, "Документы с макросами не поддерживаются.")
    main_types = [
        item.get("ContentType")
        for item in types.findall(TYPES + "Override") if item.get("PartName") == "/" + MAIN_PART
    ]
    main_relations = [
        item for item in relationships.findall(RELS + "Relationship")
        if item.get("Type") in OFFICE_RELATIONSHIPS
    ]
    if main_types != [MAIN_TYPE] or len(main_relations) != 1:
        raise RejectedUpload(422, "Не удалось подтвердить основной раздел пакета DOCX.")
    relation = main_relations[0]
    if (
        not relation.get("Id") or relation.get("Target") not in {MAIN_PART, "/" + MAIN_PART}
        or relation.get("TargetMode", "Internal") != "Internal"
    ):
        raise RejectedUpload(422, "Основной раздел DOCX должен находиться внутри архива.")


def walk(element: Element, containers: set[str]) -> Iterator[Element]:
    stack = [element]
    while stack:
        node = stack.pop()
        if node.tag in containers:
            stack.extend(reversed(node))
        else:
            yield node


def paragraph_text(paragraph: Element, ns: str) -> str:
    separators = {ns + "tab": "\t", ns + "br": "\n", ns + "cr": "\n"}
    return "".join(
        node.text or "" if node.tag == ns + "t" else separators.get(node.tag, "")
        for node in walk(paragraph, {ns + name for name in INLINE})
    ).strip()


def outline(parent: Element, ns: str) -> str | None:
    item = parent.find(ns + "outlineLvl")
    return item.get(ns + "val") if item is not None else None


def is_heading(paragraph: Element, ns: str, styles: dict[str, Element]) -> bool:
    props = paragraph.find(ns + "pPr")
    if props is None:
        return False
    level = outline(props, ns)
    if level is not None:
        return level in "012345678" and len(level) == 1
    reference = props.find(ns + "pStyle")
    style_id = reference.get(ns + "val") if reference is not None else None
    seen = set()
    while style_id in styles and style_id not in seen:
        seen.add(style_id)
        style = styles[style_id]
        style_props = style.find(ns + "pPr")
        if style_props is not None and (level := outline(style_props, ns)) is not None:
            return level in "012345678" and len(level) == 1
        name = style.find(ns + "name")
        if name is not None and HEADING_NAME.fullmatch(name.get(ns + "val", "")):
            return True
        base = style.find(ns + "basedOn")
        style_id = base.get(ns + "val") if base is not None else None
    return False


def read_styles(archive: ZipFile, names: set[str], ns: str) -> dict[str, Element]:
    relations_part = "word/_rels/document.xml.rels"
    if relations_part not in names:
        return {}
    relationships = xml_part(archive, relations_part)
    if relationships.tag != RELS + "Relationships":
        raise RejectedUpload(422, "Не удалось прочитать связи документа DOCX.")
    references = [
        item for item in relationships.findall(RELS + "Relationship")
        if item.get("Type") in STYLE_RELATIONSHIPS
    ]
    if not references:
        return {}
    reference = references[0]
    if (
        len(references) != 1
        or reference.get("TargetMode", "Internal") != "Internal"
        or reference.get("Target") not in {"styles.xml", "/word/styles.xml"}
    ):
        return {}
    if "word/styles.xml" not in names:
        raise RejectedUpload(422, "В DOCX отсутствует объявленная часть со стилями.")
    styles_root = xml_part(archive, "word/styles.xml")
    if styles_root.tag != ns + "styles":
        raise RejectedUpload(422, "Не удалось прочитать стили DOCX.")
    return {
        node.get(ns + "styleId", ""): node
        for node in styles_root.findall(ns + "style") if node.get(ns + "type") == "paragraph"
    }


def read_document(archive: ZipFile, names: set[str]) -> Extraction:
    root = xml_part(archive, MAIN_PART)
    ns = next((ns for ns in WORD_NAMESPACES if root.tag == ns + "document"), "")
    body = root.find(ns + "body") if ns else None
    if body is None:
        raise RejectedUpload(422, "DOCX не содержит корректное тело документа.")
    styles = read_styles(archive, names, ns)

    result = Extraction("docx")
    location = UnknownLocation(kind="unknown")
    total_chars = 0
    truncated = False
    unknown = False
    paragraphs = (node for node in walk(body, {ns + name for name in BLOCKS}) if node.tag == ns + "p")
    for index, paragraph in enumerate(paragraphs, start=1):
        if index > MAX_PARAGRAPHS:
            truncated = True
            break
        text = paragraph_text(paragraph, ns)
        if is_heading(paragraph, ns, styles):
            location = (
                DocxLocation(kind="docx_section", section=text)
                if 0 < len(text) <= MAX_HEADING_CHARS else UnknownLocation(kind="unknown")
            )
        if not text:
            continue
        total_chars += len(text)
        if total_chars > MAX_TEXT_CHARS:
            truncated = True
            break
        unknown |= location.kind == "unknown"
        result.fragments.append(Fragment(text, location))

    extra_text = (
        any(name.startswith(("word/header", "word/footer")) or name in {"word/footnotes.xml", "word/endnotes.xml"}
            for name in names)
        or any(node.tag in {ns + "altChunk", ns + "txbxContent"} for node in body.iter())
    )
    if truncated or extra_text:
        message = "Текст DOCX извлечён не полностью."
        if truncated:
            message += " Достигнут предел объёма текста или числа абзацев."
        if extra_text:
            message += " Дополнительные текстовые части DOCX требуют отдельной проверки."
        result.issue = DocumentIssue(
            code="partial_extraction" if result.fragments else "extraction_failed", message=message,
        )
    elif not result.fragments:
        result.issue = DocumentIssue(code="no_text", message="В теле DOCX не найден текст для извлечения.")
    elif unknown:
        result.issue = DocumentIssue(
            code="unknown_location", message="Для части абзацев не удалось определить заголовок раздела."
        )
    return result


def extract(content: bytes) -> Extraction:
    try:
        verify_zip_directory(content)
        with ZipFile(BytesIO(content)) as archive:
            names = validate_archive(archive)
            verify_package(archive, names)
            if archive.testzip() is not None:
                raise BadZipFile("CRC mismatch")
            return read_document(archive, names)
    except DefusedXmlException as error:
        raise RejectedUpload(422, "DOCX содержит запрещённые объявления XML.") from error
    except (BadZipFile, ParseError, CompressionError, EOFError, RuntimeError, ValueError) as error:
        raise RejectedUpload(422, "Архив или XML DOCX повреждён. Сохраните документ заново.") from error
