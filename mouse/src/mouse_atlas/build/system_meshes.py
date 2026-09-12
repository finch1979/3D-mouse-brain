"""Offline CCF loading and hemisphere-aware anchors for adult mouse systems."""
import hashlib
import json
import numpy as np
import trimesh
from mouse_atlas.common.paths import OUTPUTS_DIR

MESH_DIR = OUTPUTS_DIR / 'P56' / 'mesh'


def load_regions(acronyms):
    manifest = json.loads((MESH_DIR / 'manifest.json').read_text(encoding='utf-8'))
    meshes, provenance = {}, {}
    for acronym in ['root', *acronyms]:
        row = manifest[acronym]
        path = MESH_DIR / f"{row['id']}.obj"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row.get('sha256'):
            raise ValueError(f'{acronym}: source checksum missing or changed; run fetch --systems')
        source = trimesh.load_mesh(path, process=False)
        vertices = np.column_stack((source.vertices[:,2], -source.vertices[:,0], -source.vertices[:,1]))
        if acronym == 'root':
            center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2
        meshes[acronym] = trimesh.Trimesh(vertices=vertices-center, faces=source.faces, process=False)
        provenance[acronym] = {k:row[k] for k in ('id','name','source_url','sha256','atlas')}
    return meshes, provenance


def anchor(mesh, side='R', ventral=False):
    vertices = np.asarray(mesh.vertices)
    pool = vertices[vertices[:,0] > 0] if side == 'R' else vertices[vertices[:,0] < 0]
    if len(pool) == 0:
        raise ValueError(f'No vertices in hemisphere {side}')
    if ventral:
        pool = pool[pool[:,2] <= np.quantile(pool[:,2], .2)]
    center = pool.mean(axis=0)
    # A real vertex preserves the region boundary and avoids empty-space centroids.
    return pool[np.argmin(np.sum((pool-center)**2,axis=1))].tolist()
