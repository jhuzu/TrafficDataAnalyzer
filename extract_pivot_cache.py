#!/usr/bin/env python3
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

def item_value(node):
    tag = node.tag.rsplit("}", 1)[-1]
    if tag == "m":
        return None
    return node.attrib.get("v", "")

def main(source, output):
    with zipfile.ZipFile(source) as z:
        definitions = sorted(n for n in z.namelist() if n.startswith("xl/pivotCache/pivotCacheDefinition") and n.endswith(".xml"))
        if not definitions:
            raise SystemExit("此檔案未保留可還原的 Pivot Cache（找不到 pivotCacheDefinition*.xml）。")
        definition_name = definitions[0]
        suffix = definition_name.rsplit("pivotCacheDefinition", 1)[1].rsplit(".xml", 1)[0]
        records_name = f"xl/pivotCache/pivotCacheRecords{suffix}.xml"
        if records_name not in z.namelist():
            raise SystemExit(f"找到 {definition_name}，但缺少對應的 {records_name}。")
        try:
            definition = ET.fromstring(z.read(definition_name))
        except ParseError as e:
            raise SystemExit(f"Pivot Cache 定義檔 XML 格式損壞，無法解析：{e}")
        try:
            records_root = ET.fromstring(z.read(records_name))
        except ParseError as e:
            raise SystemExit(f"Pivot Cache 記錄檔 XML 格式損壞，無法解析：{e}")

        fields, shared = [], []
        for field in definition.find(f"{NS}cacheFields"):
            fields.append(field.attrib["name"])
            items = field.find(f"{NS}sharedItems")
            shared.append([item_value(cell) for cell in items] if items is not None else [])

        rows = []
        for record in records_root:
            row = []
            for index, cell in enumerate(record):
                tag = cell.tag.rsplit("}", 1)[-1]
                if tag == "x":
                    row.append(shared[index][int(cell.attrib["v"])])
                else:
                    row.append(item_value(cell))
            row.extend([None] * (len(fields) - len(row)))
            for name in ("年齡", "件數"):
                try:
                    position = fields.index(name)
                    if row[position] is not None:
                        row[position] = int(row[position])
                except (ValueError, TypeError):
                    pass
            rows.append(row)

    with open(output, "w", encoding="utf-8") as f:
        json.dump({"headers": fields, "rows": rows}, f, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法：extract_pivot_cache.py 來源.xlsm 暫存.json")
    main(sys.argv[1], sys.argv[2])
