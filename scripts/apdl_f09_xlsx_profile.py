#!/usr/bin/env python3
"""Inspect native APDL XLSX sheets, preserving source cell addresses and values."""
from __future__ import annotations
import json, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P = "{http://schemas.openxmlformats.org/package/2006/relationships}"

def inspect(path):
    result = {"filename": path.name, "sheets": []}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if "xl/sharedStrings.xml" in z.namelist():
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings=["".join(t.text or "" for t in si.iter(M+"t")) for si in root.findall(M+"si")]
        book=ET.fromstring(z.read("xl/workbook.xml"))
        relroot=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rels={e.attrib["Id"]:e.attrib["Target"] for e in relroot.findall(P+"Relationship")}
        for item in book.find(M+"sheets").findall(M+"sheet"):
            target=rels[item.attrib[R+"id"]]
            name=target.lstrip("/") if target.startswith("/") else "xl/"+target
            name=name.replace("xl/xl/","xl/")
            sheet=ET.fromstring(z.read(name))
            data=[]
            for row in sheet.findall(".//"+M+"sheetData/"+M+"row"):
                entries=[]
                for cell in row.findall(M+"c"):
                    v=cell.find(M+"v")
                    if v is None:
                        inline=cell.find(M+"is")
                        val="".join(t.text or "" for t in inline.iter(M+"t")) if inline is not None else ""
                    elif cell.attrib.get("t")=="s":
                        val=strings[int(v.text or "0")]
                    else:
                        val=v.text or ""
                    if val.strip():
                        entries.append({"at":cell.attrib.get("r"),"v":val[:160]})
                if entries: data.append(entries)
            result["sheets"].append({"sheet":item.attrib["name"],"rows":len(data),
                "cells":sum(len(r) for r in data),
                "top_rows":data[:35], "last_rows":data[-5:]})
    return result

if __name__=="__main__":
    print(json.dumps([inspect(Path(p)) for p in sys.argv[1:]],ensure_ascii=False,indent=2))
