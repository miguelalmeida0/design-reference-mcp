"""Read-only live research board. Viewer token grants read-only access to public-reference captures."""
import html


def render_board(job_id: str, view_token: str) -> str:
    root = f"/boards/{job_id}/{view_token}"
    # Fixed HTML, no untrusted content interpolated except URL-safe generated tokens.
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Design research — live capture</title>
<style>
:root{{color-scheme:dark;font-family:Inter,system-ui,Arial,sans-serif;background:#151a18;color:#e6ebdf}}
*{{box-sizing:border-box}}body{{margin:0}}header{{position:sticky;top:0;z-index:1;background:#151a18ee;border-bottom:1px solid #454d45;padding:18px clamp(16px,3vw,54px);display:flex;align-items:center;justify-content:space-between;gap:12px}}
h1{{font-size:19px;font-weight:640;letter-spacing:-.6px;margin:0}}.count{{font-variant-numeric:tabular-nums;color:#a9b6a6;font-size:14px}}
main{{padding:26px clamp(16px,3vw,54px)}}#grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:1px;background:#384238;border:1px solid #384238}}article{{min-width:0;background:#1c231e;padding:14px}}
figure{{margin:0;height:230px;overflow:hidden;background:#111711}}img{{width:100%;height:100%;object-fit:cover;object-position:top center;cursor:zoom-in}}.meta{{padding:11px 0 3px;display:flex;justify-content:space-between;gap:8px;font-size:13px}}
.source{{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.state{{color:#b9bf9c;flex-shrink:0}}a{{color:#b4dcaa;text-decoration-color:#697b65}}
p{{font-size:12px;color:#a9b6a6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:3px 0}}
#notice{{padding:15px 0;color:#b9c2b4;font-size:14px}}dialog{{background:#121712;border:1px solid #788b7d;color:#fff;padding:0;max-width:95vw;max-height:95vh}}dialog img{{max-width:90vw;max-height:86vh;width:auto;height:auto;object-fit:contain}}dialog::backdrop{{background:#000c}}
</style></head><body>
<header><h1>Actual reference captures</h1><div id="stats" class="count">Connecting…</div></header>
<main><div id="notice">Captured pages are not counted as reviewed until their visual content is inspected.</div><div id="grid"></div></main><dialog id="lightbox" onclick="this.close()"><img alt="Expanded reference screenshot"></dialog>
<script>
const root={root!r};const grid=document.getElementById('grid');const seen=new Set();
function make(tag,cls,text){{let n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n}}
async function update(){{try{{const r=await fetch(root+'/state',{{cache:'no-store'}});if(!r.ok)throw new Error('Unavailable');const j=await r.json();document.getElementById('stats').textContent=`${{j.status.captured}} captured · ${{j.status.reviewed}} reviewed · ${{j.status.state}}`;
for(const c of j.captures){{if(seen.has(c.id)){{const s=document.getElementById('s-'+c.id);if(s)s.textContent=c.inspection?'Reviewed':'Not reviewed';continue}}seen.add(c.id);const a=make('article');const f=make('figure');const img=document.createElement('img');img.loading='lazy';img.src=root+'/image/'+encodeURIComponent(c.id);img.alt='Screenshot of '+c.title;img.onclick=()=>{{const d=document.getElementById('lightbox');d.querySelector('img').src=img.src;d.showModal()}};f.append(img);a.append(f);
const meta=make('div','meta');meta.append(make('span','source',c.title),make('span','state',c.inspection?'Reviewed':'Not reviewed'));meta.lastChild.id='s-'+c.id;a.append(meta);const p=make('p',null,c.url);a.append(p);const link=document.createElement('a');link.href=c.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Open original';a.append(link);grid.append(a)}}
if(j.status.state==='complete'||j.status.state==='failed')clearInterval(poll);
}}catch(e){{document.getElementById('stats').textContent='Connection unavailable'}}}}
const poll=setInterval(update,2500);update();
</script></body></html>'''

