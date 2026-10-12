"""Reconstruct source-defined mechanical envelopes; never infer missing V3 heights.

Dependencies: cadquery-ocp, ezdxf, trimesh, shapely, numpy, olefile.
Altium component-body record layout checked against KiCad's altium_parser_pcb.cpp.
All CAD coordinates and STL values are millimetres; GLB uses metres and Y-up.
"""
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path

import ezdxf
import numpy as np
import olefile
import trimesh
from shapely.geometry import Polygon
from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorGen
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent
UNIT = 0.0254 / 10000  # Altium integer/double coordinates: 1/10000 mil.


def props(data):
    return dict(part.split("=", 1) for part in data.rstrip(b"\0").decode("cp1252").split("|") if "=" in part)


def mm(value):
    value = str(value).strip()
    return float(value[:-3]) * 0.0254 if value.endswith("mil") else float(value.removesuffix("mm"))


def property_records(data):
    offset = 0
    while offset < len(data):
        length = struct.unpack_from("<I", data, offset)[0]
        yield props(data[offset + 4:offset + 4 + length])
        offset += 4 + length
    assert offset == len(data)


def clean_ring(points):
    result = []
    for point in points:
        point = tuple(float(x) for x in point)
        if not result or np.linalg.norm(np.subtract(point, result[-1])) > 1e-7:
            result.append(point)
    if len(result) > 1 and np.linalg.norm(np.subtract(result[0], result[-1])) < 1e-7:
        result.pop()
    poly = Polygon(result)
    if not poly.is_valid or poly.area <= 0:
        raise ValueError("Invalid source polygon; refusing to silently repair geometry")
    # A consistent counterclockwise outline gives outward solid normals.
    if not poly.exterior.is_ccw:
        result.reverse()
    return result


def polygon_wire(points, z=0):
    builder = BRepBuilderAPI_MakePolygon()
    for x, y in clean_ring(points):
        builder.Add(gp_Pnt(x, y, z))
    builder.Close()
    return builder.Wire()


def rounded_outline(arcs):
    """Use all source corner circles exactly; connect their endpoints by lines."""
    cx = sum(a[0] for a in arcs) / len(arcs)
    cy = sum(a[1] for a in arcs) / len(arcs)
    arcs = sorted(arcs, key=lambda a: math.atan2(a[1] - cy, a[0] - cx))
    result = BRepBuilderAPI_MakeWire()
    for i, (x, y, radius, start, end) in enumerate(arcs):
        if end <= start:
            end += 360
        circ = gp_Circ(gp_Ax2(gp_Pnt(x, y, 0), gp_Dir(0, 0, 1)), radius)
        result.Add(BRepBuilderAPI_MakeEdge(circ, math.radians(start), math.radians(end)).Edge())
        nx, ny, nr, ns, _ = arcs[(i + 1) % len(arcs)]
        a = gp_Pnt(x + radius * math.cos(math.radians(end)), y + radius * math.sin(math.radians(end)), 0)
        b = gp_Pnt(nx + nr * math.cos(math.radians(ns)), ny + nr * math.sin(math.radians(ns)), 0)
        result.Add(BRepBuilderAPI_MakeEdge(a, b).Edge())
    assert result.IsDone()
    return result.Wire()


def hole_wire(x, y, width, height):
    if abs(width - height) < 1e-6:
        circle = gp_Circ(gp_Ax2(gp_Pnt(x, y, 0), gp_Dir(0, 0, 1)), width / 2)
        return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
    # Imported oblong drills in this source all have zero rotation.
    if width < height:
        horizontal = hole_wire(0, 0, height, width)
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.pi / 2)
        transform.SetTranslationPart(gp_Vec(x, y, 0))
        return TopoDS.Wire_s(BRepBuilderAPI_Transform(horizontal, transform, True).Shape())
    radius, half = height / 2, (width - height) / 2
    wire = BRepBuilderAPI_MakeWire()
    for xcenter, start, end in [(x + half, -90, 90), (x - half, 90, 270)]:
        circle = gp_Circ(gp_Ax2(gp_Pnt(xcenter, y, 0), gp_Dir(0, 0, 1)), radius)
        wire.Add(BRepBuilderAPI_MakeEdge(circle, math.radians(start), math.radians(end)).Edge())
        if start == -90:
            wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(x + half, y + radius, 0), gp_Pnt(x - half, y + radius, 0)).Edge())
        else:
            wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(x - half, y - radius, 0), gp_Pnt(x + half, y - radius, 0)).Edge())
    return wire.Wire()


def compound(shapes):
    result, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result, shape)
    return result


def cut_holes(outer, holes, thickness=None):
    face = BRepBuilderAPI_MakeFace(outer).Face()
    base = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, thickness)).Shape() if thickness else face
    tools = []
    for wire in holes:
        h = BRepBuilderAPI_MakeFace(wire).Face()
        tools.append(BRepPrimAPI_MakePrism(h, gp_Vec(0, 0, thickness)).Shape() if thickness else h)
    operation = BRepAlgoAPI_Cut(base, compound(tools))
    operation.SetRunParallel(False)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("Hole cutting failed")
    shape = operation.Shape()
    if not BRepCheck_Analyzer(shape).IsValid():
        raise RuntimeError("Resulting board geometry is invalid")
    return shape


def mesh_shape(shape):
    BRepMesh_IncrementalMesh(shape, 0.015, False, 0.15, True).Perform()
    vertices, triangles = [], []
    faces = TopExp_Explorer(shape, TopAbs_FACE)
    while faces.More():
        face = TopoDS.Face_s(faces.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is not None:
            offset = len(vertices)
            transform = location.Transformation()
            for i in range(1, triangulation.NbNodes() + 1):
                p = triangulation.Node(i).Transformed(transform)
                vertices.append([p.X(), p.Y(), p.Z()])
            for i in range(1, triangulation.NbTriangles() + 1):
                a, b, c = triangulation.Triangle(i).Get()
                if face.Orientation() == TopAbs_REVERSED:
                    b, c = c, b
                triangles.append([offset + a - 1, offset + b - 1, offset + c - 1])
        faces.Next()
    return trimesh.Trimesh(vertices=vertices, faces=triangles, process=True)


def write_step(items, path):
    document = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    for name, shape, color, _ in items:
        label = shapes.AddShape(shape, False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
        colors.SetColor(label, Quantity_Color(*color, Quantity_TOC_RGB), XCAFDoc_ColorGen)
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(document, STEPControl_AsIs)
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError("STEP export failed")


def write_mesh_files(items, stem, solid):
    scene = trimesh.Scene()
    payload = []
    for name, shape, color, kind in items:
        mesh = mesh_shape(shape)
        if solid and (not mesh.is_watertight or mesh.volume <= 0):
            raise ValueError(f"Non-watertight or inverted mesh: {name}")
        mesh.visual.vertex_colors = [int(x * 255) for x in color] + [255]
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        payload.append({"name": name, "kind": kind, "color": color,
                        "vertices": np.round(mesh.vertices, 5).ravel().tolist(),
                        "indices": mesh.faces.ravel().tolist()})
    if solid:
        scene.to_mesh().export(str(OUT / f"{stem}.stl"))
    # glTF: metre units; original +Z height becomes +Y, original +Y becomes -Z.
    transform = np.array([[.001, 0, 0, 0], [0, 0, .001, 0], [0, -.001, 0, 0], [0, 0, 0, 1]])
    scene.apply_transform(transform)
    scene.export(str(OUT / f"{stem}.glb"))
    return payload


def main():
    meta = json.loads((OUT / "kicad_geometry.json").read_text())
    with olefile.OleFileIO(SOURCE / "ACX720-v2机械文件.PcbDoc") as document:
        components = list(property_records(document.openstream("Components6/Data").read()))
        board_records = list(property_records(document.openstream("Board6/Data").read()))
        board = next(p for p in board_records if "VX0" in p)
        bodies_data = document.openstream("ComponentBodies6/Data").read()

    # Resolve the importer's page translation against the unique HDR2X18 footprint.
    source_anchor = next(c for c in components if c["PATTERN"] == "HDR2X18")
    imported_anchor = next(c for c in meta["footprints"] if c["pattern"] == "HDR2X18")
    offset_x = imported_anchor["position_mm"][0] - mm(source_anchor["X"])
    offset_y = imported_anchor["position_mm"][1] + mm(source_anchor["Y"])
    for c in components:
        x, y = mm(c["X"]), mm(c["Y"])
        matches = [f for f in meta["footprints"] if f["pattern"] == c["PATTERN"] and
                   math.hypot(f["position_mm"][0] - offset_x - x, offset_y - f["position_mm"][1] - y) < .001]
        if len(matches) != 1:
            raise ValueError("Cannot uniquely align source component " + c["PATTERN"])
        c["reference"] = matches[0]["reference"]

    arcs = []
    for i in range(100):
        if f"KIND{i}" not in board:
            break
        if board[f"KIND{i}"] == "1":
            a = (mm(board[f"CX{i}"]), mm(board[f"CY{i}"]), mm(board[f"R{i}"]), float(board[f"SA{i}"]), float(board[f"EA{i}"]))
            if a not in arcs:
                arcs.append(a)
    assert len(arcs) == 4
    holes, seen = [], set()
    for h in meta["holes"]:
        assert h["angle_deg"] == 0
        values = (h["position_mm"][0] - offset_x, offset_y - h["position_mm"][1], *h["size_mm"])
        key = tuple(round(x, 5) for x in values)
        if key not in seen:
            holes.append(hole_wire(*values))
            seen.add(key)
    thickness = meta["imported_stack_thickness_mm"]
    print("Building source V2 board and", len(holes), "unique drilled features", flush=True)
    board_shape = cut_holes(rounded_outline(arcs), holes, thickness)
    items = [("V2_board_source_stack_thickness_NOT_VERIFIED", board_shape, (.10, .38, .27), "board")]
    body_report, offset = [], 0
    while offset < len(bodies_data):
        tag = bodies_data[offset]
        size = struct.unpack_from("<I", bodies_data, offset + 1)[0]
        record = bodies_data[offset + 5:offset + 5 + size]
        offset += 5 + size
        assert tag == 12
        index = struct.unpack_from("<H", record, 7)[0]
        length = struct.unpack_from("<I", record, 18)[0]
        p = props(record[22:22 + length])
        assert p["MODEL.MODELTYPE"] == "0" and components[index]["LAYER"] == "TOP"
        count = struct.unpack_from("<I", record, 22 + length)[0]
        points = [tuple(v * UNIT for v in struct.unpack_from("<dd", record, 26 + length + i * 16)) for i in range(count)]
        assert len(record) == 26 + length + count * 16
        zmin, zmax = mm(p["MODEL.EXTRUDED.MINZ"]), mm(p["MODEL.EXTRUDED.MAXZ"])
        dz = mm(p.get("MODEL.3D.DZ", "0mil"))
        c = components[index]
        ref = c["reference"]
        face = BRepBuilderAPI_MakeFace(polygon_wire(points, thickness + zmin + dz)).Face()
        shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, zmax - zmin)).Shape()
        assert BRepCheck_Analyzer(shape).IsValid()
        kind = "mount_envelope" if ref.startswith("H") else "component_envelope"
        code = int(p.get("BODYCOLOR3D", "8421504"))
        color = tuple(((code >> shift) & 255) / 255 for shift in (0, 8, 16))
        items.append((f"V2_{ref}_{c['PATTERN']}_SOURCE_ENVELOPE", shape, color, kind))
        body_report.append({"reference": ref, "pattern": c["PATTERN"], "source_body_index": index,
                            "kind": kind, "source_height_mm": zmax - zmin, "source_vertex_count": count})
    assert len(body_report) == 33 and offset == len(bodies_data)
    print("Exporting V2 board plus all 33 source envelopes", flush=True)
    write_step(items, OUT / "acx720_v2_reference.step")
    payload_v2 = write_mesh_files(items, "acx720_v2_reference", True)

    drawing = ezdxf.readfile(OUT / "acx720_v3.dxf")
    space = drawing.modelspace()
    v3_arcs = [(e.dxf.center.x, e.dxf.center.y, e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle)
               for e in space.query("ARC") if e.dxf.layer == "Mechanical1"]
    v3_holes, ambiguous_slots, ambiguous_wires = [], [], []
    for e in space:
        if e.dxf.layer != "PadHoleLayer":
            continue
        if e.dxftype() == "CIRCLE":
            v3_holes.append(hole_wire(e.dxf.center.x, e.dxf.center.y, 2 * e.dxf.radius, 2 * e.dxf.radius))
        elif e.dxftype() == "LWPOLYLINE":
            from ezdxf.path import make_path
            points = [(v.x, v.y) for v in make_path(e).flattening(.005)]
            if Polygon(points).is_valid:
                v3_holes.append(polygon_wire(points))
            else:
                # Keep self-intersecting contours as source linework, not a guessed cut.
                ambiguous_slots.append(e.dxf.handle)
                wire = BRepBuilderAPI_MakePolygon()
                last = None
                for point in points:
                    if last is None or math.dist(point, last) > 1e-7:
                        wire.Add(gp_Pnt(*point, 0))
                        last = point
                if math.dist(points[0], points[-1]) > 1e-7:
                    wire.Close()
                ambiguous_wires.append(wire.Wire())
        else:
            raise ValueError("Unhandled V3 hole geometry")
    print("Building V3 planar reference; NO board thickness or component heights added", flush=True)
    v3_face = cut_holes(rounded_outline(v3_arcs), v3_holes)
    v3_items = [("V3_PLANAR_REFERENCE_NO_THICKNESS", v3_face, (.15, .46, .53), "planar")]
    step_items = v3_items + [("V3_SELF_INTERSECTING_SLOT_OUTLINES_NOT_CUT", compound(ambiguous_wires), (.8, .4, .1), "linework")]
    write_step(step_items, OUT / "acx720_v3_planar_reference.step")
    payload_v3 = write_mesh_files(v3_items, "acx720_v3_planar_reference", False)

    # Include existing V3 silkscreen as line geometry in the offline viewer.
    from ezdxf.path import make_path
    lines = []
    for e in space:
        if e.dxf.layer not in {"TopOverlay", "Mechanical14", "Mechanical15", "Mechanical16", "PadHoleLayer"}:
            continue
        try:
            p = list(make_path(e).flattening(.025))
        except (TypeError, ValueError):
            continue
        for a, b in zip(p, p[1:]):
            lines.extend([round(a.x, 5), round(a.y, 5), .02, round(b.x, 5), round(b.y, 5), .02])
    payload = {"v2": payload_v2, "v3": payload_v3, "v3_lines": lines}
    template = (OUT / "viewer_template.html").read_text()
    (OUT / "open_3d.html").write_text(template.replace("__MODEL_DATA__", json.dumps(payload, separators=(",", ":"))))

    from ezdxf.addons.drawing import RenderContext, Frontend, layout, config
    from ezdxf.addons.drawing.svg import SVGBackend
    backend = SVGBackend()
    cfg = config.Configuration(background_policy=config.BackgroundPolicy.WHITE,
                               color_policy=config.ColorPolicy.BLACK)
    Frontend(RenderContext(drawing), backend, config=cfg).draw_layout(space, finalize=True)
    (OUT / "acx720_v3_drawing.svg").write_text(backend.get_string(layout.Page(0, 0)))

    report = {"source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()},
              "v2": {"body_count": 33, "unique_drilled_features": len(holes),
                     "imported_stack_thickness_mm_unverified": thickness,
                     "board_bbox_mm": [0, 0, 149.861016, 109.22], "bodies": body_report},
              "v3": {"units": "mm", "board_width_mm": 138.049, "board_height_mm": 91.567,
                     "hole_entities": len(v3_holes) + len(ambiguous_slots), "valid_hole_cuts": len(v3_holes),
                     "self_intersecting_slots_preserved_as_linework": ambiguous_slots,
                     "modelspace_entity_types": dict(Counter(e.dxftype() for e in space)),
                     "source_has_3d_solids": False, "export_is_zero_thickness_surface": True,
                     "dxf_audit_errors": len(drawing.audit().errors)},
              "conversion_tolerances_mm": {"mesh_linear_deflection": .015, "v3_slot_flattening": .005},
              "warnings": ["V2 and V3 board sizes and revisions differ: never combine their geometry.",
                           "V2 component bodies all use source-defined 3.81 mm envelope height, including mounting-hole envelopes; these are not detailed physical parts.",
                           "V2 PCB stack thickness is imported from incomplete mechanical PCB data and is not verified against hardware.",
                           "V3 has no Z/height data: STEP and GLB contain a planar reference only.",
                           "12 V3 slot outlines self-intersect after DWG decoding; preserved as linework, not silently repaired or used as hole cuts.",
                           "LibreDWG reported source checksum/material/table warnings; DXF geometry audit has no errors.",
                           "KiCad import reported unmapped non-mechanical layers and two TH-pad warnings; conversion is not a production PCB translation."]}
    (OUT / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("CONVERSION COMPLETE", flush=True)


if __name__ == "__main__":
    main()
