"""Safe native answer formatting and host budget controls; no web renderer."""
from functools import lru_cache
from html import escape
import io
import math
import re

from PySide6.QtCore import QUrl,Qt
from PySide6.QtGui import QImage,QTextDocument
from PySide6.QtWidgets import QTextBrowser,QDialog,QVBoxLayout,QFormLayout,QHBoxLayout,QSpinBox,QLineEdit,QCheckBox,QPushButton,QMessageBox


def usage_text(usage):
    text=f"请求 {usage.get('model_calls',0)} 次 · 计算 {usage.get('tool_calls',0)} 次"
    if usage.get('unknown_usage_requests'):text+=' · '+str(usage['unknown_usage_requests'])+' 次用量未知'
    elif usage.get('model_calls'):text+=' · '+str(usage.get('known_input_tokens',0)+usage.get('known_output_tokens',0))+' tokens'
    if usage.get('known_cost') is not None:
        text+=' · 已报告用量估算 '+format(usage['known_cost'],'.6g')+' '+usage.get('currency','')
    return text


@lru_cache(maxsize=128)
def formula_png(source):
    if len(source)>512 or source.count('{')>64:return None
    try:
        from matplotlib.mathtext import math_to_image
        from matplotlib.font_manager import FontProperties
        from matplotlib import rc_context
        buffer=io.BytesIO()
        with rc_context({'text.usetex':False}):math_to_image('$'+source+'$',buffer,prop=FontProperties(size=12),dpi=150,format='png',color='#233e47')
        return buffer.getvalue()
    except (ValueError,RuntimeError,OverflowError,RecursionError):return None


def answer_html(text):
    """A small escaped Markdown subset; external/file images are never resolved."""
    images={};formula_count=0
    def inline(value):
        nonlocal formula_count
        pattern=r'(`[^`\n]{1,512}`|\*\*[^*\n]{1,2000}\*\*|\$\$[\s\S]{1,512}?\$\$|\$[^$\n]{1,512}\$|\\\([\s\S]{1,512}?\\\)|\\\[[\s\S]{1,512}?\\\])'
        parts=[];previous=0
        for match in re.finditer(pattern,value):
            parts.append(escape(value[previous:match.start()]));item=match.group()
            if item.startswith('`'):parts.append('<code>'+escape(item[1:-1])+'</code>')
            elif item.startswith('**'):parts.append('<b>'+escape(item[2:-2])+'</b>')
            else:
                source=item[2:-2] if item.startswith(('$$','\\(','\\[')) else item[1:-1]
                picture=formula_png(source) if formula_count<12 else None;formula_count+=1
                if picture:
                    key='math://formula/'+str(len(images));image=QImage.fromData(picture);images[key]=image
                    parts.append('<img src="'+key+'" width="'+str(max(1,round(image.width()/1.5)))+'" height="'+str(max(1,round(image.height()/1.5)))+'"/>')
                else:parts.append('<code>'+escape(item)+'</code>')
            previous=match.end()
        parts.append(escape(value[previous:]));return ''.join(parts)
    visible=text[:64000];blocks=[]
    for index,part in enumerate(visible.split('```')):
        if index%2:blocks.append('<pre>'+escape(part)+'</pre>');continue
        part=re.sub(r'\$\$[\s\S]{1,512}?\$\$|\\\[[\s\S]{1,512}?\\\]',lambda m:m.group().replace('\n',' '),part)
        lines=part.splitlines();cursor=0
        while cursor<len(lines):
            line=lines[cursor]
            if cursor+1<len(lines) and '|' in line and re.fullmatch(r'[\s|:\-]+',lines[cursor+1]) and '-' in lines[cursor+1]:
                rows=[line];cursor+=2
                while cursor<len(lines) and '|' in lines[cursor] and len(rows)<100:rows.append(lines[cursor]);cursor+=1
                blocks.append('<table border="1" cellspacing="0" cellpadding="5">'+''.join('<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in row.strip().strip('|').split('|')[:12])+'</tr>' for row in rows)+'</table>');continue
            heading=re.match(r'^#{1,3}\s+(.+)',line)
            blocks.append('<h3>'+inline(heading[1])+'</h3>' if heading else '<p>'+inline(line)+'</p>')
            cursor+=1
    if len(text)>len(visible):blocks.append('<p>预览已截断，完整回答保存在原始记录和结果包中。</p>')
    return '<html><body style="color:#233e47;font-family:Microsoft YaHei;font-size:13px;">'+''.join(blocks)+'</body></html>',images


class AnswerView(QTextBrowser):
    def __init__(self,text,parent=None):
        super().__init__(parent);self.setOpenExternalLinks(False);self.setOpenLinks(False);self.setReadOnly(True)
        self.setFrameShape(self.Shape.NoFrame);self.setStyleSheet('QTextBrowser{background:transparent;border:0;}');self.plain_answer=text
        html,images=answer_html(text);self._images=images
        for key,image in images.items():self.document().addResource(QTextDocument.ResourceType.ImageResource,QUrl(key),image)
        self.setHtml(html);self.setMinimumHeight(60);self.setMaximumHeight(650)
        self.document().contentsChanged.connect(self.adjust_height)

    def loadResource(self,kind,name):
        return getattr(self,'_images',{}).get(name.toString(),QImage())

    def adjust_height(self):self.setFixedHeight(min(650,max(60,math.ceil(self.document().size().height())+10)))
    def resizeEvent(self,event):super().resizeEvent(event);self.adjust_height()


class BudgetDialog(QDialog):
    def __init__(self,session,parent=None):
        super().__init__(parent);self.session=session;self.setWindowTitle('任务预算与用量');self.resize(660,650)
        from .app import label
        current=session.workflow_usage();policy=current.get('policy',session.workflow.data['policy']);layout=QVBoxLayout(self)
        layout.addWidget(label(usage_text(current),'sectionTitle'))
        layout.addWidget(label('同一任务的澄清、暂停与重启沿用累计用量；已发生请求的单价不追溯改写。保存设置不请求模型。','muted'))
        form=QFormLayout();self.spins={}
        for key,title,maximum in [('max_model_calls','模型请求上限',100),('max_tool_calls','实际计算上限',200),('request_output_tokens','单次输出上限',32768),
                                 ('max_input_tokens','累计输入token上限',10000000),('max_output_tokens','累计输出token上限',10000000),('max_active_seconds','累计活动用时（秒）',86400)]:
            field=QSpinBox();field.setRange(0 if key.startswith('max_') and key not in ('max_model_calls','max_tool_calls') else 1,maximum)
            if key=='request_output_tokens':field.setMinimum(16)
            field.setSpecialValueText('不限制');field.setValue(int(policy.get(key) or 0));self.spins[key]=field;form.addRow(title,field)
        self.texts={}
        for key,title in [('input_per_million','每百万输入token单价'),('output_per_million','每百万输出token单价'),('currency','币种'),('max_cost','任务金额上限')]:
            field=QLineEdit('' if policy.get(key) is None else str(policy[key]));field.setPlaceholderText('留空表示未知/不限制');self.texts[key]=field;form.addRow(title,field)
        self.reuse=QCheckBox('复用已核验的相同输入结果');self.reuse.setChecked(policy['reuse_results']);form.addRow('',self.reuse);layout.addLayout(form)
        layout.addWidget(label('服务未报告用量时显示未知，并保留预留值。输入按字节作保守估算，金额由填写单价估算；实际分词、缓存、推理与账单可能不同。停止远程请求不保证撤销费用。','muted'))
        details=QTextBrowser();details.setPlainText('已报告输入：'+str(current.get('known_input_tokens',0))+' tokens\n已报告输出：'+str(current.get('known_output_tokens',0))+' tokens\n未知用量请求：'+str(current.get('unknown_usage_requests',0))+'\n预留输入/输出：'+str(current.get('reserved_input_tokens',0))+' / '+str(current.get('reserved_output_tokens',0))+'\n活动用时：'+format(current.get('active_seconds',0),'.2f')+'秒');details.setMaximumHeight(130);layout.addWidget(details)
        row=QHBoxLayout();cancel=QPushButton('返回');cancel.clicked.connect(self.reject);row.addWidget(cancel);save=QPushButton('保存预算');save.clicked.connect(self.save_budget);row.addWidget(save);layout.addLayout(row)

    def save_budget(self):
        try:
            values={k:field.value() or None for k,field in self.spins.items()};values.update({k:(field.text().strip() if k=='currency' else float(field.text()) if field.text().strip() else None) for k,field in self.texts.items()})
            values['reuse_results']=self.reuse.isChecked();self.session.set_workflow_budget(values);self.accept()
        except (ValueError,RuntimeError) as error:QMessageBox.warning(self,'预算未保存',str(error))
