from html.parser import HTMLParser
from pathlib import Path
class Node:
 def __init__(self,tag='',attrs=(),parent=None,start=0):self.tag=tag;self.attrs=dict(attrs);self.parent=parent;self.children=[];self.start=start;self.end=None
 def text(self):return ' '.join(' '.join(x.text() if isinstance(x,Node) else x for x in self.children).split())
 def walk(self):
  for x in self.children:
   if isinstance(x,Node):yield x;yield from x.walk()
 def find(self,cls):return [x for x in self.walk() if cls in x.attrs.get('class','').split()]
class Parser(HTMLParser):
 def __init__(self,source):
  super().__init__();self.source=source;self.lines=[0];self.lines.extend(i+1 for i,c in enumerate(source) if c=='\n');self.root=Node();self.cur=self.root;self.feed(source)
 def get_offset(self):
  l,c=self.getpos();return self.lines[l-1]+c
 def handle_starttag(self,t,a):
  n=Node(t,a,self.cur,self.get_offset());self.cur.children.append(n)
  if t not in ['meta','link','br','hr','img','input','source','area','wbr','embed']:self.cur=n
  else:n.end=self.get_offset()+len(self.get_starttag_text())
 def handle_endtag(self,t):
  n=self.cur
  while n.parent:
   if n.tag==t:n.end=self.source.index('>',self.get_offset())+1;self.cur=n.parent;break
   n=n.parent
 def handle_data(self,d):self.cur.children.append(d)
def groups(source):return {g.attrs['id']:g for g in Parser(source).root.find('month-group')}
def cards(panel):return {n.find('card-label')[0].text():n.find('card-value')[0].text() for n in panel.find('card') if n.find('card-label') and n.find('card-value')}
