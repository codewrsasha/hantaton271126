from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

TYPES = (
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>'
)
RELATIONSHIPS = (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>'
)
STYLES = (
    f'<w:styles xmlns:w="{WORD}">'
    '<w:style w:type="paragraph" w:styleId="SyntheticHeading">'
    '<w:name w:val="Synthetic heading"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
    '</w:style></w:styles>'
)
STYLES_RELATIONSHIP = (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    'Target="styles.xml"/></Relationships>'
)


def paragraph(text: str, heading: bool = False) -> str:
    props = '<w:pPr><w:pStyle w:val="SyntheticHeading"/></w:pPr>' if heading else ""
    return f"<w:p>{props}<w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def docx(body: str, *, prefix: str = "", extras: dict[str, str] | None = None, linked_styles: bool = True) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", TYPES)
        archive.writestr("_rels/.rels", RELATIONSHIPS)
        archive.writestr("word/document.xml", f'{prefix}<w:document xmlns:w="{WORD}"><w:body>{body}</w:body></w:document>')
        archive.writestr("word/styles.xml", STYLES)
        if linked_styles:
            archive.writestr("word/_rels/document.xml.rels", STYLES_RELATIONSHIP)
        for name, content in (extras or {}).items():
            archive.writestr(name, content)
    return stream.getvalue()


def pdf(*pages: str | None, scan: bool = False, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for text in pages:
        page = writer.add_blank_page(width=300, height=300)
        if text is not None:
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
            })
            content = f"BT /F1 12 Tf 20 220 Td ({text}) Tj ET".encode("ascii")
        elif scan:
            image = DecodedStreamObject()
            image.update({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(1),
                NameObject("/Height"): NumberObject(1),
                NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                NameObject("/BitsPerComponent"): NumberObject(8),
            })
            image.set_data(bytes([0]))
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): writer._add_object(image)}),
            })
            content = b"q 100 0 0 100 25 25 cm /Im0 Do Q"
        else:
            continue
        stream = DecodedStreamObject()
        stream.set_data(content)
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic")
    result = BytesIO()
    writer.write(result)
    return result.getvalue()
