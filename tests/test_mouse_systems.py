"""Independent checks of generated new viewers against raw Allen geometry."""
import base64
import hashlib
import json
from pathlib import Path
import re
import unittest
import numpy as np
import trimesh

REPO=Path(__file__).resolve().parents[1]
MESH=REPO/'mouse/outputs/P56/mesh'
OUT=REPO/'mouse/outputs/P56/pathway_meshes'


class MouseSystems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads((OUT/'systems.json').read_text(encoding='utf-8'))
        cls.raw_root=trimesh.load_mesh(MESH/'997.obj',process=False)
        cls.origin=(cls.raw_root.vertices.min(axis=0)+cls.raw_root.vertices.max(axis=0))/2
        cls.ledger=(REPO/'docs/architecture/mouse-systems-evidence.md').read_text(encoding='utf-8')

    def test_all_nine_routes_and_geometry(self):
        self.assertEqual({s['slug'] for s in self.catalog}, {'auditory','somatosensory','gustatory','vestibular','cerebellum','limbic','pain','sleep','autonomic'})
        for system in self.catalog:
            slug=system['slug']
            with self.subTest(slug=slug):
                folder=OUT/slug
                manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
                html=(folder/f'mouse_{slug}_pathway_3d.html').read_text(encoding='utf-8')
                regions=json.loads(re.search(r'const REGIONS = (\{.*?\});',html,re.S)[1])
                self.assertEqual(set(regions),set(manifest['regions']))
                self.assertLess(len(html.encode()),25*1024*1024)
                self.assertNotRegex(html,r'<script\s+src=')
                self.assertIn('regionKey: REAL.has(key)',html)
                for acronym, info in manifest['regions'].items():
                    path=MESH/f"{info['id']}.obj"
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),info['sha256'])
                    raw=trimesh.load_mesh(path,process=False)
                    delta=raw.vertices-self.origin
                    expected=np.stack((delta[:,2],-delta[:,0],-delta[:,1]),axis=1)
                    vertices=np.frombuffer(base64.b64decode(regions[acronym]['pos_b64']),dtype='<f4').reshape(-1,3)
                    faces=np.frombuffer(base64.b64decode(regions[acronym]['idx_b64']),dtype='<u4').reshape(-1,3)
                    np.testing.assert_allclose(vertices,expected,atol=.001,rtol=0)
                    np.testing.assert_array_equal(faces,raw.faces)
                    self.assertTrue(np.isfinite(vertices).all())
                    for node in manifest['nodes'].values():
                        if node['region']!=acronym:
                            continue
                        point=np.array(node['position'])
                        self.assertEqual(point[0]>0,node['side']=='R')
                        self.assertLess(np.linalg.norm(expected-point,axis=1).min(),.001)
                for branch in manifest['branches']:
                    self.assertGreaterEqual(len(branch['nodes']),2)
                    self.assertTrue(branch['refs'])
                    for ref in branch['refs']:
                        self.assertIn('| '+ref+' ',self.ledger)
                        self.assertIn(manifest['sources'][ref]['url'],html)
                self.assertFalse(manifest['signal_timing'])

    def test_species_specific_relays_and_crossings(self):
        def chains(slug):
            return [p['nodes'] for p in json.loads((OUT/slug/'manifest.json').read_text(encoding='utf-8'))['branches']]
        self.assertIn(['PB_R','VPMpc_R','GU_R'],chains('gustatory'))
        self.assertIn(['CU_L','VPL_R','SSp-ul_R'],chains('somatosensory'))
        self.assertIn(['MV_R','III_L'],chains('vestibular'))
        self.assertIn(['IP_R','RN_L'],chains('cerebellum'))

    def test_populations_are_not_claimed_as_segmentation(self):
        for slug,names in {'limbic':['vCA1'],'pain':['RVM'],'sleep':['POA','Orexin'],'autonomic':['DVC']}.items():
            manifest=json.loads((OUT/slug/'manifest.json').read_text(encoding='utf-8'))
            for name in names:
                self.assertEqual(manifest['nodes'][name]['kind'],'approximate-population')
                self.assertNotIn(name,manifest['regions'])


if __name__=='__main__':
    unittest.main()
