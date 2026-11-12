import re
import tempfile
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from botocore.exceptions import ClientError
from sqlalchemy import update
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Video
from .security import current_user, require_csrf
from .videos import get_video, own_video
from .storage import store, bucket

router = APIRouter(prefix='/api/videos', tags=['Video upload and playback'])


class BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self,app):
        self.app = app

    async def __call__(self,scope,receive,send):
        if scope['type'] != 'http' or scope.get('method') not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        path = scope.get('path','')
        maximum = settings().max_upload_bytes if path.endswith('/source') else 65536
        headers = dict(scope.get('headers',[]))
        length = headers.get(b'content-length',b'')
        if length:
            try:
                if int(length) < 0 or int(length) > maximum:
                    return await JSONResponse({'detail':'Превышен допустимый размер загрузки'},413)(scope,receive,send)
            except ValueError:
                return await JSONResponse({'detail':'Некорректная длина запроса'},400)(scope,receive,send)
        size = 0
        started = False

        async def limited_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body',b''))
            if size > maximum:
                raise BodyTooLarge()
            return message

        async def tracked_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            await self.app(scope,limited_receive,tracked_send)
        except BodyTooLarge:
            if not started:
                await JSONResponse({'detail':'Превышен допустимый размер загрузки'},413)(scope,receive,send)


@router.put('/{video_id}/source',status_code=202)
async def upload(video_id: str,request: Request,user=Depends(require_csrf),db: Session = Depends(get_db)):
    own_video(video_id,user,db)
    claimed = db.execute(update(Video).where(Video.id == video_id,Video.status.in_(['uploading','failed']))
                         .values(status='receiving',error='',updated_at=time.time()))
    db.commit()
    if claimed.rowcount != 1:
        raise HTTPException(409,'Видео уже загружено или обрабатывается')
    try:
        with tempfile.TemporaryDirectory(prefix='stackbridge-upload-') as directory:
            path = Path(directory)/'source'
            total = 0
            with path.open('wb') as output:
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > settings().max_upload_bytes:
                        raise BodyTooLarge()
                    output.write(chunk)
            if total == 0:
                raise HTTPException(422,'Выберите непустой видеофайл')
            key = f'{video_id}/source'
            await run_in_threadpool(store().upload_file,str(path),bucket(),key)
            db.execute(update(Video).where(Video.id == video_id).values(source_key=key,size=total,status='queued',attempts=0,lease_at=0,updated_at=time.time()))
            db.commit()
    except BaseException as error:
        db.rollback()
        db.execute(update(Video).where(Video.id == video_id,Video.status == 'receiving').values(status='uploading',updated_at=time.time()))
        db.commit()
        if isinstance(error,BodyTooLarge):
            raise HTTPException(413,'Превышен допустимый размер загрузки')
        if isinstance(error,(HTTPException,KeyboardInterrupt,SystemExit)):
            raise
        if isinstance(error,ClientError):
            raise HTTPException(503,'Хранилище недоступно. Повторите загрузку')
        raise
    return {'id':video_id,'status':'queued'}


def byte_range(value,size):
    match = re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not match or not any(match.groups()) or size <= 0:
        raise ValueError('Invalid byte range')
    left,right = match.groups()
    if len(left) > 20 or len(right) > 20:
        raise ValueError('Invalid byte range')
    if left:
        start,end = int(left),min(int(right),size-1) if right else size-1
    else:
        suffix = int(right)
        if suffix <= 0:
            raise ValueError('Invalid suffix')
        start,end = max(0,size-suffix),size-1
    if start >= size or start > end:
        raise ValueError('Unsatisfiable range')
    return start,end


def object_response(key,content_type,request):
    s3 = store()
    try:
        metadata = s3.head_object(Bucket=bucket(),Key=key)
        size = metadata['ContentLength']
        start,end,status = 0,size-1,200
        headers = {'Accept-Ranges':'bytes','Content-Length':str(size),'Cache-Control':'no-store'}
        value = request.headers.get('range')
        if value:
            try:
                start,end = byte_range(value,size)
            except ValueError:
                return Response(status_code=416,headers={'Content-Range':f'bytes */{size}','Cache-Control':'no-store'})
            status = 206
            headers.update({'Content-Range':f'bytes {start}-{end}/{size}','Content-Length':str(end-start+1)})
        if request.method == 'HEAD':
            return Response(status_code=status,media_type=content_type,headers=headers)
        args = {'Bucket':bucket(),'Key':key}
        if status == 206:
            args['Range'] = f'bytes={start}-{end}'
        result = s3.get_object(**args)
    except ClientError:
        raise HTTPException(503,'Медиафайл временно недоступен')

    def chunks():
        body = result['Body']
        try:
            yield from body.iter_chunks(chunk_size=256*1024)
        finally:
            body.close()
    return StreamingResponse(chunks(),status_code=status,media_type=content_type,headers=headers)


@router.api_route('/{video_id}/media',methods=['GET','HEAD'])
def media(video_id: str,request: Request,user=Depends(current_user),db: Session = Depends(get_db)):
    video = get_video(video_id,user,db)
    if video.status != 'ready' or not video.media_key:
        raise HTTPException(409,'Видео ещё не готово к просмотру')
    return object_response(video.media_key,'video/mp4',request)


@router.api_route('/{video_id}/thumbnail',methods=['GET','HEAD'])
def thumbnail(video_id: str,request: Request,user=Depends(current_user),db: Session = Depends(get_db)):
    video = get_video(video_id,user,db)
    if not video.thumbnail_key:
        raise HTTPException(404,'Обложка ещё не готова')
    return object_response(video.thumbnail_key,'image/jpeg',request)

