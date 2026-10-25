from pathlib import Path
import html, json, re, sys

def clean(text):
    return html.unescape(re.sub(r'<[^>]*>', '', text)).replace('\xa0', ' ').strip()

def rows(text):
    return [[clean(cell) for cell in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)]
            for row in re.findall(r'<tr>(.*?)</tr>', text, re.S)]

def summary(path):
    data=Path(path).read_text(encoding='utf-8', errors='replace')
    block=re.search(r'<a name="performance">.*?<table[^>]*>(.*?)</table>',data,re.S)[1]
    clocks=[]
    for row in rows(block)[1:]:
        if len(row)!=6: continue
        clocks.append(dict(clock=row[1],requested_mhz=float(row[2].split('(')[0]),
                           estimated_fmax_mhz=float(row[3].split('(')[0]),levels=int(row[4])))
    paths=[]
    for block in re.split(r'<h3>Path&nbsp\d+</h3>',data)[1:]:
        tables=re.findall(r'<table[^>]*>(.*?)</table>',block,re.S)
        info=dict(row for row in rows(tables[0]) if len(row)==2)
        stats=dict(row for row in rows(tables[-1]) if len(row)==2)
        paths.append(dict(source=info.get('From'),destination=info.get('To'),
                          launch=info.get('Launch Clk'),latch=info.get('Latch Clk'),
                          slack_ns=float(info['Slack']),levels=int(stats['Logic Level:'])))
    return dict(report=str(Path(path).resolve()),synthesis_estimate_only=True,clocks=clocks,paths=paths)

if __name__=='__main__':
    result=summary(sys.argv[1])
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(clocks=result['clocks'],worst_paths=result['paths'][:5]),indent=2))
