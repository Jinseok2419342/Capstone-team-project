"""Add native Korean paragraph line-break protection to the authored candidate."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as ET
import sys

file = Path(sys.argv[1])
ns = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
with ZipFile(file) as z:
    entries = [(i,z.read(i.filename)) for i in z.infolist()]
count = 0
with ZipFile(file,'w',ZIP_DEFLATED) as z:
    for info,data in entries:
        if info.filename.startswith('ppt/slides/slide') and info.filename.endswith('.xml'):
            root = ET.fromstring(data)
            for p in root.findall('.//a:p',ns):
                prop=p.find('a:pPr',ns)
                if prop is None:
                    prop=ET.Element('{%s}pPr'%ns['a'])
                    p.insert(0,prop)
                prop.set('eaLnBrk','0')
                prop.set('latinLnBrk','0')
                count+=1
            for r in root.findall('.//a:rPr',ns)+root.findall('.//a:defRPr',ns)+root.findall('.//a:endParaRPr',ns):
                r.set('lang','ko-KR')
                ea=r.find('a:ea',ns)
                if ea is None:
                    ea=ET.SubElement(r,'{%s}ea'%ns['a'])
                ea.set('typeface','Malgun Gothic')
            data=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
        z.writestr(info,data)
print(f'Korean paragraph protection: {count}')
