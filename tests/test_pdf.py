import pymupdf
import pytest

from mtr_agent.pdf import extract_pdf


def test_vector_pdf_preserves_coordinates_and_candidates(tmp_path):
    path = tmp_path / 'map.pdf'
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=200)
    page.insert_text((50, 90), 'Central')
    page.insert_text((250, 90), 'Admiralty')
    page.draw_line((65, 110), (270, 110), color=(1, 0, 0), width=3)
    doc.save(path)
    doc.close()
    result = extract_pdf(path)
    assert result['requires_review']
    assert result['pages'][0]['labels'][0]['bbox']
    assert result['pages'][0]['segments'][0]['color'] == [1.0, 0.0, 0.0]
    edge = result['pages'][0]['candidate_edges'][0]
    assert {edge['a'], edge['b']} == {'CEN', 'ADM'}
    assert edge['status'] == 'unreviewed'
    assert 'minutes' not in edge
    assert result['sha256']


def test_scanned_page_and_bad_files(tmp_path):
    path = tmp_path / 'blank.pdf'
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    assert extract_pdf(path)['pages'][0]['needs_ocr']
    broken = tmp_path / 'broken.pdf'
    broken.write_text('not a pdf')
    with pytest.raises(ValueError, match='PDF'):
        extract_pdf(broken)
    with pytest.raises(ValueError, match='PDF'):
        extract_pdf(tmp_path / 'absent.pdf')
