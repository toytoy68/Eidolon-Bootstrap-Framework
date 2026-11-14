# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_display.py
# Description : Cadrage écran sans étirement et export CPU borné
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Generation geometry and display canvas are deliberately separate."""
import io
from .media_agents import MediaError

FORMATS = ('native', '16:9', '4:3-pillarbox')
OUTPUT_SIZES = ('native', '720p', '1080p')

def generation_size(kind, format, *, profile=None):
    if format == 'native': return None
    if profile == 'sdxl-text': return (1024,576) if format == '16:9' else (768,576)
    if kind == 'video': return (512,288) if format == '16:9' else (384,288)
    return (768,432) if format == '16:9' else (576,432)

def canvas_size(request):
    size = request.get('output_size', 'native')
    if size == '720p': return (1280,720)
    if size == '1080p': return (1920,1080)
    w,h=request['width'],request['height']
    if request.get('format') == '4:3-pillarbox': w=h*16//9
    return w,h

def fit(image, size, *, mask=False):
    """Uniform resize and black padding; no crop, stretch, or AI upscaling."""
    from PIL import Image
    image=image.convert('RGB'); w,h=size
    scale=min(w/image.width,h/image.height)
    fitted=(max(1,round(image.width*scale)),max(1,round(image.height*scale)))
    image=image.resize(fitted,Image.Resampling.NEAREST if mask else Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',size,(0,0,0))
    canvas.paste(image,((w-fitted[0])//2,(h-fitted[1])//2))
    return canvas

def fit_png(body, size, *, mask=False, expected=None):
    from PIL import Image
    with Image.open(io.BytesIO(body)) as image:
        if image.width>2048 or image.height>2048: raise MediaError('IMAGE_DIMENSIONS_EXCEEDED')
        if expected is not None and image.size != expected: raise MediaError('IMAGE_GEOMETRY_MISMATCH')
        result=fit(image,size,mask=mask)
        out=io.BytesIO();result.save(out,format='PNG');return out.getvalue()
