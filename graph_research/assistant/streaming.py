"""Bounded SSE framing and provisional final-answer text; no partial tool execution."""
import json
import time


class StreamFormatError(ValueError):pass


def partial_final_answer(text):
    """Read top-level JSON keys only. Preview may be discarded after validation."""
    decoder=json.JSONDecoder();index=0;action=None;answer=None
    def skip(pos):
        while pos<len(text) and text[pos].isspace():pos+=1
        return pos
    index=skip(index)
    if index>=len(text) or text[index]!='{':return None
    index+=1
    while True:
        index=skip(index)
        try:key,end=decoder.raw_decode(text,index)
        except ValueError:return answer if action=='final' else None
        if not isinstance(key,str):return None
        index=skip(end)
        if index>=len(text) or text[index]!=':':return None
        index=skip(index+1)
        if key=='answer' and index<len(text) and text[index]=='"':
            cursor=index+1;safe=cursor
            while cursor<len(text):
                char=text[cursor]
                if char=='"':break
                if char=='\\':
                    if cursor+1>=len(text):break
                    if text[cursor+1]=='u':
                        if cursor+6>len(text):break
                        try:code=int(text[cursor+2:cursor+6],16)
                        except ValueError:return None
                        width=12 if 0xd800<=code<=0xdbff else 6
                        if cursor+width>len(text):break
                        cursor+=width
                    else:cursor+=2
                else:cursor+=1
                safe=cursor
            try:answer=json.loads(text[index:safe]+'"')
            except ValueError:return None
            answer=''.join(c for c in answer if not 0xd800<=ord(c)<=0xdfff)
            if action=='final':return answer
        try:value,end=decoder.raw_decode(text,index)
        except ValueError:return answer if action=='final' else None
        if key=='action':
            action=value
            if action!='final':return None
        index=skip(end)
        if index>=len(text) or text[index]!=',':return answer if action=='final' else None
        index+=1


def sse_events(response,*,cancel=None,timeout=90):
    started=time.monotonic();total=0;buffer=b'';data=[]
    for chunk in response.iter_bytes():
        if cancel is not None and cancel.is_set():raise InterruptedError('用户停止了模型响应；用量可能未知。')
        if time.monotonic()-started>timeout:raise StreamFormatError('流式响应超过本次请求总时限。')
        total+=len(chunk)
        if total>1024*1024:raise StreamFormatError('流式响应超过1MiB。')
        buffer+=chunk
        while b'\n' in buffer:
            raw,buffer=buffer.split(b'\n',1)
            try:line=raw.rstrip(b'\r').decode('utf-8')
            except UnicodeError:raise StreamFormatError('流式响应不是有效UTF-8。') from None
            if not line:
                if data:yield '\n'.join(data);data=[]
            elif line.startswith('data:'):data.append(line[5:].lstrip(' '))
    if cancel is not None and cancel.is_set():raise InterruptedError('用户停止了模型响应；用量可能未知。')
    if buffer:
        try:line=buffer.decode('utf-8')
        except UnicodeError:raise StreamFormatError('流式响应编码不完整。') from None
        if line.startswith('data:'):data.append(line[5:].lstrip(' '))
    if data:yield '\n'.join(data)


def consume_stream(response,mode,*,on_text=None,on_usage=None,cancel=None,timeout=90):
    text='';finished=False;last_preview=0.;last_text=None;usage=None
    for raw in sse_events(response,cancel=cancel,timeout=timeout):
        if raw=='[DONE]':break
        try:event=json.loads(raw)
        except ValueError:raise StreamFormatError('流式事件不是完整JSON。') from None
        if not isinstance(event,dict):raise StreamFormatError('流式事件格式无效。')
        candidate=event.get('usage')
        if mode=='responses':
            kind=event.get('type')
            if kind in ('error','response.failed','response.incomplete'):raise StreamFormatError('模型流式响应未完成或被服务拒绝。')
            if kind=='response.output_text.delta':
                delta=event.get('delta')
                if not isinstance(delta,str):raise StreamFormatError('流式文本分片无效。')
                text+=delta
            elif kind=='response.completed':
                body=event.get('response',{});candidate=body.get('usage')
                if body.get('status') not in (None,'completed'):raise StreamFormatError('模型响应状态不是完成。')
                full=''.join(c.get('text','') for item in body.get('output',[]) for c in item.get('content',[]) if c.get('type')=='output_text')
                if full and text and full!=text:raise StreamFormatError('完成响应与文本分片不一致。')
                text=full or text;finished=True
        else:
            if event.get('error'):raise StreamFormatError('对话补全流式响应被服务拒绝。')
            choices=event.get('choices',[])
            if choices:
                choice=choices[0];delta=choice.get('delta',{}).get('content')
                if delta is not None:
                    if not isinstance(delta,str):raise StreamFormatError('对话文本分片无效。')
                    text+=delta
                reason=choice.get('finish_reason')
                if reason is not None:
                    if reason!='stop':raise StreamFormatError('模型输出不完整或不是当前JSON决策协议。')
                    finished=True
        if isinstance(candidate,dict):
            usage=candidate
            if on_usage is not None:on_usage(candidate)
        now=time.monotonic()
        if on_text is not None and now-last_preview>=.15:
            preview=partial_final_answer(text)
            if preview is not None and preview!=last_text:on_text(preview);last_text=preview;last_preview=now
    if not finished:raise StreamFormatError('流式连接结束，但没有收到完成事件；未执行任何不完整决策。')
    return text,usage
