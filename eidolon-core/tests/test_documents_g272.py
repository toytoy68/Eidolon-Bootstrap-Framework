# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_documents_g272.py
# Description : Documents réels synthétiques, bornes et reprise des reçus
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import base64
import io
import json
from pathlib import Path
import zipfile
import pytest

from eidolon_core import documents
from eidolon_core.beta_runtime import BetaRuntime, ServiceError
from tests.test_beta_runtime_g270 import config


def zipped(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, text in entries:
            z.writestr(name, text)
    return out.getvalue()


def office(kind, text="Document synthétique < non vérifié"):
    from xml.sax.saxutils import escape
    text = escape(text)
    entries = {
        "docx": [("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:body></w:document>')],
        "odt": [("content.xml", '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><text:p>'+text+'</text:p></office:document-content>')],
        "pptx": [("ppt/slides/slide1.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:t>'+text+'</a:t></a:r></a:p></p:sld>')],
        "xlsx": [("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>'+text+'</t></si></sst>'),
                 ("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="B1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')]
    }
    return zipped(entries[kind])


@pytest.mark.parametrize("kind", ["txt", "md", "csv", "docx", "odt", "pptx", "xlsx"])
def test_extract_real_formats_in_limited_child(kind):
    data = b"Document synthetique" if kind in ("txt", "md", "csv") else office(kind)
    result = documents.extract(data, "source."+kind)
    assert "Document" in result["text"] and result["format"] == kind
    assert result["bytes"] == len(data) and result["untrusted"] and not result["truncated"]
    assert result["limitations"] and len(result["sha256"]) == 64
    if kind == "xlsx":
        assert "non recalculée" in result["text"]


def test_pdf_native_text_no_ocr():
    if not Path('/usr/bin/pdftotext').is_file():
        pytest.skip('poppler-utils unavailable')
    stream = b'BT /F1 12 Tf 72 720 Td (Synthetic PDF text) Tj ET'
    data = b'%PDF-1.4\n1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources <</Font <</F1 4 0 R>>>> /Contents 5 0 R>> endobj\n4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n5 0 obj <</Length '+str(len(stream)).encode()+b'>> stream\n'+stream+b'\nendstream endobj\ntrailer <</Root 1 0 R>>\n%%EOF'
    result = documents.extract(data, 'synthetic.pdf')
    assert 'Synthetic PDF text' in result['text'] and 'aucun OCR' in result['limitations']


@pytest.mark.parametrize("entries", [
    [("../escape", "x"), ("word/document.xml", "<x/>")],
    [("word/document.xml", "<x/>"), ("word/document.xml", "<y/>")],
    [("word/vbaProject.bin", "macro"), ("word/document.xml", "<x/>")],
    [("word/document.xml", '<!DOCTYPE x [<!ENTITY e "expanded">]><x>&e;</x>')],
    [("word/document.xml", b'\xff\xfe'+ '<!DOCTYPE x><x/>'.encode('utf-16-le'))],
    [("word/document.xml", "<x>"+"a"*2000000+"</x>")],
])
def test_archive_xml_and_bomb_refused(entries):
    with pytest.raises(documents.DocumentError):
        documents.extract(zipped(entries), 'unsafe.docx')


def test_visible_truncation_and_unsupported_binary():
    result = documents.extract(b'a'*17000, 'long.txt')
    assert len(result['text']) == 16000 and result['truncated']
    for name, data in [('x.doc', b'legacy'), ('x.exe', b'MZ'), ('x.txt', b'\xff'), ('x.pdf', b'not pdf')]:
        with pytest.raises(documents.DocumentError): documents.extract(data, name)


def test_document_preview_commit_recovery_is_not_memory_write(tmp_path):
    cfg = config(tmp_path)
    def no_bridge(*a, **k): raise AssertionError('no implicit memory request')
    rt = BetaRuntime(cfg, bridge=no_bridge)
    raw = office('docx')
    params = {'name':'source.docx','data_base64':base64.b64encode(raw).decode()}
    try:
        a = rt.preview('pc0', 'actor', 'doc1', 'document.import', params)
        assert 'data_base64' not in a['proposal']['parameters']
        assert rt.preview('pc0', 'actor', 'doc1', 'document.import', params) == a
        with pytest.raises(ServiceError, match='KEY_REUSED'):
            rt.preview('pc0', 'actor', 'doc1', 'document.import', dict(params, name='other.docx'))
        with pytest.raises(ServiceError, match='NOT_FOUND'):
            rt.commit('pc1', a['proposal']['id'], a['sha256'])
        saved = rt.commit('pc0', a['proposal']['id'], a['sha256'])
        assert saved['result']['status'] == 'EXTRACTED_NOT_REMEMBERED'
        obs = rt.turn_observations('pc0', 'conv', 'turn', 'Question', a['proposal']['id'])
        assert obs[0]['state'] == 'UNVERIFIED' and 'Document' in obs[0]['text']
    finally: rt.close()
    rt = BetaRuntime(cfg, bridge=no_bridge)
    try:
        assert rt.receipts('pc0')[0] == saved and not rt.receipts('pc1')
    finally: rt.close()


def test_nas_document_changed_and_upload_limit(tmp_path):
    cfg = config(tmp_path); rt = BetaRuntime(cfg)
    path = Path(cfg['profiles']['user0']['file_roots']['nas'])/'source.docx'
    path.write_bytes(office('docx'))
    try:
        a = rt.preview('pc0','actor','nas','document.read',{'root':'nas','path':'source.docx'})
        path.write_bytes(office('docx', 'changed'))
        assert rt.commit('pc0',a['proposal']['id'],a['sha256'])['state'] == 'UNKNOWN'
        with pytest.raises(ServiceError, match='UPLOAD'):
            rt.preview('pc0','actor','big','document.import',{'name':'x.txt','data_base64':'A'*750000})
    finally: rt.close()


def test_large_receipts_remain_pageable_without_loss(tmp_path):
    rt=BetaRuntime(config(tmp_path))
    try:
        expected=[]
        for i in range(8):
            p=rt.preview('pc0','actor',f'large{i}','document.import',{'name':'long.txt','data_base64':base64.b64encode(('文'*16000).encode()).decode()})
            rt.commit('pc0',p['proposal']['id'],p['sha256']);expected.append(p['proposal']['id'])
        found=[];cursor=None;pages=0
        while True:
            page=rt.receipt_page('pc0',cursor);pages+=1
            assert len(json.dumps(page,ensure_ascii=False).encode())<262144
            found.extend(r['proposal']['id'] for r in page['receipts'])
            cursor=page['next_before']
            if cursor is None:break
        assert found==list(reversed(expected)) and pages>1
        assert not rt.receipt_page('pc1')['receipts']
    finally:rt.close()
