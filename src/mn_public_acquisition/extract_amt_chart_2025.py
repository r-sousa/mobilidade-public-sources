import os,requests,base64,fitz,json
repo="r-sousa/EU-transp-weekly"; ref="mobilidade-norte-recovery-20260919";path="statistics/assessments/norte-centro-2026-11-22/phase26/raw/AMT-rail-2025-0.pdf"
token=os.environ.get("MN_PRIVATE_READ_TOKEN") or os.environ["MN_PRIVATE_SINK_TOKEN"]
h={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json"}
u="https://api.github.com/repos/"+repo
m=requests.get(u+"/contents/"+path,params={"ref":ref},headers=h);m.raise_for_status()
b=requests.get(u+"/git/blobs/"+m.json()["sha"],headers=h);b.raise_for_status()
raw=base64.b64decode(b.json()["content"])
d=fitz.open(stream=raw,filetype="pdf")
for i,p in enumerate(d):
    t=p.get_text()
    if "192,6" in t and "Intensidade" in t:
        print("PAGE",i,flush=True)
        for block in p.get_text("dict")["blocks"]:
            for line in block.get("lines",[]):
                print(json.dumps({"box":line["bbox"],"dir":line["dir"],"text":"".join(s["text"] for s in line["spans"])},ensure_ascii=False),flush=True)
        # chart labels sometimes outlined or image: preserve page image for review
        pix=p.get_pixmap(matrix=fitz.Matrix(1.5,1.5))
        png=pix.tobytes("png")
        dest="statistics/assessments/norte-centro-2026-11-22/phase26/extracted/AMT-rail-2025-figure6-page.png"
        h["Authorization"]="Bearer "+os.environ["MN_PRIVATE_SINK_TOKEN"]
        old=requests.get(u+"/contents/"+dest,params={"ref":ref},headers=h)
        body={"message":"Preserve source page for railway utilization chart QA","branch":ref,"content":base64.b64encode(png).decode()}
        if old.ok:body["sha"]=old.json()["sha"]
        r=requests.put(u+"/contents/"+dest,headers=h,json=body);r.raise_for_status();print("PRESERVED_PAGE")
        break
