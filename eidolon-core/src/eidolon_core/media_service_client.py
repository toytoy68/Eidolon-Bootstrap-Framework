# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_service_client.py
# Description : Façade locale facultative pour raccorder Core au service média
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""No dependency on Comfy graphs, GPU libraries, or the Memory Engine.

The caller supplies an already authorized request and a stable idempotency key.
Conversation interpretation/consent remains with the existing Core media layer.
"""
import base64
import json
import re
from .media_agents import MediaError, parse_json
from .media_backends import endpoint
from .media_http import exchange

class LocalGenerationClient:
    def __init__(self, url, token, *, transport=exchange):
        self.url=endpoint(url)
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token):
            raise MediaError('INVALID_TOKEN')
        self.token=token;self.transport=transport

    def _call(self, method, path, payload=None, key=None, binary=False):
        headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'}
        if key is not None:
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key):
                raise MediaError('INVALID_IDEMPOTENCY_KEY')
            headers['Idempotency-Key']=key
        body=None if payload is None else json.dumps(payload,allow_nan=False).encode()
        content_type,data=self.transport(method,self.url+path,body,headers,64*1024*1024 if binary else 1_000_000,
                                         timeout=30,accepted_statuses=(200,201,202))
        if binary:
            if content_type not in {'image/png','video/mp4'}:raise MediaError('INVALID_MEDIA_TYPE')
            return data,content_type
        if content_type!='application/json':raise MediaError('INVALID_API_RESPONSE')
        return parse_json(data)

    @staticmethod
    def _id(value):
        if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{32}',value):raise MediaError('INVALID_JOB_ID')
        return value

    def submit(self, request, *, idempotency_key):
        result=self._call('POST','/v1/jobs',request,idempotency_key)
        self._id(result['id']);return result
    def status(self, job_id):return self._call('GET','/v1/jobs/'+self._id(job_id))
    def cancel(self, job_id):return self._call('POST','/v1/jobs/'+self._id(job_id)+'/cancel',{})
    def result(self, job_id):return self._call('GET','/v1/jobs/'+self._id(job_id)+'/result',binary=True)
    def metadata(self, job_id):return self._call('GET','/v1/jobs/'+self._id(job_id)+'/metadata')
    def models(self):return self._call('GET','/v1/models')
    def upload_png(self, body):
        if type(body) is not bytes or len(body)>8*1024*1024:raise MediaError('ASSET_LIMIT')
        return self._call('POST','/v1/assets',{'png_base64':base64.b64encode(body).decode()})
