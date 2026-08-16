import subprocess
import json
import os


BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"

ATLAS_PROJECTS = os.path.abspath(
    os.path.expandvars(r"%USERPROFILE%\Desktop\Atlas")
)


def validate_blend_file(file_name):

    if os.path.basename(file_name) != file_name:
        raise ValueError("Only filenames are allowed.")

    if not file_name.lower().endswith(".blend"):
        raise ValueError("Only .blend files are allowed.")

    path = os.path.abspath(
        os.path.join(ATLAS_PROJECTS, file_name)
    )

    if not path.startswith(ATLAS_PROJECTS + os.sep):
        raise ValueError(
            "Access outside the Atlas directory is not allowed."
        )

    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Blender file '{file_name}' was not found."
        )

    return path


def run_blender(blend_path, script, start_marker, end_marker):

    result = subprocess.run(
        [
            BLENDER,
            "--background",
            blend_path,
            "--python-expr",
            script
        ],
        capture_output=True,
        text=True,
        timeout=60
    )

    output = result.stdout

    start = output.find(start_marker)
    end = output.find(end_marker)

    if start == -1 or end == -1:
        raise RuntimeError(
            "Blender did not return a valid result.\n"
            + output[-3000:]
        )

    start += len(start_marker)

    return json.loads(
        output[start:end].strip()
    )


# ============================================================
# TOOL 1 — INSPECT SCENE
# ============================================================

def inspect_scene(file_name):

    blend_path = validate_blend_file(file_name)

    script = r"""
import bpy
import json

result = {
    "scene": bpy.context.scene.name,
    "total_objects": len(bpy.context.scene.objects),
    "objects": []
}

for obj in bpy.context.scene.objects:

    result["objects"].append({
        "name": obj.name,
        "type": obj.type,
        "location": [
            round(obj.location.x, 3),
            round(obj.location.y, 3),
            round(obj.location.z, 3)
        ],
        "dimensions": [
            round(obj.dimensions.x, 3),
            round(obj.dimensions.y, 3),
            round(obj.dimensions.z, 3)
        ]
    })

print("ATLAS_RESULT_START")
print(json.dumps(result))
print("ATLAS_RESULT_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_RESULT_START",
        "ATLAS_RESULT_END"
    )


# ============================================================
# TOOL 2 — INSPECT MESH
# ============================================================

def inspect_mesh(file_name, object_name):

    blend_path = validate_blend_file(file_name)

    script = f"""
import bpy
import json

object_name = {object_name!r}

obj = bpy.data.objects.get(object_name)

if obj is None:

    result = {{
        "error": "Object not found",
        "object_name": object_name
    }}

elif obj.type != "MESH":

    result = {{
        "error": "Object is not a mesh",
        "object_name": object_name,
        "object_type": obj.type
    }}

else:

    mesh = obj.data

    materials = []

    for slot in obj.material_slots:

        if slot.material:
            materials.append(slot.material.name)

    modifiers = []

    for modifier in obj.modifiers:

        modifiers.append({{
            "name": modifier.name,
            "type": modifier.type
        }})

    result = {{

        "object_name": obj.name,

        "vertex_count": len(mesh.vertices),

        "edge_count": len(mesh.edges),

        "polygon_count": len(mesh.polygons),

        "dimensions": [
            round(obj.dimensions.x, 3),
            round(obj.dimensions.y, 3),
            round(obj.dimensions.z, 3)
        ],

        "location": [
            round(obj.location.x, 3),
            round(obj.location.y, 3),
            round(obj.location.z, 3)
        ],

        "material_count": len(materials),

        "materials": materials,

        "modifier_count": len(modifiers),

        "modifiers": modifiers
    }}

print("ATLAS_MESH_START")
print(json.dumps(result))
print("ATLAS_MESH_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_MESH_START",
        "ATLAS_MESH_END"
    )


# ============================================================
# TOOL 3 — SCENE HEALTH
# ============================================================

def inspect_scene_health(file_name):

    blend_path = validate_blend_file(file_name)

    script = r"""
import bpy
import json

total_vertices = 0
total_edges = 0
total_polygons = 0

mesh_objects = []
materials = set()
modifiers = []

for obj in bpy.context.scene.objects:

    if obj.type != "MESH":
        continue

    mesh = obj.data

    vertices = len(mesh.vertices)
    edges = len(mesh.edges)
    polygons = len(mesh.polygons)

    total_vertices += vertices
    total_edges += edges
    total_polygons += polygons

    for slot in obj.material_slots:

        if slot.material:
            materials.add(slot.material.name)

    for modifier in obj.modifiers:

        modifiers.append({
            "object": obj.name,
            "name": modifier.name,
            "type": modifier.type
        })

    mesh_objects.append({
        "name": obj.name,
        "vertices": vertices,
        "edges": edges,
        "polygons": polygons
    })


result = {

    "scene": bpy.context.scene.name,

    "total_objects":
        len(bpy.context.scene.objects),

    "mesh_objects":
        len(mesh_objects),

    "total_vertices":
        total_vertices,

    "total_edges":
        total_edges,

    "total_polygons":
        total_polygons,

    "material_count":
        len(materials),

    "materials":
        sorted(materials),

    "modifier_count":
        len(modifiers),

    "modifiers":
        modifiers,

    "mesh_breakdown":
        mesh_objects
}


print("ATLAS_HEALTH_START")
print(json.dumps(result))
print("ATLAS_HEALTH_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_HEALTH_START",
        "ATLAS_HEALTH_END"
    )


# ============================================================
# TOOL 4 — SCENE SETTINGS
# ============================================================

def inspect_scene_settings(file_name):

    blend_path = validate_blend_file(file_name)

    script = r"""
import bpy
import json

scene = bpy.context.scene

result = {
    "scene": scene.name,

    "units": {
        "system": scene.unit_settings.system,
        "scale_length": scene.unit_settings.scale_length,
        "length_unit": scene.unit_settings.length_unit
    },

    "render": {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "fps": scene.render.fps
    },

    "animation": {
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "current_frame": scene.frame_current
    },

    "camera": (
        scene.camera.name
        if scene.camera
        else None
    ),

    "collections": [
        collection.name
        for collection in bpy.data.collections
    ],

    "world": (
        scene.world.name
        if scene.world
        else None
    )
}

print("ATLAS_SETTINGS_START")
print(json.dumps(result))
print("ATLAS_SETTINGS_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_SETTINGS_START",
        "ATLAS_SETTINGS_END"
    )


# ============================================================
# TOOL 5 — CREATE COLLECTION
# ============================================================

def create_collection(file_name, collection_name):

    blend_path = validate_blend_file(file_name)

    # --------------------------------------------------------
    # Safety restriction
    # --------------------------------------------------------

    if collection_name != "Atlas_Test":
        return {
            "error": (
                "For safety, this tool can only create "
                "the collection 'Atlas_Test'."
            )
        }

    script = f"""
import bpy
import json

collection_name = {collection_name!r}

existing = bpy.data.collections.get(
    collection_name
)

if existing:

    result = {{
        "status": "already_exists",
        "collection": collection_name
    }}

else:

    new_collection = bpy.data.collections.new(
        collection_name
    )

    bpy.context.scene.collection.children.link(
        new_collection
    )

    bpy.ops.wm.save_as_mainfile(
        filepath={blend_path!r}
    )

    result = {{
        "status": "created",
        "collection": collection_name
    }}


print("ATLAS_WRITE_START")
print(json.dumps(result))
print("ATLAS_WRITE_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_WRITE_START",
        "ATLAS_WRITE_END"
    )


# ============================================================
# TOOL 6 — OBJECT RELATIONSHIP
# ============================================================

def inspect_object_relationship(file_name, object1_name, object2_name):

    blend_path = validate_blend_file(file_name)

    script = f"""
import bpy
import json
import math

object_a_name = {object1_name!r}
object_b_name = {object2_name!r}

obj_a = bpy.data.objects.get(object_a_name)
obj_b = bpy.data.objects.get(object_b_name)

if obj_a is None:
    result = {{
        "error": "Object not found",
        "object_name": object_a_name
    }}

elif obj_b is None:
    result = {{
        "error": "Object not found",
        "object_name": object_b_name
    }}

else:
    ax, ay, az = obj_a.location.x, obj_a.location.y, obj_a.location.z
    bx, by, bz = obj_b.location.x, obj_b.location.y, obj_b.location.z

    dx = bx - ax
    dy = by - ay
    dz = bz - az

    distance = math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)

    dimensions_a = [
        round(obj_a.dimensions.x, 3),
        round(obj_a.dimensions.y, 3),
        round(obj_a.dimensions.z, 3)
    ]

    dimensions_b = [
        round(obj_b.dimensions.x, 3),
        round(obj_b.dimensions.y, 3),
        round(obj_b.dimensions.z, 3)
    ]

    result = {{
        "object_a": {{
            "name": obj_a.name,
            "type": obj_a.type,
            "location": [round(ax, 3), round(ay, 3), round(az, 3)],
            "dimensions": dimensions_a
        }},
        "object_b": {{
            "name": obj_b.name,
            "type": obj_b.type,
            "location": [round(bx, 3), round(by, 3), round(bz, 3)],
            "dimensions": dimensions_b
        }},
        "delta": {{
            "x": round(dx, 3),
            "y": round(dy, 3),
            "z": round(dz, 3)
        }},
        "distance": round(distance, 3),
        "midpoint": [
            round((ax + bx) / 2.0, 3),
            round((ay + by) / 2.0, 3),
            round((az + bz) / 2.0, 3)
        ],
        "same_dimensions": dimensions_a == dimensions_b,
        "axis_alignment": {{
            "x": dx == 0,
            "y": dy == 0,
            "z": dz == 0
        }},
        "symmetric_about_origin": (
            ax == -bx and
            ay == -by and
            az == -bz
        ),
        "midpoint_offset_from_origin": round(
            math.sqrt(
                ((ax + bx) / 2.0) ** 2 +
                ((ay + by) / 2.0) ** 2 +
                ((az + bz) / 2.0) ** 2
            ),
            3
        )
    }}

print("ATLAS_RELATIONSHIP_START")
print(json.dumps(result))
print("ATLAS_RELATIONSHIP_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_RELATIONSHIP_START",
        "ATLAS_RELATIONSHIP_END"
    )



# ============================================================
# TOOL 7 — INSPECT SOCCER COMPONENT CANDIDATES
# ============================================================

def inspect_soccer_components(file_name):

    blend_path = validate_blend_file(file_name)

    script = r"""
import bpy
import json
import re

# Conservative, name-based candidate classification.
# This tool reports evidence for candidate classifications only.

RULES = [
    ("goalpost_candidate", [
        ("goalpost", "goalpost"),
        ("goal_post", "goal_post"),
        ("goal post", "goal post")
    ]),

    ("crossbar_candidate", [
        ("crossbar", "crossbar"),
        ("cross_bar", "cross_bar"),
        ("cross bar", "cross bar")
    ]),

    ("goal_candidate", [
        ("goal", "goal")
    ]),

    ("field_surface_candidate", [
        ("playing_surface", "playing_surface"),
        ("playing surface", "playing surface"),
        ("field", "field"),
        ("pitch", "pitch"),
        ("turf", "turf"),
        ("grass", "grass")
    ]),

    ("field_marking_candidate", [
        ("center_circle", "center_circle"),
        ("centre_circle", "centre_circle"),
        ("center circle", "center circle"),
        ("centre circle", "centre circle"),
        ("halfway_line", "halfway_line"),
        ("halfway line", "halfway line"),
        ("touchline", "touchline"),
        ("sideline", "sideline"),
        ("penalty_area", "penalty_area"),
        ("penalty area", "penalty area"),
        ("penalty_box", "penalty_box"),
        ("penalty box", "penalty box"),
        ("goal_area", "goal_area"),
        ("goal area", "goal area"),
        ("field_line", "field_line"),
        ("field line", "field line"),
        ("marking", "marking"),
        ("line", "line")
    ]),

    ("corner_flag_candidate", [
        ("corner_flag", "corner_flag"),
        ("corner flag", "corner flag")
    ])
]


def normalized_name(name):
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        name.lower()
    ).strip()


def has_whole_word(normalized, word):
    return word in normalized.split()


def classify(name):

    normalized = normalized_name(name)

    candidates = []

    for classification, patterns in RULES:

        matched_terms = []

        for pattern, display_term in patterns:

            normalized_pattern = normalized_name(pattern)

            if " " in normalized_pattern:

                matched = (
                    normalized_pattern in normalized
                )

            else:

                matched = has_whole_word(
                    normalized,
                    normalized_pattern
                )

            if matched:
                matched_terms.append(
                    display_term
                )

        # Explicitly recognize names such as:
        #
        # Goal_Left_post
        # Goal_Right_Post
        #
        # which normalize to:
        #
        # goal left post
        #
        # The combination of the verified name tokens
        # "goal" + "post" is evidence for a goalpost candidate.

        if classification == "goalpost_candidate":

            if (
                has_whole_word(normalized, "goal")
                and
                has_whole_word(normalized, "post")
            ):

                if "goal + post" not in matched_terms:
                    matched_terms.append(
                        "goal + post"
                    )

        if matched_terms:

            candidates.append({
                "classification": classification,
                "matched_name_terms": matched_terms
            })

    # A specific goalpost candidate is more informative
    # than the generic goal candidate.

    if any(
        c["classification"] == "goalpost_candidate"
        for c in candidates
    ):

        candidates = [
            c
            for c in candidates
            if c["classification"] != "goal_candidate"
        ]

    return candidates


objects = []

for obj in bpy.context.scene.objects:

    candidates = classify(obj.name)

    objects.append({

        "object_name":
            obj.name,

        "object_type":
            obj.type,

        "location": [
            round(obj.location.x, 3),
            round(obj.location.y, 3),
            round(obj.location.z, 3)
        ],

        "dimensions": [
            round(obj.dimensions.x, 3),
            round(obj.dimensions.y, 3),
            round(obj.dimensions.z, 3)
        ],

        "candidate_classifications":
            candidates
    })


candidate_objects = [
    obj
    for obj in objects
    if obj["candidate_classifications"]
]


result = {

    "scene":
        bpy.context.scene.name,

    "classification_method":
        "object-name keyword matching",

    "classification_status":
        "candidate_only",

    "objects_inspected":
        len(objects),

    "candidate_objects":
        candidate_objects
}


print("ATLAS_SOCCER_COMPONENTS_START")
print(json.dumps(result))
print("ATLAS_SOCCER_COMPONENTS_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_SOCCER_COMPONENTS_START",
        "ATLAS_SOCCER_COMPONENTS_END"
    )

# ============================================================
# TOOL 8 — CREATE EMPTY MARKER
# ============================================================

def create_empty_marker(file_name, collection_name, object_name):

    blend_path = validate_blend_file(file_name)

    if collection_name != "Atlas_Test":
        return {"error": "For safety, this tool can only create objects inside the 'Atlas_Test' collection."}

    if object_name != "Atlas_Marker":
        return {"error": "For safety, this tool can only create the object 'Atlas_Marker'."}

    script = f"""
import bpy
import json

collection_name = {collection_name!r}
object_name = {object_name!r}

collection = bpy.data.collections.get(collection_name)

if collection is None:
    result = {{
        "status": "error",
        "error": "Collection not found",
        "collection": collection_name
    }}
else:
    existing = bpy.data.objects.get(object_name)

    if existing:
        result = {{
            "status": "already_exists",
            "object": object_name,
            "object_type": existing.type
        }}
    else:
        new_object = bpy.data.objects.new(object_name, None)
        collection.objects.link(new_object)
        bpy.ops.wm.save_as_mainfile(filepath={blend_path!r})
        result = {{
            "status": "created",
            "object": object_name,
            "object_type": "EMPTY",
            "collection": collection_name
        }}

print("ATLAS_MARKER_WRITE_START")
print(json.dumps(result))
print("ATLAS_MARKER_WRITE_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_MARKER_WRITE_START",
        "ATLAS_MARKER_WRITE_END"
    )

# ============================================================
# TOOL — MOVE AUTHORIZED GOALPOST
# ============================================================

def move_object(file_name, object_name, location):

    blend_path = validate_blend_file(file_name)

    # Safety restriction:
    # This tool is currently limited to the two goalpost objects
    # involved in the authorization test.

    allowed_objects = {
        "Goal_Left_post",
        "Goal_Right_Post"
    }

    if object_name not in allowed_objects:
        return {
            "error": (
                "For safety, this tool can only move "
                "Goal_Left_post or Goal_Right_Post."
            )
        }

    if (
        not isinstance(location, (list, tuple))
        or len(location) != 3
    ):
        return {
            "error": (
                "Location must contain exactly "
                "three numeric values."
            )
        }

    try:
        location = [
            float(location[0]),
            float(location[1]),
            float(location[2])
        ]
    except (TypeError, ValueError):
        return {
            "error": "Location values must be numeric."
        }

    script = f"""
import bpy
import json

object_name = {object_name!r}
target_location = {location!r}

obj = bpy.data.objects.get(object_name)

if obj is None:

    result = {{
        "status": "error",
        "error": "Object not found",
        "object_name": object_name
    }}

else:

    old_location = [
        obj.location.x,
        obj.location.y,
        obj.location.z
    ]

    obj.location = target_location

    bpy.ops.wm.save_as_mainfile(
        filepath={blend_path!r}
    )

    result = {{
        "status": "moved",
        "object_name": object_name,
        "previous_location": old_location,
        "location": [
            obj.location.x,
            obj.location.y,
            obj.location.z
        ]
    }}

print("ATLAS_MOVE_START")
print(json.dumps(result))
print("ATLAS_MOVE_END")
"""

    return run_blender(
        blend_path,
        script,
        "ATLAS_MOVE_START",
        "ATLAS_MOVE_END"
    )