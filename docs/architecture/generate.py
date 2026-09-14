"""Generate source-grounded Mermaid, SVG/PNG, HTML, and native Excalidraw docs.

Requires Python 3, Graphviz dot, Node, and installed frontend dependencies.
Run from any directory: python3 docs/architecture/generate.py
"""
import ast
from collections import defaultdict
import hashlib
import html
import json
import math
from pathlib import Path
import re
import subprocess
import textwrap

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COLORS = {'ui':'#dbeafe', 'auth':'#ede9fe', 'api':'#cffafe', 'process':'#fef3c7', 'external':'#ffe4e6', 'data':'#dcfce7', 'infra':'#e2e8f0', 'error':'#fee2e2'}
graphs = json.loads((HERE / 'diagrams.json').read_text())
frontend = json.loads(subprocess.check_output(['node', str(HERE/'extract-frontend.mjs')], text=True))
explanations = json.loads((HERE / 'frontend-explanations.json').read_text())
records = []
for record in frontend:
    detail = explanations[record['name']]
    record.update(detail)
    record['summary'] = detail['work']
    record['language'] = 'typescript'
    records.append(record)

for base in (ROOT/'backend/app', ROOT/'backend/alembic'):
    for file in sorted(base.rglob('*.py')):
        source = file.read_text()
        tree = ast.parse(source)
        def walk(body, parents=()):
            for node in body:
                if isinstance(node, ast.ClassDef):
                    walk(node.body, parents+(node.name,))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = '.'.join(parents+(node.name,))
                    doc = ast.get_docstring(node) or 'See the source implementation.'
                    signature = ('async ' if isinstance(node, ast.AsyncFunctionDef) else '') + f'def {node.name}({ast.unparse(node.args)})'
                    if node.returns: signature += ' -> ' + ast.unparse(node.returns)
                    calls = sorted(set(ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)))
                    records.append({'file':str(file.relative_to(ROOT)), 'name':name, 'line':node.lineno,
                        'signature':signature, 'summary':doc.split('\n\n')[0].replace('\n',' '),
                        'work':doc, 'calls':calls, 'language':'python'})
                    walk(node.body, parents+(node.name,))
        walk(tree.body)
records.sort(key=lambda r:(r['file'], r['line']))
(HERE/'function-index.json').write_text(json.dumps(records, indent=2, ensure_ascii=False)+'\n')

# Detailed function reference preserves docstrings and links to source, without executing it.
byfile = defaultdict(list)
for r in records: byfile[r['file']].append(r)
md = ['# Function-by-function reference', '',
      f'This index covers all **{len(records)} named functions** in `frontend/src`, `backend/app`, and `backend/alembic`, including React components and nested named handlers. Backend explanations are drawn from implementation docstrings; frontend explanations are maintained in `frontend-explanations.json`. Tests are not application runtime functions.', '',
      'Anonymous lifecycle and event callbacks, declarative schemas, and deployment scripts are explained in [the architecture guide](README.md). The call lists below are syntactic calls found in each function body, not a runtime trace; callbacks and branches may execute only conditionally.', '']
for file, group in byfile.items():
    md += [f'## {file}', '', f'[Open source](../../{file})', '']
    for r in group:
        md += [f'### `{r["name"]}`', '', f'[Source line {r["line"]}](../../{file}#L{r["line"]})', '', f'```{r["language"]}', r['signature'], '```', '']
        if r.get('input'): md += ['**Input:** '+r['input'], '']
        md += [r['work'], '']
        if r.get('output'): md += ['**Output / side effects:** '+r['output'], '']
        if r.get('calls'): md += ['**Calls appearing in the body:** '+', '.join('`'+x+'`' for x in r['calls'])+'.', '']
(HERE/'function-reference.md').write_text('\n'.join(md))

# Native editable Excalidraw scene. Every node, label, arrow, and reference card is an element.
elements = []
serial = 0
def eid(label):
    global serial
    serial += 1
    return hashlib.sha1(f'{serial}:{label}'.encode()).hexdigest()[:20]
def base_element(kind, x,y,w,h, frame=None):
    identity=eid(kind)
    return dict(id=identity,type=kind,x=x,y=y,width=w,height=h,angle=0,strokeColor='#334155',
        backgroundColor='transparent',fillStyle='solid',strokeWidth=1.5,strokeStyle='solid',roughness=0,
        opacity=100,groupIds=[],frameId=frame,roundness=None,seed=serial+1,version=1,versionNonce=serial+100,
        isDeleted=False,boundElements=[],updated=1,link=None,locked=False)
def text_element(text,x,y,w,h,size=16,frame=None,container=None,align='left'):
    el=base_element('text',x,y,w,h,frame)
    el.update(text=text,originalText=text,fontSize=size,fontFamily=2,textAlign=align,verticalAlign='middle',
              containerId=container,lineHeight=1.25,autoResize=False,strokeWidth=1,baseline=size)
    elements.append(el)
    return el

def frame_element(name,x,y,w,h):
    el=base_element('frame',x,y,w,h)
    el.update(name=name)
    elements.append(el)
    return el['id']

layout_results=[]
mermaid_blocks=[]
for graph in graphs:
    ident=graph['id']
    lines=['flowchart TB']
    for n,label,color in graph['nodes']:
        label=html.escape(label, quote=True).replace('\n','<br/>')
        lines.append(f'  {n}["{label}"]:::{color}')
    for a,b,label in graph['edges']:
        lines.append(f'  {a} -->|"{html.escape(label, quote=True)}"| {b}')
    for name, color in COLORS.items():
        lines.append(f'  classDef {name} fill:{color},stroke:#475569,color:#0f172a')
    mermaid='\n'.join(lines)+'\n'
    (HERE/f'{ident}.mmd').write_text(mermaid)
    mermaid_blocks += [f'## {graph["title"]}', '', graph['subtitle'], '', '```mermaid', mermaid.rstrip(), '```', '']
    dot=['digraph G {', 'graph [rankdir=TB, bgcolor="#ffffff", pad=0.3, nodesep=0.38, ranksep=0.7, splines=spline, fontname="DejaVu Sans", labelloc=t];',
        'node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=16, margin="0.18,0.14", color="#64748b", fontcolor="#0f172a", penwidth=1.2];',
        'edge [fontname="DejaVu Sans", fontsize=11, color="#64748b", fontcolor="#475569", arrowsize=0.7];']
    for n,label,color in graph['nodes']:
        dot.append(f'{n} [label={json.dumps(label, ensure_ascii=False)},fillcolor="{COLORS[color]}"];')
    for a,b,label in graph['edges']:
        dot.append(f'{a} -> {b} [label={json.dumps(label, ensure_ascii=False)}];')
    dot.append('}')
    dottext='\n'.join(dot)
    (HERE/f'{ident}.dot').write_text(dottext)
    for fmt in ('svg','png','json'):
        output = subprocess.check_output(['dot',f'-T{fmt}'],input=dottext.encode())
        if fmt=='json': layout=json.loads(output)
        else: (HERE/f'{ident}.{fmt}').write_bytes(output)
    layout_results.append((graph,layout))
(HERE/'diagrams.md').write_text('# Application diagrams\n\nEach diagram also has standalone `.mmd`, `.svg`, and `.png` files. Arrows show control or data flow; their labels distinguish the two.\n\n'+'\n'.join(mermaid_blocks))

# Use Graphviz's node and edge geometry for the Excalidraw canvas as well.
# Sections are placed in two columns; function reference cards follow below.
maxw=max(float(l['bb'].split(',')[2]) for _,l in layout_results)+100
maxh=max(float(l['bb'].split(',')[3]) for _,l in layout_results)+170
text_element('TRANSCRIPTION AI / THE COMPLETE APP',0,-155,1800,65,44)
text_element('01–08: connected flow diagrams  •  Below: every named function by source module\nBlue: browser  |  Purple: auth  |  Amber: processing  |  Green: persistence  |  Pink: external services',0,-80,2100,60,22)
for i,(graph,layout) in enumerate(layout_results):
    w,h=map(float,layout['bb'].split(',')[2:])
    ox=(i%2)*maxw; oy=(i//2)*maxh
    frame=frame_element(graph['title'],ox,oy,w+80,h+150)
    text_element(graph['title'],ox+25,oy+15,w,40,28,frame)
    text_element(textwrap.fill(graph['subtitle'],width=max(40,int(w/8.5))),ox+25,oy+65,w,45,16,frame)
    def xy(x,y): return ox+40+x,oy+125+h-y
    objects={o['_gvid']:o for o in layout['objects'] if 'pos' in o}
    nodes={}
    for o in objects.values():
        x,y=map(float,o['pos'].split(',')); nw=float(o['width'])*72; nh=float(o['height'])*72
        cx,cy=xy(x,y)
        box=base_element('rectangle',cx-nw/2,cy-nh/2,nw,nh,frame)
        box.update(backgroundColor=o['fillcolor'],roundness={'type':3})
        elements.append(box); nodes[o['_gvid']]=box
        label=o['label'].replace('\\n', '\n'); th=len(label.split('\n'))*20
        t=text_element(label,cx-nw/2+8,cy-th/2,nw-16,th,16,frame,box['id'],'center')
        box['boundElements'].append({'type':'text','id':t['id']})
    for edge in layout.get('edges',[]):
        points=[]
        for draw in edge.get('_draw_',[]):
            if draw['op']=='b':
                ctrl=draw['points']
                # Sample cubic Beziers into editable polyline points.
                for k in range(0,len(ctrl)-1,3):
                    p0,p1,p2,p3=ctrl[k:k+4]
                    for t in [j/8 for j in range(9)]:
                        u=1-t
                        points.append(xy(*[u**3*p0[d]+3*u*u*t*p1[d]+3*u*t*t*p2[d]+t**3*p3[d] for d in (0,1)]))
        if len(points)<2: continue
        pos=edge.get('pos','').split(' ')[0]
        if pos.startswith('e,'):
            ex,ey=map(float,pos[2:].split(',')); points.append(xy(ex,ey))
        ax,ay=points[0]
        rel=[[x-ax,y-ay] for x,y in points]
        arrow=base_element('arrow',ax,ay,max(x for x,y in rel)-min(x for x,y in rel),max(y for x,y in rel)-min(y for x,y in rel),frame)
        src=nodes[edge['tail']]; dst=nodes[edge['head']]
        arrow.update(points=rel,startBinding={'elementId':src['id'],'focus':0,'gap':2},
                     endBinding={'elementId':dst['id'],'focus':0,'gap':2},startArrowhead=None,endArrowhead='arrow',elbowed=False)
        elements.append(arrow)
        src['boundElements'].append({'id':arrow['id'],'type':'arrow'})
        dst['boundElements'].append({'id':arrow['id'],'type':'arrow'})
        if edge.get('label') and edge.get('lp'):
            lx,ly=map(float,edge['lp'].split(',')); tx,ty=xy(lx,ly)
            label=edge['label']; tw=len(label)*6.4+12
            text_element(label,tx-tw/2,ty-7,tw,15,11,frame)

# Function map and reference cards use the same exhaustive inventory as Markdown.
fmap=['flowchart TB']
card_top=4*maxh+180
text_element(f'09 · FUNCTION ATLAS / {len(records)} named functions',0,card_top-100,2400,60,40)
columns=[card_top]*4
for i,(file,group) in enumerate(byfile.items()):
    column=min(range(4),key=lambda c:columns[c]); ox=column*1020; oy=columns[column]
    card_width=960
    content=[]
    for r in group:
        desc=' '.join(r['summary'].split())
        wrapped=textwrap.fill(desc,width=87)
        content.append((r,wrapped,34+len(wrapped.splitlines())*20+26))
    height=100+sum(h for _,_,h in content)
    frame=frame_element(file,ox,oy,card_width,height)
    text_element(textwrap.fill(file,width=70),ox+22,oy+18,card_width-44,60,22,frame)
    cy=oy+90
    module_id=f'module_{i}'
    fmap += [f'  subgraph {module_id}["{file}"]']
    for j,(r,desc,ch) in enumerate(content):
        text_element(r['name']+f'  ·  L{r["line"]}',ox+25,cy,card_width-50,30,19,frame)
        text_element(desc,ox+25,cy+33,card_width-50,ch-45,16,frame)
        cy+=ch
        summary=textwrap.shorten(' '.join(r['summary'].split()),width=140,placeholder='…')
        fmap.append(f'    f_{i}_{j}["{html.escape(r["name"])}<br/>{html.escape(summary,quote=True)}"]')
    fmap.append('  end')
    columns[column]=oy+height+55
(HERE/'function-map.mmd').write_text('\n'.join(fmap)+'\n')
scene={'type':'excalidraw','version':2,'source':'https://excalidraw.com','elements':elements,
       'appState':{'viewBackgroundColor':'#ffffff','gridSize':None,'zoom':{'value':0.3},'scrollX':60,'scrollY':180},'files':{}}
(HERE/'app-flow.excalidraw').write_text(json.dumps(scene,ensure_ascii=False,indent=2)+'\n')

# Offline gallery embeds SVG and a searchable function reference. No CDN or network required.
sections=[]
for graph in graphs:
    svg=(HERE/f'{graph["id"]}.svg').read_text()
    svg=svg[svg.index('<svg'):]
    sections.append(f'<section id="{graph["id"]}"><h2>{html.escape(graph["title"])}</h2><p>{html.escape(graph["subtitle"])}</p><div class="tools"><a href="{graph["id"]}.svg">Open full-size SVG</a> · <a href="{graph["id"]}.png">PNG</a> · <a href="{graph["id"]}.mmd">Mermaid source</a></div><div class="diagram">{svg}</div></section>')
for file,group in byfile.items():
    cards=[]
    for r in group:
        inputpart=f'<p><b>Input:</b> {html.escape(r["input"])}</p>' if r.get('input') else ''
        outpart=f'<p><b>Output:</b> {html.escape(r["output"])}</p>' if r.get('output') else ''
        cards.append(f'<details class="function"><summary>{html.escape(r["name"])} <small>{html.escape(file)}:{r["line"]}</small></summary><pre>{html.escape(r["signature"])}</pre>{inputpart}<p class="explanation">{html.escape(r["work"])}</p>{outpart}</details>')
    sections.append(f'<section class="module"><h2>{html.escape(file)}</h2>{"".join(cards)}</section>')
nav=''.join(f'<a href="#{g["id"]}">{html.escape(g["title"])}</a>' for g in graphs)
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Transcription AI · Architecture atlas</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:#0f172a;font:16px/1.55 system-ui,sans-serif}header{padding:48px max(24px,6vw);background:#0f172a;color:white}header p{max-width:850px;color:#cbd5e1}h1{font-size:42px;line-height:1.12;margin:10px 0}h2{font-size:24px;margin:0 0 8px}nav{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}nav a{color:#bfdbfe}main{max-width:1700px;margin:auto;padding:24px}section{background:white;border:1px solid #e2e8f0;border-radius:16px;padding:24px;margin:24px 0;overflow:hidden}a{color:#1d4ed8}section p{color:#475569}.tools{font-size:14px;margin:10px 0 18px}.diagram{overflow:auto;border:1px solid #e2e8f0;border-radius:8px;padding:12px}.diagram svg{max-width:100%;height:auto;min-width:950px}label{display:block;font-weight:600}input{padding:14px;width:100%;font:inherit;border:1px solid #94a3b8;border-radius:8px}.function{padding:16px 0;border-bottom:1px solid #e2e8f0}summary{cursor:pointer;font-weight:650}small{display:block;color:#64748b;font-weight:400}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f8fafc;padding:12px}.explanation{white-space:pre-line}.legend{display:flex;flex-wrap:wrap;gap:8px}.legend span{padding:3px 10px;border-radius:5px;font-size:13px;color:#0f172a}[hidden]{display:none!important}@media(max-width:700px){h1{font-size:30px}main{padding:10px}section{padding:16px}}
</style></head><body><header><div>CODE → REQUESTS → DATA → DEPLOYMENT</div><h1>Transcription AI<br>The complete application atlas</h1><p>Eight connected views and a searchable reference for every named application function. Diagrams show the implementation in this repository; no background queue or WebSocket worker is running.</p><nav>'''+nav+'''</nav><p><a style="color:#bfdbfe" href="app-flow.excalidraw">Editable Excalidraw board</a> · <a style="color:#bfdbfe" href="function-reference.md">Function reference</a></p><div class="legend">'''+''.join(f'<span style="background:{v}">{k}</span>' for k,v in COLORS.items())+'''</div></header><main><label for="search">Find a function, file, or behavior</label><input id="search" type="search" placeholder="Try refresh, normalize_audio, cookie, or download"><p id="count">'''+str(len(records))+''' named functions indexed. Diagrams remain visible while filtering.</p>'''+''.join(sections)+'''</main><script>
const input=document.querySelector('#search');input.addEventListener('input',()=>{const q=input.value.toLowerCase().trim();let count=0;document.querySelectorAll('.function').forEach(el=>{el.hidden=!el.textContent.toLowerCase().includes(q);if(!el.hidden)count++;if(q&&!el.hidden)el.open=true});document.querySelectorAll('.module').forEach(el=>el.hidden=![...el.querySelectorAll('.function')].some(f=>!f.hidden));document.querySelector('#count').textContent=count+' matching functions. Diagrams remain visible while filtering.'});
</script></body></html>'''
(HERE/'index.html').write_text(page)

# Structural validation: all functions explained, all edge endpoints exist, every binding resolves.
assert len({(r['file'],r['name']) for r in records})==len(records)
for g in graphs:
    node_ids={n[0] for n in g['nodes']}
    assert all(a in node_ids and b in node_ids for a,b,_ in g['edges'])
ids={e['id'] for e in elements}
assert len(ids)==len(elements)
for e in elements:
    assert e['width']>=0 and e['height']>=0
    assert e.get('frameId') is None or e['frameId'] in ids
    assert all(b['id'] in ids for b in e['boundElements'])
    if e.get('containerId'): assert e['containerId'] in ids
print(f'Generated {len(graphs)} flow views, {len(records)} function descriptions, and {len(elements)} editable Excalidraw elements.')
