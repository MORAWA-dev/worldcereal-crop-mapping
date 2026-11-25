"""Build a QGIS project and printable map from Notebook 09 GeoTIFFs.

Run with the Python interpreter bundled with QGIS; see README.
"""
import argparse
import os
from pathlib import Path
import shutil

mac_proj = Path("/Applications/QGIS.app/Contents/Resources/qgis/proj")
if mac_proj.is_dir():
    os.environ.setdefault("PROJ_DATA", str(mac_proj))
    os.environ.setdefault("PROJ_LIB", str(mac_proj))

from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

parser = argparse.ArgumentParser()
parser.add_argument("input_dir", type=Path)
parser.add_argument("output_dir", type=Path)
args = parser.parse_args()
source = args.input_dir.resolve()
out = args.output_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
data = out / "rasters"
data.mkdir(exist_ok=True)
for name in ["crop_groups_2022.tif", "crop_group_raw_score_2022.tif"]:
    src = source / name
    if not src.is_file():
        raise FileNotFoundError(src)
    dst = data / name
    if src != dst:
        shutil.copy2(src, dst)

app = QgsApplication([], False)
prefix = os.environ.get("QGIS_PREFIX_PATH")
if not prefix and Path("/Applications/QGIS.app/Contents/Resources/qgis").exists():
    prefix = "/Applications/QGIS.app/Contents/Resources/qgis"
if prefix:
    app.setPrefixPath(prefix, True)
app.initQgis()
project = QgsProject.instance()
crs = QgsCoordinateReferenceSystem("EPSG:32630")
project.setCrs(crs)
classes = [(0, "Outside predicted cropland", "#d9d9d9"),
           (1, "Cereals", "#e6a700"), (2, "Cotton", "#0072b2"),
           (3, "Legumes", "#009e73")]
viridis = ["#440154", "#482878", "#3e4989", "#31688e", "#26828e",
           "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"]

def raster(filename, name):
    layer = QgsRasterLayer(str(data / filename), name)
    assert layer.isValid(), filename
    assert layer.crs().authid() == "EPSG:32630"
    assert layer.width() == 300 and layer.height() == 300
    project.addMapLayer(layer)
    return layer

score = raster("crop_group_raw_score_2022.tif", "Uncalibrated maximum class probability")
crop = raster("crop_groups_2022.tif", "Predicted crop groups")
assert crop.extent() == score.extent()
assert abs(crop.extent().width()-3000) < .1 and abs(crop.extent().height()-3000) < .1
crop.setRenderer(QgsPalettedRasterRenderer(crop.dataProvider(), 1, [
    QgsPalettedRasterRenderer.Class(v, QColor(c), n) for v,n,c in classes]))
lo = 1/3
shader = QgsColorRampShader(lo, 1)
shader.setColorRampType(QgsColorRampShader.Interpolated)
shader.setColorRampItemList([QgsColorRampShader.ColorRampItem(lo+(1-lo)*i/9, QColor(c), f"{lo+(1-lo)*i/9:.2f}") for i,c in enumerate(viridis)])
rs = QgsRasterShader(lo, 1)
rs.setRasterShaderFunction(shader)
renderer = QgsSingleBandPseudoColorRenderer(score.dataProvider(), 1, rs)
renderer.setClassificationMin(lo)
renderer.setClassificationMax(1)
score.setRenderer(renderer)
project.layerTreeRoot().findLayer(score.id()).setItemVisibilityChecked(False)
project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(crop.extent(), crs))

layout = QgsPrintLayout(project)
layout.initializeDefaults()
layout.setName("Koumbia | Exploratory crop-group mapping 2022")
layout.pageCollection().pages()[0].setPageSize("A4", QgsLayoutItemPage.Landscape)
layout.renderContext().setDpi(300)
INK = "#183b3f"

def place(item, x, y, w, h):
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y))
    item.attemptResize(QgsLayoutSize(w, h))
    return item

def label(text, x, y, w, h, size=9, bold=False, color=INK, center=False):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    font = QFont("Helvetica Neue")
    font.setPointSizeF(size)
    font.setBold(bold)
    item.setFont(font)
    item.setFontColor(QColor(color))
    item.setMargin(0)
    item.setHAlign(Qt.AlignHCenter if center else Qt.AlignLeft)
    item.setVAlign(Qt.AlignVCenter)
    return place(item,x,y,w,h)

def box(x,y,w,h,color,outline="transparent"):
    item=QgsLayoutItemShape(layout)
    item.setShapeType(QgsLayoutItemShape.Rectangle)
    item.setSymbol(QgsFillSymbol.createSimple({"color":color,"outline_color":outline,
        "outline_width":"0.15","outline_style":"no" if outline=="transparent" else "solid"}))
    return place(item,x,y,w,h)

def map_item(layer,x,name):
    item=QgsLayoutItemMap(layout)
    item.setId(name)
    place(item,x,31,126,126)
    item.setCrs(crs)
    item.setLayers([layer])
    item.setKeepLayerSet(True)
    item.storeCurrentLayerStyles()
    item.setKeepLayerStyles(True)
    item.zoomToExtent(crop.extent())
    item.setFrameEnabled(True)
    item.setFrameStrokeColor(QColor("#a0aaaa"))
    item.setFrameStrokeWidth(QgsLayoutMeasurement(.18))
    return item

m1=map_item(crop,14,"Crop groups")
m2=map_item(score,157,"Model score")
layout.setReferenceMap(m1)
label("Exploratory Crop-Group Mapping in Koumbia, Burkina Faso | 2022",10,4,277,10,17,True,center=True)
label("WorldCereal  •  Monthly Presto embeddings  •  Histogram Gradient Boosting  •  10 m resolution",10,15,277,6,9.5,center=True)
label("(a) Predicted crop groups",14,23,126,7,11,True)
label("(b) Uncalibrated model score",157,23,126,7,11,True)
label("Crop groups",14,159,126,6,10,True)
for i,(_,name,color) in enumerate(classes):
    col,row=divmod(i,2)
    x=14+col*72
    y=166+row*6
    box(x,y+1,4,3.5,color,"#909090")
    label(name,x+6,y,66 if col==0 else 48,5,8.5)
label("Maximum predicted class probability",157,159,126,6,10,True)
for i in range(100):
    t=(i+.5)/100*9
    j=min(int(t),8)
    f=t-j
    a,b=QColor(viridis[j]),QColor(viridis[j+1])
    color=QColor(*[round(u+(v-u)*f) for u,v in zip(a.getRgb()[:3],b.getRgb()[:3])])
    box(157+i*1.1,166,1.11,4,color.name())
for value in [lo,.5,.75,1]:
    x=157+(value-lo)/(1-lo)*110
    label(f"{value:.2f}",x-6,170,12,5,8,center=True)
label("White: outside classified cropland. Scores are overconfident.",157,176,130,5,8)
label("2022 retrospective reference evaluation (n = 262)",157,182,130,5,8,True)
label("Accuracy 53.05% | Balanced accuracy 49.36% | Macro F1 47.63%",157,188,130,5,7.8)
scale=QgsLayoutItemScaleBar(layout)
scale.setStyle("Single Box")
scale.setLinkedMap(m1)
scale.applyDefaultSize()
scale.setUnits(Qgis.DistanceUnit.Kilometers)
scale.setUnitsPerSegment(.5)
scale.setNumberOfSegments(2)
scale.setNumberOfSegmentsLeft(0)
scale.setUnitLabel("km")
scale.setHeight(1.8)
scale.setFont(QFont("Helvetica Neue",8))
layout.addLayoutItem(scale)
scale.attemptMove(QgsLayoutPoint(14,185))
label("↑ N (grid north)",101,185,39,7,9,True)
box(10,197,277,.22,"#a0aaaa")
label("Source: WorldCereal, Sentinel-1/2, AgERA5, terrain | 9 km² pilot | WGS 84 / UTM 30N | Ibrahim Kabore, November 2026",10,198,277,5,7.5,center=True)
label("Research demonstration only. Crop groups and cropland mask are not independently validated; do not estimate crop areas.",10,203,277,5,7.2,center=True)
project.layoutManager().addLayout(layout)
project.setFilePathStorage(Qgis.FilePathType.Relative)
project.setFileName(str(out/"Koumbia_2022.qgz"))
assert project.write()
export=QgsLayoutExporter(layout)
img=QgsLayoutExporter.ImageExportSettings(); img.dpi=300
pdf=QgsLayoutExporter.PdfExportSettings(); pdf.dpi=300
assert export.exportToImage(str(out/"Koumbia_2022.png"),img)==QgsLayoutExporter.Success
assert export.exportToPdf(str(out/"Koumbia_2022.pdf"),pdf)==QgsLayoutExporter.Success
print("Saved project, PNG and PDF:",out)
