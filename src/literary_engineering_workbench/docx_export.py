"""DOCX export helpers for final literary artifacts.

The exporter intentionally uses only the Python standard library. It creates a
small, valid WordprocessingML package from Markdown-like chapter exports so the
workbench can deliver editable Word files without adding runtime dependencies.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree
from xml.sax.saxutils import escape


DOCX_KINDS = {"novel", "screenplay", "video_prompt_pack", "report"}


@dataclass(frozen=True)
class DocxExportResult:
    source_path: Path
    docx_path: Path
    title: str
    paragraph_count: int
    warning_count: int


def export_markdown_to_docx(
    source_path: Path,
    output_path: Path | None = None,
    *,
    title: str = "",
    kind: str = "novel",
    overwrite: bool = True,
) -> DocxExportResult:
    """Export a Markdown/text artifact to an editable DOCX file."""

    source = source_path.resolve()
    if not source.exists():
        raise FileNotFoundError(f"source markdown not found: {source}")
    if not source.is_file():
        raise ValueError(f"source must be a file: {source}")

    doc_kind = kind if kind in DOCX_KINDS else "novel"
    out = output_path or source.with_suffix(".docx")
    out = out if out.is_absolute() else source.parent / out
    if out.exists() and not overwrite:
        raise FileExistsError(f"output already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)

    text = source.read_text(encoding="utf-8", errors="ignore")
    inferred_title = title.strip() or _infer_title(text) or source.stem
    paragraphs, warnings = _markdown_to_paragraphs(text, kind=doc_kind)
    if not paragraphs:
        paragraphs = [_paragraph("未读取到可导出的正文。", style="Normal")]
        warnings.append("source produced no paragraphs")

    _write_docx(
        out,
        title=inferred_title,
        body_xml="\n".join(paragraphs),
        paragraph_count=len(paragraphs),
        kind=doc_kind,
    )
    inspect_docx(out)
    return DocxExportResult(
        source_path=source,
        docx_path=out,
        title=inferred_title,
        paragraph_count=len(paragraphs),
        warning_count=len(warnings),
    )


def inspect_docx(path: Path) -> dict[str, object]:
    """Run a lightweight structural check on a generated DOCX package."""

    docx_path = path.resolve()
    if not docx_path.exists():
        raise FileNotFoundError(f"docx not found: {docx_path}")
    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "docProps/core.xml",
        "docProps/app.xml",
        "word/document.xml",
        "word/styles.xml",
        "word/numbering.xml",
        "word/settings.xml",
        "word/_rels/document.xml.rels",
    }
    with zipfile.ZipFile(docx_path) as package:
        names = set(package.namelist())
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"invalid DOCX package, missing: {', '.join(missing)}")
        document_xml = package.read("word/document.xml")
        styles_xml = package.read("word/styles.xml")
        ElementTree.fromstring(document_xml)
        ElementTree.fromstring(styles_xml)
    paragraph_count = document_xml.count(b"<w:p")
    return {
        "path": str(docx_path),
        "paragraph_count": paragraph_count,
        "missing": [],
    }


def _infer_title(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line:
            return line[:80]
    return ""


def _markdown_to_paragraphs(text: str, *, kind: str) -> tuple[list[str], list[str]]:
    paragraphs: list[str] = []
    warnings: list[str] = []
    in_code = False
    code_buffer: list[str] = []
    heading1_seen = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                if code_buffer:
                    paragraphs.extend(_code_paragraph(item) for item in code_buffer)
                code_buffer = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buffer.append(line)
            continue
        if not stripped:
            continue
        if re.fullmatch(r"[-*_]{3,}", stripped):
            paragraphs.append(_paragraph("", style="Spacer"))
            continue
        if stripped.startswith("# "):
            paragraphs.append(_paragraph(stripped[2:].strip(), style="Title", alignment="center"))
            continue
        if stripped.startswith("## "):
            page_break = heading1_seen and kind in {"novel", "screenplay"}
            heading1_seen = True
            paragraphs.append(_paragraph(stripped[3:].strip(), style="Heading1", page_break_before=page_break))
            continue
        if stripped.startswith("### "):
            paragraphs.append(_paragraph(stripped[4:].strip(), style="Heading2"))
            continue
        if stripped.startswith("#### "):
            paragraphs.append(_paragraph(stripped[5:].strip(), style="Heading3"))
            continue
        if stripped.startswith("> "):
            paragraphs.append(_paragraph(stripped[2:].strip(), style="Quote"))
            continue
        if stripped.startswith("- "):
            paragraphs.append(_paragraph(stripped[2:].strip(), style="ListParagraph", numbering="bullet"))
            continue
        number_match = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if number_match:
            paragraphs.append(_paragraph(number_match.group(2).strip(), style="ListParagraph", numbering="number"))
            continue
        paragraphs.append(_paragraph(stripped, style="Normal"))

    if in_code:
        warnings.append("unclosed code fence")
        paragraphs.extend(_code_paragraph(item) for item in code_buffer)
    return paragraphs, warnings


def _code_paragraph(text: str) -> str:
    return _paragraph(text or " ", style="Code")


def _paragraph(
    text: str,
    *,
    style: str = "Normal",
    alignment: str = "",
    numbering: str = "",
    page_break_before: bool = False,
) -> str:
    ppr: list[str] = []
    if style and style != "Normal":
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if numbering == "bullet":
        ppr.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')
    elif numbering == "number":
        ppr.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>')
    if page_break_before:
        ppr.append("<w:pageBreakBefore/>")
    ppr.append('<w:spacing w:before="0" w:after="160" w:line="360" w:lineRule="auto"/>')
    if alignment:
        ppr.append(f'<w:jc w:val="{alignment}"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>"
    run_xml = "".join(_inline_runs(text))
    return f"<w:p>{ppr_xml}{run_xml}</w:p>"


def _inline_runs(text: str) -> Iterable[str]:
    if not text:
        yield "<w:r><w:t></w:t></w:r>"
        return
    pattern = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            yield _run(text[pos : match.start()])
        token = match.group(0)
        if token.startswith("**"):
            yield _run(token[2:-2], bold=True)
        elif token.startswith("`"):
            yield _run(token[1:-1], code=True)
        pos = match.end()
    if pos < len(text):
        yield _run(text[pos:])


def _run(text: str, *, bold: bool = False, code: bool = False) -> str:
    props = []
    if bold:
        props.append("<w:b/><w:bCs/>")
    if code:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Microsoft YaHei"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    space = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f"<w:r>{rpr}<w:t{space}>{escape(text)}</w:t></w:r>"


def _write_docx(path: Path, *, title: str, body_xml: str, paragraph_count: int, kind: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", _content_types())
        package.writestr("_rels/.rels", _root_rels())
        package.writestr("docProps/core.xml", _core_props(title, timestamp))
        package.writestr("docProps/app.xml", _app_props(paragraph_count))
        package.writestr("word/_rels/document.xml.rels", _document_rels())
        package.writestr("word/styles.xml", _styles())
        package.writestr("word/numbering.xml", _numbering())
        package.writestr("word/settings.xml", _settings())
        package.writestr("word/document.xml", _document(title, body_xml, kind))


def _document(title: str, body_xml: str, kind: str) -> str:
    subject = {
        "novel": "长篇正文 DOCX 导出",
        "screenplay": "剧本工作稿 DOCX 导出",
        "video_prompt_pack": "长视频提示词包 DOCX 导出",
        "report": "文档 DOCX 导出",
    }.get(kind, "DOCX 导出")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Subtitle"/><w:jc w:val="center"/></w:pPr>
      <w:r><w:t>{escape(subject)}</w:t></w:r>
    </w:p>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
      <w:cols w:space="720"/>
      <w:docGrid w:linePitch="312"/>
    </w:sectPr>
  </w:body>
</w:document>
'''


def _content_types() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>
'''


def _root_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'''


def _document_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>
'''


def _core_props(title: str, timestamp: str) -> str:
    safe_title = escape(title)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{safe_title}</dc:title>
  <dc:creator>literary-engineering-workbench</dc:creator>
  <cp:lastModifiedBy>literary-engineering-workbench</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>
</cp:coreProperties>
'''


def _app_props(paragraph_count: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>literary-engineering-workbench</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <Paragraphs>{paragraph_count}</Paragraphs>
  <Company></Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>0.1</AppVersion>
</Properties>
'''


def _styles() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:after="160" w:line="360" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="240" w:after="240"/><w:jc w:val="center"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
    <w:pPr><w:spacing w:after="120"/><w:jc w:val="center"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:color w:val="666666"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="360" w:after="240"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="240" w:after="180"/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="Heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="160" w:after="120"/><w:outlineLvl w:val="2"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Quote">
    <w:name w:val="Quote"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="720" w:right="720"/><w:spacing w:before="120" w:after="120"/></w:pPr>
    <w:rPr><w:i/><w:iCs/><w:color w:val="555555"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Code">
    <w:name w:val="Code"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="80" w:after="80"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Microsoft YaHei"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Spacer">
    <w:name w:val="Spacer"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="120" w:after="120"/></w:pPr>
  </w:style>
</w:styles>
'''


def _numbering() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="1">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>
'''


def _settings() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="100"/>
  <w:defaultTabStop w:val="720"/>
  <w:characterSpacingControl w:val="doNotCompress"/>
</w:settings>
'''
