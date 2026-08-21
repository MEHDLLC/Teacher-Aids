"""The five Platonic solids, and what a printer needs to know about them.

Two things are wanted from a polyhedron here and neither is the mesh.  A
geometry set wants its *edges*, so it can be printed as a frame a child can
see through and count.  A die wants its *faces* -- where each one is, which
way it points, and which way is up on it -- so a number can be sunk into each.

Both come from the same place: build the convex hull of the vertices, then
merge the coplanar triangles the hull is made of back into the flat faces they
came from.  Reading the faces back off the hull rather than writing them down
by hand means the vertex table is the only thing that can be wrong, and a
wrong vertex table is obvious the moment you look at the result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import manifold3d as m3
import numpy as np

from . import geom

PHI = (1.0 + math.sqrt(5.0)) / 2.0

# name -> the faces it has, for the dice that use them
PLATONIC: dict[str, int] = {
    "tetrahedron": 4,
    "cube": 6,
    "octahedron": 8,
    "dodecahedron": 12,
    "icosahedron": 20,
}


@dataclass(frozen=True)
class Face:
    """One flat face: where it is, which way it faces, and its own axes."""

    centre: np.ndarray        # (3,) in model space
    normal: np.ndarray        # (3,) unit, pointing out
    right: np.ndarray         # (3,) unit, in the face plane
    up: np.ndarray            # (3,) unit, in the face plane
    inradius: float           # largest circle that fits, from the centre
    sides: int
    # The face's outline in its own (right, up) frame, wound counter-clockwise
    # and centred on `centre`. Empty for the synthetic faces a cube die builds.
    ring: tuple[tuple[float, float], ...] = ()
    # Which of the polyhedron's vertices this face uses. Two faces sharing two
    # of them share an edge, which is how the dihedral angles are found.
    corners: frozenset = frozenset()


@dataclass(frozen=True)
class Polyhedron:
    vertices: np.ndarray      # (n, 3)
    edges: list[tuple[int, int]]
    faces: list[Face]

    @property
    def counts(self) -> tuple[int, int, int]:
        """Faces, edges, vertices -- the three numbers Euler relates."""
        return (len(self.faces), len(self.edges), len(self.vertices))

    def check_euler(self) -> bool:
        faces, edges, vertices = self.counts
        return vertices - edges + faces == 2

    def solid(self) -> geom.Solid:
        return m3.Manifold.hull_points(self.vertices)

    def frame(self, rib: float) -> geom.Solid:
        """The solid hollowed out and its faces opened: an open edge frame.

        Cut, never assembled. Building a frame by unioning one bar per edge is
        the obvious way and it does not survive contact with a symmetric
        solid: five bars meet at every vertex of an icosahedron, some of their
        faces land exactly coplanar, and the union comes out with edges
        belonging to four triangles -- which manifold accepts and every mesh
        checker and slicer rejects. Rotating the bars, rounding them or
        capping the vertices with balls each fixes one solid and breaks
        another, because the coincidences are a property of the symmetry, not
        of the section.

        Subtraction has none of that. Erode the body by `rib` to get a shell,
        then punch each face's own outline, pulled in by `rib`, through that
        shell. What is left is the material within `rib` of an edge, and every
        surface of it came from the original solid or from one clean cut.
        """
        body = self.solid()
        core = body.minkowski_difference(
            m3.Manifold.sphere(rib, circular_segments=24))
        if core.is_empty():
            raise ValueError(
                f"a {rib:.1f} mm rib is thicker than this solid; there is "
                "nothing left to hollow."
            )
        shell = body - core

        # Eroding by a sphere of radius `rib` leaves a shell exactly `rib`
        # thick measured perpendicular to any face, so the window only has to
        # be half again as deep as that.
        depth = rib * 1.5
        windows = []
        for index, face in enumerate(self.faces):
            if len(face.ring) < 3:
                continue
            inset = geom.polygon(face.ring).offset(
                -self._window_inset(index, rib), m3.JoinType.Miter, 4.0, 8)
            if inset.is_empty():
                continue
            prism = geom.extrude(inset, depth + 1.0, at_z=-depth)
            windows.append(place_on_face(prism, face))
        if not windows:
            return shell

        frame = geom.difference(shell, windows)
        if frame.is_empty():
            raise ValueError(
                f"a {rib:.1f} mm rib leaves nothing of this solid; its faces "
                "are smaller than twice the rib."
            )
        # Never hand back a frame that would fail on disk. The construction
        # above is careful, and a shape nobody anticipated is exactly the case
        # where being told is worth more than being handed a broken STL.
        if not geom.edge_manifold(frame):
            raise ValueError(
                "this frame came out with edges shared by more than two "
                "triangles, which no slicer will accept. Try a different "
                "`rib`, or build this solid solid rather than framed."
            )
        return frame

    def _window_inset(self, index: int, rib: float) -> float:
        """How far in from a face's edge its window has to start.

        Not simply `rib`. The core is the body pulled in by `rib` from every
        face at once, so at a sharp edge its own edge sits `rib / tan(t/2)` in
        from the original, where t is the dihedral angle. Cut the window any
        closer than that and it reaches past the core's edge into the strut
        the frame is made of, and the strut pinches to nothing at the corners:
        that is exactly, and only, what breaks a tetrahedron, whose 70 degree
        dihedral makes the factor 1.41 rather than the cube's 1.
        """
        face = self.faces[index]
        tightest = math.pi
        for other_index, other in enumerate(self.faces):
            if other_index == index or len(face.corners & other.corners) < 2:
                continue
            cosine = -float(np.dot(face.normal, other.normal))
            tightest = min(tightest, math.acos(max(-1.0, min(1.0, cosine))))
        if tightest <= 1e-6 or tightest >= math.pi:
            return rib
        needed = rib / math.tan(tightest / 2.0)
        return max(rib, needed) * 1.05


def vertices_of(name: str) -> np.ndarray:
    """Vertices of a Platonic solid, scaled to a circumradius of 1."""
    if name == "tetrahedron":
        raw = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    elif name == "cube":
        raw = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    elif name == "octahedron":
        raw = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1),
               (0, 0, -1)]
    elif name == "dodecahedron":
        raw = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        for a in (-1, 1):
            for b in (-1, 1):
                raw += [(0, a / PHI, b * PHI), (a / PHI, b * PHI, 0),
                        (a * PHI, 0, b / PHI)]
    elif name == "icosahedron":
        raw = []
        for a in (-1, 1):
            for b in (-1, 1):
                raw += [(0, a, b * PHI), (a, b * PHI, 0), (a * PHI, 0, b)]
    else:
        raise KeyError(
            f"unknown polyhedron {name!r}; available: "
            + ", ".join(sorted(PLATONIC))
        )
    points = np.array(raw, dtype=float)
    return points / np.linalg.norm(points[0])


def from_points(points: np.ndarray) -> Polyhedron:
    """A convex polyhedron read off the hull of a set of points.

    Lets anything convex -- a cuboid, a prism, a pyramid -- get the same face
    and edge information the Platonic solids get, and therefore the same
    `frame`, without a second implementation.
    """
    pts = np.asarray(points, dtype=float)
    faces = _faces_from_hull(pts)
    return Polyhedron(pts, _edges_from_faces(pts, faces), faces)


def build(name: str, circumradius: float = 1.0,
          face_down: bool = True) -> Polyhedron:
    """A Platonic solid, optionally rotated to stand on a face at z=0."""
    points = vertices_of(name) * circumradius
    faces = _faces_from_hull(points)
    if face_down:
        points = _rotate_face_down(points, faces[0])
        faces = _faces_from_hull(points)
        points = points - [0.0, 0.0, points[:, 2].min()]
        faces = _faces_from_hull(points)
    solid = Polyhedron(points, _edges_from_faces(points, faces), faces)
    if not solid.check_euler():
        raise ValueError(
            f"{name}: read back {solid.counts[0]} faces, {solid.counts[1]} "
            f"edges and {solid.counts[2]} vertices, which do not satisfy "
            "Euler's formula. The vertex table is wrong."
        )
    return solid


def _faces_from_hull(points: np.ndarray) -> list[Face]:
    """Merge the hull's triangles back into the flat faces they came from."""
    hull = m3.Manifold.hull_points(points)
    mesh = hull.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=float)[:, :3]
    tris = np.asarray(mesh.tri_verts, dtype=np.int64)
    lookup = _lookup(points, verts)

    corners = verts[tris]
    normals = np.cross(corners[:, 1] - corners[:, 0],
                       corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals),
                        where=lengths > 1e-12)

    groups: dict[tuple, list[int]] = {}
    for index, normal in enumerate(normals):
        if lengths[index, 0] <= 1e-12:
            continue
        key = tuple(np.round(normal, 4) + 0.0)      # +0.0 folds -0.0 into 0.0
        groups.setdefault(key, []).append(index)

    faces: list[Face] = []
    for key, indices in groups.items():
        # The rounded key is only how triangles were grouped. Taking the
        # normal from it would leave the face out of true by up to half a
        # rounding step, which is a micron of tilt on the bed and, worse, a
        # number engraved into a face that is not quite where the face is.
        # Average the real normals instead.
        normal = normals[indices].mean(axis=0)
        normal = normal / np.linalg.norm(normal)
        used = np.unique(tris[indices])
        ring = verts[used]
        centre = ring.mean(axis=0)
        right = _perpendicular(normal)
        up = np.cross(normal, right)
        # The inradius is how far the centre is from the nearest edge, which
        # is what limits how big a number can be sunk into the face.
        inradius, outline = _face_outline(ring, centre, right, up)
        faces.append(Face(centre, normal, right, up, inradius, len(used),
                          outline,
                          frozenset(lookup[int(v)] for v in used)))
    # A stable order, so the same solid always numbers its faces the same way.
    faces.sort(key=lambda f: (round(f.centre[2], 6), round(f.centre[1], 6),
                              round(f.centre[0], 6)))
    return faces


def _face_outline(ring: np.ndarray, centre: np.ndarray, right: np.ndarray,
                  up: np.ndarray):
    """A face's outline in its own plane, and how far its nearest edge is.

    The vertices come off the hull in triangle order, so they are sorted by
    angle about the centre first: an outline in the wrong order is a polygon
    that crosses itself, which extrudes to nothing.
    """
    flat = np.stack([(ring - centre) @ right, (ring - centre) @ up], axis=1)
    loop = flat[np.argsort(np.arctan2(flat[:, 1], flat[:, 0]))]
    best = float("inf")
    for index in range(len(loop)):
        a = loop[index]
        b = loop[(index + 1) % len(loop)]
        edge = b - a
        span = float(np.linalg.norm(edge))
        if span < 1e-9:
            continue
        # Distance from the origin (the face centre in this frame) to the edge.
        best = min(best, abs(edge[0] * a[1] - edge[1] * a[0]) / span)
    return best, tuple((float(x), float(y)) for x, y in loop)


def _edges_from_faces(points: np.ndarray, faces: list[Face]) -> list[tuple[int, int]]:
    """The real edges: where two faces meet, not where two triangles do."""
    hull = m3.Manifold.hull_points(points)
    mesh = hull.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=float)[:, :3]
    tris = np.asarray(mesh.tri_verts, dtype=np.int64)

    corners = verts[tris]
    normals = np.cross(corners[:, 1] - corners[:, 0],
                       corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals),
                        where=lengths > 1e-12)

    seen: dict[tuple[int, int], list[int]] = {}
    for index, tri in enumerate(tris):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            key = (int(min(a, b)), int(max(a, b)))
            seen.setdefault(key, []).append(index)

    lookup = _lookup(points, verts)

    edges = set()
    for (a, b), owners in seen.items():
        if len(owners) != 2:
            continue
        # An edge inside a flat face has the same normal on both sides; a real
        # edge is a crease.
        if np.allclose(normals[owners[0]], normals[owners[1]], atol=1e-4):
            continue
        edges.add((min(lookup[a], lookup[b]), max(lookup[a], lookup[b])))
    return sorted(edges)


def _lookup(points: np.ndarray, verts: np.ndarray) -> dict[int, int]:
    """Map hull vertices back onto the vertex table the caller passed in."""
    out = {}
    for index, point in enumerate(verts):
        out[index] = int(np.argmin(np.linalg.norm(points - point, axis=1)))
    return out


def _rotate_face_down(points: np.ndarray, face: Face) -> np.ndarray:
    """Turn the solid so `face` lies flat on z=0."""
    return points @ _rotation_to(face.normal, np.array([0.0, 0.0, -1.0])).T


def _rotation_to(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """The rotation matrix taking unit vector `source` onto unit `target`."""
    source = source / np.linalg.norm(source)
    target = target / np.linalg.norm(target)
    axis = np.cross(source, target)
    sine = np.linalg.norm(axis)
    cosine = float(np.dot(source, target))
    if sine < 1e-12:
        if cosine > 0:
            return np.eye(3)
        # Antiparallel: any perpendicular axis, half a turn about it.
        axis = _perpendicular(source)
        cross = _skew(axis)
        return np.eye(3) + 2.0 * cross @ cross
    axis = axis / sine
    cross = _skew(axis)
    angle = math.atan2(sine, cosine)
    return (np.eye(3) + math.sin(angle) * cross
            + (1.0 - math.cos(angle)) * cross @ cross)


def _skew(axis: np.ndarray) -> np.ndarray:
    x, y, z = axis
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def _perpendicular(vector: np.ndarray) -> np.ndarray:
    """Any unit vector at right angles to `vector`."""
    other = (np.array([0.0, 0.0, 1.0]) if abs(vector[2]) < 0.9
             else np.array([1.0, 0.0, 0.0]))
    out = np.cross(vector, other)
    return out / np.linalg.norm(out)


def place_on_face(shape_solid: geom.Solid, face: Face,
                  sink: float = 0.0) -> geom.Solid:
    """Move a solid built in the XY plane onto a face, facing outward.

    `sink` pushes it that far *into* the body along the face normal, which is
    how a number gets engraved rather than stuck on.
    """
    basis = np.stack([face.right, face.up, face.normal], axis=1)
    matrix = np.zeros((3, 4))
    matrix[:, :3] = basis
    matrix[:, 3] = face.centre - face.normal * sink
    return shape_solid.transform(matrix)
