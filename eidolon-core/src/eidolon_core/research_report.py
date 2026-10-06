# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_report.py
# Description : Projection des URL du rapport Web, sans changer les requêtes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Project a validated coordinator report; no network or authorization here.

Only structured URL fields are minimized. Paths, titles, snippets and page text
remain data, possibly sensitive. Digests are references, not secret protection.
The input is internal trusted state, not a general report validation API.
"""
from copy import deepcopy
import hashlib
from urllib.parse import urlsplit, urlunsplit


def _url_fields(record, name, *, full_digest=True):
    url = record.get(name)
    if url is None:
        return
    try:
        if type(url) is not str or len(url) > 2048:
            raise ValueError('invalid URL')
        raw = url.encode('utf-8')
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname:
            raise ValueError('invalid URL')
        # Canonical source URLs have no userinfo. Also strip it from any
        # optional hop description supplied by a trusted injected reader.
        record[name] = urlunsplit((parts.scheme, parts.netloc.rsplit('@', 1)[-1], parts.path, '', ''))
        if full_digest:
            record[name + '_sha256'] = hashlib.sha256(raw).hexdigest()
        if parts.query:
            record[name + '_query_sha256'] = hashlib.sha256(parts.query.encode('utf-8')).hexdigest()
    except (ValueError, UnicodeError):
        record[name] = None
        record[name + '_omitted'] = 'INVALID_URL'


def project_report(report):
    """Copy, then minimize display URLs without touching cache/transport URLs."""
    result = deepcopy(report)
    result['version'] = 2
    result['url_disclosure'] = 'origin_path_and_sha256'
    for source in result['sources']:
        _url_fields(source, 'url')
        _url_fields(source, 'final_url')
        retrieval = source.get('retrieval')
        if type(retrieval) is dict:
            _url_fields(retrieval, 'final_url')
            hops = retrieval.get('hops')
            if hops is not None:
                if type(hops) is not list or len(hops) > 11 or any(type(hop) is not dict for hop in hops):
                    retrieval.pop('hops')
                    retrieval['hops_omitted'] = 'INVALID_HOPS'
                else:
                    for hop in hops:
                        # Transport hop URLs are already minimized; do not
                        # mislabel a hash of that path as the full request URL.
                        _url_fields(hop, 'url', full_digest=False)
    return result
