"""Conservative offline script checks, not model-language identification."""
import re
from PySide6.QtWidgets import QComboBox
from .i18n import tr

LANGUAGE_CODES=("zh","en","ja","ko","yue","auto","all_zh","all_ja","all_ko","all_yue","auto_yue")


class LanguageCombo(QComboBox):
    def __init__(self,value="zh",parent=None):
        super().__init__(parent);self.setEditable(True)
        names={"zh":tr("tts.lang_zh","中文"),"en":"English","ja":"日本語","ko":"한국어","yue":tr("tts.lang_yue","粤语"),"auto":tr("tts.lang_auto","自动识别")}
        for code in LANGUAGE_CODES:
            base=code.removeprefix("all_").removesuffix("_yue") if code.startswith("auto") else code.removeprefix("all_")
            label=names.get(base,code)
            if code.startswith("all_"):label += " / " + tr("tts.lang_all","纯语言")
            self.addItem(label+" ("+code+")",code)
        self.setText(value)
        self.setToolTip(tr("tts.language_help","可选择常用语言或自行填写 API 代码；具体支持取决于接口与模型。"))

    def code(self):
        i=self.currentIndex()
        return str(self.itemData(i)) if i>=0 and self.currentText()==self.itemText(i) else self.currentText().strip()

    def text(self):return self.code()
    def setText(self,value):
        i=self.findData(str(value))
        if i>=0:self.setCurrentIndex(i)
        else:self.setEditText(str(value))


def inspect_text(text,code):
    code=str(code).split("-")[0].lower()
    if code in {"auto","auto_yue"} or not text.strip():return None
    base=code.removeprefix("all_")
    counts={"ja":len(re.findall(r"[\u3040-\u30ff]",text)),"ko":len(re.findall(r"[\uac00-\ud7af]",text)),"han":len(re.findall(r"[\u3400-\u9fff]",text)),"latin":len(re.findall(r"[a-zA-Z]",text))}
    total=sum(counts.values())
    if not total:return None
    if base not in {"zh","yue","en","ja","ko"}:return "unknown"
    if base in {"zh","yue"} and (counts["ja"] or counts["ko"] or counts["latin"]>=4 and not counts["han"]):return "mismatch"
    if base=="en" and counts["han"]+counts["ja"]+counts["ko"]>counts["latin"]:return "mismatch"
    if base=="ja" and not counts["ja"]:
        return "uncertain" if counts["han"] or total<4 else "mismatch"
    if base=="ko" and not counts["ko"]:return "uncertain" if total<4 else "mismatch"
    if total<4:return "uncertain"
    return None


def language_issues(lines,settings,provider_id):
    if provider_id not in {"gpt_sovits","azure_speech"}:return []
    code=settings.get("text_lang",settings.get("locale",""));issues=[]
    for i,text in enumerate(lines,1):
        result=inspect_text(text,code)
        if result:issues.append(dict(field="text",line=i,text=text[:150],code=code,reason=result))
    if provider_id=="gpt_sovits":
        text=settings.get("prompt","");code=settings.get("prompt_lang","")
        result=inspect_text(text,code)
        if result:issues.append(dict(field="reference",line=0,text=text[:150],code=code,reason=result))
    return issues
