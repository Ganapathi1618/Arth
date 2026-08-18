"""Generates a synthetic NCERT-style page for pipeline testing."""
import pymupdf
doc = pymupdf.open(); page = doc.new_page()
page.insert_text((60,70),"Chapter 5: Photosynthesis",fontname="hebo",fontsize=17)
page.insert_text((60,100),"5.1 Introduction",fontname="hebo",fontsize=13)
body=("Photosynthesis is the process by which green plants use sunlight to "
"synthesise food from carbon dioxide and water. Chlorophyll, the green pigment "
"in leaves, absorbs light energy. The overall reaction can be written as a "
"balanced chemical equation.")
page.insert_textbox(pymupdf.Rect(60,115,540,175),body,fontname="helv",fontsize=10.5)
page.insert_text((60,200),"6CO2 + 6H2O -> C6H12O6 + 6O2",fontname="cour",fontsize=11)
page.insert_text((60,235),"Table 5.1 Rate of photosynthesis",fontname="hebo",fontsize=11)
x=[60,200,340,480]; y0=250; rh=26
for r in range(4):
    for c in range(3):
        page.draw_rect(pymupdf.Rect(x[c],y0+r*rh,x[c+1],y0+(r+1)*rh),color=(0,0,0),width=0.7)
rows=[["Light intensity","Temperature","Rate observed"],["Low","25 C","Slow"],["Medium","25 C","Moderate"],["High","25 C","Rapid"]]
for r,row in enumerate(rows):
    for c,v in enumerate(row):
        page.insert_text((x[c]+7,y0+r*rh+17),v,fontname="hebo" if r==0 else "helv",fontsize=9.5)
page.draw_circle((300,420),52,color=(0.1,0.4,0.1),width=1.4)
page.insert_text((262,425),"leaf diagram",fontname="helv",fontsize=8.5)
page.insert_text((60,520),"Q1. Define photosynthesis in your own words.",fontname="helv",fontsize=10.5)
page.insert_text((60,540),"Q2. Name the pigment involved in this process.",fontname="helv",fontsize=10.5)
page.insert_text((60,800),"NCERT Class 7 Science",fontname="helv",fontsize=8)
doc.save("tests/sample_textbook.pdf")
