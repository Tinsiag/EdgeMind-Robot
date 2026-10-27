"""Read frozen Gowin synthesis evidence; never starts implementation or hardware I/O."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hierarchy(path):
    result=[]
    def walk(node, parent=""):
        current=parent+"/"+node.attrib["name"]
        row={"path":current}
        row.update({k:int(v.split("(")[0]) for k,v in node.attrib.items() if k!="name"})
        result.append(row)
        for child in node:walk(child,current)
    walk(ET.parse(path).getroot())
    return result


def net_degrees(path):
    # Counts explicit named pin connections, including outputs. Not flattened fanout.
    largest=[]
    text=path.read_text(encoding="utf-8",errors="replace")
    for match in re.finditer(r"(?ms)^module\s+(\S+).*?^endmodule",text):
        counts=Counter()
        for expression in re.findall(r"\.\w+\s*\(([^()]*)\)",match[0]):
            for net in re.findall(r"\\[^\s,{}]+|[A-Za-z_][\w$]*(?:\[\d+\])?",expression):
                if not re.fullmatch(r"[bdho][0-9a-fxz]+",net,re.I):counts[net]+=1
        largest.extend({"module":match[1],"net":net,"pin_degree":count} for net,count in counts.most_common(8))
    return sorted(largest,key=lambda x:x["pin_degree"],reverse=True)[:60]


def report(build, baseline, out):
    record=json.loads((build/"result.json").read_text(encoding="utf-8"))
    if not record["compile_passed"] or record["sources_changed"]:
        raise ValueError("Completed unchanged synthesis is required")
    changed=[p for p,digest in record["source_sha256"].items() if not Path(p).is_file() or sha(Path(p))!=digest]
    if changed:raise ValueError("Inputs changed since synthesis: "+str(changed))
    syn=build/"impl/gwsynthesis"
    if sha(syn/"a741.vg")!=record["synthesis_netlist_sha256"]:raise ValueError("Netlist hash mismatch")
    rows=hierarchy(syn/"a741_syn_rsc.xml")
    old=hierarchy(baseline/"impl/gwsynthesis/a741_syn_rsc.xml")
    fields=("T_Lut","T_Register","T_Alu","T_Bsram")
    comparison={k:{"before":old[0].get(k,0),"after":rows[0].get(k,0),
                   "delta":rows[0].get(k,0)-old[0].get(k,0)} for k in fields}
    rpt=(syn/"a741_syn.rpt.html").read_text(encoding="utf-8",errors="replace")
    utilization=re.search(r'<a name="utilization">.*?<table[^>]*>(.*?)</table>',rpt,re.S)
    util=[]
    for row in re.findall(r"<tr>(.*?)</tr>",utilization[1],re.S):
        util.append([html.unescape(re.sub(r"<[^>]+>","",x)).replace("\xa0"," ").strip()
                     for x in re.findall(r"<td[^>]*>(.*?)</td>",row,re.S)])
    timeline=[json.loads(line) for line in (build/"build-timeline.jsonl").read_text(encoding="utf-8").splitlines()]
    stages=[item for item in timeline if re.search(r"GowinSynthesis (start|finish)|Placement|Routing|Timing|Total.*(time|Time)",item["line"])]
    result={"scope":"same device/tool/screen-test pad lock; old navigation/HDMI/video versus current basic design",
            "build_directory":str(build),"baseline_directory":str(baseline),"seconds":record["seconds"],
            "comparison":comparison,"utilization_table":util,
            "dsp_primitives":{k:v for k,v in rows[0].items() if k.startswith("T_MULT")},
            "actual_cls":None,"final_wns_ns":None,"final_tns_ns":None,"congestion":None,
            "pnr_completed":False,"hardware_tested":False,
            "synthesis_timing":record["synthesis_timing"],"stage_messages":stages,
            "timeline_caveat":"stdout receipt time is not an internal EDA phase timer",
            "evidence_sha256":{str(p):sha(p) for p in (build/"result.json",build/"build.tcl",syn/"a741.vg",syn/"a741_syn_rsc.xml",syn/"a741_syn.rpt.html",baseline/"impl/gwsynthesis/a741_syn_rsc.xml")}}
    out.mkdir(parents=True,exist_ok=True)
    for name,value in (("resources.json",result),("hierarchy.json",rows),
                       ("net-pin-degree.json",{"metric":"named module-local pin-connection degree, including outputs; NOT exact flattened fanout","largest":net_degrees(syn/"a741.vg")})):
        (out/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"comparison":comparison,"seconds":record["seconds"],"actual_cls":None},indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",type=Path,required=True)
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args();report(args.build.resolve(),args.baseline.resolve(),args.out.resolve())
