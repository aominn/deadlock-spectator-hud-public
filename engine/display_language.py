"""Display-only language handling; never transform identity, paths or config keys."""
from pathlib import Path
import json,re
_MESSAGES=json.loads((Path(__file__).with_name('manager-messages.json')).read_text(encoding='utf-8'))
_PREFIXES=sorted((key for key in _MESSAGES if key.endswith('：')),key=len,reverse=True)
def language(value):return 'ja' if str(value).lower().replace('_','-').split('-')[0] in ('ja','japanese') else 'en'
def message(text,locale):
 if language(locale)=='ja' or not isinstance(text,str):return text
 if text in _MESSAGES:return _MESSAGES[text]
 for prefix in _PREFIXES:
  if text.startswith(prefix):return _MESSAGES[prefix]+message(text[len(prefix):],locale)
 return 'The operation could not be completed. Check the installation and try again.' if re.search('[ぁ-んァ-ヶ一-龥]',text) else text
